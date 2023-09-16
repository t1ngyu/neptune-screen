import time
import struct
import serial
import asyncio
import serial_asyncio
import logging
from pathlib import Path

logger = logging.getLogger('TJC')
logger.setLevel(logging.DEBUG)

import functools
def my_decorator(f):
    cached = {}
    @functools.wraps(f)
    def wrapper(self, name, value):
        if name not in cached or cached[name] != value:
            cached[name] = value
            return f(self, name, value)
    return wrapper

class ScreenMixin:
    debug = True

    def send_cmd(self, msg):
        data = bytearray()
        if isinstance(msg, str):
            if self.debug:
                logger.debug(f'<send_cmd> {msg}')
            data.extend(msg.encode('utf-8'))
        elif isinstance(msg, (bytes, bytearray)):
            data.extend(msg)
        else:
            logger.error(type(msg))
            raise Exception()
        data.extend(bytes([0xff, 0xff, 0xff]))
        self.write(data)

    def sys_init(self, url, version):
        self.send_cmd(f'information.klipper_ver.txt="{version}"')
        self.send_cmd(f'information.url.txt="{url}"')
    
    def page_boot(self):
        logger.info('Page: boot')
        self.send_cmd('page boot')
        self.send_cmd('boot.tm_notify.en=1')

    def page_main_init(self):
        logger.info('Page: main')
        self.send_cmd('page main')
    
    @my_decorator
    def set_control_value(self, name, value):
        if isinstance(value, str):
            if name == 'main.nozzletemp.txt':
                self.debug = False
            self.send_cmd(f'{name}="{value}"')
        else:
            self.send_cmd(f'{name}={value}')

    def global_update(self, **vals):
        if 'extruder_temp' in vals:
            text = f'{vals["extruder_temp"]:3.0f} / {vals["extruder_target_temp"]:0.0f}'
            self.set_control_value('main.nozzletemp.txt', text)
        if 'bed_temp' in vals:
            text = f'{vals["bed_temp"]:3.0f} / {vals["bed_target_temp"]:0.0f}'
            self.set_control_value('main.bedtemp.txt', text)
        if 'led_state' in vals:
            val = 0 if vals['led_state'] == 0 else 1
            self.set_control_value('led_state', val)
        if 'fan_speed' in vals:
            val = int(vals['fan_speed'] * 100)
            self.set_control_value('fan_speed', val)
        if 'print_state' in vals:
            val = 1 if vals['print_state'] == 'paused' else 0
            self.set_control_value('paused', val)
   
    def page_file(self, page, page_max, file_list, file_ext_list, path):
        self.send_cmd(f'file.page.val={page}')
        self.send_cmd(f'file.page_max.val={page_max}')
        self.send_cmd(f'file.item_list.txt="{file_list}"')
        self.send_cmd(f'file.item_ext_list.txt="{file_ext_list}"')
        self.send_cmd(f'file.dir.txt="{path}"')
        self.send_cmd('click load_list,1')

    async def page_ask_print(self, thumbnail):
        self.send_cmd('exp0.path=""')
        if thumbnail:
            success = await asyncio.to_thread(self.upload_file_to_ram, thumbnail, 't.jpg')
            if success:
                self.send_cmd('exp0.path="ram/t.jpg"')
                self.send_cmd('name.aph=0')

    def page_printing_init(self, filename=None, thumbnail=None):
        logger.info('Page: printpause')
        self.send_cmd('page printpause')
        if filename is not None:
            self.send_cmd(f'filename.txt="{Path(filename).stem}"')
        if thumbnail:
            self.upload_file_to_ram(thumbnail, 't.jpg')
            self.send_cmd('exp0.path="ram/t.jpg"')

    def page_printing_update(self, progress, print_time, z, print_speed):
        self.set_control_value('printpause.printprocess.val', int(progress*100))
        self.set_control_value('printpause.printvalue.txt', str(int(progress*100)))
        self.set_control_value('printpause.printtime.txt', print_time)
        self.set_control_value('printpause.zvalue.val', int(z*100))
        self.set_control_value('printpause.printspeed.txt', str(int(print_speed*100)))

    def page_finish(self, filename):
        self.send_cmd('page printfinish')
        self.send_cmd(f'printfinish.file.txt="{filename}"')

    def page_home(self):
       self.send_cmd('page warn_rdlevel') 

    def page_leveling(self, matrix, offset):
        logger.info('Page: leveling')
        if not matrix or not matrix[0]:
            matrix = [[0] * 6] * 6
        index = 0
        for idx, row in enumerate(matrix):
            if idx % 2 == 1:
                for col in row:
                    self.send_cmd(f'x{index}.val={int(col*100)}')
                    index += 1
            else:
                for col in row[::-1]:
                    self.send_cmd(f'x{index}.val={int(col*100)}')
                    index += 1

    def warning(self, enabled):
        if enabled:
            self.send_cmd('cfgpio 7,3,0')
            self.send_cmd('pwmf=2500')
            self.send_cmd('pwm7=50')
        else:
            self.send_cmd('pwm7=0')

    def create_thumbnail(self, filename, width, height, fillcolor=0):
        import io
        from PIL import Image
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

    def upload_file_to_ram(self, data, dst):
        # clear screen state
        self.ser.write(b'\x00\xff\xff\xff')
        time.sleep(0.05)
        self.ser.write(f'twfile "ram/{dst}",{len(data)}'.encode() + b'\xff\xff\xff')
        val = self.ser.read(4)
        if val[0] != 0xfe:
            logger.error(f'twfile: status={val.hex(" ")}')
            return False

        header = bytearray.fromhex('3a a1 bb 44 7f ff fe')
        chunk_no = 0
        chunk_size = 4096
        i = 0
        while i < len(data):
            wsize = chunk_size
            if len(data) - i < chunk_size:
                wsize = len(data) - i
            info = struct.pack('<BHH', 0, chunk_no, wsize)
            # logger.debug(f'[{n}] {i:5d}, {wsize:5d} / {len(data):5d}')
            # logger.debug((header + info).hex(' '))
            self.ser.write(header)
            self.ser.write(info)
            self.ser.write(data[i:i+wsize])
            i += wsize
            chunk_no += 1
            val = self.ser.read(1)
            if not val or (i != len(data) and val[0] != 0x05) or (i == len(data) and val[0] != 0xfd):
                logger.error(f'ret: {val.hex(" ")}')
                return False
        self.ser.write(b'\x00\xff\xff\xff')
        return True

    def scan_device(self):
        baudrate_list = (512000, 115200, 9600, 921600)
        for baudrate in baudrate_list:
            self.ser.apply_settings({'baudrate': baudrate, 'timeout': 0.4})
            logger.debug(f'Connect screen with baudrate: {baudrate}')
            self.ser.write(b'\x00\xff\xff\xff')
            self.ser.write(b'\x00\xff\xff\xff')
            time.sleep(0.1)
            self.ser.write(b'connect\xff\xff\xff')
            data = self.ser.read(100)
            if data:
                logger.debug(data)
                if b'comok' in data:
                    logger.debug('Connected.')
                    return True
        logger.error('Connect screen failed!')

    def download_firmware(self, firmware, auto_connect=True):
        if auto_connect:
            if not self.scan_device():
                return False
        with open(firmware, 'rb') as fp:
            content = fp.read()
        logger.info('Begin update screen firmware...')
        # 让屏幕进入卡顿2.5秒,防止现有工程不断发送数据干扰下载
        self.ser.write(b'delay=2500\xff\xff\xff')
        self.ser.write(b'0\xff\xff\xff')
        # 1.5秒后发下载指令
        DOWNLOAD_BAUDRATE = 921600
        # DOWNLOAD_BAUDRATE = 9600
        time.sleep(1.5)
        logger.debug(f'Switch baudrate to {DOWNLOAD_BAUDRATE}')
        logger.debug(f'whmi-wri {len(content)},{DOWNLOAD_BAUDRATE},0')
        self.ser.write(f'whmi-wri {len(content)},{DOWNLOAD_BAUDRATE},0'.encode() + b'\xff\xff\xff')
        # 等待发送完毕，再修改波特率
        time.sleep(0.2)
        # 屏幕收到修改波特率命令后270ms后回复0x05，timeout设的久一点
        self.ser.apply_settings({'baudrate': DOWNLOAD_BAUDRATE, 'timeout': 0.5})
        self.ser.reset_input_buffer()
        status = self.ser.read()
        logger.debug(f'Status: {status}')
        if status and status[0] == 0x05:
            CHUNK_SIZE = 4096
            i = 0
            while i < len(content):
                chunk = content[i : i + CHUNK_SIZE]
                self.ser.write(chunk)
                status = self.ser.read()
                if not status or status[0] != 0x05:
                    return False
                i += len(chunk)
        return True

    def set_fan(self, enable):
        self.ser.rts = True if enable else False


class TJC(ScreenMixin):
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.5)

    def write(self, msg):
        self.ser.write(msg)
    
    def close(self):
        self.ser.close()
    
    def get_version(self):
        self.ser.reset_input_buffer()
        self.page_boot()
        self.ser.apply_settings({'timeout': 1.5})
        data = self.ser.read(30)
        logger.debug(data)
        if data:
            pos = data.find(b'boot version=')
            if pos == -1:
                return None
            data = data[pos:].decode().split('=')[-1]
            return int(data)
    

class AsyncSerialScreenProtocol(asyncio.Protocol):
    on_request = None

    def connection_made(self, transport):
        self.transport = transport
        self.recv_data = bytearray()

    def data_received(self, data):
        self.recv_data.extend(data)
        while len(self.recv_data) >= 3:
            if self.recv_data[0] != 0x5a or self.recv_data[1] != 0xa5:
                logger.debug(f'{self.recv_data[0]:02x}')
                self.recv_data.pop(0)
                continue
            packet_size = self.recv_data[2]
            if len(self.recv_data) < 3 + packet_size:
                break
            packet = self.recv_data[0:3+packet_size]
            try:
                if self.on_request:
                    data = packet[3:]
                    asyncio.create_task(self.on_request(data.decode('utf-8')))
                self.recv_data = self.recv_data[len(packet):]
            except Exception as e:
                logger.error(e)
                self.recv_data.clear()

    def pause_reading(self):
        # This will stop the callbacks to data_received
        self.transport.pause_reading()

    def resume_reading(self):
        # This will start the callbacks to data_received again with all data that has been received in the meantime.
        self.transport.resume_reading()

class AsyncTJCScreen(ScreenMixin):

    def __init__(self):
        self.transport = None
        self.protocol = None
        self.ser = None

    async def start(self, port, baudrate=115200):
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(asyncio.get_event_loop(), AsyncSerialScreenProtocol, port, baudrate=baudrate)
        self.ser = self.transport.serial

    def set_request_handler(self, handler):
        self.protocol.on_request = handler

    def write(self, data):
        self.transport.write(data)

    def test(self, transport:serial_asyncio.SerialTransport):
        transport.pause_reading

    def start_raw_serial(self):
        # stop reading & set timeout=0
        self.settings = self.ser.get_settings()
        self.transport.pause_reading()
        self.ser.reset_input_buffer()
        self.ser.apply_settings({'timeout': 100})
    
    def end_raw_serial(self):
        # restore settings & read
        self.ser.reset_input_buffer()
        self.transport.resume_reading()
        self.ser.apply_settings(self.settings)

    def upload_file_to_ram(self, data, dst):
        logger.debug('Switch serial to sync mode.')
        self.start_raw_serial()
        try:
            return super().upload_file_to_ram(data, dst)
        except:
            pass
        finally:
            logger.debug('Switch serial back to async mode.')
            self.end_raw_serial()

    def download_firmware(self, firmware):
        logger.debug('Switch serial to sync mode.')
        self.start_raw_serial()
        try:
            return super().download_firmware(firmware)
        except:
            pass
        finally:
            logger.debug('Switch serial back to async mode.')
            self.end_raw_serial()
