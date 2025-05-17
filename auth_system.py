import os
import sys
import json
import hashlib
import time
from pathlib import Path
import logging
import sqlite3
from PyQt5.QtWidgets import (QApplication, QWidget, QDialog, QLabel, QLineEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout,
                           QMessageBox, QCheckBox, QMainWindow, QFrame, QComboBox)
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPalette

# Đường dẫn thư mục
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / 'config'
DATABASE_DIR = BASE_DIR / 'database'
LOGS_DIR = BASE_DIR / 'logs'
ICON_DIR = BASE_DIR / 'icons'

# Tạo thư mục
for dir_path in [CONFIG_DIR, DATABASE_DIR, LOGS_DIR, ICON_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'auth.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AuthSystem")

class UserAuthManager:
    """Quản lý người dùng và xác thực"""
    
    def __init__(self, db_path=DATABASE_DIR / "users.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """Khởi tạo cơ sở dữ liệu người dùng"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Bảng người dùng
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT,
                        email TEXT,
                        role TEXT DEFAULT 'user',
                        is_active INTEGER DEFAULT 1,
                        last_login TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        failed_attempts INTEGER DEFAULT 0,
                        locked_until TIMESTAMP
                    )
                ''')
                
                # Bảng phiên đăng nhập
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        session_token TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        ip_address TEXT,
                        user_agent TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                # Bảng lịch sử mật khẩu
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS password_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        password_hash TEXT NOT NULL,
                        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                # Bảng nhật ký hoạt động
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        activity_type TEXT,
                        description TEXT,
                        ip_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                # Kiểm tra và tạo tài khoản admin mặc định nếu cần
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                if cursor.fetchone()[0] == 0:
                    # Tạo tài khoản admin mặc định
                    admin_password = self._hash_password("admin123")
                    cursor.execute('''
                        INSERT INTO users (username, password_hash, full_name, role)
                        VALUES (?, ?, ?, ?)
                    ''', ('admin', admin_password, 'Administrator', 'admin'))
                    
                    logger.info("Created default admin account")
                
                conn.commit()
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def _hash_password(self, password):
        """Mã hóa mật khẩu bằng SHA-256 với salt"""
        salt = "OCRAuth2025"  # Salt cố định cho ứng dụng
        salted = password + salt
        return hashlib.sha256(salted.encode()).hexdigest()
    
    def register_user(self, username, password, full_name="", email="", role="user"):
        """Đăng ký người dùng mới"""
        try:
            # Kiểm tra username đã tồn tại chưa
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    return False, "Tên người dùng đã tồn tại"
                
                # Mã hóa mật khẩu
                password_hash = self._hash_password(password)
                
                # Thêm người dùng mới
                cursor.execute('''
                    INSERT INTO users (username, password_hash, full_name, email, role)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, password_hash, full_name, email, role))
                
                user_id = cursor.lastrowid
                
                # Lưu vào lịch sử mật khẩu
                cursor.execute('''
                    INSERT INTO password_history (user_id, password_hash)
                    VALUES (?, ?)
                ''', (user_id, password_hash))
                
                # Ghi nhật ký
                cursor.execute('''
                    INSERT INTO activity_logs (user_id, activity_type, description)
                    VALUES (?, ?, ?)
                ''', (user_id, "REGISTER", f"New user registered: {username}"))
                
                conn.commit()
                logger.info(f"New user registered: {username}")
                return True, "Đăng ký thành công"
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return False, f"Lỗi đăng ký: {str(e)}"
    
    def authenticate(self, username, password, ip_address="127.0.0.1"):
        """Xác thực đăng nhập"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Lấy thông tin người dùng
                cursor.execute('''
                    SELECT id, password_hash, is_active, failed_attempts, locked_until, role
                    FROM users WHERE username = ?
                ''', (username,))
                
                user = cursor.fetchone()
                if not user:
                    return False, "Tên đăng nhập không tồn tại", None
                
                user_id, stored_hash, is_active, failed_attempts, locked_until, role = user
                
                # Kiểm tra tài khoản bị khóa
                if locked_until and time.time() < locked_until:
                    remaining = int(locked_until - time.time())
                    return False, f"Tài khoản bị tạm khóa. Thử lại sau {remaining//60} phút", None
                
                # Kiểm tra tài khoản bị vô hiệu hóa
                if not is_active:
                    return False, "Tài khoản đã bị vô hiệu hóa", None
                
                # Kiểm tra mật khẩu
                if self._hash_password(password) != stored_hash:
                    # Tăng số lần thất bại
                    new_attempts = failed_attempts + 1
                    lock_time = None
                    
                    # Khóa tài khoản nếu quá 5 lần thất bại
                    if new_attempts >= 5:
                        lock_time = int(time.time() + 15*60)  # Khóa 15 phút
                        cursor.execute('''
                            UPDATE users
                            SET failed_attempts = ?, locked_until = ?
                            WHERE id = ?
                        ''', (new_attempts, lock_time, user_id))
                    else:
                        cursor.execute('''
                            UPDATE users 
                            SET failed_attempts = ?
                            WHERE id = ?
                        ''', (new_attempts, user_id))
                    
                    # Ghi nhật ký
                    cursor.execute('''
                        INSERT INTO activity_logs (user_id, activity_type, description, ip_address)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, "LOGIN_FAILED", f"Failed login attempt: {username}", ip_address))
                    
                    conn.commit()
                    
                    if lock_time:
                        return False, "Sai mật khẩu. Tài khoản bị khóa 15 phút do nhập sai nhiều lần", None
                    else:
                        remaining = 5 - new_attempts
                        return False, f"Sai mật khẩu. Còn {remaining} lần thử", None
                
                # Đăng nhập thành công - Cập nhật
                cursor.execute('''
                    UPDATE users
                    SET failed_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (user_id,))
                
                # Tạo phiên mới
                session_token = self._generate_session_token(user_id)
                expires_at = int(time.time() + 24*60*60)  # Hết hạn sau 24 giờ
                
                cursor.execute('''
                    INSERT INTO sessions (user_id, session_token, expires_at, ip_address)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, session_token, expires_at, ip_address))
                
                # Ghi nhật ký
                cursor.execute('''
                    INSERT INTO activity_logs (user_id, activity_type, description, ip_address)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, "LOGIN", f"User logged in: {username}", ip_address))
                
                conn.commit()
                logger.info(f"User authenticated: {username}")
                
                # Trả về kết quả
                user_data = {
                    'id': user_id,
                    'username': username,
                    'role': role,
                    'session_token': session_token
                }
                
                return True, "Đăng nhập thành công", user_data
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, f"Lỗi xác thực: {str(e)}", None
    
    def _generate_session_token(self, user_id):
        """Tạo token phiên làm việc"""
        seed = f"{user_id}_{time.time()}_{os.urandom(8).hex()}"
        return hashlib.sha256(seed.encode()).hexdigest()
    
    def verify_session(self, user_id, session_token):
        """Xác minh phiên làm việc"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM sessions
                    WHERE user_id = ? AND session_token = ? AND expires_at > ?
                ''', (user_id, session_token, int(time.time())))
                
                if cursor.fetchone():
                    return True
                return False
        except Exception as e:
            logger.error(f"Session verification error: {str(e)}")
            return False
    
    def change_password(self, user_id, current_password, new_password):
        """Thay đổi mật khẩu"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Kiểm tra mật khẩu hiện tại
                cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()
                if not result:
                    return False, "Người dùng không tồn tại"
                
                current_hash = result[0]
                if self._hash_password(current_password) != current_hash:
                    return False, "Mật khẩu hiện tại không đúng"
                
                # Kiểm tra mật khẩu mới có trùng với mật khẩu cũ không
                cursor.execute('''
                    SELECT password_hash FROM password_history
                    WHERE user_id = ?
                    ORDER BY changed_at DESC
                    LIMIT 3
                ''', (user_id,))
                
                recent_passwords = [row[0] for row in cursor.fetchall()]
                if self._hash_password(new_password) in recent_passwords:
                    return False, "Mật khẩu mới không được trùng với 3 mật khẩu gần đây"
                
                # Cập nhật mật khẩu mới
                new_hash = self._hash_password(new_password)
                cursor.execute('''
                    UPDATE users
                    SET password_hash = ?
                    WHERE id = ?
                ''', (new_hash, user_id))
                
                # Lưu vào lịch sử mật khẩu
                cursor.execute('''
                    INSERT INTO password_history (user_id, password_hash)
                    VALUES (?, ?)
                ''', (user_id, new_hash))
                
                # Ghi nhật ký
                cursor.execute('''
                    INSERT INTO activity_logs (user_id, activity_type, description)
                    VALUES (?, ?, ?)
                ''', (user_id, "PASSWORD_CHANGE", "Password changed"))
                
                # Hủy tất cả các phiên hiện tại
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                
                conn.commit()
                logger.info(f"Password changed for user ID: {user_id}")
                return True, "Thay đổi mật khẩu thành công"
                
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return False, f"Lỗi thay đổi mật khẩu: {str(e)}"
    
    def logout(self, user_id, session_token):
        """Đăng xuất"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Xóa phiên hiện tại
                cursor.execute('''
                    DELETE FROM sessions
                    WHERE user_id = ? AND session_token = ?
                ''', (user_id, session_token))
                
                # Ghi nhật ký
                cursor.execute('''
                    INSERT INTO activity_logs (user_id, activity_type, description)
                    VALUES (?, ?, ?)
                ''', (user_id, "LOGOUT", "User logged out"))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
    
    def get_user_info(self, user_id):
        """Lấy thông tin người dùng"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, full_name, email, role, is_active, last_login, created_at
                    FROM users WHERE id = ?
                ''', (user_id,))
                
                user = cursor.fetchone()
                if user:
                    return {
                        'id': user[0],
                        'username': user[1],
                        'full_name': user[2],
                        'email': user[3],
                        'role': user[4],
                        'is_active': bool(user[5]),
                        'last_login': user[6],
                        'created_at': user[7]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return None
            
    def update_user_info(self, user_id, full_name=None, email=None):
        """Cập nhật thông tin người dùng"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if full_name is not None:
                    updates.append("full_name = ?")
                    params.append(full_name)
                    
                if email is not None:
                    updates.append("email = ?")
                    params.append(email)
                    
                if not updates:
                    return True, "Không có thông tin cần cập nhật"
                    
                params.append(user_id)
                
                query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                # Ghi nhật ký
                cursor.execute('''
                    INSERT INTO activity_logs (user_id, activity_type, description)
                    VALUES (?, ?, ?)
                ''', (user_id, "PROFILE_UPDATE", "User profile updated"))
                
                conn.commit()
                return True, "Cập nhật thông tin thành công"
                
        except Exception as e:
            logger.error(f"Error updating user info: {str(e)}")
            return False, f"Lỗi cập nhật thông tin: {str(e)}"