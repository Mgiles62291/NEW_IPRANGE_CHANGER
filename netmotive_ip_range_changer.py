import sys
import subprocess
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QIcon, QPixmap

APP_NAME = "Netmotive IP Range Changer"
PROFILE_FILE = Path("profiles.json")
LOGO_FILE = Path(__file__).with_name("logo.png")  # drop a 256×256 PNG next to the script

# --------------------- Utility helpers --------------------------------------

def run_netsh(cmd: list[str]):
    try:
        completed = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return completed.stdout.strip()
    except subprocess.CalledProcessError as exc:
        QMessageBox.critical(None, "Netsh Error", f"Command: {' '.join(cmd)}\n\n{exc.stderr}")
        return None


def get_adapters() -> list[str]:
    output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
    adapters = []
    for line in output.splitlines():
        if any(tag in line for tag in ("Dedicated", "Ethernet", "Wi-Fi")):
            adapters.append(" ".join(line.split()[3:]))
    return adapters or ["Ethernet"]


def load_profiles() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except Exception:
            QMessageBox.warning(None, APP_NAME, "profiles.json corrupt – starting fresh.")
    return {}


def save_profiles(profiles: dict):
    PROFILE_FILE.write_text(json.dumps(profiles, indent=2))

# ------------------ netsh builders -----------------------------------------

def quoted(name: str) -> str:
    return f'"{name}"'


def build_static_cmd(adapter: str, profile: dict):
    return [
        "netsh", "interface", "ip", "set", "address", quoted(adapter), "static",
        profile["ip"], profile["mask"], profile["gateway"], "1"
    ]


def build_dns_cmd(adapter: str, dns: str, dhcp: bool):
    if dhcp:
        return ["netsh", "interface", "ip", "set", "dns", quoted(adapter), "dhcp"]
    return ["netsh", "interface", "ip", "set", "dns", quoted(adapter), "static", dns]


def build_dhcp_cmd(adapter: str):
    return ["netsh", "interface", "ip", "set", "address", quoted(adapter), "dhcp"]


def apply_profile(adapter: str, profile):
    if profile == "dhcp":
        run_netsh(build_dhcp_cmd(adapter))
        run_netsh(build_dns_cmd(adapter, "", True))
        return
    if not all(profile.get(k) for k in ("ip", "mask", "gateway", "dns")):
        QMessageBox.warning(None, APP_NAME, "Fill in IP, Mask, Gateway, and DNS for a static profile.")
        return
    run_netsh(build_static_cmd(adapter, profile))
    run_netsh(build_dns_cmd(adapter, profile["dns"], False))

# ------------------------- Main Window --------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(680, 540)
        self.setStyleSheet(self.futuristic_stylesheet())

        self.profiles: dict = load_profiles()

        # UI widgets
        self.adapterBox = QComboBox(); self.adapterBox.addItems(get_adapters())
        self.profileList = QListWidget(); self.refresh_profile_list()

        self.profileNameEdit = QLineEdit(); self.profileNameEdit.setPlaceholderText("Profile Name")
        self.ipEdit = QLineEdit(); self.ipEdit.setPlaceholderText("IP e.g. 192.168.1.50")
        self.maskEdit = QLineEdit(); self.maskEdit.setPlaceholderText("Subnet Mask e.g. 255.255.255.0")
        self.gatewayEdit = QLineEdit(); self.gatewayEdit.setPlaceholderText("Gateway e.g. 192.168.1.1")
        self.dnsEdit = QLineEdit(); self.dnsEdit.setPlaceholderText("DNS e.g. 8.8.8.8")

        self.applyBtn = QPushButton("Apply Selected")
        self.addBtn = QPushButton("Add Profile")
        self.updateBtn = QPushButton("Update Profile")
        self.deleteBtn = QPushButton("Delete Profile")
        self.dhcpBtn = QPushButton("Add DHCP Profile")

        # Layout
        layout = QVBoxLayout()

        # Logo banner (if available)
        if LOGO_FILE.exists():
            logo_label = QLabel(); logo_label.setAlignment(Qt.AlignCenter)
            pix = QPixmap(str(LOGO_FILE)).scaledToHeight(64, mode=Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
            layout.addWidget(logo_label)

        top = QHBoxLayout(); top.addWidget(QLabel("Adapter:")); top.addWidget(self.adapterBox); top.addStretch(); layout.addLayout(top)
        layout.addWidget(QLabel("Saved Profiles")); layout.addWidget(self.profileList, 1)
        for w in (self.profileNameEdit, self.ipEdit, self.maskEdit, self.gatewayEdit, self.dnsEdit):
            layout.addWidget(w)
        btns = QHBoxLayout();
        for b in (self.applyBtn, self.addBtn, self.updateBtn, self.deleteBtn, self.dhcpBtn):
            btns.addWidget(b)
        layout.addLayout(btns)
        container = QWidget(); container.setLayout(layout); self.setCentralWidget(container)

        # Signals
        self.profileList.itemClicked.connect(self.load_selected_profile)
        self.applyBtn.clicked.connect(self.apply_selected)
        self.addBtn.clicked.connect(self.add_profile)
        self.updateBtn.clicked.connect(self.update_profile)
        self.deleteBtn.clicked.connect(self.delete_profile)
        self.dhcpBtn.clicked.connect(self.add_dhcp_profile)

    # ---------------- Core methods ----------------
    def refresh_profile_list(self):
        self.profileList.clear()
        for name in self.profiles:
            self.profileList.addItem(name)

    def load_selected_profile(self, item: QListWidgetItem):
        name = item.text(); self.profileNameEdit.setText(name)
        prof = self.profiles[name]
        if prof == "dhcp":
            for e in (self.ipEdit, self.maskEdit, self.gatewayEdit, self.dnsEdit): e.clear()
            return
        self.ipEdit.setText(prof.get("ip", "")); self.maskEdit.setText(prof.get("mask", ""))
        self.gatewayEdit.setText(prof.get("gateway", "")); self.dnsEdit.setText(prof.get("dns", ""))

    def collect_fields(self):
        return {
            "ip": self.ipEdit.text().strip(),
            "mask": self.maskEdit.text().strip(),
            "gateway": self.gatewayEdit.text().strip(),
            "dns": self.dnsEdit.text().strip()
        }

    # CRUD
    def add_profile(self):
        name = self.profileNameEdit.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Profile name required.")
            return
        if name in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Profile exists – use Update.")
            return
        self.profiles[name] = self.collect_fields(); save_profiles(self.profiles); self.refresh_profile_list()

    def update_profile(self):
        name = self.profileNameEdit.text().strip()
        if not name or name not in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Select existing profile first.")
            return
        self.profiles[name] = self.collect_fields(); save_profiles(self.profiles); self.refresh_profile_list()

    def delete_profile(self):
        item = self.profileList.currentItem();
        if not item: return
        name = item.text()
        if QMessageBox.question(self, APP_NAME, f"Delete '{name}'?") == QMessageBox.Yes:
            del self.profiles[name]; save_profiles(self.profiles); self.refresh_profile_list()

    def add_dhcp_profile(self):
        name = self.profileNameEdit.text().strip() or "DHCP"
        if name in self.profiles:
            QMessageBox.warning(self
