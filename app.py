import sys
import requests
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pandas as pd

# عنوان الخادم السحابي
BASE_URL = "https://school-evidence-c4a7.onrender.com"

class LoginWindow(QMainWindow):
    """نافذة تسجيل الدخول"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نظام توثيق الشواهد - تسجيل الدخول")
        self.setFixedSize(400, 500)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a2a6c, stop:0.5 #b21f1f, stop:1 #fdbb4d);
            }
        """)
        
        # المكونات
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 80, 40, 80)
        
        # الشعار
        logo = QLabel("📸")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size: 64px;")
        layout.addWidget(logo)
        
        # العنوان
        title = QLabel("نظام توثيق الشواهد")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        # اسم المستخدم
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("اسم المستخدم")
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border-radius: 10px;
                border: none;
                background: white;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.username_input)
        
        # كلمة السر
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("كلمة السر")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border-radius: 10px;
                border: none;
                background: white;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.password_input)
        
        # زر الدخول
        login_btn = QPushButton("دخول")
        login_btn.setStyleSheet("""
            QPushButton {
                padding: 12px;
                border-radius: 10px;
                background: #667eea;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background: #5a67d8;
            }
        """)
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        
        # معلومات
        info = QLabel("🔐 admin / admin123")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        layout.addWidget(info)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #ffcccc;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        # التحقق من إدخال البيانات
        if not username or not password:
            self.status_label.setText("الرجاء إدخال اسم المستخدم وكلمة السر")
            return
        
        try:
            # أولاً: اختبار الاتصال بالخادم
            self.status_label.setText("جاري الاتصال بالخادم...")
            status_response = requests.get(f"{BASE_URL}/api/status", timeout=5)
            
            if status_response.status_code != 200:
                self.status_label.setText("الخادم لا يستجيب بشكل صحيح")
                return
                
            # ثانياً: محاولة تسجيل الدخول
            self.status_label.setText("جاري تسجيل الدخول...")
            response = requests.post(
                f"{BASE_URL}/api/login",
                json={"username": username, "password": password},
                timeout=10
            )
            data = response.json()
            
            if data.get('success'):
                self.main_window = MainWindow(username, data.get('is_admin', False))
                self.main_window.show()
                self.close()
            else:
                self.status_label.setText(data.get('error', 'خطأ في تسجيل الدخول'))
                
        except requests.exceptions.ConnectionError:
            self.status_label.setText("خطأ: لا يمكن الاتصال بالخادم. تأكد من اتصال الإنترنت")
        except requests.exceptions.Timeout:
            self.status_label.setText("خطأ: انتهى وقت الاتصال. الخادم بطيء")
        except Exception as e:
            self.status_label.setText(f"خطأ غير متوقع: {str(e)}")


class MainWindow(QMainWindow):
    """النافذة الرئيسية للتطبيق"""
    def __init__(self, username, is_admin):
        super().__init__()
        self.username = username
        self.is_admin = is_admin
        self.setWindowTitle(f"نظام توثيق الشواهد - مرحباً {username}")
        self.setGeometry(100, 100, 1200, 700)
        
        # تطبيق نمط Windows 11
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QPushButton {
                background-color: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a67d8;
            }
            QTableWidget {
                background-color: white;
                border-radius: 12px;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                font-weight: bold;
            }
            QTabWidget::pane {
                background-color: white;
                border-radius: 12px;
            }
            QTabBar::tab {
                padding: 10px 20px;
                font-size: 14px;
            }
        """)
        
        # الشريط الجانبي
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1a2a6c, stop:1 #b21f1f);
            border-radius: 0;
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(15)
        sidebar_layout.setContentsMargins(15, 30, 15, 30)
        
        # الشعار
        logo = QLabel("📸 نظام التوثيق")
        logo.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        logo.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(logo)
        
        # أزرار التنقل
        self.dashboard_btn = QPushButton("📊 لوحة التحكم")
        self.dashboard_btn.clicked.connect(lambda: self.switch_page(0))
        sidebar_layout.addWidget(self.dashboard_btn)
        
        self.evidences_btn = QPushButton("📋 جميع التوثيقات")
        self.evidences_btn.clicked.connect(lambda: self.switch_page(1))
        sidebar_layout.addWidget(self.evidences_btn)
        
        if is_admin:
            self.stats_btn = QPushButton("📈 إحصائيات المراقبين")
            self.stats_btn.clicked.connect(lambda: self.switch_page(2))
            sidebar_layout.addWidget(self.stats_btn)
            
            self.users_btn = QPushButton("👥 إدارة المستخدمين")
            self.users_btn.clicked.connect(lambda: self.switch_page(3))
            sidebar_layout.addWidget(self.users_btn)
        
        sidebar_layout.addStretch()
        
        # زر تسجيل الخروج
        logout_btn = QPushButton("🚪 تسجيل خروج")
        logout_btn.clicked.connect(self.logout)
        sidebar_layout.addWidget(logout_btn)
        
        # المحتوى الرئيسي
        self.content = QStackedWidget()
        
        # صفحة 1: لوحة التحكم
        self.dashboard_page = DashboardPage(is_admin)
        self.content.addWidget(self.dashboard_page)
        
        # صفحة 2: جميع التوثيقات
        self.evidences_page = EvidencesPage()
        self.content.addWidget(self.evidences_page)
        
        # صفحة 3: إحصائيات المراقبين
        if is_admin:
            self.stats_page = StatsPage()
            self.content.addWidget(self.stats_page)
            
            # صفحة 4: إدارة المستخدمين
            self.users_page = UsersPage()
            self.content.addWidget(self.users_page)
        
        # تخطيط الصفحة الرئيسية
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content, 1)
        
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # تحديث البيانات
        self.refresh_all()
    
    def switch_page(self, index):
        self.content.setCurrentIndex(index)
        self.refresh_current_page()
    
    def refresh_current_page(self):
        current = self.content.currentWidget()
        if hasattr(current, 'refresh'):
            current.refresh()
    
    def refresh_all(self):
        self.dashboard_page.refresh()
        self.evidences_page.refresh()
        if self.is_admin:
            self.stats_page.refresh()
            self.users_page.refresh()
    
    def logout(self):
        try:
            requests.post(f"{BASE_URL}/api/logout")
        except:
            pass
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()


class DashboardPage(QWidget):
    """صفحة لوحة التحكم الرئيسية"""
    def __init__(self, is_admin):
        super().__init__()
        self.is_admin = is_admin
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # عنوان
        title = QLabel("لوحة التحكم")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # بطاقات الإحصائيات
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        
        self.total_card = self.create_card("إجمالي التوثيقات", "0", "📊")
        cards_layout.addWidget(self.total_card)
        
        self.today_card = self.create_card("توثيقات اليوم", "0", "📅")
        cards_layout.addWidget(self.today_card)
        
        if is_admin:
            self.users_card = self.create_card("عدد المراقبين", "0", "👥")
            cards_layout.addWidget(self.users_card)
        
        layout.addLayout(cards_layout)
        
        # التوثيقات الأخيرة
        recent_label = QLabel("آخر التوثيقات")
        recent_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(recent_label)
        
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["المراقب", "العنصر", "الشاهد", "التاريخ"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.recent_table)
    
    def create_card(self, title, value, icon):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        layout = QVBoxLayout(card)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(value_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666;")
        layout.addWidget(title_label)
        
        # تخزين مراجع للتحديث
        card.value_label = value_label
        return card
    
    def refresh(self):
        try:
            if self.is_admin:
                response = requests.get(f"{BASE_URL}/api/admin/all-evidences", timeout=10)
            else:
                response = requests.get(f"{BASE_URL}/api/get-my-evidences", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    evidences = data.get('data', [])
                    
                    # تحديث الإحصائيات
                    self.total_card.value_label.setText(str(len(evidences)))
                    
                    today_count = sum(1 for e in evidences 
                                    if e.get('created_at', '').startswith(datetime.now().strftime('%Y-%m-%d')))
                    self.today_card.value_label.setText(str(today_count))
                    
                    if self.is_admin:
                        users_count = len(set(e.get('username') for e in evidences))
                        self.users_card.value_label.setText(str(users_count))
                    
                    # عرض آخر 10 توثيقات
                    self.recent_table.setRowCount(min(10, len(evidences)))
                    for i, ev in enumerate(evidences[:10]):
                        self.recent_table.setItem(i, 0, QTableWidgetItem(ev.get('username', '-')))
                        self.recent_table.setItem(i, 1, QTableWidgetItem(str(ev.get('element_id', '-'))))
                        self.recent_table.setItem(i, 2, QTableWidgetItem(ev.get('witness_text', '-')[:50]))
                        self.recent_table.setItem(i, 3, QTableWidgetItem(ev.get('created_at', '-')[:10]))
                    
                    for i in range(self.recent_table.rowCount()):
                        self.recent_table.setRowHeight(i, 40)
        except Exception as e:
            print(f"خطأ في تحديث لوحة التحكم: {e}")


class EvidencesPage(QWidget):
    """صفحة عرض جميع التوثيقات"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # عنوان
        title = QLabel("جميع التوثيقات")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # زر التصدير
        export_btn = QPushButton("📥 تصدير إلى Excel")
        export_btn.clicked.connect(self.export_to_excel)
        layout.addWidget(export_btn)
        
        # جدول البيانات
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "المراقب", "العنصر", "الشاهد", "التاريخ", "الصورة"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
    
    def refresh(self):
        try:
            response = requests.get(f"{BASE_URL}/api/admin/all-evidences", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    evidences = data.get('data', [])
                    
                    self.table.setRowCount(len(evidences))
                    for i, ev in enumerate(evidences):
                        self.table.setItem(i, 0, QTableWidgetItem(str(i+1)))
                        self.table.setItem(i, 1, QTableWidgetItem(ev.get('username', '-')))
                        self.table.setItem(i, 2, QTableWidgetItem(str(ev.get('element_id', '-'))))
                        self.table.setItem(i, 3, QTableWidgetItem(ev.get('witness_text', '-')[:60]))
                        self.table.setItem(i, 4, QTableWidgetItem(ev.get('created_at', '-')[:10]))
                        
                        # زر عرض الصورة
                        btn = QPushButton("📷 عرض")
                        btn.clicked.connect(lambda checked, url=ev.get('image_url', ''): self.show_image(url))
                        self.table.setCellWidget(i, 5, btn)
                    
                    for i in range(self.table.rowCount()):
                        self.table.setRowHeight(i, 50)
        except Exception as e:
            print(f"خطأ في تحديث التوثيقات: {e}")
    
    def show_image(self, url):
        if url:
            dialog = QDialog()
            dialog.setWindowTitle("عرض الصورة")
            dialog.setModal(True)
            
            layout = QVBoxLayout(dialog)
            
            # تحميل الصورة
            try:
                response = requests.get(url, timeout=30)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                label = QLabel()
                label.setPixmap(pixmap.scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                layout.addWidget(label)
                
                close_btn = QPushButton("إغلاق")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)
                
                dialog.exec_()
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"لا يمكن تحميل الصورة: {e}")
    
    def export_to_excel(self):
        try:
            response = requests.get(f"{BASE_URL}/api/admin/all-evidences", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    df = pd.DataFrame(data.get('data', []))
                    filename = f"evidences_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    df.to_excel(filename, index=False)
                    QMessageBox.information(self, "نجاح", f"تم التصدير بنجاح إلى {filename}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل التصدير: {e}")


class StatsPage(QWidget):
    """صفحة إحصائيات المراقبين"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        title = QLabel("إحصائيات المراقبين")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["المراقب", "عدد التوثيقات", "آخر توثيق", "النشاط"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
    
    def refresh(self):
        try:
            response = requests.get(f"{BASE_URL}/api/admin/all-evidences", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    evidences = data.get('data', [])
                    
                    # تجميع حسب المراقب
                    stats = {}
                    for ev in evidences:
                        username = ev.get('username', 'unknown')
                        if username not in stats:
                            stats[username] = {'count': 0, 'last': None}
                        stats[username]['count'] += 1
                        created = ev.get('created_at')
                        if created and (not stats[username]['last'] or created > stats[username]['last']):
                            stats[username]['last'] = created
                    
                    self.table.setRowCount(len(stats))
                    for i, (username, data) in enumerate(stats.items()):
                        self.table.setItem(i, 0, QTableWidgetItem(username))
                        self.table.setItem(i, 1, QTableWidgetItem(str(data['count'])))
                        self.table.setItem(i, 2, QTableWidgetItem(data['last'][:10] if data['last'] else '-'))
                        
                        # نشاط المراقب
                        activity = "🟢 نشط" if data['count'] > 0 else "⚪ غير نشط"
                        self.table.setItem(i, 3, QTableWidgetItem(activity))
        except Exception as e:
            print(f"خطأ في تحديث الإحصائيات: {e}")


class UsersPage(QWidget):
    """صفحة إدارة المستخدمين"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        title = QLabel("إدارة المستخدمين")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # زر إضافة مستخدم
        add_btn = QPushButton("➕ إضافة مستخدم جديد")
        add_btn.clicked.connect(self.add_user)
        layout.addWidget(add_btn)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["اسم المستخدم", "الاسم الكامل", "النوع", "الإجراءات"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
    
    def refresh(self):
        try:
            response = requests.get(f"{BASE_URL}/api/admin/users", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    users = data.get('data', [])
                    
                    self.table.setRowCount(len(users))
                    for i, user in enumerate(users):
                        self.table.setItem(i, 0, QTableWidgetItem(user.get('username', '-')))
                        self.table.setItem(i, 1, QTableWidgetItem(user.get('full_name', '-')))
                        self.table.setItem(i, 2, QTableWidgetItem("مدير" if user.get('username') == 'admin' else "مراقب"))
                        
                        btn = QPushButton("🗑️ حذف")
                        btn.setEnabled(user.get('username') != 'admin')
                        btn.clicked.connect(lambda checked, u=user.get('username'): self.delete_user(u))
                        self.table.setCellWidget(i, 3, btn)
        except Exception as e:
            print(f"خطأ في تحديث المستخدمين: {e}")
    
    def add_user(self):
        dialog = QDialog()
        dialog.setWindowTitle("إضافة مستخدم جديد")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        
        username = QLineEdit()
        username.setPlaceholderText("اسم المستخدم")
        layout.addWidget(username)
        
        password = QLineEdit()
        password.setPlaceholderText("كلمة السر")
        password.setEchoMode(QLineEdit.Password)
        layout.addWidget(password)
        
        full_name = QLineEdit()
        full_name.setPlaceholderText("الاسم الكامل")
        layout.addWidget(full_name)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        def save():
            if not username.text():
                QMessageBox.warning(dialog, "تنبيه", "يرجى إدخال اسم المستخدم")
                return
            try:
                response = requests.post(
                    f"{BASE_URL}/api/admin/add-user",
                    json={
                        "username": username.text(),
                        "password": password.text() or "pass123",
                        "full_name": full_name.text()
                    }
                )
                if response.json().get('success'):
                    QMessageBox.information(dialog, "نجاح", "تم إضافة المستخدم بنجاح")
                    dialog.accept()
                    self.refresh()
                else:
                    QMessageBox.warning(dialog, "خطأ", response.json().get('error', 'فشل الإضافة'))
            except Exception as e:
                QMessageBox.warning(dialog, "خطأ", str(e))
        
        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec_()
    
    def delete_user(self, username):
        reply = QMessageBox.question(self, "تأكيد", f"هل أنت متأكد من حذف المستخدم {username}؟",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.post(
                    f"{BASE_URL}/api/admin/delete-user",
                    json={"username": username, "id": 0}
                )
                if response.json().get('success'):
                    QMessageBox.information(self, "نجاح", "تم حذف المستخدم بنجاح")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "خطأ", response.json().get('error', 'فشل الحذف'))
            except Exception as e:
                QMessageBox.warning(self, "خطأ", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # تعيين التطبيق ليدعم اللغة العربية
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    login_window = LoginWindow()
    login_window.show()
    
    sys.exit(app.exec_())
