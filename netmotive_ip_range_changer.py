import sys
import subprocess
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
)
from PySide6.QtGui import QIcon, QPixmap

APP_NAME = "Netmotive IP Range Changer"
PROFILE_FILE = Path("profiles.json")
LOGO_FILE = Path(__file__).with_name("logo.png")          # optional 256×256 PNG

# ────────────────── helpers ──────────────────
def run_netsh(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, shell=True, check=True,
                             capture_output=True, text=True)
        return out.stdout.strip()
    except subprocess.CalledProcessError as e:
        QMessageBox.critical(None, "Netsh Error",
                             f"Command: {' '.join(cmd)}\n\n{e.stderr}")
        return None


def get_adapters() -> list[str]:
    out = subprocess.check_output("netsh interface show interface",
                                  shell=True, text=True)
    return [" ".join(l.split()[3:]) for l in out.splitlines()
            if any(tag in l for tag in ("Dedicated", "Ethernet", "Wi-Fi"))] or ["Ethernet"]


def load_profiles() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except Exception:
            QMessageBox.warning(None, APP_NAME, "profiles.json corrupt – starting fresh.")
    return {}


def save_profiles(p: dict) -> None:
    PROFILE_FILE.write_text(json.dumps(p, indent=2))

# ────────────────── netsh builders ──────────────────
q = lambda s: f'"{s}"'


def static_cmd(adapter: str, p: dict) -> list[str]:
    return ["netsh", "interface", "ip", "set", "address", q(adapter), "static",
            p["ip"], p["mask"], p["gateway"], "1"]          # metric


def dns_cmd(adapter: str, dns: str, dhcp=False) -> list[str]:
    return ["netsh", "interface", "ip", "set", "dns", q(adapter),
            "dhcp" if dhcp else "static", *( [] if dhcp else [dns] )]


def dhcp_cmd(adapter: str) -> list[str]:
    return ["netsh", "interface", "ip", "set", "address", q(adapter), "dhcp"]


def apply_profile(adapter: str, profile):
    if profile == "dhcp":
        run_netsh(dhcp_cmd(adapter)); run_netsh(dns_cmd(adapter, "", True)); return
    if not all(profile.get(k) for k in ("ip", "mask", "gateway", "dns")):
        QMessageBox.warning(None, APP_NAME, "Static profile needs IP/Mask/GW/DNS"); return
    run_netsh(static_cmd(adapter, profile)); run_netsh(dns_cmd(adapter, profile["dns"]))

# ────────────────── UI ──────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(720, 600)
        self.setStyleSheet(self._style())

        self.profiles = load_profiles()

        # widgets
        self.adapterBox = QComboBox(); self.adapterBox.addItems(get_adapters())
        self.profileList = QListWidget(); self._refresh()
        self.profileName = QLineEdit(placeholderText="Profile Name")
        self.ip   = QLineEdit(placeholderText="IP e.g. 192.168.1.50")
        self.mask = QLineEdit(placeholderText="Subnet Mask e.g. 255.255.255.0")
        self.gw   = QLineEdit(placeholderText="Gateway e.g. 192.168.1.1")
        self.dns  = QLineEdit(placeholderText="DNS e.g. 8.8.8.8")

        # buttons
        self.apply  = QPushButton("Apply Selected")
        self.add    = QPushButton("Add Profile")
        self.update = QPushButton("Update Profile")
        self.delete = QPushButton("Delete Profile")
        self.addDhcp = QPushButton("Add DHCP Profile")

        # layout
        root = QVBoxLayout()
        if LOGO_FILE.exists():
            lbl = QLabel(alignment=Qt.AlignCenter)
            lbl.setPixmap(QPixmap(str(LOGO_FILE)).scaledToHeight(64, Qt.SmoothTransformation))
            root.addWidget(lbl)
        top = QHBoxLayout(); top.addWidget(QLabel("Adapter:")); top.addWidget(self.adapterBox); top.addStretch()
        root.addLayout(top)
        root.addWidget(QLabel("Saved Profiles")); root.addWidget(self.profileList, 1)
        for w in (self.profileName, self.ip, self.mask, self.gw, self.dns): root.addWidget(w)
        btnRow = QHBoxLayout()
        for b in (self.apply, self.add, self.update, self.delete, self.addDhcp): btnRow.addWidget(b)
        root.addLayout(btnRow)
        container = QWidget(); container.setLayout(root); self.setCentralWidget(container)

        # signals
        self.profileList.itemClicked.connect(self._load)
        self.apply.clicked.connect(self._apply)
        self.add.clicked.connect(self._add)
        self.update.clicked.connect(self._update)
        self.delete.clicked.connect(self._delete)
        self.addDhcp.clicked.connect(self._add_dhcp)

    # ───── helpers
    def _refresh(self): self.profileList.clear(); self.profileList.addItems(self.profiles.keys())
    def _load(self, item):
        n=item.text(); self.profileName.setText(n); p=self.profiles[n]
        if p=="dhcp": [e.clear() for e in (self.ip,self.mask,self.gw,self.dns)]; return
        self.ip.setText(p["ip"]); self.mask.setText(p["mask"]); self.gw.setText(p["gateway"]); self.dns.setText(p["dns"])
    def _collect(self): return {"ip":self.ip.text().strip(),"mask":self.mask.text().strip(),"gateway":self.gw.text().strip(),"dns":self.dns.text().strip()}

    # CRUD
    def _add(self):
        n=self.profileName.text().strip()
        if not n: QMessageBox.warning(self,APP_NAME,"Name required");return
        if n in self.profiles: QMessageBox.warning(self,APP_NAME,"Exists–Update?");return
        self.profiles[n]=self._collect(); save_profiles(self.profiles); self._refresh()
    def _update(self):
        n=self.profileName.text().strip()
        if n not in self.profiles: QMessageBox.warning(self,APP_NAME,"Select existing");return
        self.profiles[n]=self._collect(); save_profiles(self.profiles); self._refresh()
    def _delete(self):
        it=self.profileList.currentItem()
        if not it: return
        n=it.text()
        if QMessageBox.question(self,APP_NAME,f"Delete '{n}'?")==QMessageBox.Yes:
            del self.profiles[n]; save_profiles(self.profiles); self._refresh()
    def _add_dhcp(self):
        n=self.profileName.text().strip() or "DHCP"
        if n in self.profiles: QMessageBox.warning(self,APP_NAME,"Name exists");return
        self.profiles[n]="dhcp"; save_profiles(self.profiles); self._refresh()

    def _apply(self):
        it=self.profileList.currentItem()
        if not it: QMessageBox.information(self,APP_NAME,"Select profile"); return
        apply_profile(self.adapterBox.currentText(), self.profiles[it.text()])
        QMessageBox.information(self,APP_NAME,f"Applied '{it.text()}'")

    # style
    @staticmethod
    def _style():
        return (\"*{color:#C8E6FA;font-family:'Segoe UI';font-size:13px;}\"\n"
                \"QMainWindow{background:#0d1117;} QLabel{color:#58A6FF;}\"\n"
                \"QLineEdit,QListWidget,QComboBox{background:#161B22;border:1px solid #30363d;border-radius:4px;padding:4px;}\"\n"
                \"QPushButton{background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px;}\"\n"
                \"QPushButton:hover{background:#30363d;} QPushButton:pressed{background:#10567b;}\")\n"

# ────────────────── entry ──────────────────
def main():
    app = QApplication(sys.argv)
    MainWindow().show()
    sys.exit(app.exec())

if __name__ == \"__main__\": main()
