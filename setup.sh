#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ~/printer_data ]; then
	echo Directory not found: ~/printer_data
	exit 1
fi

# setup venv
python3 -m venv venv
venv/bin/python3 -m pip install -r requirements.txt

# create NeptuneScreen.service
cat NeptuneScreen.service.tpl > NeptuneScreen.service
echo WorkingDirectory=`pwd` >> NeptuneScreen.service
echo ExecStart=`pwd`/venv/bin/python `pwd`/neptune-screen.py >> NeptuneScreen.service
echo Restart=always >> NeptuneScreen.service

if [ -e  ]
# install moonraker managed_services
if ! grep -q 'NeptuneScreen' ~/printer_data/moonraker.asvc ; then
	echo NeptuneScreen >> ~/printer_data/moonraker.asvc
fi

# install neptune-screen.json
cp config.json.example ~/printer_data/config/neptune-screen.json

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
