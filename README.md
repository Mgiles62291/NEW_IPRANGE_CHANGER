# Netmotive IP Range Changer

Futuristic Qt-based GUI to manage IP profiles on Windows adapters.

## Features
* List Ethernet/Wi‑Fi adapters
* Create / edit / delete static or DHCP profiles
* Persist profiles in `profiles.json`
* One-click apply via `netsh`

## Run from source
```bash
pip install -r requirements.txt
python netmotive_ip_range_changer.py  # run as Administrator
```

## Build the EXE
```bash
pip install pyinstaller
pyinstaller --onefile --windowed netmotive_ip_range_changer.py
```

## CI
GitHub Actions workflow builds and uploads the EXE on every push.
