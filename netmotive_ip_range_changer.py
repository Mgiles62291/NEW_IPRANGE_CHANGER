import sys
import subprocess
import json
import os
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Netmotive IP Range Changer"
PROFILE_FILE = Path("profiles.json")

# ---------- Utility functions -------------------------------------------------
def run_netsh(cmd: list[str]):
    """Run a netsh command list, show popup if fails."""
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        QMessageBox.critical(None, "Netsh Error", f"Command: {' '.join(cmd)}\n\n{e.stderr}")
        raise

def get_adapters() -> list[str]:
    """Return list of interface names that are *up* and not loopback."""
    output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
    adapters = []
    for line in output.splitlines():
        if "Dedicated" in line or "Ethernet" in line or "Wi-Fi" in line:
            name = line.split()[-1]
            adapters.append(name)
    return adapters

def load_profiles() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except Exception:
            QMessageBox.warning(None, APP_NAME, "profiles.json is corrupt – starting fresh.")
    return {}

def save_profiles(profiles: dict):
    PROFILE_FILE.write_text(json.dumps(profiles, indent=2))

def apply_profile(adapter: str, profile):
    if profile == "dhcp":
        run_netsh(["netsh", "interface", "ip", "set", "address", adapter, "dhcp"])
        run_netsh(["netsh", "interface", "ip", "set", "dns", adapter, "dhcp"])
        return
    run_netsh([
        "netsh", "interface", "ip", "set", "address", adapter, "static",
        profile["ip"], profile["mask"], profile["gateway"]
    ])
    run_netsh([
        "netsh", "interface", "ip", "set", "dns", adapter, "static",
        profile["dns"]
    ])

# ---------- GUI ---------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(540, 420)
        self.setStyleSheet(self.futuristic_stylesheet())

        self.profiles = load_profiles()

        self.adapterBox = QComboBox()
        self.adapterBox.addItems(get_adapters())

        self.profileList = QListWidget()
        self.refresh_profile_list()

        self.ipEdit = QLineEdit()
        self.maskEdit = QLineEdit()
        self.gatewayEdit = QLineEdit()
        self.dnsEdit = QLineEdit()

        self.applyBtn = QPushButton("Apply Profile")
        self.saveBtn = QPushButton("Save / Update Profile")
        self.deleteBtn = QPushButton("Delete Profile")
        self.newBtn = QPushButton("New (DHCP)")

        top = QHBoxLayout()
        top.addWidget(QLabel("Adapter:"))
        top.addWidget(self.adapterBox)
        top.addStretch()

        form = QVBoxLayout()
        form.addWidget(QLabel("Profile List"))
        form.addWidget(self.profileList)
        form.addWidget(QLabel("IP Address")); form.addWidget(self.ipEdit)
        form.addWidget(QLabel("Subnet Mask")); form.addWidget(self.maskEdit)
        form.addWidget(QLabel("Gateway")); form.addWidget(self.gatewayEdit)
        form.addWidget(QLabel("DNS")); form.addWidget(self.dnsEdit)

        btns = QHBoxLayout()
        btns.addWidget(self.applyBtn)
        btns.addWidget(self.saveBtn)
        btns.addWidget(self.deleteBtn)
        btns.addWidget(self.newBtn)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(top)
        mainLayout.addLayout(form)
        mainLayout.addLayout(btns)

        container = QWidget(); container.setLayout(mainLayout)
        self.setCentralWidget(container)

        self.profileList.itemClicked.connect(self.populate_fields)
        self.applyBtn.clicked.connect(self.apply_clicked)
        self.saveBtn.clicked.connect(self.save_clicked)
        self.deleteBtn.clicked.connect(self.delete_clicked)
        self.newBtn.clicked.connect(self.create_dhcp_profile)

    # ---- Helpers ----
    def refresh_profile_list(self):
        self.profileList.clear()
        for name in self.profiles:
            self.profileList.addItem(name)

    def populate_fields(self, item: QListWidgetItem):
        name = item.text()
        profile = self.profiles[name]
        if profile == "dhcp":
            for edit in (self.ipEdit, self.maskEdit, self.gatewayEdit, self.dnsEdit):
                edit.clear()
            return
        self.ipEdit.setText(profile.get("ip", ""))
        self.maskEdit.setText(profile.get("mask", ""))
        self.gatewayEdit.setText(profile.get("gateway", ""))
        self.dnsEdit.setText(profile.get("dns", ""))

    def apply_clicked(self):
        item = self.profileList.currentItem()
        if not item:
            QMessageBox.information(self, APP_NAME, "Select a profile first.")
            return
        adapter = self.adapterBox.currentText()
        apply_profile(adapter, self.profiles[item.text()])
        QMessageBox.information(self, APP_NAME, f"Profile '{item.text()}' applied to {adapter}.")

    def save_clicked(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, APP_NAME, "Enter profile name:")
        if not ok or not name:
            return
        self.profiles[name] = {
            "ip": self.ipEdit.text(),
            "mask": self.maskEdit.text(),
            "gateway": self.gatewayEdit.text(),
            "dns": self.dnsEdit.text()
        }
        save_profiles(self.profiles)
        self.refresh_profile_list()

    def delete_clicked(self):
        item = self.profileList.currentItem()
        if not item:
            return
        name = item.text()
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, APP_NAME, f"Delete profile '{name}'?") == QMessageBox.Yes:
            del self.profiles[name]
            save_profiles(self.profiles)
            self.refresh_profile_list()

    def create_dhcp_profile(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, APP_NAME, "Enter DHCP profile name:", text="DHCP")
        if not ok or not name:
            return
        self.profiles[name] = "dhcp"
        save_profiles(self.profiles)
        self.refresh_profile_list()

    @staticmethod
    def futuristic_stylesheet() -> str:
        return """
        * { color:#C8E6FA; font-family:'Segoe UI',sans-serif; font-size:13px; }
        QMainWindow { background-color:#0d1117; }
        QLabel { color:#58A6FF; }
        QLineEdit,QListWidget,QComboBox {
            background-color:#161B22;
            border:1px solid #30363d;
            border-radius:4px;
            padding:4px;
        }
        QPushButton {
            background-color:#21262d;
            border:1px solid #30363d;
            border-radius:6px;
            padding:6px;
        }
        QPushButton:hover { background-color:#30363d; }
        QPushButton:pressed { background-color:#10567b; }
        """

def main():
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
