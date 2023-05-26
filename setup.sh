#!/bin/bash
klipper_path=~
cd "$(dirname "$0")"

if [ ! -d ${klipper_path}/printer_data ]; then
	echo Directory not found: ${klipper_path}/printer_datav
	exit 1
fi

sudo apt install python3-venv
# setup venv
python3 -m venv venv
venv/bin/python3 -m pip install -r requirements.txt

# config moonraker
if ! grep -q 'NeptuneScreen' ${klipper_path}/printer_data/moonraker.asvc ; then
	echo NeptuneScreen >> ${klipper_path}/printer_data/moonraker.asvc
fi

if ! grep -q 'NeptuneScreen' ${klipper_path}/printer_data/config/moonraker.conf ; then
	repo_url=`git remote get-url origin`
	sed -E "s#http.+git#${repo_url}#g" moonraker.conf.example >> ${klipper_path}/printer_data/config/moonraker.conf
fi

# install neptune-screen.json
cp config.json.example ${klipper_path}/printer_data/config/neptune-screen.json

# create NeptuneScreen.service
sed "s#ROOT_DIR#`pwd`#g" NeptuneScreen.service.tpl > NeptuneScreen.service

# install NeptuneScreen service
if [ -e /etc/systemd/system/NeptuneScreen.service ]; then
	sudo rm /etc/systemd/system/NeptuneScreen.service
fi
if [ -e /etc/systemd/system/multi-user.target.wants/NeptuneScreen.service ]; then
	sudo rm /etc/systemd/system/multi-user.target.wants/NeptuneScreen.service
fi
sudo ln -s `pwd`/NeptuneScreen.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable NeptuneScreen.service
sudo systemctl start NeptuneScreen

echo Installation completed.
echo Please reboot the machine
