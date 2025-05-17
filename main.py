#!/usr/bin/env python
"""
Main application file for OCR Document Management System
Handles user authentication before initializing the main window
"""
import os
import sys
import time
import logging
import traceback
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QDialog, QLabel, QMessageBox,
                           QSplashScreen, QProgressBar, QVBoxLayout, QWidget)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QPixmap, QColor

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OCRApp")

# Import thư viện chính
try:
    #(NẾU DÙNG OFFLINE)
    from main_window import MainWindow
    # Import từ auth_system.py - UserAuthManager
    from auth_system import UserAuthManager
    # Import từ login.py - LoginDialog, ChangePasswordDialog
    from login import LoginDialog, ChangePasswordDialog, CustomSplashScreen
except ImportError as e:
    print(f"Error importing required modules: {str(e)}")
    sys.exit(1)

def restart_application():
    """Khởi động lại ứng dụng"""
    python = sys.executable
    os.execl(python, python, *sys.argv)
    
def run_authentication():
    """Chạy quá trình xác thực trước khi khởi chạy MainWindow"""
    auth_manager = UserAuthManager()
    
    # Hiển thị splash screen
    splash = CustomSplashScreen()
    splash.show()
    
    # Chạy loading animation
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
        try:
            # Lấy dữ liệu người dùng
            user_data = None
            if hasattr(login_dialog, 'user_data'):
                user_data = login_dialog.user_data
            else:
                # Nếu login_dialog không lưu user_data, lấy từ kết quả signal
                success, message, user_data = auth_manager.authenticate(
                    login_dialog.username_input.text().strip(),
                    login_dialog.password_input.text()
                )
                if not success or not user_data:
                    raise ValueError("Failed to retrieve user data after login")
                
            logger.info(f"User authenticated: {user_data['username']}")
                
            # Khởi tạo MainWindow
            main_window = MainWindow()
            
            # Thêm thông tin user
            main_window.current_user = user_data
            
            # Thêm menu User và các chức năng liên quan
            if hasattr(main_window, 'menuBar'):
                # Tìm menu User hoặc tạo mới
                user_menu = None
                for action in main_window.menuBar().actions():
                    if action.text() == "&User":
                        user_menu = action.menu()
                        break
                
                if not user_menu:
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
            logger.info("Main window initialized and displayed")
            
            return main_window
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error initializing main window: {str(e)}\n{error_details}")
            QMessageBox.critical(None, "Lỗi khởi tạo", 
                               f"Không thể khởi tạo giao diện chính: {str(e)}")
            sys.exit(1)
    else:
        # Người dùng đóng dialog mà không đăng nhập
        logger.info("User cancelled login")
        sys.exit(0)

if __name__ == "__main__":
    # Thiết lập ứng dụng
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("OCR Document Manager")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("OCRApp")
    
    try:
        # Chạy xác thực và nhận main_window
        main_window = run_authentication()
        
        # Khởi động vòng lặp sự kiện
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application startup error: {str(e)}")
        traceback.print_exc()
        QMessageBox.critical(
            None, 
            "Lỗi khởi động ứng dụng",
            f"Không thể khởi động ứng dụng: {str(e)}\n\n"
            "Vui lòng kiểm tra logs để biết thêm chi tiết."
        )
        sys.exit(1)