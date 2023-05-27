import io
import os
import time
import json
import asyncio
import logging
from pathlib import Path
from typing import Any
from pprint import pprint
import requests
from PIL import Image
from moonraker_api.const import *
from moonraker_api import MoonrakerListener, MoonrakerClient
import tjc

logging.basicConfig(format="[%(asctime)s][%(name)s][%(levelname)s]%(message)s")
logging.getLogger('moonraker_api').setLevel(logging.FATAL)
logging.getLogger('TJC').setLevel(logging.DEBUG)
logger = logging.getLogger('KlipperScreen')
logger.setLevel(logging.DEBUG)


class KlipperScreen(MoonrakerListener):

    def __init__(self, config_file):
        with open(config_file, 'r') as fp:
            self.config = json.load(fp)
        self.has_connected = False
        self.screen = tjc.AsyncTJCScreen()
        self.client = MoonrakerClient(self, self.config['Moonraker'])
        self.ip = ''
        self.version = ''
        self.fs = {}
        self.extruder_temp = 0
        self.extruder_target_temp = 0
        self.bed_temp = 0
        self.bed_target_temp = 0
        self.print_speed = 1
        self.print_progress = 0
        self.print_duration = 0
        self.print_state = ''
        self.filename = ''
        self.led_state = 0
        self.fan_speed = 0
        self.z_value = 0
        self.homed_axes = ''
        self.bed_mesh_profiles = None
        self.bed_mesh_profile_name = None
        self.bed_mesh_probed_matrix = None

    async def start(self) -> None:
        logger.info('Start NeptuneScreen...')
        try:
            await self.connect()
        except:
            pass

    async def state_changed(self, state: str) -> None:
        if state == 'ws_connected':
            self.has_connected = True
            self.screen.page_boot()
        elif state == 'ws_stopped':
            if self.has_connected:
                self.has_connected = False
                logger.info('Disconnected.')
                logger.info('Re-connect...')
            await asyncio.sleep(2)
            await self.connect()

    async def connect(self):
        logger.debug('connecting...')
        await self.screen.start(self.config['Serial'], self.config['Baudrate'])
        self.screen.set_request_handler(self.on_screen_request)
        await self.client.connect()

    async def on_exception(self, exception: BaseException) -> None:
        """Notifies of exceptions from the websocket run loop."""
        if self.has_connected:
            logger.debug("Received exception from API websocket %s", str(exception))

    async def _get_files2(self, path):
        result = await self.call('server.files.get_directory', path=f'gcodes{path}')
        files = []
        for item in result['dirs']:
            if not item['dirname'].startswith('.'):
                files.append({'name': item['dirname'], 'type': 'directory'})
        for item in result['files']:
            _, ext = os.path.splitext(item['filename'])
            if ext.lower() in ('.gcode', '.gco'):
                files.append({'name': item['filename'], 'type': 'file'})
        return files

    async def fs_handler(self, data):
        _, _, page, page_size, path = data.split(' ', maxsplit=4)
        page, page_size = int(page), int(page_size)
        # 处理上一层的请求
        if path.endswith('../'):
            path = path.rsplit('/', maxsplit=3)[0]
            if path == '':
                path = '/'
            page = 0
        # 获取文件列表，缓存中没有就重新请求
        if path not in self.fs:
            self.fs[path] = await self._get_files2(path)
        files = self.fs.get(path, [])
        # 分页处理，格式转换
        page_max = (len(files) + page_size  -1) // page_size - 1
        files = files[page*page_size:(page + 1)*page_size]
        file_list = []
        file_ext_list = []
        for item in files:
            if item['type'] == 'directory':
                name, ext = item['name'] + '/', '#'
            else:
                name, ext = os.path.splitext(item['name'])
            file_list.append(name)
            file_ext_list.append(ext)
        if len(file_list) < page_size:
            padding = page_size - len(file_list)
            file_list += [' ' for _ in range(padding)]
            file_ext_list += [' ' for _ in range(padding)]
        # 更新页面
        self.screen.page_file(page, page_max, '|'.join(file_list), '|'.join(file_ext_list), path)

    async def on_screen_request(self, data):
        # 处理屏幕发送的请求
        logger.debug(f'request: {data}')
        fields = data.split(' ')
        group = fields[0]
        if group == 'boot':
            self.screen.send_cmd('boot.tm_notify.en=0')
            await self.initialize()
        elif group == 'g':
            gcode = data.split(' ', maxsplit=1)[-1]
            logger.debug(f'[G-Code] {gcode}')
            if gcode.split(' ')[0] in ('G1',):
                if not self.homed_axes:
                    self.screen.page_home()
                    return
            await self.call('printer.gcode.script', script=gcode)
        elif group == 'fs':
            if fields[1] == 'ls':
                await self.fs_handler(data)
            elif fields[1] == 'preview':
                filename = data.split(' ', maxsplit=2)[-1].strip('/')
                thumbnail = await self.get_thumbnail(filename)
                await self.screen.page_ask_print(thumbnail)
        elif group == 'print':
            if fields[1] == 'start':
                # if not self.homed_axes:
                #     await self.call('printer.gcode.script', script='G28')
                filename = data.split(' ', maxsplit=2)[-1].strip('/')
                await self.call('printer.print.start', filename=filename)
            elif fields[1] == 'pause':
                await self.call('printer.print.pause')
            elif fields[1] == 'resume':
                await self.call('printer.print.resume')
            elif fields[1] == 'cancel':
                await self.call('printer.print.cancel')
        elif group == 'page':
            if fields[1] == 'leveling':
                if self.bed_mesh_profiles and not self.bed_mesh_profile_name:
                    gcode = f'BED_MESH_PROFILE LOAD="{self.bed_mesh_profiles[0]}"'
                    await self.call('printer.gcode.script', script=gcode)
                    await asyncio.sleep(0.2)
                self.screen.page_leveling(self.bed_mesh_probed_matrix, 0)
        else:
            logger.error(f'Invalid command: {data}')

    async def on_notification(self, method: str, data: Any) -> None:
        try:
            await self._on_notification(method, data)
        except Exception as e:
            logger.error("Uncaught exception", exc_info=e)
    
    def update_state(self, data):
        vals = {}
        for category, category_data in data.items():
            if category == 'heater_bed':
                for name, val in category_data.items():
                    if name == 'temperature':
                        vals['bed_temp'] = val
                    elif name == 'target':
                        vals['bed_target_temp'] = val
            elif category == 'extruder':
                for name, val in category_data.items():
                    if name == 'temperature':
                        vals['extruder_temp'] = val
                    elif name == 'target':
                        vals['extruder_target_temp'] = val
            elif category == 'print_stats':
                for name, val in category_data.items():
                    if name == 'state':
                        vals['print_state'] = val
                    elif name == 'filename':
                        vals['filename'] = val
                    elif name == 'print_duration':
                        vals['print_duration'] = val
            elif category == 'fan':
                for name, val in category_data.items():
                    if name == 'speed':
                        vals['fan_speed'] = val
            elif category == 'display_status':
                for name, val in category_data.items():
                    if name == 'progress':
                        vals['print_progress'] = val
            elif category == 'gcode_move':
                for name, val in category_data.items():
                    if name == 'speed_factor':
                        vals['print_speed'] = val
                    elif name == 'gcode_position':
                        vals['z_value'] = val[2]
            elif category == 'output_pin LED_pin':
                for name, val in category_data.items():
                    if name == 'value':
                        vals['led_state'] = val
            elif category == 'toolhead':
                for name, val in category_data.items():
                    if name == 'homed_axes':
                        vals['homed_axes'] = val
            elif category == 'bed_mesh':
                for name, val in category_data.items():
                    if name == 'probed_matrix':
                        vals['bed_mesh_probed_matrix'] = val
                        logger.debug('recv value')
                    elif name == 'profile_name':
                        vals['bed_mesh_profile_name'] = val
                    elif name =='profiles':
                        vals['bed_mesh_profiles'] = list(val.keys())
            else:
                logger.debug(f'{category}:{category_data}')

        for key, val in vals.items():
            setattr(self, key, val)
        return vals
    
    def get_print_left_time(self, duration, progress, speed):
        if progress == 0:
            progress = 0.001
        total = duration / progress
        file_left = (total - duration) / speed
        return file_left

    def format_time(self, duration):
        duration = int(duration)
        hour = duration // 3600
        minute = (duration % 3600) // 60
        seconds = (duration % 3600) % 60
        if hour:
            return f'{hour}h {minute}min {seconds}s'
        else:
            return f'{minute}min {seconds}s'

    last_update_time = 0
    async def _on_notification(self, method: str, data: Any) -> None:
        if method == 'notify_status_update':
            vals = self.update_state(data[0])
            if ('extruder_temp') in vals or ('extruder_target_temp' in vals):
                vals['extruder_temp'] = self.extruder_temp
                vals['extruder_target_temp'] = self.extruder_target_temp
            if ('bed_temp' in vals) or ('bed_target_temp' in vals):
                vals['bed_temp'] = self.bed_temp
                vals['bed_target_temp'] = self.bed_target_temp
            self.screen.global_update(**vals)
            if 'print_state' in vals and self.print_state in ('printing', 'paused'):
                self.screen.page_printing_init()
        elif method == 'notify_proc_stat_update':
            # 根据CPU温度控制风扇的开和关
            cpu_temp = data[0]['cpu_temp']
            if cpu_temp > self.config['FanStartTemp']:
                self.screen.set_fan(True)
            elif cpu_temp < self.config['FanStopTemp']:
                self.screen.set_fan(False)
        elif method == 'notify_gcode_response':
            pass
        elif method == 'notify_history_changed':
            action = data[0]['action']
            logger.debug(data)
            if action == 'added':
                self.screen.page_printing_init(data[0]['job']['filename'])
            elif action == 'finished':
                self.screen.page_finish()
        elif method == 'notify_filelist_changed':
            path = data[0]['item']['path']
            directory = '/'
            if '/' in path:
                directory = '/' + path.rsplit('/', maxsplit=1)[0]
            logger.debug(f'fs change: path={path}, update_dir={directory}')
            if directory in self.fs:
                del self.fs[directory]
        else:
            logger.debug("Received notification %s -> %s", method, data)
        
        # 定时更新打印页面
        if time.time() - self.last_update_time >= 1:
            if self.print_state in ('printing', 'paused'):
                left_time = self.get_print_left_time(self.print_duration, self.print_progress, self.print_speed)
                left_time_str = self.format_time(left_time)
                self.screen.page_printing_update(self.print_progress, left_time_str, self.z_value, self.print_speed)
            self.last_update_time = time.time()

    async def call(self, method, **kwargs):
        return await self.client.call_method(method, **kwargs)

    async def initialize(self):
        # Get klipper version
        result = await self.call('printer.info')
        self.version = result['software_version'].split('-')[0]
        # Get IP address
        self.ip = await self._get_ip()
        print(f'klipper version: {self.version} (@{self.ip})')
        # Get file list
        self.fs['/'] = await self._get_files2('/')

        # Test
        # info = await self.call('printer.objects.list')
        # objects = {x:None for x in info['objects']}
        # data = await self.call('printer.objects.query', objects=objects)
        # with open('objects.json', 'w') as fp:
        #     import json
        #     json.dump(data, fp, indent=4)

        # Get Initial states
        subscribe_fields = {
            'print_stats': ['state', 'info', 'print_duration', 'filename'],
            'heater_bed': ['temperature', 'target'],
            'extruder': ['temperature', 'target'],
            'toolhead': ['position', 'homed_axes'],
            'fan': ['speed'],
            'display_status': ['progress'],
            "gcode_move": ["speed_factor", "gcode_position"],
            'output_pin LED_pin': ['value'],
            'bed_mesh': ['probed_matrix', 'profile_name', 'profiles'],
        }
        data = await self.subscribe(subscribe_fields)
        # pprint(data)
        vals = self.update_state(data['status'])
        self.screen.sys_init(f'http://{self.ip}', self.version)
        logger.info(f'Startup State: {self.print_state}')
        self.screen.global_update(**vals)
        if self.print_state in ('printing', 'paused'):
            thumbnail = await self.get_thumbnail(self.filename)
            self.screen.page_printing_init(self.filename, thumbnail)
            left_time = self.get_print_left_time(self.print_duration, self.print_progress, self.print_speed)
            left_time_str = self.format_time(left_time)
            self.screen.page_printing_update(self.print_progress, left_time_str, self.z_value, self.print_speed)
        else:
            self.screen.page_main_init()


    def _create_thumbnail(self, filename, width, height, fillcolor=0):
        im = Image.open(filename)
        im = im.rotate(270, expand=True)
        w, h = im.size
        if w != width or h != height:
            scale_w = w / width
            scale_h = h / height
            if scale_w != scale_h:
                if scale_w > scale_h:
                    new_w = w
                    new_h = int(height * scale_w)
                    pos = (0, (new_h - h) // 2)
                else:
                    new_w = int(width * scale_h)
                    new_h = h
                    pos = ((new_w - w) // 2, 0)
                new_im = Image.new('RGB', (new_w, new_h), fillcolor)
                new_im.paste(im, pos)
                im = new_im
            im = im.resize((width, height))
        fp = io.BytesIO()
        im = im.convert('RGB')
        im.save(fp, format='jpeg')
        return fp.getvalue()

    async def get_thumbnail(self, filename):
        thumbnails = await self.call('server.files.thumbnails', filename=filename)
        max_width = 0
        perfer_input = None
        for item in thumbnails:
            if item['width'] == 160:
                perfer_input = item['thumbnail_path']
                break
            elif item['width'] > max_width:
                max_width = item['width']
                perfer_input = item['thumbnail_path']
        
        if perfer_input:
            resp = requests.get(f'http://{self.client.host}:{self.client.port}/server/files/gcodes/{perfer_input}')
            fp = io.BytesIO(resp.content)
            return self._create_thumbnail(fp, 160, 160)

    async def subscribe(self, fields):
        logger.info('Subscribe notifications')
        await self.call('printer.objects.subscribe')
        return await self.call('printer.objects.subscribe', objects=fields)

    async def _get_ip(self):
        info = await self.call('machine.system_info')
        return info['system_info']['network']['wlan0']['ip_addresses'][0]['address']


async def main():
    config_file = Path('~/printer_data/config/neptune-screen.json').expanduser().resolve()
    klipperScreen = KlipperScreen(config_file)
    await klipperScreen.start()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(main())
    loop.run_forever()


