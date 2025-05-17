from PyQt5.QtWidgets import (QApplication, QWidget, QDialog, QLabel, QLineEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout,
                           QMessageBox, QCheckBox, QMainWindow, QFrame, QRadioButton,
                           QComboBox, QGroupBox, QSplashScreen, QSpacerItem,
                           QSizePolicy, QProgressBar)
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPalette, QMovie
from license_dialogs import LicenseKeyDialog
import os
import sys
import time
from pathlib import Path
import logging

# Import UserAuthManager từ auth_system.py
from auth_system import UserAuthManager

# Các đường dẫn cơ bản
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / 'config'
ASSETS_DIR = BASE_DIR / 'assets'
LOGS_DIR = BASE_DIR / 'logs'

# Đảm bảo thư mục tồn tại
for dir_path in [CONFIG_DIR, ASSETS_DIR, LOGS_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'login.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LoginSystem")

class LoginDialog(QDialog):
    """Hộp thoại đăng nhập"""
    
    login_successful = pyqtSignal(dict)  # Signal phát ra khi đăng nhập thành công với dữ liệu người dùng
    
    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Đăng nhập - Hệ thống OCR Văn Bản")
        self.setMinimumWidth(450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Logo và tiêu đề
        logo_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_path = str(ASSETS_DIR / "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        else:
            # Placeholder nếu không có logo
            logo_label.setText("LOGO")
            logo_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db;")
            logo_label.setAlignment(Qt.AlignCenter)
            logo_label.setFixedSize(80, 80)
            
        # Tiêu đề chính
        title_label = QLabel("HỆ THỐNG OCR VĂN BẢN")
        title_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
        """)
        subtitle_label = QLabel("Quản lý và trích xuất thông tin từ văn bản hành chính")
        subtitle_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        
        title_layout = QVBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.setSpacing(5)
        
        logo_layout.addWidget(logo_label)
        logo_layout.addLayout(title_layout)
        logo_layout.setStretch(1, 1)
        main_layout.addLayout(logo_layout)
        
        # Đường phân cách
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
        
        # Form đăng nhập
        login_form = QGroupBox("Đăng nhập tài khoản")
        login_form.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        form_layout = QFormLayout(login_form)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 25, 15, 15)
        
        # Tên đăng nhập
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập tên đăng nhập...")
        self.username_input.setMinimumHeight(35)
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        username_label = QLabel("Tài khoản:")
        username_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(username_label, self.username_input)
        
        # Mật khẩu
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Nhập mật khẩu...")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(35)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        password_label = QLabel("Mật khẩu:")
        password_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(password_label, self.password_input)
        
        # Remember me
        remember_layout = QHBoxLayout()
        self.remember_checkbox = QCheckBox("Ghi nhớ đăng nhập")
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        # Quên mật khẩu
        self.forgot_password_btn = QPushButton("Quên mật khẩu?")
        self.forgot_password_btn.setFlat(True)
        self.forgot_password_btn.setCursor(Qt.PointingHandCursor)
        self.forgot_password_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #3498db;
                text-decoration: underline;
                background: transparent;
            }
            QPushButton:hover {
                color: #2980b9;
            }
        """)
        self.forgot_password_btn.clicked.connect(self.forgot_password)
        
        remember_layout.addWidget(self.remember_checkbox)
        remember_layout.addStretch()
        remember_layout.addWidget(self.forgot_password_btn)
        
        form_layout.addRow("", remember_layout)
        
        main_layout.addWidget(login_form)
        
        # Hiển thị thông báo lỗi
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("""
            color: #e74c3c;
            padding: 5px;
            background-color: #fadbd8;
            border-radius: 4px;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)
        
        # Nút đăng nhập
        self.login_btn = QPushButton("ĐĂNG NHẬP")
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
            }
        """)
        self.login_btn.clicked.connect(self.login)
        
        main_layout.addWidget(self.login_btn)
        
        # Đăng ký tài khoản
        register_layout = QHBoxLayout()
        register_label = QLabel("Chưa có tài khoản?")
        
        self.register_btn = QPushButton("Đăng ký")
        self.register_btn.setFlat(True)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #3498db;
                text-decoration: underline;
                background: transparent;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #2980b9;
            }
        """)
        self.register_btn.clicked.connect(self.show_register)
        
        register_layout.addStretch()
        register_layout.addWidget(register_label)
        register_layout.addWidget(self.register_btn)
        register_layout.addStretch()
        
        main_layout.addLayout(register_layout)
        
        # Focus vào tên đăng nhập
        self.username_input.setFocus()
        
        # Enter để đăng nhập
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.login)
        
        # Kết nối Enter key cho nút đăng nhập
        self.login_btn.setDefault(True)
    
    def login(self):
        """Xử lý đăng nhập"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_error("Vui lòng nhập đầy đủ thông tin đăng nhập")
            return
        
        # Xác thực đăng nhập
        success, message, user_data = self.auth_manager.authenticate(username, password)
        
        if success:
            # Lưu user data và cho đăng nhập trực tiếp (không cần kiểm tra license key nữa)
            self.user_data = user_data
            
            if self.remember_checkbox.isChecked():
                settings = QSettings("OCRApp", "DocumentManagement")
                settings.setValue("username", username)
                settings.setValue("remember_login", True)
            else:
                settings = QSettings("OCRApp", "DocumentManagement")
                settings.remove("username")
                settings.setValue("remember_login", False)
                
            # Đăng nhập thành công - emit tín hiệu và chấp nhận dialog
            self.login_successful.emit(user_data)
            self.accept()
        else:
            self.show_error(message)

    def show_error(self, message):
        """Hiển thị thông báo lỗi"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

        # Tự động ẩn sau 5 giây
        QTimer.singleShot(5000, lambda: self.error_label.setVisible(False))

    def show_register(self):
        """Mở dialog đăng ký"""
        register_dialog = RegisterDialog(self.auth_manager, self)
        if register_dialog.exec_() == QDialog.Accepted:
            # Điền username từ đăng ký thành công
            self.username_input.setText(register_dialog.username)
            self.password_input.setFocus()

    def forgot_password(self):
        """Xử lý quên mật khẩu - hiển thị thông tin liên hệ và mã QR Zalo"""
        # Tạo dialog thông tin liên hệ
        contact_dialog = QDialog(self)
        contact_dialog.setWindowTitle("Khôi phục mật khẩu")
        contact_dialog.setMinimumWidth(400)
        contact_dialog.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(contact_dialog)
        layout.setSpacing(15)

        # Tiêu đề
        title_label = QLabel("KHÔI PHỤC MẬT KHẨU")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Thông báo
        message_label = QLabel(
            "Để khôi phục mật khẩu, vui lòng liên hệ với quản trị viên "
            "theo thông tin dưới đây:"
        )
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size: 12px; margin-bottom: 10px;")
        message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(message_label)

        # Thông tin liên hệ
        contact_info = QFrame()
        contact_info.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
        """)
        contact_layout = QVBoxLayout(contact_info)

        # Email
        email_label = QLabel("📧 Email: nguyenngoduydmx@gmail.com")
        email_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(email_label)

        # Số điện thoại
        phone_label = QLabel("📱 Điện thoại: (+84) 876761806")
        phone_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(phone_label)

        # Zalo
        zalo_label = QLabel("💬 Zalo: Quét mã QR bên dưới")
        zalo_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(zalo_label)

        layout.addWidget(contact_info)

        # Mã QR Zalo
        qr_frame = QFrame()
        qr_layout = QVBoxLayout(qr_frame)

        qr_image = QLabel()
        qr_path = str(ASSETS_DIR / "zalo_qr.jpg")
        if os.path.exists(qr_path):
            qr_pixmap = QPixmap(qr_path).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr_image.setPixmap(qr_pixmap)
        else:
            # Tạo placeholder nếu không có ảnh QR
            qr_image.setText("Mã QR Zalo")
            qr_image.setStyleSheet("""
                font-size: 16px;
                color: #777;
                border: 2px dashed #ccc;
            """)
        qr_layout.addWidget(qr_image)
        
        qr_frame.setFixedHeight(250)
        layout.addWidget(qr_frame)
        
        self.setLayout(layout)
        
    def show_register(self):
        """Mở dialog đăng ký"""
        register_dialog = RegisterDialog(self.auth_manager, self)
        if register_dialog.exec_() == QDialog.Accepted:
            # Điền username từ đăng ký thành công
            self.username_input.setText(register_dialog.username)
            self.password_input.setFocus()
    
    def forgot_password(self):
        """Xử lý quên mật khẩu - hiển thị thông tin liên hệ và mã QR Zalo"""
        # Tạo dialog thông tin liên hệ
        contact_dialog = QDialog(self)
        contact_dialog.setWindowTitle("Khôi phục mật khẩu")
        contact_dialog.setMinimumWidth(400)
        contact_dialog.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(contact_dialog)
        layout.setSpacing(15)
        
        # Tiêu đề
        title_label = QLabel("KHÔI PHỤC MẬT KHẨU")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Thông báo
        message_label = QLabel(
            "Để khôi phục mật khẩu, vui lòng liên hệ với quản trị viên "
            "theo thông tin dưới đây:"
        )
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size: 12px; margin-bottom: 10px;")
        message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(message_label)
        
        # Thông tin liên hệ
        contact_info = QFrame()
        contact_info.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
        """)
        contact_layout = QVBoxLayout(contact_info)
        
        # Email
        email_label = QLabel("📧 Email: nguyenngoduydmx@gmail.com")
        email_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(email_label)
        
        # Số điện thoại
        phone_label = QLabel("📱 Điện thoại: (+84) 876761806")
        phone_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(phone_label)
        
        # Zalo
        zalo_label = QLabel("💬 Zalo: Quét mã QR bên dưới")
        zalo_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        contact_layout.addWidget(zalo_label)
        
        layout.addWidget(contact_info)
        
        # Mã QR Zalo
        qr_frame = QFrame()
        qr_layout = QVBoxLayout(qr_frame)
        
        qr_image = QLabel()
        qr_path = str(ASSETS_DIR / "zalo_qr.jpg")
        if os.path.exists(qr_path):
            qr_pixmap = QPixmap(qr_path).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr_image.setPixmap(qr_pixmap)
        else:
            # Tạo placeholder nếu không có ảnh QR
            qr_image.setText("Mã QR Zalo")
            qr_image.setStyleSheet("""
                font-size: 16px;
                color: #777;
                border: 2px dashed #ccc;
                border-radius: 10px;
                padding: 80px;
                text-align: center;
            """)
        
        qr_image.setAlignment(Qt.AlignCenter)
        qr_layout.addWidget(qr_image)
        
        # Thêm hướng dẫn
        qr_instruction = QLabel("Liên hệ qua Zalo để được hỗ trợ nhanh nhất")
        qr_instruction.setStyleSheet("font-style: italic; color: #666; margin-top: 5px;")
        qr_instruction.setAlignment(Qt.AlignCenter)
        qr_layout.addWidget(qr_instruction)
        
        layout.addWidget(qr_frame)
        
        # Nút đóng
        close_btn = QPushButton("Đóng")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        close_btn.clicked.connect(contact_dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Hiển thị dialog
        contact_dialog.exec_()

class RegisterDialog(QDialog):
    """Dialog đăng ký tài khoản mới"""
    
    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.username = ""  # Lưu username để trả về khi đăng ký thành công
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Đăng ký tài khoản mới")
        self.setMinimumWidth(450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Tiêu đề
        title_label = QLabel("ĐĂNG KÝ TÀI KHOẢN MỚI")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        description = QLabel("Vui lòng điền đầy đủ thông tin để tạo tài khoản mới")
        description.setStyleSheet("color: #7f8c8d;")
        description.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(description)
        
        # Form đăng ký
        form_group = QGroupBox()
        form_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
            }
        """)
        
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 15, 15, 15)
        
        # Tên đăng nhập
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập tên đăng nhập...")
        self.username_input.setMinimumHeight(35)
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        username_label = QLabel("Tài khoản:")
        username_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(username_label, self.username_input)
        
        # Họ tên
        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Nhập họ tên đầy đủ...")
        self.fullname_input.setMinimumHeight(35)
        self.fullname_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        fullname_label = QLabel("Họ tên:")
        fullname_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(fullname_label, self.fullname_input)
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Nhập địa chỉ email...")
        self.email_input.setMinimumHeight(35)
        self.email_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        email_label = QLabel("Email:")
        email_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(email_label, self.email_input)
        
        # Mật khẩu
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Nhập mật khẩu...")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(35)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        password_label = QLabel("Mật khẩu:")
        password_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(password_label, self.password_input)
        
        # Xác nhận mật khẩu
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Nhập lại mật khẩu...")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setMinimumHeight(35)
        self.confirm_password_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        confirm_label = QLabel("Xác nhận mật khẩu:")
        confirm_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(confirm_label, self.confirm_password_input)
        
        # Mã đăng ký - Nếu bạn muốn giới hạn người đăng ký
        self.register_code_input = QLineEdit()
        self.register_code_input.setPlaceholderText("Để trống nếu không có")
        self.register_code_input.setMinimumHeight(35)
        self.register_code_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        code_label = QLabel("Mã đăng ký (nếu có):")
        code_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(code_label, self.register_code_input)
        
        main_layout.addWidget(form_group)
        
        # Hiển thị thông báo lỗi
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("""
            color: #e74c3c;
            padding: 5px;
            background-color: #fadbd8;
            border-radius: 4px;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)
        
        # Điều khoản sử dụng
        terms_layout = QHBoxLayout()
        self.terms_checkbox = QCheckBox("Tôi đồng ý với")
        self.terms_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        self.terms_btn = QPushButton("điều khoản sử dụng")
        self.terms_btn.setFlat(True)
        self.terms_btn.setCursor(Qt.PointingHandCursor)
        self.terms_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #3498db;
                text-decoration: underline;
                background: transparent;
            }
            QPushButton:hover {
                color: #2980b9;
            }
        """)
        self.terms_btn.clicked.connect(self.show_terms)
        
        terms_layout.addWidget(self.terms_checkbox)
        terms_layout.addWidget(self.terms_btn)
        terms_layout.addStretch()
        
        main_layout.addLayout(terms_layout)
        
        # Nút đăng ký và hủy
        buttons_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("HỦY BỎ")
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                color: #2c3e50;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #dde4e6;
            }
            QPushButton:pressed {
                background-color: #ccd6db;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.register_btn = QPushButton("ĐĂNG KÝ")
        self.register_btn.setMinimumHeight(45)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #219653;
            }
        """)
        self.register_btn.clicked.connect(self.register)
        
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.register_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # Focus vào tên đăng nhập
        self.username_input.setFocus()
    
    def show_error(self, message):
        """Hiển thị thông báo lỗi"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        
        # Tự động ẩn sau 5 giây
        QTimer.singleShot(5000, lambda: self.error_label.setVisible(False))
    
    def show_terms(self):
        """Hiển thị điều khoản sử dụng"""
        terms_text = """
        <h3>Điều khoản sử dụng hệ thống OCR Văn Bản</h3>
        <p><b>1. Quy định chung:</b> Người dùng cần tuân thủ các quy định sử dụng phần mềm.</p>
        <p><b>2. Bảo mật:</b> Người dùng chịu trách nhiệm bảo vệ thông tin tài khoản.</p>
        <p><b>3. Sử dụng hợp pháp:</b> Chỉ sử dụng phần mềm cho mục đích hợp pháp.</p>
        <p><b>4. Hạn chế trách nhiệm:</b> Nhà phát triển không chịu trách nhiệm với các thiệt hại gián tiếp.</p>
        <p><b>5. Dữ liệu:</b> Người dùng chịu trách nhiệm về nội dung dữ liệu tải lên.</p>
        """
        
        QMessageBox.about(self, "Điều khoản sử dụng", terms_text)
        
    def register(self):
        """Xử lý đăng ký"""
        # Lấy thông tin từ form
        username = self.username_input.text().strip()
        fullname = self.fullname_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        register_code = self.register_code_input.text().strip()
        
        # Kiểm tra điều khoản
        if not self.terms_checkbox.isChecked():
            self.show_error("Bạn phải đồng ý với điều khoản sử dụng")
            return
        
        # Kiểm tra thông tin
        if not username:
            self.show_error("Tên đăng nhập không được để trống")
            return
            
        if len(username) < 4:
            self.show_error("Tên đăng nhập phải có ít nhất 4 ký tự")
            return
            
        if not password:
            self.show_error("Mật khẩu không được để trống")
            return
            
        if len(password) < 6:
            self.show_error("Mật khẩu phải có ít nhất 6 ký tự")
            return
            
        if password != confirm_password:
            self.show_error("Mật khẩu và xác nhận mật khẩu không khớp")
            return
        
        # Kiểm tra mã đăng ký nếu cần
        if register_code and register_code != "OCR2025":  # Mã đăng ký mẫu
            self.show_error("Mã đăng ký không hợp lệ")
            return
            
        # Thực hiện đăng ký
        success, message = self.auth_manager.register_user(
            username, password, full_name=fullname, email=email
        )
        
        if success:
            self.username = username  # Lưu username để trả về
            QMessageBox.information(
                self,
                "Đăng ký thành công",
                "Tài khoản đã được tạo thành công.\nBạn có thể đăng nhập ngay bây giờ."
            )
            self.accept()
        else:
            self.show_error(message)

class ChangePasswordDialog(QDialog):
    """Dialog thay đổi mật khẩu"""
    
    def __init__(self, auth_manager, user_id, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.user_id = user_id
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Thay đổi mật khẩu")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Tiêu đề
        title_label = QLabel("THAY ĐỔI MẬT KHẨU")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        description = QLabel("Vui lòng nhập mật khẩu hiện tại và mật khẩu mới")
        description.setStyleSheet("color: #7f8c8d;")
        description.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(description)
        
        # Form thay đổi mật khẩu
        form_group = QGroupBox()
        form_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
            }
        """)
        
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 15, 15, 15)
        
        # Mật khẩu hiện tại
        self.current_password = QLineEdit()
        self.current_password.setPlaceholderText("Nhập mật khẩu hiện tại...")
        self.current_password.setEchoMode(QLineEdit.Password)
        self.current_password.setMinimumHeight(35)
        self.current_password.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        current_label = QLabel("Mật khẩu hiện tại:")
        current_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(current_label, self.current_password)
        
        # Mật khẩu mới
        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Nhập mật khẩu mới...")
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_password.setMinimumHeight(35)
        self.new_password.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        new_label = QLabel("Mật khẩu mới:")
        new_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(new_label, self.new_password)
        
        # Xác nhận mật khẩu mới
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Nhập lại mật khẩu mới...")
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setMinimumHeight(35)
        self.confirm_password.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        
        confirm_label = QLabel("Xác nhận mật khẩu:")
        confirm_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(confirm_label, self.confirm_password)
        
        main_layout.addWidget(form_group)
        
        # Hiển thị thông báo lỗi
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("""
            color: #e74c3c;
            padding: 5px;
            background-color: #fadbd8;
            border-radius: 4px;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)
        
        # Nút lưu và hủy
        buttons_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("HỦY BỎ")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                color: #2c3e50;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dde4e6;
            }
            QPushButton:pressed {
                background-color: #ccd6db;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("LƯU THAY ĐỔI")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
            }
        """)
        self.save_btn.clicked.connect(self.change_password)
        
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # Focus vào mật khẩu hiện tại
        self.current_password.setFocus()
    
    def show_error(self, message):
        """Hiển thị thông báo lỗi"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        
        # Tự động ẩn sau 5 giây
        QTimer.singleShot(5000, lambda: self.error_label.setVisible(False))
    
    def change_password(self):
        """Xử lý thay đổi mật khẩu"""
        current_password = self.current_password.text()
        new_password = self.new_password.text()
        confirm_password = self.confirm_password.text()
        
        # Kiểm tra thông tin
        if not current_password:
            self.show_error("Vui lòng nhập mật khẩu hiện tại")
            return
            
        if not new_password:
            self.show_error("Vui lòng nhập mật khẩu mới")
            return
            
        if len(new_password) < 6:
            self.show_error("Mật khẩu mới phải có ít nhất 6 ký tự")
            return
            
        if new_password != confirm_password:
            self.show_error("Mật khẩu mới và xác nhận không khớp")
            return
            
        if current_password == new_password:
            self.show_error("Mật khẩu mới không được trùng với mật khẩu cũ")
            return
            
        # Thực hiện thay đổi mật khẩu
        success, message = self.auth_manager.change_password(
            self.user_id, current_password, new_password
        )
        
        if success:
            QMessageBox.information(
                self,
                "Thành công",
                "Mật khẩu đã được thay đổi thành công.\nBạn sẽ cần đăng nhập lại."
            )
            self.accept()
        else:
            self.show_error(message)

class CustomSplashScreen(QDialog):
    """Màn hình chờ khởi động tùy chỉnh"""
    
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setFixedSize(600, 400)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Tiêu đề
        title_label = QLabel("HỆ THỐNG OCR VĂN BẢN")
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(20)
        
        # Phiên bản
        version_label = QLabel("Phiên bản 2.0.0")
        version_label.setStyleSheet("color: #7f8c8d;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        layout.addStretch()
        
        # Thanh tiến trình
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Trạng thái tải
        self.status_label = QLabel("Đang khởi tạo...")
        self.status_label.setStyleSheet("color: #2c3e50;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Copyright
        copyright_label = QLabel("© 2025 OCR System. All rights reserved.")
        copyright_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
        
        # Center dialog on screen
        screen_geometry = QApplication.desktop().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
        
    def update_progress(self, value, status=""):
        """Cập nhật tiến trình và trạng thái"""
        self.progress_bar.setValue(value)
        if status:
            self.status_label.setText(status)
        QApplication.processEvents()
        
def integrate_login_to_main(main_window_class):
    """Tích hợp hệ thống đăng nhập vào lớp MainWindow hiện có"""
    
    # Lớp MainWindow mới kế thừa từ lớp cũ
    class AuthenticatedMainWindow(main_window_class):
        def __init__(self, *args, **kwargs):
            # Khởi tạo hệ thống xác thực
            self.auth_manager = UserAuthManager()
            self.current_user = None
            
            # Bắt đầu với splash screen
            self.splash = CustomSplashScreen()
            self.splash.show()
            self.simulate_loading()
            
            # Kiểm tra đăng nhập tự động
            settings = QSettings("OCRApp", "DocumentManagement")
            remember_login = settings.value("remember_login", False, type=bool)
            saved_username = settings.value("username", "")
            
            if remember_login and saved_username:
                # Không thể tự động đăng nhập hoàn toàn vì bảo mật
                # Nhưng sẽ điền sẵn username
                self.show_login(auto_username=saved_username)
            else:
                self.show_login()
                
        def simulate_loading(self):
            """Mô phỏng quá trình tải ứng dụng"""
            # Các bước khởi tạo
            steps = [
                (10, "Kiểm tra cơ sở dữ liệu..."),
                (25, "Tải cấu hình hệ thống..."),
                (40, "Khởi tạo công cụ OCR..."),
                (60, "Chuẩn bị giao diện người dùng..."),
                (80, "Kiểm tra kết nối..."),
                (95, "Hoàn tất..."),
                (100, "Sẵn sàng")
            ]
            
            for progress, status in steps:
                self.splash.update_progress(progress, status)
                time.sleep(0.2)
                QApplication.processEvents()
            
            # Dừng thêm 1 giây sau khi hiển thị "Sẵn sàng"
            time.sleep(1)
            
            # Tự động đóng splash screen
            self.splash.close()
            
        def show_login(self, auto_username=""):
            """Hiển thị màn hình đăng nhập"""
            login_dialog = LoginDialog(self.auth_manager)
            
            # Điền username nếu có
            if auto_username:
                login_dialog.username_input.setText(auto_username)
                login_dialog.remember_checkbox.setChecked(True)
                login_dialog.password_input.setFocus()
            
            # Kết nối signal đăng nhập thành công
            login_dialog.login_successful.connect(self.login_successful)
            
            # Hiển thị dialog đăng nhập
            if login_dialog.exec_() != QDialog.Accepted:
                # Người dùng đóng dialog mà không đăng nhập
                sys.exit(0)
                
        def login_successful(self, user_data):
            """Xử lý khi đăng nhập thành công"""
            self.current_user = user_data
            logger.info(f"Login successful, initializing main window...")
            
            # Ẩn splash screen
            self.splash.close()
            
            # Khởi tạo MainWindow gốc - sử dụng cách đơn giản nhất
            try:
                # Cách 1: Khởi tạo main window không tham số
                super().__init__()
                logger.info("MainWindow initialized successfully")
                
                # Cập nhật thông tin người dùng đăng nhập
                self.update_ui_after_login()
                logger.info("UI updated after login")
                
                # Hiển thị cửa sổ chính
                self.show()
                logger.info("MainWindow displayed")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Error initializing main window: {str(e)}\n{error_details}")
                QMessageBox.critical(None, "Lỗi khởi tạo", 
                                f"Không thể khởi tạo giao diện chính: {str(e)}")
                sys.exit(1)
            
        def update_ui_after_login(self):
            """Cập nhật UI sau khi đăng nhập thành công"""
            # Thêm thông tin người dùng vào statusbar
            if hasattr(self, 'statusBar'):
                user_info_label = QLabel(f"Đăng nhập: {self.current_user['username']} | Vai trò: {self.current_user['role']}")
                self.statusBar().addPermanentWidget(user_info_label)
            
            # Thêm chức năng đổi mật khẩu vào menu
            if hasattr(self, 'menuBar'):
                # Tìm menu User hoặc tạo mới
                user_menu = None
                for action in self.menuBar().actions():
                    if action.text() == "&User":
                        user_menu = action.menu()
                        break
                
                if not user_menu:
                    user_menu = self.menuBar().addMenu("&User")
                
                # Thêm hành động đổi mật khẩu
                change_pwd_action = user_menu.addAction("Đổi mật khẩu")
                change_pwd_action.triggered.connect(self.show_change_password)
                
                # Thêm hành động đăng xuất
                logout_action = user_menu.addAction("Đăng xuất")
                logout_action.triggered.connect(self.logout)
            
        def show_change_password(self):
            """Hiển thị dialog đổi mật khẩu"""
            dialog = ChangePasswordDialog(
                self.auth_manager, 
                self.current_user['id'],
                self
            )
            
            if dialog.exec_() == QDialog.Accepted:
                # Đăng xuất sau khi đổi mật khẩu
                self.logout()
        
        def logout(self):
            """Đăng xuất khỏi hệ thống"""
            if self.current_user:
                # Thực hiện đăng xuất
                success = self.auth_manager.logout(
                    self.current_user['id'],
                    self.current_user['session_token']
                )
                
                if success:
                    # Lưu trạng thái hiện tại nếu cần
                    self.save_current_state()
                    
                    # Đóng cửa sổ hiện tại
                    self.close()
                    
                    # Khởi động lại ứng dụng
                    QTimer.singleShot(100, lambda: restart_application())
        
        def save_current_state(self):
            """Lưu trạng thái hiện tại trước khi đăng xuất"""
            # Thêm mã để lưu trạng thái hiện tại nếu cần
            pass
        
        def closeEvent(self, event):
            """Xử lý khi đóng ứng dụng"""
            # Đăng xuất trước khi đóng nếu người dùng đã đăng nhập
            if hasattr(self, 'current_user') and self.current_user:
                self.auth_manager.logout(
                    self.current_user['id'],
                    self.current_user['session_token']
                )
            
            # Gọi closeEvent của lớp cha
            super().closeEvent(event)
    
    return AuthenticatedMainWindow

def restart_application():
    """Khởi động lại ứng dụng"""
    python = sys.executable
    os.execl(python, python, *sys.argv)

def create_authenticated_main_window(main_window_class):
    """Tạo quá trình xác thực trước khi khởi chạy MainWindow"""
    
    def run_authentication():
        auth_manager = UserAuthManager()
        
        # Hiển thị splash screen
        splash = CustomSplashScreen()
        splash.show()
        
        # Chạy loading animation
        for i, (progress, status) in enumerate([
            (10, "Kiểm tra cơ sở dữ liệu..."),
            (25, "Tải cấu hình hệ thống..."),
            (40, "Khởi tạo công cụ OCR..."),
            (60, "Chuẩn bị giao diện người dùng..."),
            (80, "Kiểm tra kết nối..."),
            (95, "Hoàn tất..."),
            (100, "Sẵn sàng")
        ]):
            splash.update_progress(progress, status)
            time.sleep(0.2)
            QApplication.processEvents()
        
        # Đóng splash sau 1 giây
        time.sleep(1)
        splash.close()
        
        # Kiểm tra đăng nhập tự động
        settings = QSettings("OCRApp", "DocumentManagement")
        remember_login = settings.value("remember_login", False, type=bool)
        saved_username = settings.value("username", "")
        
        # Hiển thị login dialog
        login_dialog = LoginDialog(auth_manager)
        if remember_login and saved_username:
            login_dialog.username_input.setText(saved_username)
            login_dialog.remember_checkbox.setChecked(True)
            login_dialog.password_input.setFocus()
        
        # Nếu đăng nhập thành công
        if login_dialog.exec_() == QDialog.Accepted:
            user_data = login_dialog.user_data  # Giả sử bạn lưu user_data trong LoginDialog
            
            # Khởi tạo MainWindow
            main_window = main_window_class()
            
            # Thêm thông tin user
            main_window.current_user = user_data
            
            # Thêm menu User và các chức năng liên quan
            if hasattr(main_window, 'menuBar'):
                user_menu = main_window.menuBar().addMenu("&User")
                
                # Hàm đổi mật khẩu
                def show_change_password():
                    dialog = ChangePasswordDialog(auth_manager, user_data['id'])
                    if dialog.exec_() == QDialog.Accepted:
                        # Đăng xuất sau khi đổi mật khẩu
                        QMessageBox.information(main_window, "Thông báo", 
                                             "Mật khẩu đã được thay đổi. Bạn sẽ cần đăng nhập lại.")
                        restart_application()
                
                # Hàm đăng xuất
                def logout():
                    auth_manager.logout(user_data['id'], user_data['session_token'])
                    restart_application()
                
                # Thêm các actions
                change_pwd_action = user_menu.addAction("Đổi mật khẩu")
                change_pwd_action.triggered.connect(show_change_password)
                
                logout_action = user_menu.addAction("Đăng xuất")
                logout_action.triggered.connect(logout)
            
            # Hiển thị thông tin người dùng trên statusbar
            if hasattr(main_window, 'statusBar'):
                user_info_label = QLabel(f"Đăng nhập: {user_data['username']} | Vai trò: {user_data['role']}")
                main_window.statusBar().addPermanentWidget(user_info_label)
            
            # Hiển thị MainWindow
            main_window.show()
            return main_window
        else:
            # Người dùng đóng dialog mà không đăng nhập
            sys.exit(0)
    
    # Trả về hàm thay vì class
    return run_authentication

# Mã chạy thử nghiệm khi chạy trực tiếp file này
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("OCR Document Manager")
    app.setOrganizationName("OCRApp")
    
    # Tạo auth manager
    auth_manager = UserAuthManager()
    
    # Hiển thị dialog đăng nhập
    login_dialog = LoginDialog(auth_manager)
    login_dialog.login_successful.connect(lambda user_data: print(f"Đăng nhập thành công: {user_data}"))
    
    login_dialog.show()
    sys.exit(app.exec_())