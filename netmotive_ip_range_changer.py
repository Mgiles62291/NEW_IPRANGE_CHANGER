import sys, subprocess, json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui  import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

APP_NAME = "Netmotive IP Range Changer"
PROFILE_FILE = Path("profiles.json")
LOGO_FILE   = Path(__file__).with_name("logo.png")

def run_netsh(cmd):
    try:
        return subprocess.run(cmd, shell=True, check=True,
                              capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as err:
        QMessageBox.critical(None, "Netsh Error",
                             f"Command: {' '.join(cmd)}\n\n{err.stderr}")
        return None

def get_adapters():
    out = subprocess.check_output("netsh interface show interface", shell=True, text=True)
    return [" ".join(l.split()[3:]) for l in out.splitlines()
            if any(t in l for t in ("Dedicated", "Ethernet", "Wi-Fi"))] or ["Ethernet"]

def load_profiles():
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text())
        except ValueError:
            QMessageBox.warning(None, APP_NAME, "profiles.json corrupt – starting fresh.")
    return {}

def save_profiles(p): PROFILE_FILE.write_text(json.dumps(p, indent=2))

q = lambda s: f'"{s}"'
static_cmd = lambda a,p: ["netsh","interface","ip","set","address",q(a),"static",p["ip"],p["mask"],p["gateway"],"1"]
dns_cmd    = lambda a,d,dhcp=False: ["netsh","interface","ip","set","dns",q(a),"dhcp" if dhcp else "static",*( [] if dhcp else [d] )]
dhcp_cmd   = lambda a: ["netsh","interface","ip","set","address",q(a),"dhcp"]

def apply_profile(adapter, prof):
    if prof == "dhcp":
        run_netsh(dhcp_cmd(adapter)); run_netsh(dns_cmd(adapter,"",True)); return
    if not all(prof.get(k) for k in ("ip","mask","gateway","dns")):
        QMessageBox.warning(None, APP_NAME, "Static profile requires IP / Mask / Gateway / DNS."); return
    run_netsh(static_cmd(adapter, prof)); run_netsh(dns_cmd(adapter, prof["dns"]))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if LOGO_FILE.exists(): self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.setMinimumSize(720,620)
        self.setStyleSheet(self._style())
        self.profiles = load_profiles()
        self.adapterBox  = QComboBox(); self.adapterBox.addItems(get_adapters())
        self.profileList = QListWidget(); self._refresh()
        self.profileName = QLineEdit(placeholderText="Profile Name")
        self.ip   = QLineEdit(placeholderText="IP")
        self.mask = QLineEdit(placeholderText="Mask")
        self.gw   = QLineEdit(placeholderText="Gateway")
        self.dns  = QLineEdit(placeholderText="DNS")
        self.apply=QPushButton("Apply"); self.add=QPushButton("Add"); self.update=QPushButton("Update"); self.delete=QPushButton("Delete"); self.addDHCP=QPushButton("Add DHCP")
        root=QVBoxLayout()
        if LOGO_FILE.exists():
            lbl=QLabel(alignment=Qt.AlignCenter); lbl.setPixmap(QPixmap(str(LOGO_FILE)).scaledToHeight(64,Qt.SmoothTransformation)); root.addWidget(lbl)
        top=QHBoxLayout(); top.addWidget(QLabel("Adapter:")); top.addWidget(self.adapterBox); top.addStretch(); root.addLayout(top)
        root.addWidget(QLabel("Saved Profiles")); root.addWidget(self.profileList,1)
        for w in (self.profileName,self.ip,self.mask,self.gw,self.dns): root.addWidget(w)
        btn=QHBoxLayout(); [btn.addWidget(b) for b in (self.apply,self.add,self.update,self.delete,self.addDHCP)]; root.addLayout(btn)
        cont=QWidget(); cont.setLayout(root); self.setCentralWidget(cont)
        self.profileList.itemClicked.connect(self._load); self.apply.clicked.connect(self._apply); self.add.clicked.connect(self._add); self.update.clicked.connect(self._update); self.delete.clicked.connect(self._delete); self.addDHCP.clicked.connect(self._add_dhcp)
    def _refresh(self): self.profileList.clear(); self.profileList.addItems(self.profiles.keys())
    def _save_ref(self): save_profiles(self.profiles); self._refresh()
    def _load(self,i): n=i.text(); self.profileName.setText(n); p=self.profiles[n]; 
        [e.clear() for e in (self.ip,self.mask,self.gw,self.dns)] if p=="dhcp" else (self.ip.setText(p["ip"]),self.mask.setText(p["mask"]),self.gw.setText(p["gateway"]),self.dns.setText(p["dns"]))
    def _collect(self): return {"ip":self.ip.text().strip(),"mask":self.mask.text().strip(),"gateway":self.gw.text().strip(),"dns":self.dns.text().strip()}
    def _add(self): n=self.profileName.text().strip(); 
        QMessageBox.warning(self,APP_NAME,"Name required") if not n else QMessageBox.warning(self,APP_NAME,"Profile exists") if n in self.profiles else (self.profiles.__setitem__(n,self._collect()), self._save_ref())
    def _update(self): n=self.profileName.text().strip(); 
        QMessageBox.warning(self,APP_NAME,"Select existing") if n not in self.profiles else (self.profiles.__setitem__(n,self._collect()), self._save_ref())
    def _delete(self): it=self.profileList.currentItem(); 
        (None if not it else (n:=it.text(), (del self.profiles[n], self._save_ref()) if QMessageBox.question(self,APP_NAME,f"Delete '{n}'?")==QMessageBox.Yes else None))
    def _add_dhcp(self): n=self.profileName.text().strip() or "DHCP"; 
        QMessageBox.warning(self,APP_NAME,"Name exists") if n in self.profiles else (self.profiles.__setitem__(n,"dhcp"), self._save_ref())
    def _apply(self): it=self.profileList.currentItem(); 
        QMessageBox.information(self,APP_NAME,"Select profile") if not it else (apply_profile(self.adapterBox.currentText(), self.profiles[it.text()]), QMessageBox.information(self,APP_NAME,f"Applied '{it.text()}'"))
    @staticmethod
    def _style(): return("*{color:#C8E6FA;font-family:'Segoe UI';font-size:13px}""QMainWindow{background:#0d1117}""QLabel{color:#58A6FF}""QLineEdit,QListWidget,QComboBox{background:#161B22;border:1px solid #30363d;border-radius:4px;padding:4px}""QPushButton{background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px}""QPushButton:hover{background:#30363d}""QPushButton:pressed{background:#10567b}")
def main():
    app=QApplication(sys.argv); MainWindow().show(); sys.exit(app.exec())
if __name__=="__main__": main()
