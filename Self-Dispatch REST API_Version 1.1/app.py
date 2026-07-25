"""
PyQt GUI for Dell TechDirect and Lenovo warranty/claim workflows.

The app is designed to be wired to the real vendor REST APIs; for now it uses
local sample payloads to let you exercise the UI without hitting the network.
"""

import base64
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

import requests  # noqa: F401 - kept for when real API calls are wired
from PyQt5 import QtCore, QtGui, QtWidgets


BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "Self-Dispatch REST API_Sample Payloads"


class AppState:
    """Holds the current vendor session and cache."""

    def __init__(self) -> None:
        self.vendor: Optional[str] = None
        self.username: Optional[str] = None
        self.client: Optional["VendorClient"] = None
        self.claims: List[Dict] = []

    def is_authenticated(self) -> bool:
        return bool(self.client and self.username)


class VendorClient:
    """Interface every vendor client should expose."""

    def login(self, username: str, password: str) -> Dict:
        raise NotImplementedError

    def list_claims(self, filter_text: str = "") -> List[Dict]:
        raise NotImplementedError

    def check_warranty(self, identifier: str) -> Dict:
        raise NotImplementedError

    def create_claim(self, payload: Dict, attachments: List[Dict]) -> Dict:
        raise NotImplementedError


class DellTechDirectClient(VendorClient):
    """
    Placeholder Dell TechDirect REST client.

    Replace the mock implementations with real HTTPS calls when you are ready
    to connect to Dell's environment. The sample payloads ship with the repo
    so you can validate the UI flow without network access.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or "https://apigtw.dell.com/techdirect"
        self.token: Optional[str] = None

    def login(self, username: str, password: str) -> Dict:
        # TODO: POST to Dell OAuth2/token endpoint and store bearer token.
        self.token = f"mock-token-for-{username}"
        return {"user": username, "token": self.token}

    def list_claims(self, filter_text: str = "") -> List[Dict]:
        sample_file = SAMPLES_DIR / "Inquiry Response Payload.json"
        if sample_file.exists():
            data = json.loads(sample_file.read_text())
        else:
            data = []
        filter_text = filter_text.lower().strip()
        if not filter_text:
            return data
        filtered = []
        for claim in data:
            blob = json.dumps(claim).lower()
            if filter_text in blob:
                filtered.append(claim)
        return filtered

    def check_warranty(self, service_tag: str) -> Dict:
        # TODO: Call Dell inquiry endpoint with the provided service tag.
        return {
            "service_tag": service_tag,
            "status": "In Warranty",
            "days_left": 180,
            "checked_at": dt.datetime.utcnow().isoformat() + "Z",
        }

    def create_claim(self, payload: Dict, attachments: List[Dict]) -> Dict:
        if len(attachments) == 0:
            raise ValueError("Dell requires at least one attachment (max 8).")
        if len(attachments) > 8:
            raise ValueError("Dell supports a maximum of 8 attachments.")

        # Encode attachments to base64 as Dell expects file bytes in payload.
        encoded_attachments = []
        for attachment in attachments:
            path = Path(attachment["path"])
            if not path.exists():
                raise FileNotFoundError(f"Attachment missing: {path}")
            content = base64.b64encode(path.read_bytes()).decode("ascii")
            encoded_attachments.append(
                {
                    "description": attachment["description"] or path.name,
                    "file_name": path.name,
                    "file_bytes": content,
                }
            )

        sample_file = SAMPLES_DIR / "Dispatch Request Payload - Parts.json"
        if sample_file.exists():
            base_payload = json.loads(sample_file.read_text())
        else:
            base_payload = {}

        final_payload = {**base_payload, **payload, "attachments": encoded_attachments}

        # TODO: POST final_payload to Dell dispatch endpoint with auth header.
        response = {
            "submitted_payload": final_payload,
            "mock_response": "SR123456789",
            "submitted_at": dt.datetime.utcnow().isoformat() + "Z",
        }
        return response


class LenovoClient(VendorClient):
    """
    Placeholder Lenovo client so the UI has parity with Dell.

    Swap the stubs for Lenovo's real endpoints; structure matches the Dell
    contract to simplify usage from the UI.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or "https://api.lenovo.com/techdirect"
        self.token: Optional[str] = None

    def login(self, username: str, password: str) -> Dict:
        # TODO: Implement Lenovo auth flow.
        self.token = f"mock-lenovo-token-{username}"
        return {"user": username, "token": self.token}

    def list_claims(self, filter_text: str = "") -> List[Dict]:
        # TODO: Call Lenovo claims endpoint.
        mock = [
            {
                "code": "LNV-001",
                "status": "Open",
                "problem_description": "Sample Lenovo claim",
                "created": dt.datetime.utcnow().isoformat() + "Z",
            }
        ]
        if not filter_text:
            return mock
        blob = filter_text.lower().strip()
        return [c for c in mock if blob in json.dumps(c).lower()]

    def check_warranty(self, serial: str) -> Dict:
        # TODO: Call Lenovo warranty endpoint.
        return {
            "serial": serial,
            "status": "In Warranty",
            "expires_on": (dt.date.today() + dt.timedelta(days=200)).isoformat(),
        }

    def create_claim(self, payload: Dict, attachments: List[Dict]) -> Dict:
        encoded = []
        for attachment in attachments:
            path = Path(attachment["path"])
            content = base64.b64encode(path.read_bytes()).decode("ascii")
            encoded.append(
                {
                    "description": attachment["description"] or path.name,
                    "file_name": path.name,
                    "file_bytes": content,
                }
            )
        final_payload = {**payload, "attachments": encoded}
        # TODO: POST to Lenovo claim endpoint.
        return {
            "submitted_payload": final_payload,
            "mock_response": "LNV-CLAIM-123",
            "submitted_at": dt.datetime.utcnow().isoformat() + "Z",
        }


def make_client(vendor: str) -> VendorClient:
    if vendor.lower() == "dell":
        return DellTechDirectClient()
    if vendor.lower() == "lenovo":
        return LenovoClient()
    raise ValueError(f"Unsupported vendor {vendor}")


class LoginPage(QtWidgets.QWidget):
    login_requested = QtCore.pyqtSignal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QGridLayout(self)
        title = QtWidgets.QLabel("Self-Dispatch Login")
        title.setFont(QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold))
        layout.addWidget(title, 0, 0, 1, 2)

        layout.addWidget(QtWidgets.QLabel("Vendor"), 1, 0)
        self.vendor_combo = QtWidgets.QComboBox()
        self.vendor_combo.addItems(["Dell", "Lenovo"])
        layout.addWidget(self.vendor_combo, 1, 1)

        layout.addWidget(QtWidgets.QLabel("Username"), 2, 0)
        self.username = QtWidgets.QLineEdit()
        layout.addWidget(self.username, 2, 1)

        layout.addWidget(QtWidgets.QLabel("Password"), 3, 0)
        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.password, 3, 1)

        login_btn = QtWidgets.QPushButton("Login")
        login_btn.clicked.connect(self._emit_login)
        layout.addWidget(login_btn, 4, 0, 1, 2)
        layout.setRowStretch(5, 1)

    def _emit_login(self) -> None:
        vendor = self.vendor_combo.currentText()
        username = self.username.text().strip()
        password = self.password.text().strip()
        if not (vendor and username and password):
            QtWidgets.QMessageBox.warning(self, "Missing info", "Please provide vendor, username, and password.")
            return
        self.login_requested.emit(vendor, username, password)


class DashboardPage(QtWidgets.QWidget):
    open_warranty_requested = QtCore.pyqtSignal()
    open_claim_requested = QtCore.pyqtSignal()
    refresh_requested = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QHBoxLayout()
        self.user_label = QtWidgets.QLabel("Not signed in")
        self.user_label.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Bold))
        header.addWidget(self.user_label)
        header.addStretch()

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter claims...")
        refresh_btn = QtWidgets.QPushButton("Refresh claims")
        refresh_btn.clicked.connect(self._emit_refresh)
        warranty_btn = QtWidgets.QPushButton("Warranty checker")
        warranty_btn.clicked.connect(self.open_warranty_requested.emit)
        claim_btn = QtWidgets.QPushButton("Make claim")
        claim_btn.clicked.connect(self.open_claim_requested.emit)

        header.addWidget(QtWidgets.QLabel("Filter"))
        header.addWidget(self.filter_edit)
        header.addWidget(refresh_btn)
        header.addWidget(warranty_btn)
        header.addWidget(claim_btn)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Code", "Status", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

    def set_user(self, vendor: str, username: str) -> None:
        self.user_label.setText(f"{vendor} | {username}")

    def render_claims(self, claims: List[Dict]) -> None:
        self.table.setRowCount(0)
        for claim in claims:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(claim.get("code", "")))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(claim.get("status", "")))
            desc = claim.get("problem_description") or claim.get("description", "")
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(desc))

    def _emit_refresh(self) -> None:
        self.refresh_requested.emit(self.filter_edit.text())


class AttachmentManager(QtWidgets.QWidget):
    """Pick files with a max count; Dell requires at least one."""

    def __init__(self, max_files: int = 8) -> None:
        super().__init__()
        self.max_files = max_files
        self.attachments: List[Dict] = []
        layout = QtWidgets.QVBoxLayout(self)
        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)

        btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add file")
        add_btn.clicked.connect(self.add_file)
        remove_btn = QtWidgets.QPushButton("Remove selected")
        remove_btn.clicked.connect(self.remove_selected)
        btns.addWidget(add_btn)
        btns.addWidget(remove_btn)
        layout.addLayout(btns)

    def add_file(self) -> None:
        if len(self.attachments) >= self.max_files:
            QtWidgets.QMessageBox.warning(self, "Limit", f"Maximum of {self.max_files} attachments.")
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select attachment")
        if not path:
            return
        desc, ok = QtWidgets.QInputDialog.getText(self, "Attachment description", "Optional description:")
        if not ok:
            desc = ""
        self.attachments.append({"path": path, "description": desc})
        self.list_widget.addItem(f"{Path(path).name} | {desc}")

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.list_widget.selectedIndexes()}, reverse=True)
        for row in rows:
            self.list_widget.takeItem(row)
            self.attachments.pop(row)


class ClaimFormPage(QtWidgets.QWidget):
    submit_requested = QtCore.pyqtSignal(dict, list)
    back_requested = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QGridLayout(self)
        title = QtWidgets.QLabel("Create Claim")
        title.setFont(QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold))
        layout.addWidget(title, 0, 0, 1, 4)

        self.service_tag = QtWidgets.QLineEdit()
        self.tech_email = QtWidgets.QLineEdit()
        self.primary_contact = QtWidgets.QLineEdit()
        self.contact_phone = QtWidgets.QLineEdit()
        self.problem_description = QtWidgets.QLineEdit()
        self.troubleshooting_notes = QtWidgets.QLineEdit()
        self.reference_po = QtWidgets.QLineEdit()
        self.request_on_site = QtWidgets.QCheckBox("Request on-site technician")
        self.request_on_site.setChecked(True)

        fields = [
            ("Service Tag / Serial", self.service_tag),
            ("Technician Email", self.tech_email),
            ("Primary Contact Name", self.primary_contact),
            ("Primary Contact Phone", self.contact_phone),
            ("Problem Description", self.problem_description),
            ("Troubleshooting Notes", self.troubleshooting_notes),
            ("Reference PO", self.reference_po),
        ]
        for idx, (label, widget) in enumerate(fields, start=1):
            layout.addWidget(QtWidgets.QLabel(label), idx, 0)
            layout.addWidget(widget, idx, 1, 1, 3)

        layout.addWidget(self.request_on_site, len(fields) + 1, 1)
        layout.addWidget(QtWidgets.QLabel("Attachments (Dell 1–8)"), len(fields) + 2, 0, 1, 4)
        self.attachments = AttachmentManager()
        layout.addWidget(self.attachments, len(fields) + 3, 0, 1, 4)

        submit_btn = QtWidgets.QPushButton("Submit")
        submit_btn.clicked.connect(self._emit_submit)
        back_btn = QtWidgets.QPushButton("Back to dashboard")
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(submit_btn, len(fields) + 4, 2)
        layout.addWidget(back_btn, len(fields) + 4, 3)
        layout.setRowStretch(len(fields) + 5, 1)

    def _emit_submit(self) -> None:
        if not self.service_tag.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing data", "Service tag / serial is required.")
            return
        payload = {
            "service_tag": self.service_tag.text().strip(),
            "tech_email": self.tech_email.text().strip(),
            "primary_contact_name": self.primary_contact.text().strip(),
            "primary_contact_phone": self.contact_phone.text().strip(),
            "problem_description": self.problem_description.text().strip(),
            "troubleshooting_notes": self.troubleshooting_notes.text().strip(),
            "reference_po_number": self.reference_po.text().strip(),
            "request_on_site_technician": self.request_on_site.isChecked(),
        }
        self.submit_requested.emit(payload, self.attachments.attachments)


class WarrantyDialog(QtWidgets.QDialog):
    def __init__(self, parent, client: VendorClient) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Warranty checker")
        self.resize(420, 250)
        layout = QtWidgets.QVBoxLayout(self)
        self.identifier = QtWidgets.QLineEdit()
        self.identifier.setPlaceholderText("Service Tag / Serial")
        layout.addWidget(self.identifier)
        check_btn = QtWidgets.QPushButton("Check")
        check_btn.clicked.connect(self.check)
        layout.addWidget(check_btn)
        self.result = QtWidgets.QPlainTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result)

    def check(self) -> None:
        ident = self.identifier.text().strip()
        if not ident:
            QtWidgets.QMessageBox.warning(self, "Missing", "Provide a service tag or serial.")
            return
        result = self.client.check_warranty(ident)
        self.result.setPlainText(json.dumps(result, indent=2))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self.setWindowTitle("Self-Dispatch Portal")
        self.resize(1000, 720)

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage()
        self.dashboard_page = DashboardPage()
        self.claim_page = ClaimFormPage()

        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.claim_page)

        self.login_page.login_requested.connect(self.handle_login)
        self.dashboard_page.open_warranty_requested.connect(self.open_warranty)
        self.dashboard_page.open_claim_requested.connect(self.open_claim_form)
        self.dashboard_page.refresh_requested.connect(self.refresh_claims)
        self.claim_page.submit_requested.connect(self.submit_claim)
        self.claim_page.back_requested.connect(self.show_dashboard)

        self.show_login()

    def show_login(self) -> None:
        self.stack.setCurrentWidget(self.login_page)

    def show_dashboard(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_page)

    def open_claim_form(self) -> None:
        self.stack.setCurrentWidget(self.claim_page)

    def open_warranty(self) -> None:
        dialog = WarrantyDialog(self, self.state.client)
        dialog.exec_()

    def handle_login(self, vendor: str, username: str, password: str) -> None:
        try:
            client = make_client(vendor)
            client.login(username, password)
            self.state.vendor = vendor
            self.state.username = username
            self.state.client = client
            self.dashboard_page.set_user(vendor, username)
            self.refresh_claims("")
            self.show_dashboard()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Login failed", str(exc))

    def refresh_claims(self, filter_text: str) -> None:
        if not self.state.client:
            return
        try:
            claims = self.state.client.list_claims(filter_text)
            self.state.claims = claims
            self.dashboard_page.render_claims(claims)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Refresh failed", str(exc))

    def submit_claim(self, payload: Dict, attachments: List[Dict]) -> None:
        try:
            response = self.state.client.create_claim(payload, attachments)
            QtWidgets.QMessageBox.information(self, "Claim submitted", json.dumps(response, indent=2))
            self.show_dashboard()
            self.refresh_claims("")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Submit failed", str(exc))


def main() -> None:
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
