"""
Netmotive IP Range Changer
==========================

• Lists your NICs (Ethernet/Wi-Fi)
• Lets you save static or DHCP “profiles”
• One-click apply
• Shows a logo banner + window icon if a 256 × 256 `logo.png`
  is placed in the same folder as the script / EXE.
"""

import sys
import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
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

APP_NAME = "Netmotive IP Range Changer"
PROFILE_FILE = Path("profiles.json")
LOGO_FILE = Path(__file__).with_name("logo.png")  # optional PNG

# ───────────────────────── helpers ─────────────────────────
def run_netsh(cmd: list[str]) -> str | None:
    """Run a netsh command; show stderr in a dialog on error."""
    try:
        out = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return out.stdout.strip()
    except subprocess.CalledProcessError as err:
        QMessageBox.critical(
            None, "Netsh Error", f"Command: {' '.join(cmd)}\n\n{err.stderr}"
        )
        return None


def get_adapters() -> list[str]:
    """Return NIC names (spaces preserved)."""
    out = subprocess.check_output(
        "netsh interface show interface", shell=True, text=True
    )
    names = [
        " ".join(line.split()[3:])
        for line in out.splitlines()
        if any(tag in line for tag in ("Dedicated", "Ethernet", "Wi-Fi"))
    ]
    return names or ["Ethernet"]


def load_profiles() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except ValueError:
            QMessageBox.warning(None, APP_NAME, "profiles.json corrupt – starting fresh.")
    return {}


def save_profiles(profiles: dict) -> None:
    PROFILE_FILE.write_text(json.dumps(profiles, indent=2))


# ───────────────────── netsh builders ─────────────────────
q = lambda s: f'"{s}"'  # quote names with spaces


def static_cmd(adapter: str, p: dict) -> list[str]:
    return [
        "netsh",
        "interface",
        "ip",
        "set",
        "address",
        q(adapter),
        "static",
        p["ip"],
        p["mask"],
        p["gateway"],
        "1",
    ]  # metric 1


def dns_cmd(adapter: str, dns: str, dhcp: bool) -> list[str]:
    return (
        ["netsh", "interface", "ip", "set", "dns", q(adapter), "dhcp"]
        if dhcp
        else ["netsh", "interface", "ip", "set", "dns", q(adapter), "static", dns]
    )


def dhcp_cmd(adapter: str) -> list[str]:
    return ["netsh", "interface", "ip", "set", "address", q(adapter), "dhcp"]


def apply_profile(adapter: str, profile) -> None:
    if profile == "dhcp":
        run_netsh(dhcp_cmd(adapter))
        run_netsh(dns_cmd(adapter, "", True))
        return

    if not all(profile.get(k) for k in ("ip", "mask", "gateway", "dns")):
        QMessageBox.warning(
            None, APP_NAME, "Static profile requires IP / Mask / Gateway / DNS."
        )
        return

    run_netsh(static_cmd(adapter, profile))
    run_netsh(dns_cmd(adapter, profile["dns"], False))


# ───────────────────────── GUI ─────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # Window basics
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(720, 620)
        self.setStyleSheet(self._style())

        # Data
        self.profiles: dict = load_profiles()

        # Widgets ───────────────────────────────────────────
        self.adapter_box = QComboBox()
        self.adapter_box.addItems(get_adapters())

        self.profile_list = QListWidget()
        self._refresh_list()

        self.profile_name = QLineEdit(placeholderText="Profile Name")
        self.ip   = QLineEdit(placeholderText="IP e.g. 192.168.1.50")
        self.mask = QLineEdit(placeholderText="Subnet Mask e.g. 255.255.255.0")
        self.gw   = QLineEdit(placeholderText="Gateway e.g. 192.168.1.1")
        self.dns  = QLineEdit(placeholderText="DNS e.g. 8.8.8.8")

        self.apply_btn  = QPushButton("Apply")
        self.add_btn    = QPushButton("Add")
        self.update_btn = QPushButton("Update")
        self.delete_btn = QPushButton("Delete")
        self.dhcp_btn   = QPushButton("Add DHCP")

        # Layout ────────────────────────────────────────────
        root = QVBoxLayout()

        if LOGO_FILE.exists():
            banner = QLabel(alignment=Qt.AlignCenter)
            banner.setPixmap(
                QPixmap(str(LOGO_FILE)).scaledToHeight(64, Qt.SmoothTransformation)
            )
            root.addWidget(banner)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Adapter:"))
        top_row.addWidget(self.adapter_box)
        top_row.addStretch()
        root.addLayout(top_row)

        root.addWidget(QLabel("Saved Profiles"))
        root.addWidget(self.profile_list, 1)

        for w in (self.profile_name, self.ip, self.mask, self.gw, self.dns):
            root.addWidget(w)

        btn_row = QHBoxLayout()
        for b in (
            self.apply_btn,
            self.add_btn,
            self.update_btn,
            self.delete_btn,
            self.dhcp_btn,
        ):
            btn_row.addWidget(b)
        root.addLayout(btn_row)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        # Signals
        self.profile_list.itemClicked.connect(self._load_profile)
        self.apply_btn.clicked.connect(self._apply_profile)
        self.add_btn.clicked.connect(self._add_profile)
        self.update_btn.clicked.connect(self._update_profile)
        self.delete_btn.clicked.connect(self._delete_profile)
        self.dhcp_btn.clicked.connect(self._add_dhcp_profile)

    # ───── list helpers
    def _refresh_list(self) -> None:
        self.profile_list.clear()
        self.profile_list.addItems(self.profiles.keys())

    def _save_and_refresh(self) -> None:
        save_profiles(self.profiles)
        self._refresh_list()

    def _load_profile(self, item: QListWidgetItem) -> None:
        name = item.text()
        self.profile_name.setText(name)
        prof = self.profiles[name]

        if prof == "dhcp":
            for field in (self.ip, self.mask, self.gw, self.dns):
                field.clear()
            return

        self.ip.setText(prof["ip"])
        self.mask.setText(prof["mask"])
        self.gw.setText(prof["gateway"])
        self.dns.setText(prof["dns"])

    def _collect_fields(self) -> dict:
        return {
            "ip": self.ip.text().strip(),
            "mask": self.mask.text().strip(),
            "gateway": self.gw.text().strip(),
            "dns": self.dns.text().strip(),
        }

    # ───── CRUD handlers
    def _add_profile(self) -> None:
        name = self.profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Name required.")
            return
        if name in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Profile exists – use Update.")
            return

        self.profiles[name] = self._collect_fields()
        self._save_and_refresh()

    def _update_profile(self) -> None:
        name = self.profile_name.text().strip()
        if name not in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Select an existing profile.")
            return

        self.profiles[name] = self._collect_fields()
        self._save_and_refresh()

    def _delete_profile(self) -> None:
        item = self.profile_list.currentItem()
        if not item:
            return
        name = item.text()
        if QMessageBox.question(self, APP_NAME, f"Delete '{name}'?") == QMessageBox.Yes:
            del self.profiles[name]
            self._save_and_refresh()

    def _add_dhcp_profile(self) -> None:
        name = self.profile_name.text().strip() or "DHCP"
        if name in self.profiles:
            QMessageBox.warning(self, APP_NAME, "Name exists.")
            return
        self.profiles[name] = "dhcp"
        self._save_and_refresh()

    # ───── apply handler
    def _apply_profile(self) -> None:
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.information(self, APP_NAME, "Select a profile.")
            return
        adapter = self.adapter_box.currentText()
        apply_profile(adapter, self.profiles[item.text()])
        QMessageBox.information(self, APP_NAME, f"Applied '{item.text()}'")

    # ───── stylesheet
    @staticmethod
    def _style() -> str:
        return (
            "* {color:#C8E6FA; font-family:'Segoe UI'; font-size:13px;}"
            "QMainWindow {background-color:#0d1117;}"
            "QLabel {color:#58A6FF;}"
            "QLineEdit, QListWidget, QComboBox {"
            "  background-color:#161B22;"
            "  border:1px solid #30363d;"
            "  border-radius:4px;"
            "  padding:4px;"
            "}"
            "QPushButton {"
            "  background-color:#21262d;"
            "  border:1px solid #30363d;"
            "  border-radius:6px;"
            "  padding:6px;"
            "}"
            "QPushButton:hover {background-color:#30363d;}"
            "QPushButton:pressed {background-color:#10567b;}"
        )


# ───────────────────────── entry ─────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    MainWindow().show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
