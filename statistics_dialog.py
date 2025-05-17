# Trong statistics_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                           QTableWidgetItem, QGroupBox, QLabel, QPushButton, 
                           QHeaderView, QTabWidget, QWidget, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import pandas as pd
import logging

logger = logging.getLogger("OCRApp")

class StatisticsDialog(QDialog):
    """Dialog hiển thị thống kê"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
        self.load_statistics()

    def setup_ui(self):
        self.setWindowTitle("Thống kê hệ thống")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        layout = QVBoxLayout(self)

        # Tab widget chính
        self.tab_widget = QTabWidget()
        
        # Tab tổng quan
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        
        # Tổng quát
        overview_group = QGroupBox("Thông tin tổng quan")
        overview_group_layout = QVBoxLayout()
        self.total_label = QLabel()
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        overview_group_layout.addWidget(self.total_label)
        overview_group.setLayout(overview_group_layout)
        overview_layout.addWidget(overview_group)
        
        # Thống kê theo loại
        type_group = QGroupBox("Thống kê theo loại văn bản")
        type_layout = QVBoxLayout()
        self.type_table = QTableWidget()
        self.type_table.setColumnCount(2)
        self.type_table.setHorizontalHeaderLabels(["Loại văn bản", "Số lượng"])
        self.type_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.type_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        type_layout.addWidget(self.type_table)
        type_group.setLayout(type_layout)
        overview_layout.addWidget(type_group)
        
        # Thống kê độ khẩn
        urgency_group = QGroupBox("Thống kê theo độ khẩn")
        urgency_layout = QVBoxLayout()
        self.urgency_table = QTableWidget()
        self.urgency_table.setColumnCount(2)
        self.urgency_table.setHorizontalHeaderLabels(["Độ khẩn", "Số lượng"])
        self.urgency_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.urgency_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        urgency_layout.addWidget(self.urgency_table)
        urgency_group.setLayout(urgency_layout)
        overview_layout.addWidget(urgency_group)
        
        self.tab_widget.addTab(overview_tab, "Tổng quan")
        
        # Tab văn bản mới
        recent_tab = QWidget()
        recent_layout = QVBoxLayout(recent_tab)
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["ID", "Tên file", "Ngày tạo", "Số ký hiệu"])
        self.recent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        recent_layout.addWidget(self.recent_table)
        self.tab_widget.addTab(recent_tab, "Văn bản mới nhất")
        
        # Tab thống kê thời gian
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)
        self.time_table = QTableWidget()
        self.time_table.setColumnCount(2)
        self.time_table.setHorizontalHeaderLabels(["Tháng", "Số lượng"])
        self.time_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        time_layout.addWidget(self.time_table)
        self.tab_widget.addTab(time_tab, "Thống kê theo thời gian")
        
        layout.addWidget(self.tab_widget)
        
        # Nút điều khiển
        button_box = QHBoxLayout()
        
        self.export_btn = QPushButton("Xuất báo cáo")
        self.export_btn.clicked.connect(self.export_statistics)
        
        self.close_btn = QPushButton("Đóng")
        self.close_btn.clicked.connect(self.close)
        
        button_box.addStretch()
        button_box.addWidget(self.export_btn)
        button_box.addWidget(self.close_btn)
        
        layout.addLayout(button_box)

    def load_statistics(self):
        """Load thống kê từ database"""
        stats = self.db.get_statistics()
        if not stats:
            return

        # Cập nhật tổng quan
        self.total_label.setText(f"Tổng số văn bản: {stats['total_documents']}")

        # Cập nhật bảng loại văn bản
        self.type_table.setRowCount(len(stats['by_type']))
        for i, (type_name, count) in enumerate(stats['by_type']):
            self.type_table.setItem(i, 0, QTableWidgetItem(type_name or "Không xác định"))
            self.type_table.setItem(i, 1, QTableWidgetItem(str(count)))

        # Cập nhật bảng độ khẩn
        self.urgency_table.setRowCount(len(stats['by_urgency']))
        for i, (urgency, count) in enumerate(stats['by_urgency']):
            item = QTableWidgetItem(urgency or "Không")
            if urgency == "Độ Mật":
                item.setBackground(QColor(255, 200, 200))
            elif urgency == "Hỏa Tốc":
                item.setBackground(QColor(255, 140, 0))
                item.setForeground(QColor(255, 255, 255))
            self.urgency_table.setItem(i, 0, item)
            self.urgency_table.setItem(i, 1, QTableWidgetItem(str(count)))

        # Cập nhật văn bản mới nhất
        self.recent_table.setRowCount(len(stats['recent_docs']))
        for i, (doc_id, filename, created_at, so_kh) in enumerate(stats['recent_docs']):
            self.recent_table.setItem(i, 0, QTableWidgetItem(str(doc_id)))
            self.recent_table.setItem(i, 1, QTableWidgetItem(filename))
            self.recent_table.setItem(i, 2, QTableWidgetItem(str(created_at)))
            self.recent_table.setItem(i, 3, QTableWidgetItem(so_kh))

        # Cập nhật thống kê theo thời gian
        self.time_table.setRowCount(len(stats['by_month']))
        for i, (month, count) in enumerate(stats['by_month']):
            self.time_table.setItem(i, 0, QTableWidgetItem(month))
            self.time_table.setItem(i, 1, QTableWidgetItem(str(count)))

    def export_statistics(self):
        """Xuất thống kê ra file Excel"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất báo cáo", "", "Excel Files (*.xlsx)"
            )
            if not file_path:
                return

            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'

            stats = self.db.get_statistics()
            if not stats:
                return

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Tổng quan
                overview_data = {
                    'Thông tin': ['Tổng số văn bản'],
                    'Số lượng': [stats['total_documents']]
                }
                pd.DataFrame(overview_data).to_excel(writer, sheet_name='Tổng quan', index=False)

                # Thống kê theo loại
                type_data = pd.DataFrame(stats['by_type'], columns=['Loại văn bản', 'Số lượng'])
                type_data.to_excel(writer, sheet_name='Theo loại', index=False)

                # Thống kê theo độ khẩn
                urgency_data = pd.DataFrame(stats['by_urgency'], columns=['Độ khẩn', 'Số lượng'])
                urgency_data.to_excel(writer, sheet_name='Theo độ khẩn', index=False)

                # Thống kê theo thời gian
                time_data = pd.DataFrame(stats['by_month'], columns=['Tháng', 'Số lượng'])
                time_data.to_excel(writer, sheet_name='Theo thời gian', index=False)

                # Văn bản mới nhất
                recent_data = pd.DataFrame(
                    stats['recent_docs'],
                    columns=['ID', 'Tên file', 'Ngày tạo', 'Số ký hiệu']
                )
                recent_data.to_excel(writer, sheet_name='Văn bản mới', index=False)

            QMessageBox.information(self, "Thành công", f"Đã xuất báo cáo thống kê tới {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi xuất báo cáo: {str(e)}")