[Unit]
Description=Klipper Screen for Neptune3Pro
Requires=network-online.target
After=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
SupplementaryGroups=moonraker-admin
RemainAfterExit=yes
WorkingDirectory=ROOT_DIR
ExecStart=ROOT_DIR/venv/bin/python ROOT_DIR/neptune-screen.py
Restart=always
