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
LOGO_FILE = Path(__file__).with_name("logo.png")  # place a PNG next to the EXE if you like

# ───────────────────────── helpers ─────────────────────────
def run_netsh(cmd: list[str]) -> str | None:
    """Run a netsh command; show stderr in a dialog if it fails."""
    try:
        out = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return out.stdout.strip()
    except subprocess.CalledProcessError as exc:
        QMessageBox.critical(None, "Netsh Error",
                             f"Command: {' '.join(cmd)}\n\n{exc.stderr}")
        return None


def get_adapters() -> list[str]:
    """Return NIC interface names (spaces preserved)."""
    out = subprocess.check_output("netsh interface show interface", shell=True, text=True)
    adapters = [
        " ".join(l.split()[3:])
        for l in out.splitlines()
        if any(tag in l for tag in ("Dedicated", "Ethernet", "Wi-Fi"))
    ]
    return adapters or ["Ethernet"]


def load_profiles() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except Exception:
            QMessageBox.warning(None, APP_NAME,
                                "profiles.json corrupt – starting fresh.")
    return {}


def save_profiles(p: dict):
    PROFILE_FILE.write_text(json.dumps(p, indent=2))


# ───────────────────── netsh builders ─────────────────────
q = lambda s: f'"{s}"'  # quote interface names with spaces


def static_cmd(adapter: str, p: dict) -> list[str]:
    return [
        "netsh", "interface", "ip", "set", "address", q(adapter), "static",
        p["ip"], p["mask"], p["gateway"], "1"       # metric 1
    ]


def dns_cmd(adapter: str, dns: str, dhcp: bool) -> list[str]:
    return (
        ["netsh", "interface", "ip", "set", "dns", q(adapter), "dhcp"]
        if dhcp else
        ["netsh", "interface", "ip", "set", "dns", q(adapter), "static", dns]
    )


def dhcp_cmd(adapter: str) -> list[str]:
    return ["netsh", "interface", "ip", "set", "address", q(adapter), "dhcp"]


def apply_profile(adapter: str, profile):
    if profile == "dhcp":
        run_netsh(dhcp_cmd(adapter))
        run_netsh(dns_cmd(adapter, "", True))
        return

    required = ("ip", "mask", "gateway", "dns")
    if not all(profile.get(k) for k in required):
        QMessageBox.warning(None, APP_NAME,
                            "Static profile requires IP / Mask / Gateway / DNS.")
        return
    run_netsh(static_cmd(adapter, profile))
    run_netsh(dns_cmd(adapter, profile["dns"], False))


# ───────────────────────── main window ─────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(720, 620)
        self.setStyleSheet(self._style())

        self.profiles = load_profiles()

        # Widgets
        self.adapterBox = QComboBox()
        self.adapterBox.addItems(get_adapters())

        self.profileList = QListWidget()
        self._refresh_list()

        self.profileName = QLineEdit(placeholderText="Profile Name")
        self.ip   = QLineEdit(placeholderText="IP e.g. 192.168.1.50")
        self.mask = QLineEdit(placeholderText="Subnet Mask e.g. 255.255.255.0")
        self.gw   = QLineEdit(placeholderText="Gateway e.g. 192.168.1.1")
        self.dns  = QLineEdit(placeholderText="DNS e.g. 8.8.8.8")

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

        top = QHBoxLayout()
        top.addWidget(QLabel("Adapter:"))
        top.addWidget(self.adapterBox)
        top.addStretch()
        root.addLayout(top)

        root.addWidget(QLabel("Saved Profiles"))
        root.addWidget(self.profileList, 1)

        for w in (self.profileName, self.ip, self.mask, self.gw, self.dns):
            root.addWidget(w)

        btn_row = QHBoxLayout()
        for b in (self.applyBtn, self.addBtn, self.updateBtn, self.deleteBtn, self.dhcpBtn):
            btn_row.addWidget(b)
        root.addLayout(btn_row)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        # Signals
        self.profileList.itemClicked.connect(self._load)
        self.applyBtn.clicked.connect(self._apply)
        self.addBtn.clicked.connect(self._add)
        self.updateBtn.clicked.connect(self._update)
        self.deleteBtn.clicked.connect(self._delete)
        self.dhcpBtn.clicked.connect(self._add_dhcp)

    # ───── list helpers
    def _refresh_list(self):
        self.profileList.clear()
        self.profileList.addItems(self.profiles.keys())

    def _load(self, item: QListWidgetItem):
        name = item.text()
        self.profileName.setText(name)
        prof = self.profiles[name]
        if prof == "dhcp":
            for e in (self.ip, self.mask, self.gw, self.dns):
                e.clear()
            return
        self.ip.setText(prof["ip"])
        self.mask.setText(prof["mask"])
        self.gw.setText(prof["gateway"])
        self.dns.setText(prof["dns"])

    def _collect(self) -> dict:
        return {
            "ip": self.ip.text().strip(),
            "mask": self.mask.text().strip(),
            "gateway": self.gw.text().strip(),
            "dns": self.dns.text().strip()
        }

    # ───── CRUD
    def _add(self):
        n = self.profileName.text().strip()
        if not n:
            QMessageBox.warning(self, APP_NAME, "Name required")
            return
        if n in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Profile exists – use Update")
            return
        self.profiles[n] = self._collect()
        save_profiles(self.profiles)
        self._refresh_list()

    def _update(self):
        n = self.profileName.text().strip()
        if n not in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Select existing profile")
            return
        self.profiles[n] = self._collect()
        save_profiles(self.profiles)
        self._refresh_list()

    def _delete(self):
        it = self.profileList.currentItem()
        if not it:
            return
        n = it.text()
        if QMessageBox.question(self, APP_NAME, f"Delete '{n}'?") == QMessageBox.Yes:
            del self.profiles[n]
            save_profiles(self.profiles)
            self._refresh_list()

    def _add_dhcp(self):
        n = self.profileName.text().strip() or "DHCP"
        if n in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Name exists")
            return
        self.profiles[n] = "dhcp"
        save_profiles(self.profiles)
        self._refresh_list()

    def _apply(self):
        it = self.profileList.currentItem()
        if not it:
            QMessageBox.information(self, APP_NAME, "Select a profile")
            return
        apply_profile(self.adapterBox.currentText(),
                      self.profiles[it.text()])
        QMessageBox.information(self, APP_NAME,
                                f"Applied '{it.text()}'")

    # ───── stylesheet
    @staticmethod
    def _style() -> str:
        return (
            "* {color:#C8E6FA; font-family:'Segoe UI'; font-size:13px;}"
            "QMainWindow {background-color:#0d1117;}"
            "QLabel {color:#58A6FF;}"
            "QLineEdit, QListWidget, QComboBox {background-color:#161B22;"
            " border:1px solid #30363d; border-radius:4px; padding:4px;}"
            "QPushButton {background-color:#21262d; border:1px solid #30363d;"
            " border-radius:6px; padding:6px;}"
            "QPushButton:hover {background-color:#30363d;}"
            "QPushButton:pressed {background-color:#10567b;}"
        )

# ───────────────────────── entry ─────────────────────────
def main():
    app = QApplication(sys.argv)
    MainWindow().show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
