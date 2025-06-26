# Netmotive IP Range Changer

Futuristic Qt-based GUI for Windows that lets you:

* List Ethernet/Wi‑Fi adapters
* Create / edit / delete IP profiles (static or DHCP)
* Apply a profile with one click
* Persist profiles in **profiles.json**

## Running from source
```bash
pip install -r requirements.txt
python netmotive_ip_range_changer.py   # run as Administrator
```

## Building the portable `.exe`
```bash
pip install pyinstaller
pyinstaller --onefile --windowed netmotive_ip_range_changer.py
# output → dist/netmotive_ip_range_changer.exe
```

## CI build
Push to `main` or tag `v*` and GitHub Actions builds the EXE artifact automatically.
