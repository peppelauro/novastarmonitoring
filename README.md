# novastarmonitoring

Python script for reading and sending command via UART to a NovaStar M300 device
Based on the original code by https://github.com/makomi/uart2csv

Read infos (temperature, voltage) from the receiving cards Novastar MD300, using the serial protocol of the device.

Make it executable:

pip install pyinstaller

pyinstaller novainfo.py --onefile
