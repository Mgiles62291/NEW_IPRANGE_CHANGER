import sys
import subprocess
import json
from pathlib import Path

from PySide6.QtCore import Qt
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
LOGO_FILE = Path(__file__).with_name("logo.png")  # optional PNG shown in title & banner

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def run_netsh(cmd: list[str]):
    """Execute a netsh command; show stderr in a dialog on error."""
    try:
        completed = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return completed.stdout.strip()
    except subprocess.CalledProcessError as exc:
        QMessageBox.critical(None, "Netsh Error", f"Command: {' '.join(cmd)}\n\n{exc.stderr}")
        return None


def get_adapters() -> list[str]:
    """Return NIC interface names (spaces preserved)."""
    output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
    adapters: list[str] = []
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

# ─────────────────────────────────────────────────────────────────────────────
# netsh builders
# ─────────────────────────────────────────────────────────────────────────────

quoted = lambda s: f'"{s}"'

def build_static_cmd(adapter: str, profile: dict):
    return [
        "netsh", "interface", "ip", "set", "address", quoted(adapter), "static",
        profile["ip"], profile["mask"], profile["gateway"], "1"  # metric 1
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
        QMessageBox.warning(None, APP_NAME, "IP / Mask / Gateway / DNS required for static profile.")
        return

    run_netsh(build_static_cmd(adapter, profile))
    run_netsh(build_dns_cmd(adapter, profile["dns"], False))

# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(720, 580)
        self.setStyleSheet(self.futuristic_stylesheet())

        self.profiles: dict = load_profiles()

        # Widgets
        self.adapterBox = QComboBox(); self.adapterBox.addItems(get_adapters())
        self.profileList = QListWidget(); self.refresh_profile_list()

        self.profileNameEdit = QLineEdit(placeholderText="Profile Name")
        self.ipEdit = QLineEdit(placeholderText="IP e.g. 192.168.1.50")
        self.maskEdit = QLineEdit(placeholderText="Subnet Mask e.g. 255.255.255.0")
        self.gatewayEdit = QLineEdit(placeholderText="Gateway e.g. 192.168.1.1")
        self.dnsEdit = QLineEdit(placeholderText="DNS e.g. 8.8.8.8")

        self.applyBtn  = QPushButton("Apply Selected")
        self.addBtn    = QPushButton("Add Profile")
        self.updateBtn = QPushButton("Update Profile")
        self.deleteBtn = QPushButton("Delete Profile")
        self.dhcpBtn   = QPushButton("Add DHCP Profile")

        # Layout
        root = QVBoxLayout()

        if LOGO_FILE.exists():
            banner = QLabel(alignment=Qt.AlignCenter)
            banner.setPixmap(QPixmap(str(LOGO_FILE)).scaledToHeight(64, Qt.SmoothTransformation))
            root.addWidget(banner)

        top = QHBoxLayout(); top.addWidget(QLabel("Adapter:")); top.addWidget(self.adapterBox); top.addStretch(); root.addLayout(top)
        root.addWidget(QLabel("Saved Profiles")); root.addWidget(self.profileList, 1)
        for w in (self.profileNameEdit, self.ipEdit, self.maskEdit, self.gatewayEdit, self.dnsEdit):
            root.addWidget(w)
        btnRow = QHBoxLayout();
        for b in (self.applyBtn, self.addBtn, self.updateBtn, self.deleteBtn, self.dhcpBtn):
            btnRow.addWidget(b)
        root.addLayout(btnRow)

        container = QWidget(); container.setLayout(root); self.setCentralWidget(container)

        # Signals
        self.profileList.itemClicked.connect(self.load_selected_profile)
        self.applyBtn.clicked.connect(self.apply_selected)
        self.addBtn.clicked.connect(self.add_profile)
        self.updateBtn.clicked.connect(self.update_profile)
        self.deleteBtn.clicked.connect(self.delete_profile)
        self.dhcpBtn.clicked.connect(self.add_dhcp_profile)

    # ───────── List handling ─────────
    def refresh_profile_list(self):
        self.profileList.clear()
        for name in self.profiles:
            self.profileList.addItem(name)

    def load_selected_profile(self, item: QListWidgetItem):
        name = item.text()
        self.profileNameEdit.setText(name)
        prof = self.profiles[name]
        if prof == "dhcp":
            for e in (self.ipEdit, self.maskEdit, self.gatewayEdit, self.dnsEdit):
                e.clear()
            return
        self.ipEdit.setText(prof.get("ip", ""))
        self.maskEdit.setText(prof.get("mask", ""))
        self.gatewayEdit.setText(prof.get("gateway", ""))
        self.dnsEdit.setText(prof.get("dns", ""))

    def collect_fields(self) -> dict:
        return {
            "ip": self.ipEdit.text().strip(),
            "mask": self.maskEdit.text().strip(),
            "gateway": self.gatewayEdit.text().strip(),
            "dns": self.dnsEdit.text().strip(),
        }

    # ───────── CRUD ─────────
    def add_profile(self):
        name = self.profileNameEdit.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Profile name required."); return
        if name in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Profile exists – use Update."); return
        self.profiles[name] = self.collect_fields()
        save_profiles(self.profiles); self.refresh_profile_list()

    def update_profile(self):
        name = self.profileNameEdit.text().strip()
        if not name or name not in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Select existing profile first."); return
        self.profiles[name] = self.collect_fields()
        save_profiles(self.profiles); self.refresh_profile_list()

    def delete_profile(self):
        item = self.profileList.currentItem()
        if not item:
            return
        name = item.text()
        if QMessageBox.question(self, APP_NAME, f"Delete '{name}'?") == QMessageBox.Yes:
            del self.profiles[name]
            save_profiles(self.profiles); self.refresh_profile_list()

    def add_dhcp_profile(self):
        name = self.profileNameEdit.text().strip() or "DHCP"
        if name in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Name exists – choose another."); return
        self.profiles[name] = "dhcp"
        save_profiles(self.profiles); self.refresh_profile_list()

    # ───────── Apply profile ─────────
    def apply_selected(self):
        item = self.profileList.currentItem()
        if not item:
            QMessageBox.information(self, APP_NAME, "Select a profile first."); return
        adapter = self.adapterBox.currentText()
        apply_profile(adapter, self.profiles[item.text()])
        QMessageBox.information(self, APP_NAME, f"Profile '{item.text()}' applied to {adapter}.")

    # ───────── Style ─────────
    @staticmethod
    def futuristic_stylesheet() -> str:
        return (
            "*{color:#C8E6FA;font-family:'Segoe UI';font-size:13px;}"
            "QMainWindow{background-color:#0d1117;}"
            "QLabel{color:#58A6FF;}"
            "QLineEdit,QListWidget,QComboBox{background-color:#161B22;border:1px solid #30363d;border-radius:4px;padding:4px;}"
            "QPushButton{background-color:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px;}"
            "QPushButton:hover{background
