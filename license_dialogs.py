from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QIcon, QFont, QColor
import datetime

class LicenseKeyDialog(QDialog):
    """Dialog nhập license key cho user"""
    
    def __init__(self, db, user_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Enter License Key")
        self.setMinimumWidth(400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header section
        header = QLabel("License Activation")
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px;
        """)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Info message
        info = QLabel(
            "Please enter your license key to activate the application.\n"
            "Contact administrator if you don't have a key."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #7f8c8d;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        # Key input
        form_group = QGroupBox()
        form_layout = QFormLayout(form_group)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setMinimumHeight(35)
        self.key_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        form_layout.addRow("License Key:", self.key_input)
        layout.addWidget(form_group)
        
        # Error message
        self.error_label = QLabel()
        self.error_label.setStyleSheet("""
            color: #e74c3c;
            padding: 10px;
            background: #fadbd8;
            border-radius: 5px;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        activate_btn = QPushButton("Activate")
        activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        activate_btn.clicked.connect(self.activate_license)
        
        cancel_btn = QPushButton("Cancel") 
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(activate_btn)
        
        layout.addLayout(btn_layout)
        
    def activate_license(self):
        key = self.key_input.text().strip()
        if not key:
            self.show_error("Please enter a license key")
            return
            
        try:
            success, msg = self.db.verify_license(key, self.user_id)
            if success:
                self.accept()
            else:
                self.show_error(msg)
        except Exception as e:
            self.show_error(str(e))
            
    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()
        QTimer.singleShot(5000, self.error_label.hide)

class LicenseManagerDialog(QDialog):
    """Dialog quản lý license cho admin"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
        self.load_licenses()
        
    def setup_ui(self):
        self.setWindowTitle("License Management")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("New License")
        add_btn.setIcon(QIcon.fromTheme("document-new"))
        add_btn.clicked.connect(self.add_license)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.clicked.connect(self.load_licenses)
        
        export_btn = QPushButton("Export")
        export_btn.setIcon(QIcon.fromTheme("document-export"))
        export_btn.clicked.connect(self.export_licenses)
        
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        toolbar.addWidget(export_btn)
        
        layout.addLayout(toolbar)
        
        # License table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Key", "User", "Type", "Created", "Activated",
            "Expires", "Status", "Actions"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set column widths
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 8):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
            
        layout.addWidget(self.table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        
    def load_licenses(self):
        """Load licenses from database"""
        try:
            licenses = self.db.get_all_licenses()
            self.table.setRowCount(len(licenses))
            
            for i, lic in enumerate(licenses):
                self.table.setItem(i, 0, QTableWidgetItem(lic['key_string']))
                self.table.setItem(i, 1, QTableWidgetItem(lic['username']))
                self.table.setItem(i, 2, QTableWidgetItem(lic['type']))
                self.table.setItem(i, 3, QTableWidgetItem(lic['created_at']))
                self.table.setItem(i, 4, QTableWidgetItem(lic['activated_at'] or ''))
                self.table.setItem(i, 5, QTableWidgetItem(lic['expires_at']))
                
                # Status with color
                status_item = QTableWidgetItem(lic['status'])
                if lic['status'] == 'active':
                    status_item.setBackground(QColor('#2ecc71'))
                elif lic['status'] == 'expired':
                    status_item.setBackground(QColor('#e74c3c'))
                self.table.setItem(i, 6, status_item)
                
                # Action buttons
                actions = QWidget()
                action_layout = QHBoxLayout(actions)
                
                revoke_btn = QPushButton("Revoke")
                revoke_btn.clicked.connect(lambda: self.revoke_license(lic['id']))
                
                extend_btn = QPushButton("Extend")
                extend_btn.clicked.connect(lambda: self.extend_license(lic['id']))
                
                action_layout.addWidget(revoke_btn)
                action_layout.addWidget(extend_btn)
                
                self.table.setCellWidget(i, 7, actions)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load licenses: {str(e)}")
            
    def add_license(self):
        """Show dialog to add new license"""
        dialog = NewLicenseDialog(self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_licenses()
            
    def revoke_license(self, license_id):
        """Revoke a license"""
        reply = QMessageBox.question(
            self,
            "Confirm Revoke",
            "Are you sure you want to revoke this license?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                reason = QInputDialog.getText(
                    self, "Revoke License",
                    "Enter reason for revocation:"
                )[0]
                
                success = self.db.revoke_license(license_id, reason)
                if success:
                    self.load_licenses()
                    QMessageBox.information(self, "Success", "License revoked successfully")
                else:
                    QMessageBox.warning(self, "Error", "Failed to revoke license")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                
    def extend_license(self, license_id):
        """Extend a license"""
        try:
            dialog = ExtendLicenseDialog(self.db, license_id, self)
            if dialog.exec_() == QDialog.Accepted:
                self.load_licenses()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def export_licenses(self):
        """Export licenses to Excel"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Licenses",
                "",
                "Excel Files (*.xlsx)"
            )
            
            if filename:
                self.db.export_licenses_to_excel(filename)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Licenses exported to {filename}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

class NewLicenseDialog(QDialog):
    """Dialog to create new license"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Create New License")
        layout = QFormLayout(self)
        
        # User selection
        self.user_combo = QComboBox()
        self.load_users()
        layout.addRow("User:", self.user_combo)
        
        # License type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            'trial (7 days)',
            'monthly (30 days)',
            'quarterly (90 days)', 
            'biannual (180 days)',
            'yearly (365 days)'
        ])
        layout.addRow("Type:", self.type_combo)
        
        # Note
        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(100)
        layout.addRow("Note:", self.note_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self.create_license)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(create_btn)
        layout.addRow("", btn_layout)
        
    def load_users(self):
        """Load users without active license"""
        try:
            users = self.db.get_users_without_license()
            for user in users:
                self.user_combo.addItem(
                    user['username'],
                    userData=user['id']
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def create_license(self):
        """Create new license"""
        try:
            user_id = self.user_combo.currentData()
            key_type = self.type_combo.currentText().split()[0]
            note = self.note_edit.toPlainText()
            
            key = self.db.create_license(user_id, key_type, note)
            if key:
                QMessageBox.information(
                    self,
                    "Success",
                    f"License created successfully.\nKey: {key}"
                )
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to create license")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class ExtendLicenseDialog(QDialog):
    """Dialog to extend license duration"""
    
    def __init__(self, db, license_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.license_id = license_id
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Extend License")
        layout = QFormLayout(self)
        
        # Duration selection  
        self.duration_combo = QComboBox()
        self.duration_combo.addItems([
            '1 month',
            '3 months',
            '6 months',
            '1 year'
        ])
        layout.addRow("Extend by:", self.duration_combo)
        
        # Reason
        self.reason_edit = QLineEdit()
        layout.addRow("Reason:", self.reason_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        extend_btn = QPushButton("Extend")
        extend_btn.clicked.connect(self.extend_license)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(extend_btn)
        layout.addRow("", btn_layout)
        
    def extend_license(self):
        """Extend the license"""
        try:
            duration = int(self.duration_combo.currentText().split()[0])
            reason = self.reason_edit.text()
            
            success = self.db.extend_license(
                self.license_id,
                duration,
                reason
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    "License extended successfully"
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to extend license"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class LicenseReportDialog(QDialog):
    """Dialog hiển thị báo cáo license"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        self.setWindowTitle("License Reports")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout(self)
        
        # Tab widget cho các loại báo cáo
        self.tab_widget = QTabWidget()
        
        # Tab thống kê tổng quan
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        
        # Các metrics chính
        metrics_group = QGroupBox("Key Metrics")
        metrics_layout = QGridLayout(metrics_group)
        
        self.total_licenses = QLabel("0")
        self.active_licenses = QLabel("0")
        self.expired_licenses = QLabel("0")
        self.revenue = QLabel("$0")
        
        metrics_layout.addWidget(QLabel("Total Licenses:"), 0, 0)
        metrics_layout.addWidget(self.total_licenses, 0, 1)
        metrics_layout.addWidget(QLabel("Active Licenses:"), 0, 2)
        metrics_layout.addWidget(self.active_licenses, 0, 3)
        metrics_layout.addWidget(QLabel("Expired Licenses:"), 1, 0)
        metrics_layout.addWidget(self.expired_licenses, 1, 1)
        metrics_layout.addWidget(QLabel("Total Revenue:"), 1, 2)
        metrics_layout.addWidget(self.revenue, 1, 3)
        
        overview_layout.addWidget(metrics_group)
        
        # License type distribution
        type_group = QGroupBox("License Types")
        type_layout = QVBoxLayout(type_group)
        self.type_table = QTableWidget()
        self.type_table.setColumnCount(3)
        self.type_table.setHorizontalHeaderLabels([
            "Type", "Count", "Revenue"
        ])
        type_layout.addWidget(self.type_table)
        overview_layout.addWidget(type_group)
        
        self.tab_widget.addTab(overview_tab, "Overview")
        
        # Tab lịch sử giao dịch
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDateTime.currentDateTime().addMonths(-1).date())
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDateTime.currentDateTime().date())
        
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_to)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(['All Types', 'Trial', 'Monthly', 'Quarterly', 'Biannual', 'Yearly'])
        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.type_filter)
        
        filter_btn = QPushButton("Apply Filter")
        filter_btn.clicked.connect(self.apply_filter)
        filter_layout.addWidget(filter_btn)
        
        history_layout.addLayout(filter_layout)
        
        # Transaction table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Action", "Key", "User", "Details", "Admin"
        ])
        history_layout.addWidget(self.history_table)
        
        self.tab_widget.addTab(history_tab, "Transaction History")
        
        # Tab dự báo hết hạn
        expiry_tab = QWidget()
        expiry_layout = QVBoxLayout(expiry_tab)
        
        # Bảng license sắp hết hạn
        self.expiry_table = QTableWidget()
        self.expiry_table.setColumnCount(5)
        self.expiry_table.setHorizontalHeaderLabels([
            "User", "Key", "Type", "Expires", "Days Left"
        ])
        expiry_layout.addWidget(self.expiry_table)
        
        self.tab_widget.addTab(expiry_tab, "Expiry Forecast")
        
        layout.addWidget(self.tab_widget)
        
        # Export buttons
        btn_layout = QHBoxLayout()
        
        export_excel_btn = QPushButton("Export to Excel")
        export_excel_btn.clicked.connect(self.export_excel)
        
        export_pdf_btn = QPushButton("Export to PDF") 
        export_pdf_btn.clicked.connect(self.export_pdf)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(export_excel_btn)
        btn_layout.addWidget(export_pdf_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
    def load_data(self):
        """Load report data"""
        try:
            # Load overview metrics
            metrics = self.db.get_license_metrics()
            self.total_licenses.setText(str(metrics['total']))
            self.active_licenses.setText(str(metrics['active'])) 
            self.expired_licenses.setText(str(metrics['expired']))
            self.revenue.setText(f"${metrics['revenue']:,.2f}")
            
            # Load type distribution
            types = self.db.get_license_types()
            self.type_table.setRowCount(len(types))
            for i, t in enumerate(types):
                self.type_table.setItem(i, 0, QTableWidgetItem(t['type']))
                self.type_table.setItem(i, 1, QTableWidgetItem(str(t['count'])))
                self.type_table.setItem(i, 2, QTableWidgetItem(f"${t['revenue']:,.2f}"))
                
            # Load transaction history
            self.load_history()
            
            # Load expiry forecast
            expiry = self.db.get_expiry_forecast()
            self.expiry_table.setRowCount(len(expiry))
            for i, e in enumerate(expiry):
                self.expiry_table.setItem(i, 0, QTableWidgetItem(e['username']))
                self.expiry_table.setItem(i, 1, QTableWidgetItem(e['key']))
                self.expiry_table.setItem(i, 2, QTableWidgetItem(e['type']))
                self.expiry_table.setItem(i, 3, QTableWidgetItem(e['expires']))
                
                days = QTableWidgetItem(str(e['days_left']))
                if e['days_left'] <= 7:
                    days.setBackground(QColor('#e74c3c'))
                elif e['days_left'] <= 30:
                    days.setBackground(QColor('#f1c40f'))
                self.expiry_table.setItem(i, 4, days)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load report data: {str(e)}")
            
    def load_history(self):
        """Load transaction history with filters"""
        try:
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()
            key_type = self.type_filter.currentText()
            if key_type == 'All Types':
                key_type = None
                
            history = self.db.get_license_history(date_from, date_to, key_type)
            self.history_table.setRowCount(len(history))
            
            for i, h in enumerate(history):
                self.history_table.setItem(i, 0, QTableWidgetItem(h['date']))
                self.history_table.setItem(i, 1, QTableWidgetItem(h['action']))
                self.history_table.setItem(i, 2, QTableWidgetItem(h['key']))
                self.history_table.setItem(i, 3, QTableWidgetItem(h['username']))
                self.history_table.setItem(i, 4, QTableWidgetItem(h['details']))
                self.history_table.setItem(i, 5, QTableWidgetItem(h['admin']))
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load history: {str(e)}")
            
    def apply_filter(self):
        """Apply history filters"""
        self.load_history()
        
    def export_excel(self):
        """Export report to Excel"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Report",
                "",
                "Excel Files (*.xlsx)"
            )
            
            if filename:
                self.db.export_license_report(filename, 'excel')
                QMessageBox.information(
                    self,
                    "Success",
                    f"Report exported to {filename}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
            
    def export_pdf(self):
        """Export report to PDF"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Report",
                "",
                "PDF Files (*.pdf)"
            )
            
            if filename:
                self.db.export_license_report(filename, 'pdf')
                QMessageBox.information(
                    self,
                    "Success", 
                    f"Report exported to {filename}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
