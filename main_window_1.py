"""
Hệ thống OCR Văn Bản
Phần mềm quản lý và trích xuất thông tin từ văn bản hành chính
"""
from pdf2image import convert_from_path
from typing import List, Dict, Any, Optional, Union, Tuple
import os
import sys
from pathlib import Path
import fitz
import numpy as np
import cv2
from PIL import Image
import google.generativeai as genai
import json
import sqlite3
from ultralytics import YOLO
import time
from tqdm import tqdm
import logging
from datetime import datetime
import pandas as pd
import multiprocessing as mp
import threading
from queue import Empty, Queue
import qdarkstyle
from typing import List, Dict, Any, Optional, Tuple
import io
import shutil
import re
import traceback
from statistics_dialog import StatisticsDialog
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
                           QLineEdit, QTextEdit, QScrollArea, QFrame, QSplitter, QMessageBox,
                           QComboBox, QMenu, QAction, QProgressBar, QDialog, QShortcut,
                           QCompleter, QRadioButton, QButtonGroup, QGroupBox, QTabWidget,
                           QHeaderView, QSpacerItem, QSizePolicy, QStatusBar, QToolBar, 
                           QToolButton, QStyle, QStyleFactory, QCalendarWidget, QDateEdit, 
                           QCheckBox, QStyledItemDelegate, QGraphicsDropShadowEffect, QGridLayout, QFormLayout, QInputDialog,
                           QDialogButtonBox)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QSize, QRect, QPoint, QTimer, QStringListModel,
                         QDate, QDateTime, QEvent, QPropertyAnimation, QEasingCurve, QSettings,
                         QModelIndex, QSortFilterProxyModel, QAbstractTableModel, QRegExp, QUrl)
from PyQt5.QtGui import (QImage, QPixmap, QPainter, QPen, QKeySequence, QFont, QIcon, QColor,
                       QBrush, QLinearGradient, QPalette, QFontDatabase, QCursor, QRegExpValidator,
                       QDesktopServices, QPainterPath, QStandardItemModel, QStandardItem)
from vintern_ocr import VinternOCR  # Thay thế pytesseract bằng Vintern OCR

# Cấu hình cơ bản
APP_VERSION = "2.0.0"
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / 'output'
DATABASE_DIR = BASE_DIR / 'database'
LOGS_DIR = BASE_DIR / 'logs'
IMAGES_DIR = OUTPUT_DIR / 'images'
RESULTS_DIR = OUTPUT_DIR / 'results'
BACKUP_DIR = BASE_DIR / 'backup'
CONFIG_DIR = BASE_DIR / 'config'
TEMP_DIR = BASE_DIR / 'temp'
ICON_DIR = BASE_DIR / 'icons'

# Tạo thư mục
for dir_path in [OUTPUT_DIR, DATABASE_DIR, LOGS_DIR, IMAGES_DIR, 
                RESULTS_DIR, BACKUP_DIR, CONFIG_DIR, TEMP_DIR, ICON_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'ocr_app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OCRApp")

# Configuration Constants
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DATABASE_TIMEOUT = 30.0
MAX_RETRY_ATTEMPTS = 5
DEFAULT_USER = "OCR System"
DEFAULT_WAIT_CURSOR = True
AUTOSAVE_INTERVAL = 60000  # ms (1 minute)
MAX_RECENT_FILES = 10

#############################
# Database Connection Pool  #
#############################
class DBConnectionPool:
    """Thread-safe database connection pool for SQLite"""
    
    def __init__(self, db_path, max_connections=10, timeout=30.0):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.connections = {}
        self.lock = threading.RLock()
        
    def get_connection(self):
        """Get a connection for the current thread"""
        thread_id = threading.get_ident()
        
        with self.lock:
            if thread_id not in self.connections:
                if len(self.connections) >= self.max_connections:
                    # Find and close the oldest connection
                    oldest_thread = min(self.connections.keys(), 
                                       key=lambda k: self.connections[k]['last_used'])
                    self.connections[oldest_thread]['conn'].close()
                    del self.connections[oldest_thread]
                
                # Create new connection
                conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                conn.row_factory = sqlite3.Row
                self._optimize_connection(conn)
                
                self.connections[thread_id] = {
                    'conn': conn,
                    'last_used': time.time()
                }
            else:
                # Update last used time
                self.connections[thread_id]['last_used'] = time.time()
                
            return self.connections[thread_id]['conn']
    
    def _optimize_connection(self, conn):
        """Optimize SQLite connection settings"""
        conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes, still safe
        conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
        conn.execute("PRAGMA temp_store = MEMORY")  # Store temp data in memory
        conn.execute("PRAGMA foreign_keys = ON")    # Enable foreign key constraints
        return conn
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            for conn_data in self.connections.values():
                try:
                    conn_data['conn'].close()
                except:
                    pass
            self.connections.clear()
    
    def execute_with_retry(self, query, params=None, max_retries=5):
        """Execute a query with retry for locked database"""
        conn = self.get_connection()
        
        for attempt in range(max_retries):
            try:
                cursor = conn.cursor()
                if params:
                    result = cursor.execute(query, params)
                else:
                    result = cursor.execute(query)
                conn.commit()
                return result
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = 0.1 * (2 ** attempt)
                    logger.warning(f"Database locked, retrying in {sleep_time:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    conn.rollback()
                    raise
            except Exception as e:
                conn.rollback()
                raise

#############################
# Theme Manager & Styling   #
#############################
class ThemeManager:
    """Manages application theming and styling"""
    
    # Define color schemes
    COLOR_SCHEMES = {
        "light": {
            "primary": "#2c3e50",
            "secondary": "#3498db",
            "accent": "#e74c3c",
            "background": "#ecf0f1",
            "text": "#2c3e50",
            "border": "#bdc3c7",
            "hover": "#d6dbdf",
            "button_text": "#ffffff",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "danger": "#e74c3c",
            "info": "#3498db"
        },
        "dark": {
            "primary": "#34495e",
            "secondary": "#2980b9",
            "accent": "#e74c3c",
            "background": "#2c3e50",
            "text": "#ecf0f1",
            "border": "#7f8c8d",
            "hover": "#34495e",
            "button_text": "#ffffff",
            "success": "#27ae60",
            "warning": "#f39c12",
            "danger": "#c0392b",
            "info": "#2980b9"
        }
    }
    
    def __init__(self):
        self.dark_mode = False
        self.custom_colors = {}
        self.font_size = 10
        self.font_family = "Segoe UI"
        self.load_theme_settings()

    def load_theme_settings(self):
        """Load theme settings from file"""
        try:
            settings_path = CONFIG_DIR / 'theme_settings.json'
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.dark_mode = settings.get('dark_mode', False)
                    self.custom_colors = settings.get('custom_colors', {})
                    self.font_size = settings.get('font_size', 10)
                    self.font_family = settings.get('font_family', "Segoe UI")
            else:
                self.dark_mode = False
        except Exception as e:
            logger.error(f"Error loading theme settings: {str(e)}")
            self.dark_mode = False

    def save_theme_settings(self):
        """Save theme settings to file"""
        try:
            settings_path = CONFIG_DIR / 'theme_settings.json'
            with open(settings_path, 'w', encoding='utf-8') as f:
                settings = {
                    'dark_mode': self.dark_mode,
                    'custom_colors': self.custom_colors,
                    'font_size': self.font_size,
                    'font_family': self.font_family
                }
                json.dump(settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving theme settings: {str(e)}")

    def toggle_theme(self, app: QApplication):
        """Toggle between light and dark mode"""
        try:
            self.dark_mode = not self.dark_mode
            self.apply_theme(app)
            self.save_theme_settings()
            return self.dark_mode
        except Exception as e:
            logger.error(f"Error toggling theme: {str(e)}")
            return self.dark_mode
    
    def apply_theme(self, app: QApplication):
        """Apply current theme to application"""
        if self.dark_mode:
            # Apply dark theme (qdarkstyle)
            stylesheet = qdarkstyle.load_stylesheet_pyqt5()
            app.setStyleSheet(stylesheet)
            
            # Set dark palette
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
            
        else:
            # Apply light theme
            app.setStyleSheet("")
            app.setPalette(app.style().standardPalette())
            
            # Apply custom light stylesheet
            stylesheet = """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: white;
                border: 1px solid #dddddd;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #3498db;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #3498db;
            }
            QHeaderView::section {
                background-color: #e6e6e6;
                padding: 4px;
                border: 1px solid #dddddd;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #dddddd;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e6e6e6;
                border: 1px solid #dddddd;
                border-bottom: none;
                padding: 6px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QScrollBar {
                background-color: #f5f5f5;
            }
            QScrollBar::handle {
                background-color: #cccccc;
                border-radius: 4px;
            }
            QScrollBar::handle:hover {
                background-color: #bbbbbb;
            }
            QGroupBox {
                border: 1px solid #dddddd;
                border-radius: 4px;
                margin-top: 1ex;
                padding-top: 1ex;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: white;
                color: #3498db;
                font-weight: bold;
            }
            """
            app.setStyleSheet(stylesheet)
        
        # Apply font settings
        font = QFont(self.font_family, self.font_size)
        app.setFont(font)
    
    def get_color(self, color_name):
        """Get color from current theme"""
        scheme = "dark" if self.dark_mode else "light"
        
        # Check for custom color override
        if color_name in self.custom_colors:
            return QColor(self.custom_colors[color_name])
            
        # Use default theme color
        if color_name in self.COLOR_SCHEMES[scheme]:
            return QColor(self.COLOR_SCHEMES[scheme][color_name])
            
        # Fallback
        return QColor(self.dark_mode and "#ecf0f1" or "#2c3e50")
    
    def set_custom_color(self, color_name, color_value):
        """Set custom color override"""
        self.custom_colors[color_name] = color_value
        self.save_theme_settings()
    
    def set_font(self, family, size):
        """Set application font"""
        self.font_family = family
        self.font_size = size
        self.save_theme_settings()

#############################
#   PDF Viewer Component    #
#############################
class PDFViewer(QWidget):
    """PDF viewing widget with page navigation and detection visualization"""
    
    pageChanged = pyqtSignal(int)
    zoomChanged = pyqtSignal(float)
    
    # Zoom levels in percentage
    ZOOM_LEVELS = [25, 50, 75, 100, 125, 150, 175, 200, 250, 300]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page = 0
        self.pages = []
        self.detection_boxes = []
        self.pdf_path = None
        self.is_updating = False
        self.zoom_level = 100  # percentage
        self.zoom_idx = 3      # index in ZOOM_LEVELS (100%)
        self.rotation = 0      # degrees (0, 90, 180, 270)
        self.highlight_text = ""
        self.dpi = 150         # Base DPI for rendering
        
        # Thuộc tính cho việc vẽ box
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selection_rect = None
        self.is_drawing = False
        
        # Chế độ hiện tại (vẽ hoặc di chuyển)
        self.mode = "draw"  # "draw" hoặc "pan"
        
        # Biến cho việc pan (di chuyển) hình ảnh
        self.is_panning = False
        self.pan_start_point = QPoint()
        
        # Màu sắc cho các box
        self.selection_color = QColor(255, 0, 0)  # Màu đỏ cho selection box
        
        # Cho phép theo dõi chuột và sự kiện
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        
        # Navigation controls
        self.first_btn = QPushButton()
        self.first_btn.setIcon(QIcon(str(ICON_DIR / "first.png")))  
        self.first_btn.setToolTip("First Page")
        self.first_btn.clicked.connect(self.goto_first_page)
        self.first_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(QIcon(str(ICON_DIR / "previous.png")))
        self.prev_btn.setToolTip("Previous Page")
        self.prev_btn.clicked.connect(self.previous_page)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        # Page label
        self.page_label = QLabel("Page: 0/0")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setMinimumWidth(100)
        self.page_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-weight: bold;
                padding: 2px 8px;
            }
        """)

        # Page jump controls
        self.page_edit = QLineEdit()
        self.page_edit.setMaximumWidth(50)
        self.page_edit.setPlaceholderText("#")
        self.page_edit.returnPressed.connect(self.jump_to_page)
        self.page_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        self.jump_btn = QPushButton("Go")
        self.jump_btn.setMaximumWidth(40)
        self.jump_btn.clicked.connect(self.jump_to_page)
        self.jump_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # Next/Last buttons
        self.next_btn = QPushButton()
        self.next_btn.setIcon(QIcon(str(ICON_DIR / "next.png")))
        self.next_btn.setToolTip("Next Page")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        self.last_btn = QPushButton()
        self.last_btn.setIcon(QIcon(str(ICON_DIR / "last.png")))
        self.last_btn.setToolTip("Last Page")
        self.last_btn.clicked.connect(self.goto_last_page)
        self.last_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        # Zoom controls
        self.zoom_out_btn = QPushButton()
        self.zoom_out_btn.setIcon(QIcon(str(ICON_DIR / "zoom-out.png")))
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
            }
        """)

        self.zoom_in_btn = QPushButton()
        self.zoom_in_btn.setIcon(QIcon(str(ICON_DIR / "zoom-in.png")))
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
            }
        """)

        # Rotate controls
        self.rotate_left_btn = QPushButton()
        self.rotate_left_btn.setIcon(QIcon(str(ICON_DIR / "rotate-left.png")))
        self.rotate_left_btn.setToolTip("Rotate Left")
        self.rotate_left_btn.clicked.connect(self.rotate_left)
        self.rotate_left_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)

        self.rotate_right_btn = QPushButton()
        self.rotate_right_btn.setIcon(QIcon(str(ICON_DIR / "rotate-right.png")))
        self.rotate_right_btn.setToolTip("Rotate Right")
        self.rotate_right_btn.clicked.connect(self.rotate_right)
        self.rotate_right_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)

        # Zoom label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(60)
        self.zoom_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-weight: bold;
                padding: 2px 8px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        # Add controls to toolbar
        toolbar.addWidget(self.first_btn)
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_btn)
        toolbar.addWidget(self.last_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.page_edit)
        toolbar.addWidget(self.jump_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.rotate_left_btn)
        toolbar.addWidget(self.rotate_right_btn)
        
        # Image display in scrollable area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        # Sử dụng custom label để xử lý sự kiện vẽ và chuột
        self.image_label = CustomImageLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setBackgroundRole(QPalette.Base)
        
        # Quan trọng: Sử dụng đúng policy để không bị méo hình
        self.image_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.image_label.setScaledContents(False)  # Tắt scaled contents
        
        self.scroll_area.setWidget(self.image_label)
        
        # Add to main layout
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self.scroll_area)
        
        # Add OCR Button for selected area
        self.ocr_btn = QPushButton("OCR Selected Area")
        self.ocr_btn.setEnabled(False)  # Disabled by default until a selection is made
        self.ocr_btn.clicked.connect(self.ocr_selected_area)
        self.ocr_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #777777;
            }
        """)
        
        # Add clear selection button
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.setEnabled(False)  # Disabled by default
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #777777;
            }
        """)
        
        # Add button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ocr_btn)
        button_layout.addWidget(self.clear_selection_btn)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # Set initial state
        self.update_controls()

    def load_pdf(self, pdf_path):
        """Load a PDF file using pdf2image"""
        try:
            from pdf2image import convert_from_path
            
            self.pdf_path = pdf_path
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                self.pages = []
                self.current_page = 0
                self.update_controls()
                return False
                
            # Convert PDF to images
            self.pages = convert_from_path(pdf_path, dpi=self.dpi)
            self.current_page = 0
            self.detection_boxes = []
            self.update_page_display()
            self.update_controls()
            return True
            
        except Exception as e:
            logger.error(f"Error loading PDF: {str(e)}")
            self.pages = []
            self.current_page = 0
            self.update_controls()
            return False

    def set_detection_boxes(self, boxes):
        """Set detection boxes to visualize"""
        self.detection_boxes = boxes
        if not self.is_updating:  # Chỉ gọi update khi không đang update
            self.update_page_display()

    def set_highlight_text(self, text):
        """Set text to highlight in the document"""
        self.highlight_text = text
        # Note: Text highlighting may require different implementation with pdf2image
        self.update_page_display()

    def update_controls(self):
        """Update navigation controls based on document state"""
        has_doc = len(self.pages) > 0
        
        # Update page display
        if has_doc:
            self.page_label.setText(f"Page: {self.current_page + 1}/{len(self.pages)}")
        else:
            self.page_label.setText("Page: 0/0")
            
        # Enable/disable controls
        self.first_btn.setEnabled(has_doc and self.current_page > 0)
        self.prev_btn.setEnabled(has_doc and self.current_page > 0)
        self.next_btn.setEnabled(has_doc and self.current_page < len(self.pages) - 1)
        self.last_btn.setEnabled(has_doc and self.current_page < len(self.pages) - 1)
        self.page_edit.setEnabled(has_doc)
        self.jump_btn.setEnabled(has_doc)
        self.zoom_in_btn.setEnabled(has_doc and self.zoom_idx < len(self.ZOOM_LEVELS) - 1)
        self.zoom_out_btn.setEnabled(has_doc and self.zoom_idx > 0)
        self.rotate_left_btn.setEnabled(has_doc)
        self.rotate_right_btn.setEnabled(has_doc)
        
        # Update zoom display
        self.zoom_label.setText(f"{self.zoom_level}%")

    def update_page_display(self):
        """Render current page"""
        # Ngăn đệ quy
        if self.is_updating:
            return
            
        self.is_updating = True
        
        try:
            if not self.pages or self.current_page >= len(self.pages):
                self.image_label.clear()
                self.is_updating = False
                return

            # Get the PIL Image for current page
            current_pil_image = self.pages[self.current_page]
            
            # Apply rotation if needed
            if self.rotation != 0:
                current_pil_image = current_pil_image.rotate(-self.rotation, expand=True)
            
            # Convert PIL Image to QImage for display
            img_data = current_pil_image.convert('RGB')
            width, height = img_data.size
            
            # Convert to QImage
            bytes_per_line = 3 * width
            q_image = QImage(img_data.tobytes('raw', 'RGB'), width, height, bytes_per_line, QImage.Format_RGB888)
            
            # Tạo QPixmap từ QImage
            pixmap = QPixmap.fromImage(q_image)
            self.current_pixmap = pixmap  # Lưu pixmap hiện tại để sử dụng trong paintEvent
            
            # Tính toán tỷ lệ zoom
            zoom_factor = self.zoom_level / 100.0
            
            # Tắt scaleContents để tránh méo hình và cho phép custom drawing
            self.image_label.setScaledContents(False)
            
            # Thay đổi kích thước của QLabel để vừa với hình ảnh đã zoom
            scaled_width = int(pixmap.width() * zoom_factor)
            scaled_height = int(pixmap.height() * zoom_factor)
            self.image_label.setMinimumSize(scaled_width, scaled_height)
            self.image_label.resize(scaled_width, scaled_height)
            
            # Thêm pixmap vào label (chỉ để giữ reference, việc vẽ sẽ do paintEvent)
            # Note: có thể không cần thiết vì chúng ta đã vẽ trong paintEvent
            # Nhưng gán pixmap giúp QLabel có thể hiểu kích thước
            self.image_label.setPixmap(pixmap)
            
            # Gọi hàm update để vẽ lại
            self.image_label.update()
            
            # Emit page changed signal
            self.pageChanged.emit(self.current_page)
                
        except Exception as e:
            print(f"Error updating page display: {str(e)}")
            # Create an empty white image as fallback
            fallback_img = QImage(600, 800, QImage.Format_RGB888)
            fallback_img.fill(Qt.white)
            self.current_pixmap = QPixmap.fromImage(fallback_img)
            self.image_label.setPixmap(QPixmap.fromImage(fallback_img))  # Thêm dòng này
            self.image_label.update()
            
        self.is_updating = False

    def previous_page(self):
        """Go to previous page"""
        if self.pages and self.current_page > 0:
            self.current_page -= 1
            self.update_page_display()
            self.update_controls()

    def next_page(self):
        """Go to next page"""
        if self.pages and self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_page_display()
            self.update_controls()
            
    def goto_first_page(self):
        """Go to first page"""
        if self.pages and self.current_page > 0:
            self.current_page = 0
            self.update_page_display()
            self.update_controls()
            
    def goto_last_page(self):
        """Go to last page"""
        if self.pages and self.current_page < len(self.pages) - 1:
            self.current_page = len(self.pages) - 1
            self.update_page_display()
            self.update_controls()
            
    def jump_to_page(self):
        """Jump to specific page number"""
        if not self.pages:
            return
            
        try:
            page_num = int(self.page_edit.text())
            if page_num < 1:
                page_num = 1
            elif page_num > len(self.pages):
                page_num = len(self.pages)
                
            self.current_page = page_num - 1
            self.update_page_display()
            self.update_controls()
            self.page_edit.clear()
        except ValueError:
            # Invalid input, do nothing
            self.page_edit.clear()
            
    def zoom_in(self):
        """Increase zoom level"""
        if not self.pages:
            return
            
        if self.zoom_idx < len(self.ZOOM_LEVELS) - 1:
            self.zoom_idx += 1
            self.zoom_level = self.ZOOM_LEVELS[self.zoom_idx]
            self.update_page_display()
            self.update_controls()
            self.zoomChanged.emit(self.zoom_level / 100.0)
            
    def zoom_out(self):
        """Decrease zoom level"""
        if not self.pages:
            return
            
        if self.zoom_idx > 0:
            self.zoom_idx -= 1
            self.zoom_level = self.ZOOM_LEVELS[self.zoom_idx]
            self.update_page_display()
            self.update_controls()
            self.zoomChanged.emit(self.zoom_level / 100.0)
    
    def set_zoom(self, zoom_percentage):
        """Set zoom to specific percentage"""
        if not self.pages:
            return
            
        # Find closest zoom level
        self.zoom_level = min(self.ZOOM_LEVELS, key=lambda x: abs(x - zoom_percentage))
        self.zoom_idx = self.ZOOM_LEVELS.index(self.zoom_level)
        self.update_page_display()
        self.update_controls()
        self.zoomChanged.emit(self.zoom_level / 100.0)
        
    def rotate_left(self):
        """Rotate view 90 degrees counterclockwise"""
        if not self.pages:
            return
            
        self.rotation = (self.rotation - 90) % 360
        self.update_page_display()
        
    def rotate_right(self):
        """Rotate view 90 degrees clockwise"""
        if not self.pages:
            return
            
        self.rotation = (self.rotation + 90) % 360
        self.update_page_display()
        
    def reset_view(self):
        """Reset zoom and rotation to defaults"""
        if not self.pages:
            return
            
        self.zoom_level = 100
        self.zoom_idx = self.ZOOM_LEVELS.index(self.zoom_level)
        self.rotation = 0
        self.update_page_display()
        self.update_controls()
        self.zoomChanged.emit(self.zoom_level / 100.0)

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        if self.pages:
            self.update_page_display()

    def clear(self):
        """Clear current display"""
        self.pages = []
        self.current_page = 0
        self.detection_boxes = []
        self.pdf_path = None
        self.zoom_level = 100
        self.zoom_idx = self.ZOOM_LEVELS.index(self.zoom_level)
        self.rotation = 0
        self.highlight_text = ""
        self.image_label.clear()
        self.update_controls()
        
    def get_current_page_image(self):
        """Get current page as QImage"""
        if not self.pages or self.current_page >= len(self.pages):
            return None
            
        try:
            pil_image = self.pages[self.current_page]
            img_data = pil_image.convert('RGB')
            width, height = img_data.size
            bytes_per_line = 3 * width
            return QImage(img_data.tobytes('raw', 'RGB'), width, height, bytes_per_line, QImage.Format_RGB888)
        except Exception as e:
            logger.error(f"Error getting page image: {str(e)}")
            return None

    def extract_text_from_current_page(self):
        """Extract text from current page"""
        # Note: pdf2image doesn't provide text extraction
        # You would need to use another library like PyPDF2 or pdfplumber for this
        # For now, return empty string 
        return ""
        
    def clear_selection(self):
        """Clear the current selection box"""
        self.selection_rect = None
        self.image_label.update()
        self.ocr_btn.setEnabled(False)
        self.clear_selection_btn.setEnabled(False)
    
    def get_selection_in_original_coords(self):
        """Convert selected area from display coordinates to original image coordinates"""
        if not self.selection_rect or not hasattr(self, 'current_pixmap') or self.current_pixmap is None:
            return None
            
        # Tải hình ảnh hiện tại và zoom factor
        pixmap = self.current_pixmap
        zoom_factor = self.zoom_level / 100.0
        
        # Kích thước của hình ảnh sau khi zoom
        scaled_width = pixmap.width() * zoom_factor
        scaled_height = pixmap.height() * zoom_factor
        
        # Tính toán vị trí offset của hình ảnh trong label (căn giữa)
        offset_x = (self.image_label.width() - scaled_width) / 2
        offset_y = (self.image_label.height() - scaled_height) / 2
        
        # Lấy tọa độ của rectangle selection
        sel_x = self.selection_rect.x()
        sel_y = self.selection_rect.y() 
        sel_width = self.selection_rect.width()
        sel_height = self.selection_rect.height()
        
        # Chuyển đổi từ tọa độ hiển thị sang tọa độ gốc
        orig_x = (sel_x - offset_x) / zoom_factor
        orig_y = (sel_y - offset_y) / zoom_factor
        orig_width = sel_width / zoom_factor
        orig_height = sel_height / zoom_factor
        
        # Đảm bảo tọa độ nằm trong phạm vi hình ảnh gốc
        orig_x = max(0, min(pixmap.width(), orig_x))
        orig_y = max(0, min(pixmap.height(), orig_y))
        
        # Đảm bảo rằng việc cắt không vượt quá biên hình ảnh
        if orig_x + orig_width > pixmap.width():
            orig_width = pixmap.width() - orig_x
        if orig_y + orig_height > pixmap.height():
            orig_height = pixmap.height() - orig_y
        
        # Debug info 
        print(f"Selection on screen: {sel_x}, {sel_y}, {sel_width}, {sel_height}")
        print(f"Original image coordinates: {orig_x}, {orig_y}, {orig_width}, {orig_height}")
        
        # Trả về rectangle trong tọa độ gốc (sử dụng int để tránh lỗi khi cắt ảnh)
        return QRect(int(orig_x), int(orig_y), int(orig_width), int(orig_height))
    

    def batch_completed(self, results):
        """Handle completion of batch OCR process"""
        try:
            num_processed = 0
            for file_path, result, detections in results:
                try:
                    # Kiểm tra xem file có phải là file tạm
                    is_temp_file = self.is_converted_pdf(file_path)
                    
                    # Nếu là file tạm, tạo bản sao vĩnh viễn
                    if is_temp_file:
                        perm_filename = f"{Path(file_path).stem}_perm_{int(time.time())}.pdf"
                        permanent_file_path = str(OUTPUT_DIR / perm_filename)
                        shutil.copy2(file_path, permanent_file_path)
                        logger.info(f"Created permanent copy: {permanent_file_path}")
                        file_path = permanent_file_path
                    
                    # Add document to database
                    doc_id = self.db.add_document(file_path, result)
                    
                    # Format và chuẩn hóa detections trước khi lưu vào DB
                    try:
                        for i, page_detection in enumerate(detections):
                            # Nếu page_detection là dictionary, chuyển sang JSON
                            if isinstance(page_detection, dict):
                                serialized_detection = json.dumps(page_detection)
                                self.db.add_page_detections(doc_id, i+1, serialized_detection)
                            # Nếu page_detection là list, chuyển từng item sang JSON
                            elif isinstance(page_detection, list):
                                for item in page_detection:
                                    if isinstance(item, dict):
                                        serialized_item = json.dumps(item)
                                        self.db.add_page_detections(doc_id, i+1, serialized_item)
                    except Exception as e:
                        logger.error(f"Error formatting detections: {str(e)}")
                    
                    num_processed += 1
                    
                    # Clean up temporary converted PDF if needed
                    if is_temp_file and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Removed temporary PDF: {file_path}")
                        except Exception as e:
                            logger.warning(f"Could not remove temporary PDF: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
            
            # Refresh document list
            self.load_documents()
            
            if results:
                # Remember last directory
                self.settings.setValue("last_directory", str(Path(results[0][0]).parent))
            
            QMessageBox.information(
                self, 
                "Batch Processing Complete", 
                f"Successfully processed {num_processed} out of {len(results)} files."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error in batch processing: {str(e)}")

    def show_error(self, error_msg):
        """Display error message"""
        QMessageBox.critical(self, "Error", f"An error occurred: {error_msg}")

    def load_documents(self):
        """Load all documents from database"""
        try:
            documents = self.db.get_all_documents()
            self.update_document_table(documents)
            self.update_document_gallery(documents)
            
            # Update document count
            doc_count = len(documents)
            self.doc_count_label.setText(f"Documents: {doc_count}")
            
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error loading documents: {str(e)}")

    def update_document_table(self, documents):
        """Update document table with data"""
        self.doc_table.setSortingEnabled(False)
        self.doc_table.setRowCount(len(documents))
        
        for row, doc in enumerate(documents):
            # ID
            id_item = QTableWidgetItem(str(doc[0]))
            id_item.setData(Qt.UserRole, doc[0])  # Store ID for reference
            self.doc_table.setItem(row, 0, id_item)
            
            # Filename
            filename_item = QTableWidgetItem(doc[2])
            filename_item.setToolTip(doc[1])  # Full path as tooltip
            self.doc_table.setItem(row, 1, filename_item)
            
            # Date created
            date_item = QTableWidgetItem(str(doc[3]))
            self.doc_table.setItem(row, 2, date_item)
            
            # Version count
            version_item = QTableWidgetItem(str(doc[5]))
            version_item.setTextAlignment(Qt.AlignCenter)
            self.doc_table.setItem(row, 3, version_item)
            
            # Document number
            number_item = QTableWidgetItem(str(doc[8] or ""))
            self.doc_table.setItem(row, 4, number_item)
            
            # Document urgency
            urgency_text = doc[10] or "Không"
            urgency_item = QTableWidgetItem(urgency_text)
            urgency_item.setTextAlignment(Qt.AlignCenter)
            
            # Color code urgency
            if urgency_text == "Độ Mật":
                urgency_item.setBackground(QColor(255, 200, 200))  # Light red
            elif urgency_text == "Hỏa Tốc":
                urgency_item.setBackground(QColor(255, 140, 0))  # Orange
                urgency_item.setForeground(QColor(255, 255, 255))  # White text
                
            self.doc_table.setItem(row, 5, urgency_item)
            
            # Page count
            page_count_item = QTableWidgetItem(str(doc[4] or ""))
            page_count_item.setTextAlignment(Qt.AlignCenter)
            self.doc_table.setItem(row, 6, page_count_item)
            
        self.doc_table.setSortingEnabled(True)
    def update_document_gallery(self, documents):
        """Update document gallery with thumbnails"""
        self.doc_gallery.clear()
        
        # Calculate number of rows needed (with 4 columns)
        num_rows = (len(documents) + 3) // 4
        self.doc_gallery.setRowCount(num_rows)
        
        # Add documents to gallery
        for i, doc in enumerate(documents):
            # Calculate row and column
            row = i // 4
            col = i % 4
            
            # Create thumbnail item
            item = QTableWidgetItem()
            item.setData(Qt.UserRole, doc[0])  # Store document ID
            
            # Set item text (document info)
            doc_info = f"{doc[2]}\nID: {doc[0]}"
            if doc[8]:  # So ky hieu
                doc_info += f"\n{doc[8]}"
            if doc[10]:  # Do khan
                doc_info += f"\n{doc[10]}"
                
            item.setText(doc_info)
            item.setTextAlignment(Qt.AlignCenter)
            
            # Load thumbnail if available or generate
            self.load_thumbnail_for_item(item, doc[1], doc[0])
            
            # Set item size
            self.doc_gallery.setItem(row, col, item)
            self.doc_gallery.setRowHeight(row, 200)
            
    def load_thumbnail_for_item(self, item, file_path, doc_id):
        """Load or generate thumbnail for gallery item"""
        # Check for cached thumbnail
        thumb_path = IMAGES_DIR / f"thumb_{doc_id}.jpg"
        
        if os.path.exists(thumb_path):
            # Load existing thumbnail
            pixmap = QPixmap(str(thumb_path))
            item.setIcon(QIcon(pixmap))
            return
            
        # Generate thumbnail if file exists
        if os.path.exists(file_path):
            try:
                # Open first page of PDF
                with fitz.open(file_path) as pdf:
                    if len(pdf) > 0:
                        page = pdf[0]
                        # Render page to pixmap
                        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                        
                        # Convert to QImage and save thumbnail
                        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                        img.save(str(thumb_path), "JPG")
                        
                        # Set item icon
                        item.setIcon(QIcon(QPixmap.fromImage(img)))
                        return
            except Exception as e:
                logger.error(f"Error generating thumbnail: {str(e)}")
                
        # Use default icon if thumbnail generation failed
        item.setIcon(QIcon.fromTheme("application-pdf"))

    def gallery_item_selected(self, item):
        """Handle selection in gallery view"""
        doc_id = item.data(Qt.UserRole)
        if doc_id:
            self.show_document(doc_id)

    def show_document(self, doc_id):
        """Display a document and its data"""
        try:
            # Get document data
            doc_version = self.db.get_latest_version(doc_id)
            doc_info = self.db.get_document_info(doc_id)
            
            if not doc_version or not doc_info:
                QMessageBox.warning(self, "Warning", "Document data not found")
                return
                    
            # Store current document ID
            self.current_doc_id = doc_id  # Đảm bảo lưu đúng ID hiện tại
            
            # Load document content in editor FIRST - đặt ID trước rồi mới load data
            self.ocr_editor.doc_id = doc_id  # Đặt lại ID một cách rõ ràng
            self.ocr_editor.db = self.db    # Đảm bảo DB reference luôn được cập nhật
            self.ocr_editor.load_data(doc_version)
            self.ocr_editor.update_suggestions(self.db)
            
            # Load document versions
            versions = self.db.get_document_versions(doc_id)
            self.update_version_list(versions)
            
            # Update metadata display
            self.update_metadata_display(doc_info, doc_version)
            
            # Load PDF file
            pdf_path = doc_info[1]
            if os.path.exists(pdf_path):
                if self.pdf_viewer.load_pdf(pdf_path):
                    self.load_page_detections(doc_id, self.pdf_viewer.current_page)
                else:
                    self.detections_by_page = {}
            else:
                QMessageBox.warning(self, "Warning", f"PDF file not found: {pdf_path}")
                self.pdf_viewer.clear()
                self.detections_by_page = {}
                    
            # Update status bar
            self.update_status_info(doc_id, doc_info)
                    
        except Exception as e:
            logger.error(f"Error showing document: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Error loading document: {str(e)}")
            
    def update_document_gallery(self, documents):
        """Update document gallery with thumbnails"""
        self.doc_gallery.clear()
        
        # Calculate number of rows needed (with 4 columns)
        num_rows = (len(documents) + 3) // 4
        self.doc_gallery.setRowCount(num_rows)
        
        # Add documents to gallery
        for i, doc in enumerate(documents):
            # Calculate row and column
            row = i // 4
            col = i % 4
            
            # Create thumbnail item
            item = QTableWidgetItem()
            item.setData(Qt.UserRole, doc[0])  # Store document ID
            
            # Set item text (document info)
            doc_info = f"{doc[2]}\nID: {doc[0]}"
            if doc[8]:  # So ky hieu
                doc_info += f"\n{doc[8]}"
            if doc[10]:  # Do khan
                doc_info += f"\n{doc[10]}"
                
            item.setText(doc_info)
            item.setTextAlignment(Qt.AlignCenter)
            
            # Load thumbnail if available or generate
            self.load_thumbnail_for_item(item, doc[1], doc[0])
            
            # Set item size
            self.doc_gallery.setItem(row, col, item)
            self.doc_gallery.setRowHeight(row, 200)
            
    def load_thumbnail_for_item(self, item, file_path, doc_id):
        """Load or generate thumbnail for gallery item"""
        # Check for cached thumbnail
        thumb_path = IMAGES_DIR / f"thumb_{doc_id}.jpg"
        
        if os.path.exists(thumb_path):
            # Load existing thumbnail
            pixmap = QPixmap(str(thumb_path))
            item.setIcon(QIcon(pixmap))
            return
            
        # Generate thumbnail if file exists
        if os.path.exists(file_path):
            try:
                # Open first page of PDF
                with fitz.open(file_path) as pdf:
                    if len(pdf) > 0:
                        page = pdf[0]
                        # Render page to pixmap
                        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                        
                        # Convert to QImage and save thumbnail
                        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                        img.save(str(thumb_path), "JPG")
                        
                        # Set item icon
                        item.setIcon(QIcon(QPixmap.fromImage(img)))
                        return
            except Exception as e:
                logger.error(f"Error generating thumbnail: {str(e)}")
                
        # Use default icon if thumbnail generation failed
        item.setIcon(QIcon.fromTheme("application-pdf"))

    def gallery_item_selected(self, item):
        """Handle selection in gallery view"""
        doc_id = item.data(Qt.UserRole)
        if doc_id:
            self.show_document(doc_id)

    def show_document(self, doc_id):
        """Display a document and its data"""
        try:
            # Get document data
            doc_version = self.db.get_latest_version(doc_id)
            doc_info = self.db.get_document_info(doc_id)
            
            if not doc_version or not doc_info:
                QMessageBox.warning(self, "Warning", "Document data not found")
                return
                        
            # Store current document ID
            self.current_doc_id = doc_id  # Đảm bảo lưu đúng ID hiện tại
            
            # Load document content in editor FIRST - đặt ID trước rồi mới load data
            self.ocr_editor.doc_id = doc_id  # Đặt lại ID một cách rõ ràng
            self.ocr_editor.db = self.db    # Đảm bảo DB reference luôn được cập nhật
            self.ocr_editor.load_data(doc_version)
            self.ocr_editor.update_suggestions(self.db)
            
            # Load document versions
            versions = self.db.get_document_versions(doc_id)
            self.update_version_list(versions)
            
            # Update metadata display
            self.update_metadata_display(doc_info, doc_version)
            
            # Load PDF file
            pdf_path = doc_info[1]
            if os.path.exists(pdf_path):
                if self.pdf_viewer.load_pdf(pdf_path):
                    self.load_page_detections(doc_id, self.pdf_viewer.current_page)
                else:
                    self.detections_by_page = {}
            else:
                QMessageBox.warning(self, "Warning", f"PDF file not found: {pdf_path}")
                self.pdf_viewer.clear()
                self.detections_by_page = {}
                    
            # Update status bar
            self.update_status_info(doc_id, doc_info)
                    
        except Exception as e:
            logger.error(f"Error showing document: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Error loading document: {str(e)}")

    def load_page_detections(self, doc_id, page_num):
        """Load detections for a specific page"""
        if not doc_id or page_num is None or not hasattr(self.pdf_viewer, 'set_detection_boxes'):
            return
            
        try:
            detections = self.db.get_document_detections(doc_id, page_num)
            
            if isinstance(detections, list):  # Ensure detections is a list
                boxes = []
                for d in detections:
                    if isinstance(d, dict) and 'box' in d:
                        box = d.get('box', [])
                        if len(box) >= 4:
                            boxes.append(box)
                
                self.pdf_viewer.set_detection_boxes(boxes)
            else:
                self.pdf_viewer.set_detection_boxes([])
                
        except Exception as e:
            print(f"Error loading page detections: {str(e)}")  
            self.pdf_viewer.set_detection_boxes([])

    def update_metadata_display(self, doc_info, doc_version):
        """Update metadata information display"""
        try:
            if not doc_info or not doc_version:
                for field in self.metadata_fields.values():
                    field.clear()
                return
                    
            # Basic info
            self.metadata_fields['id'].setText(str(doc_info[0]))
            self.metadata_fields['filename'].setText(doc_info[2])
            self.metadata_fields['created'].setText(str(doc_info[3]))
            self.metadata_fields['modified'].setText(str(doc_info[4]))
            
            # Fix: Hiển thị số trang đúng
            # page_count ở vị trí index 7 trong bảng documents
            if len(doc_info) > 7 and doc_info[7] is not None:
                self.metadata_fields['pages'].setText(str(doc_info[7]))
            else:
                # Nếu không có thông tin số trang trong DB, thử đọc từ file PDF
                file_path = doc_info[1]
                if os.path.exists(file_path) and file_path.lower().endswith('.pdf'):
                    try:
                        with fitz.open(file_path) as pdf:
                            page_count = len(pdf)
                            self.metadata_fields['pages'].setText(str(page_count))
                            
                            # Cập nhật page_count vào DB
                            if self.current_doc_id:
                                try:
                                    conn = self.db.conn_pool.get_connection()
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        'UPDATE documents SET page_count = ? WHERE id = ?',
                                        (page_count, self.current_doc_id)
                                    )
                                    conn.commit()
                                except Exception as e:
                                    logger.error(f"Error updating page count: {str(e)}")
                    except:
                        self.metadata_fields['pages'].setText("1")
                else:
                    self.metadata_fields['pages'].setText("N/A")
            
            # File size
            file_path = doc_info[1]
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024:
                    self.metadata_fields['filesize'].setText(f"{size_bytes} B")
                elif size_bytes < 1024 * 1024:
                    self.metadata_fields['filesize'].setText(f"{size_bytes/1024:.1f} KB")
                else:
                    self.metadata_fields['filesize'].setText(f"{size_bytes/(1024*1024):.1f} MB")
            else:
                self.metadata_fields['filesize'].setText("File not found")
                    
            # Version count
            versions = self.db.get_document_versions(doc_info[0])
            self.metadata_fields['versions'].setText(str(len(versions)))
            
            # Document content fields
            self.metadata_fields['cqbh'].setText(f"{doc_version[3] or ''}\n{doc_version[4] or ''}")
            self.metadata_fields['so_kh'].setText(doc_version[5] or '')
            self.metadata_fields['loai_vb'].setText(doc_version[9] or '')  # Chỉ số 9 là loai_vb trong bảng
            
            # Độ khẩn with color coding
            do_khan = doc_version[7] or 'Không'  # Chỉ số 7 là do_khan trong bảng
            self.metadata_fields['do_khan'].setText(do_khan)
            
            # Định dạng màu cho độ khẩn
            if do_khan == 'Hỏa Tốc':
                self.metadata_fields['do_khan'].setStyleSheet("color: red; font-weight: bold;")
            elif do_khan == 'Thượng Khẩn':
                self.metadata_fields['do_khan'].setStyleSheet("color: orangered; font-weight: bold;")
            elif do_khan == 'Khẩn':
                self.metadata_fields['do_khan'].setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.metadata_fields['do_khan'].setStyleSheet("")
                
            # Độ mật with color coding
            do_mat = doc_version[8] or 'Không'  # Chỉ số 8 là do_mat trong bảng
            self.metadata_fields['do_mat'].setText(do_mat)
            
            # Định dạng màu cho độ mật
            if do_mat == 'Mật':
                self.metadata_fields['do_mat'].setStyleSheet("color: darkgreen; font-weight: bold;")
            elif do_mat == 'Tối Mật':
                self.metadata_fields['do_mat'].setStyleSheet("color: darkblue; font-weight: bold;")
            elif do_mat == 'Tuyệt Mật':
                self.metadata_fields['do_mat'].setStyleSheet("color: purple; font-weight: bold;")
            else:
                self.metadata_fields['do_mat'].setStyleSheet("")
                    
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")
            for field in self.metadata_fields.values():
                field.clear()

    def update_status_info(self, doc_id, doc_info):
        """Update status bar with document info"""
        if doc_info and os.path.exists(doc_info[1]):
            file_info = f"ID: {doc_id} | {os.path.basename(doc_info[1])}"
            self.doc_info_label.setText(file_info)
        else:
            self.doc_info_label.setText("")

    def document_selected(self, item):
        """Handle document selection in table"""
        try:
            row = item.row()
            doc_id = int(self.doc_table.item(row, 0).text())
            self.show_document(doc_id)
        except Exception as e:
            logger.error(f"Error selecting document: {str(e)}")

    def version_selected(self, item):
        """Handle version selection in table"""
        try:
            row = item.row()
            version_num = int(self.version_list.item(row, 0).text())
            
            if not self.current_doc_id:
                return
                
            # Load the specific version
            version_data = self.db.get_document_version(self.current_doc_id, version_num)
            if version_data:
                # Đặt ID tài liệu trước khi load dữ liệu
                self.ocr_editor.doc_id = self.current_doc_id  # Đặt ID tài liệu trực tiếp
                self.ocr_editor.load_data(version_data)
                self.update_metadata_display(self.db.get_document_info(self.current_doc_id), version_data)
                
        except Exception as e:
            logger.error(f"Error loading version: {str(e)}")

    def update_version_list(self, versions):
        """Update version list with document versions"""
        self.version_list.setRowCount(len(versions))
        for row, version in enumerate(versions):
            # Version number
            version_item = QTableWidgetItem(str(version[2]))
            self.version_list.setItem(row, 0, version_item)
            
            # Modified by - Hiển thị tên đăng nhập/người thao tác (OCR System, DuyBBB, v.v)
            modified_by = version[13] if version[13] else "Unknown"
            # Tên đăng nhập/người thao tác nên được lưu trực tiếp, không phải parse
            modified_by_item = QTableWidgetItem(modified_by)
            self.version_list.setItem(row, 1, modified_by_item)
            
            # Date - Đảm bảo hiển thị đúng định dạng ngày giờ
            date_str = str(version[14])
            # Kiểm tra nếu có giá trị ngày hợp lệ
            if date_str and date_str.lower() != "none":
                # Hiển thị theo định dạng dd/MM/yyyy hh:mm
                try:
                    from datetime import datetime
                    # Cố gắng phân tích chuỗi thời gian SQLite
                    if "-" in date_str and ":" in date_str:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                        date_item = QTableWidgetItem(formatted_date)
                    else:
                        date_item = QTableWidgetItem(date_str)
                except Exception as e:
                    # Nếu không phân tích được, hiển thị nguyên dạng
                    date_item = QTableWidgetItem(date_str)
            else:
                date_item = QTableWidgetItem("")
                
            self.version_list.setItem(row, 2, date_item)

    def update_document(self, doc_id, updates):
        """Update document with new data"""
        try:
            # Verify the document ID matches current selection
            if doc_id != self.current_doc_id:
                raise ValueError(f"Document ID mismatch: trying to update {doc_id} but current document is {self.current_doc_id}")
                
            # Lấy tên đăng nhập của người dùng để lưu vào phiên bản mới
            # Uu tiên lưu LUON là tên đăng nhập, không phải tên đầy đủ
            modified_by = self.current_user.get("username", "OCR System")
                
            # Create new version với thông tin người sửa
            new_version = self.db.create_new_version(doc_id, updates, modified_by=modified_by)
            
            if new_version:
                # Refresh document list
                self.load_documents()
                
                # Reload the same document
                self.show_document(doc_id)
                
                # Update suggestions
                self.ocr_editor.update_suggestions(self.db)
                
                self.statusBar().showMessage(f"Document {doc_id} updated successfully", 5000)
            else:
                raise Exception("Failed to create new version")
                
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error updating document: {str(e)}")

    def field_value_changed(self, field_name, new_value):
        """Handle field value change for real-time updates"""
        # This can be used for real-time validation or UI updates
        # without waiting for save
        pass

    def search_documents(self):
        """Search documents based on query and search type"""
        query = self.search_input.text()
        search_type = self.search_type.currentText().lower()
        
        # Map UI search type to database search type
        type_mapping = {
            "tất cả": "all",
            "tên file": "file_name",
            "nội dung": "content",
            "số ký hiệu": "so_ki_hieu",
            "độ khẩn": "do_khan"
        }
        
        db_search_type = type_mapping.get(search_type, "all")
        
        try:
            documents = self.db.search_documents(query, db_search_type)
            self.update_document_table(documents)
            self.update_document_gallery(documents)
            
            self.statusBar().showMessage(
                f"Tìm thấy {len(documents)} tài liệu phù hợp với '{query}'", 5000
            )
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            self.statusBar().showMessage(f"Lỗi tìm kiếm: {str(e)}", 5000)

    def show_advanced_search(self):
        """Show advanced search dialog"""
        # This would implement a more complex search dialog
        # with multiple criteria
        pass

    def export_to_excel(self):
        """Export all documents to Excel with optional filtering"""
        try:
            # Import custom export methods
            from export_methods_updated import export_to_excel as excel_exporter
            
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất ra Excel", "", "Excel Files (*.xlsx)"
            )
            
            if file_path:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                
                # Get current search/filter criteria
                query = self.search_input.text()
                search_type = self.search_type.currentText().lower()
                
                filter_criteria = {}
                if query:
                    if search_type == "tên file":
                        filter_criteria['file_name'] = query
                    elif search_type == "số ký hiệu":
                        filter_criteria['so_ki_hieu'] = query
                    elif search_type == "độ khẩn":
                        filter_criteria['do_khan'] = query
                    # Đã loại bỏ filter theo do_mat vì cột này không tồn tại
                    else:
                        filter_criteria['text'] = query
                
                # Sử dụng hàm xuất Excel từ module riêng biệt
                excel_exporter(self.db.conn_pool, file_path, filter_criteria)
                QMessageBox.information(self, "Thành công", f"Dữ liệu đã được xuất ra {file_path}")
            
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Xuất Excel thất bại: {str(e)}")
    
    def export_to_json(self):
        """Export all documents to JSON with optional filtering"""
        try:
            # Import custom export methods
            from export_methods_updated import export_to_json as json_exporter
            
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất ra JSON", "", "JSON Files (*.json)"
            )
            
            if file_path:
                if not file_path.endswith('.json'):
                    file_path += '.json'
                
                # Get current search/filter criteria
                query = self.search_input.text()
                search_type = self.search_type.currentText().lower()
                
                filter_criteria = {}
                if query:
                    if search_type == "tên file":
                        filter_criteria['file_name'] = query
                    elif search_type == "số ký hiệu":
                        filter_criteria['so_ki_hieu'] = query
                    elif search_type == "độ khẩn":
                        filter_criteria['do_khan'] = query
                    # Đã loại bỏ filter theo do_mat vì cột này không tồn tại
                    else:
                        filter_criteria['text'] = query
                
                # Sử dụng hàm xuất JSON từ module riêng biệt
                json_exporter(self.db.conn_pool, file_path, filter_criteria)
                QMessageBox.information(self, "Thành công", f"Dữ liệu đã được xuất ra {file_path}")
            
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Xuất JSON thất bại: {str(e)}")


    def backup_database(self):
        """Create backup of the database"""
        try:
            backup_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Backup Database", 
                str(BACKUP_DIR / f"documents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"),
                "Database Files (*.db)"
            )
            
            if backup_path:
                if not backup_path.endswith('.db'):
                    backup_path += '.db'
                
                # Close database connections
                self.db.close()
                
                # Copy database file
                shutil.copy2(self.db.db_path, backup_path)
                
                # Reconnect
                self.db = DocumentDatabase()
                
                QMessageBox.information(
                    self, 
                    "Backup Complete", 
                    f"Database backed up to:\n{backup_path}"
                )
                
        except Exception as e:
            logger.error(f"Database backup error: {str(e)}")
            QMessageBox.critical(self, "Backup Error", f"Database backup failed: {str(e)}")

    def toggle_preview(self):
        """Toggle PDF preview for currently selected document"""
        if not self.current_doc_id:
            QMessageBox.information(self, "Information", "Please select a document first")
            return
            
        # Get document info
        doc_info = self.db.get_document_info(self.current_doc_id)
        if not doc_info:
            QMessageBox.warning(self, "Warning", "Document information not found")
            return
            
        # Check if file exists
        pdf_path = doc_info[1]
        if not os.path.exists(pdf_path):
            QMessageBox.warning(self, "File not found", f"PDF file not found at: {pdf_path}")
            return
            
        # Show preview dialog
        preview = PreviewDialog(pdf_path, self)
        preview.exec_()

    def toggle_dark_mode(self):
        """Toggle dark mode"""
        is_dark = self.theme_manager.toggle_theme(QApplication.instance())
        
        # Update menu checkmark
        for action in self.menuBar().actions():
            if action.text() == "&View":
                for subaction in action.menu().actions():
                    if subaction.text() == "Dark Mode":
                        subaction.setChecked(is_dark)
                        break
                break

    def switch_view(self, view_mode):
        """Switch between different view modes"""
        if view_mode == self.current_view_mode:
            return
            
        self.current_view_mode = view_mode
        
        if view_mode == "details":
            self.doc_tabs.setCurrentIndex(0)
        elif view_mode == "gallery":
            self.doc_tabs.setCurrentIndex(1)

    def page_changed(self, page_num):
        """Handle PDF page change"""
        if self.current_doc_id:
            self.load_page_detections(self.current_doc_id, page_num)

    def show_settings(self):
        """Show settings dialog"""
        # This would open a settings dialog where user can
        # configure application settings
        pass

    def show_statistics(self):
        """Show document statistics"""
        # This would show statistics about documents in the system
        pass

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About OCR Document Manager",
            f"<h2>OCR Document Manager</h2>"
            f"<p>Version: {APP_VERSION}</p>"
            f"<p>A document management system with OCR capabilities.</p>"
            f"<p>© 2025 All Rights Reserved</p>"
        )

    def show_help(self):
        """Show help documentation"""
        help_file = BASE_DIR / "help.html"
        if os.path.exists(help_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_file)))
        else:
            QMessageBox.information(
                self,
                "Help",
                "Hướng dẫn sử dụng:\n\n"
                "1. Thêm tài liệu: Sử dụng nút 'Thêm File' hoặc menu File > Thêm File\n"
                "2. Xử lý OCR: Hệ thống sẽ tự động trích xuất văn bản\n"
                "3. Chỉnh sửa kết quả: Sử dụng panel bên phải để chỉnh sửa\n"
                "4. Tìm kiếm: Nhập từ khóa vào ô tìm kiếm\n"
                "5. Xuất dữ liệu: Sử dụng chức năng Xuất Excel\n"
            )

    def refresh_view(self):
        """Refresh current view and reload data"""
        self.load_documents()
        
        # Get currently selected document
        if self.current_doc_id:
            self.show_document(self.current_doc_id)
        else:
            self.clear_current_view()
            
        self.statusBar().showMessage("Data refreshed", 3000)

    def clear_selection(self):
        """Clear current selection"""
        self.doc_table.clearSelection()
        self.version_list.clearSelection()
        self.current_doc_id = None
        self.clear_current_view()
        
    def clear_current_view(self):
        """Clear all views and editors"""
        self.pdf_viewer.clear()
        self.ocr_editor.clear()
        
        # Clear metadata
        for field in self.metadata_fields.values():
            field.clear()
            
        self.version_list.setRowCount(0)
        self.detections_by_page = {}
        self.doc_info_label.setText("")

    def save_current(self):
        """Save current document changes"""
        if self.current_doc_id:
            self.ocr_editor.save_changes()
        else:
            QMessageBox.information(self, "No selection", "Please select a document first")

    def auto_save(self):
        """Auto-save current document if changes detected"""
        if self.current_doc_id and self.ocr_editor.save_btn.isEnabled():
            self.ocr_editor.save_changes()
            self.statusBar().showMessage("Auto-saved", 2000)

    def closeEvent(self, event):
        """Handle application close"""
        # Save window settings
        self.save_window_settings()
        
        # Save theme settings
        self.theme_manager.save_theme_settings()
        
        # Check for unsaved changes
        if self.current_doc_id and self.ocr_editor.save_btn.isEnabled():
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'You have unsaved changes. Do you want to save before exiting?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self.ocr_editor.save_changes()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
                return
        
        # Close database connections
        self.db.close()
        
        # Stop any running workers
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.cancel()
            self.ocr_worker.wait(1000)
            
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.batch_worker.wait(1000)
            
        if self.repair_worker and self.repair_worker.isRunning():
            self.repair_worker.cancel()
            self.repair_worker.wait(1000)
            
        # Accept close event
        event.accept()
def main():
    # Must set these attributes before creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    # Set application info
    app.setApplicationName("OCR Document Manager")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("OCRApp")
    
    # Set application style
    app.setStyle(QStyleFactory.create('Fusion'))
    
    # Register custom fonts if available
    font_dir = BASE_DIR / 'fonts'
    if font_dir.exists():
        for font_file in font_dir.glob('*.ttf'):
            QFontDatabase.addApplicationFont(str(font_file))
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()