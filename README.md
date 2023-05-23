# neptune-screen


## 安装说明

1. 升级屏幕固件*.tft
2. 通过ssh登录Klipper主机，切换到klipper用户，克隆本仓库，并安装（安装服务需要root权限，安装过程中会提示输入root用户密码）
    ```bash
    su klipper
    cd ~
    git clone https://github.com/t1ngyu/neptune-screen.git
    bash neptune-screen/setup.sh
    ```
3. 重启Klipper主机
4. 设置屏幕参数
    
    浏览器打开Fluidd（kilpper的web界面），"配置" 页面内编辑neptune-screen.json，设置屏幕连接的串口（默认值对应海王星专用HUB）
    ```json
    {
        "Serial": "/dev/serial/by-path/platform-ci_hdrc.0-usb-0:1.1:1.0-port0",
        "Baudrate": 512000,
        "Moonraker": "localhost",
        "FanStartTemp": 51,
        "FanStopTemp": 49
    }
    ```
    * Serial

        屏幕对应的串口

    * Baudrate

        当前屏幕固件使用该值，不要修改
    
    * Moonraker

        Klipper主机的IP地址，该服务也运行在Klipper主机上，填localhost即可

    * FanStartTemp
    
        CPU温度高于该值，开启风扇

    * FanStopTemp
    
        CPU温度低于该值，关闭风扇

5. 修改Klipper主板对应的串口（使用海王星专用HUB时，需要设置为/dev/serial/by-path/开头的路径）

6. Fluidd界面右上角，弹出菜单中 "服务" 一栏中重启NeptuneScreen服务。

7. （可选步骤）Fluidd界面支持更新NeptuneScreen

    浏览器打开Fluidd（kilpper的web界面），"配置" 页面内编辑moonraker.conf，加入以下内容，即可在 "设置" -> "软件更新" 处更新NeptuneScreen程序
    ```ini
    [update_manager NeptuneScreen]
    type: git_repo
    channel: dev
    path: ~/neptune-screen
    origin: https://github.com/t1ngyu/neptune-screen.git
    is_system_service: True
    managed_services:
    NeptuneScreen
    ```

## 注意事项

* 海王星屏幕的通讯接口为串口，因此非海王星专用HUB只要通过USB转串口线将屏幕连接到HUB上也是可以的；

* 海王星专用HUB上的USB转串口芯片与海王星主板的USB转串口芯片的VID/PID一样，因此串口路径不能使用/dev/serial/by-id开头的路径，改为/dev/serial/by-path/下的路径，该路径和USB口的位置对应，如果后续打印机主板插到了HUB的另外一个USB口上，需要修改Klipper内[mcu]的Serial参数；

* 温度控制HUB内散热风扇的开启和关闭，实际是设置屏幕串口的RTS引脚的电平，使用非海王星HUB时，如果有电子电路经验，自行搭建电路控制风扇也可；


## 海王星专用HUB

https://oshwhub.com/t1ngyu/wifi-stick-dock