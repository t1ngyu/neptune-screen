# neptune-screen

## 项目背景

海王星3pro出厂系统为marlin，使用上位机安装klipper后原厂屏幕就废弃了，对于自带屏幕的上位机不需要该项目，对于没有屏幕的上位机，可以使用该项目将原厂屏幕利用起来。

原厂屏幕接口为串口，通过USB转串口连接到klipper上位机，在上位机上运行本程序，本程序作为屏幕和klipper之间的桥梁，使屏幕可以操控klipper进行打印。


## 主要功能

* 使海王星3Pro屏幕支持Klipper
* 实现了基本的浏览文件打印、打印状态显示、手动移动、预加热喷头和热床等功能
* 自动更新屏幕固件


## 安装说明

1. 通过ssh使用klipper用户登录Klipper主机，克隆本仓库，并安装（安装服务需要root权限，安装过程中会提示输入root用户密码）
    ```bash
    git clone https://github.com/t1ngyu/neptune-screen.git
    bash neptune-screen/setup.sh
    ```
2. 重启Klipper主机
3. 设置屏幕参数
    
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

4. 修改Klipper主板对应的串口（使用海王星专用HUB时，需要设置为/dev/serial/by-path/开头的路径）

5. Fluidd界面右上角，弹出菜单中 "服务" 一栏中重启NeptuneScreen服务。


## 更换安装源

考虑github有时访问速度比较慢，仓库在gitee做了镜像，将安装说明第1步中的地址换为gitee仓库地址即可；
```bash
git clone https://github.com/t1ngyu/neptune-screen.git
改为
git clone https://gitee.com/t1ngyu/neptune-screen.git
```


## 海王星专用HUB

海王星3pro屏幕接口为串口，采用电话线端子，自己接线需要拆开屏幕接线，另外需要USB转串口线，因此我做了海王星3pro专用USB hub，项目地址：https://oshwhub.com/t1ngyu/wifi-stick-dock

主要功能：
* 集成了电话线插座，可以直接插上屏幕
* 集成了USB转串口芯片
* 集成了TF卡读卡器，可以直接插TF卡
* 集成了程序可控制的风扇接口，通过温度控制风扇开启和关系
* 布局可以直接插随身WIFI上位机

### 注意事项

* 海王星专用HUB上的USB转串口芯片与海王星主板的USB转串口芯片的VID/PID一样，因此串口路径不能使用/dev/serial/by-id开头的路径，改为/dev/serial/by-path/下的路径，该路径和USB口的位置对应，如果后续打印机主板插到了HUB的另外一个USB口上，需要修改Klipper内[mcu]的Serial参数；

* 温度控制HUB内散热风扇的开启和关闭，实际是设置屏幕连接的串口的RTS引脚的电平，使用非海王星HUB时，如果有电子电路经验，自行搭建电路控制风扇也可；