[Unit]
Description=Klipper Screen for Neptune3Pro
Requires=network-online.target
After=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=klipper
SupplementaryGroups=moonraker-admin
RemainAfterExit=yes

