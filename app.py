import io
from urllib.parse import urlparse
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import os
import uuid
import base64
from datetime import datetime
import sqlite3
import json
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-12345'
CORS(app)

# ============ إعداد المسارات للملفات ============
BASE_DIR = os.environ.get('RENDER', False) and '/tmp' or os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'images')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'evidence.db')

# إعداد المجلدات الثابتة - تأكد من أن المسار مطلق وليس نسبي
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
app.static_folder = STATIC_FOLDER
app.static_url_path = '/static'



# ============ إعدادات Supabase ============
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
# ============ دوال إدارة المستخدمين ============

@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    """جلب جميع المستخدمين"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, full_name, 'user' as type FROM users ORDER BY id")
    rows = c.fetchall()
    conn.close()
    
    users = [{'id': r[0], 'username': r[1], 'full_name': r[2], 'type': r[3]} for r in rows]
    return jsonify({'success': True, 'data': users})

@app.route('/api/admin/add-user', methods=['POST'])
def admin_add_user():
    """إضافة مستخدم جديد"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'اسم المستخدم وكلمة السر مطلوبان'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # التحقق من عدم وجود المستخدم
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'اسم المستخدم موجود مسبقاً'})
    
    try:
        c.execute("INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
                  (username, password, full_name))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم إضافة المستخدم بنجاح'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/update-user', methods=['POST'])
def admin_update_user():
    """تعديل مستخدم (اسم المستخدم، الاسم الكامل، كلمة السر)"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    user_id = data.get('id')
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    old_username = data.get('old_username')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    updates = []
    values = []
    
    if username and username != old_username:
        # التحقق من عدم وجود اسم المستخدم الجديد
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'اسم المستخدم موجود مسبقاً'})
        updates.append("username = ?")
        values.append(username)
        
        # تحديث username في جدول evidences أيضاً
        c.execute("UPDATE evidences SET username = ? WHERE username = ?", (username, old_username))
    
    if password:
        updates.append("password = ?")
        values.append(password)
    if full_name:
        updates.append("full_name = ?")
        values.append(full_name)
    
    if not updates:
        conn.close()
        return jsonify({'success': False, 'error': 'لا توجد بيانات للتحديث'})
    
    values.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    
    try:
        c.execute(query, values)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم تحديث المستخدم بنجاح'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete-user', methods=['POST'])
def admin_delete_user():
    """حذف مستخدم"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    user_id = data.get('id')
    username = data.get('username')
    
    # منع حذف المدير الرئيسي
    if username == 'admin':
        return jsonify({'success': False, 'error': 'لا يمكن حذف حساب المدير الرئيسي'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # حذف توثيقات المستخدم أولاً
        c.execute("DELETE FROM evidences WHERE username=?", (username,))
        # ثم حذف المستخدم
        c.execute("DELETE FROM users WHERE id=? AND username!=?", (user_id, 'admin'))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم حذف المستخدم بنجاح'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/reset-password', methods=['POST'])
def admin_reset_password():
    """إعادة تعيين كلمة السر لمستخدم"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    user_id = data.get('id')
    new_password = data.get('new_password', 'pass123')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'تم تغيير كلمة السر إلى: {new_password}'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
# ============ بيانات العناصر والشواهد (21 عنصراً كاملاً) ============
ELEMENTS = {
    "1-1-1-1": {"title": "الخطة التشغيلية والمتابعة", "witnesses": [
        "1- وجود الخطة التشغيلية / تحليل"
    ]},
    "2-1-1-1": {"title": "تتابع المدرسة", "witnesses": [
        "1- شواهد ما هو موجود وفي الخطة الشهرية المتابعة",
        "2- استمارة المتابعة",
        "3- تصاميم إذا وصلوا وحدت",
        "4- اجتماع إداري لتصميم المتابعة"
    ]},
    "1-1-2-1": {"title": "القيم الإسلامية والهوية الوطنية", "witnesses": [
        "1- القيم الإسلامية والهوية الوطنية",
        "2- يوم الوطني",
        "3- يوم التأسيس - يوم المعلم (تقدير المعلم)",
        "4- انتظار في صفحة التميز بين القيم",
        "5- شراكة أولياء الأمور",
        "6- مشاركة الطلاب"
    ]},
    "1-2-2-1": {"title": "ميثاق مهنة التعليم واللجان", "witnesses": [
        "1- اجتماع المعلمين عن ميثاق مهنة التعليم",
        "2- توقيع المعلمين على الاطلاع على ميثاق مهنة التعليم",
        "3- زيد عن الميثاق",
        "4- مشاركة معلمين في اللجان",
        "5- اللجان المدرسية",
        "6- تواصل المعلم مع أولياء الأمور",
        "7- الانضباط الوظيفي (كتاب النشاط)",
        "8- كلمات الانضباط",
        "9- المناوبة والإشراف"
    ]},
    "3-1-2-1": {"title": "الانضباط المدرسي", "witnesses": [
        "1- نشرة تثقيفية",
        "2- السلوك الانضباطي موقع الطلاب",
        "3- الغياب والتأخير",
        "4- معالجة التأخر",
        "5- معالجة الغياب",
        "6- رسائل الغياب",
        "7- محاضر هروب من الحصة والخطط العلاجية"
    ]},
    "1-2-2-2": {"title": "السلوك الإيجابي", "witnesses": [
        "1- تقييم السلوك الإيجابي 20%",
        "2- مشاكل الطلاب السلوكية وعلاجها",
        "3- تعزيز السلوك الإيجابي",
        "4- ورش عمل للسلوك الإيجابي",
        "5- حوار الطلاب",
        "6- اللقاء",
        "7- برامج وزارية",
        "8- شهادات شكر",
        "9- رسائل شكر",
        "10- برامج غرس القيم الإسلامية"
    ]},
    "2-1-1-5": {"title": "خطة النشاط والموهوبين", "witnesses": [
        "1- حفز الموهوبين (السجل)",
        "2- الدخول في برنامج الموهوبين",
        "3- مسابقة الموهوبين",
        "4- بحوث",
        "5- مسابقة علمية",
        "6- دورات تدريبية كإدارة الوقت"
    ]},
    "1-2-1-1": {"title": "زيارة المعلمين والطلاب", "witnesses": [
        "1- سجل زيارات المعلمين",
        "2- حملة تطوعية لجنة النظام من الطلاب",
        "3- حوار الطلاب",
        "4- مشاركة (أنس الطلاب)",
        "5- مشاركة أكثر من طلاب في مشروع (عمل في مادة علمية)"
    ]},
    "2-1-3-1": {"title": "مشاركة الأسرة", "witnesses": [
        "1- مجلس الآباء",
        "2- مشاركة للأسرة في الأنشطة الطلابية والعمل",
        "3- أعمال عند الموجهين (عن بعد)",
        "4- مشاركة المدرسة في الأيام والمناسبات العالمية",
        "5- قروب قواعد وأولياء أمور واتس، تليجرام",
        "6- تواصل مع أولياء في علاج ضعف الطلاب",
        "7- استبيان رضا المستفيد",
        "8- مشاركة أولياء الأمور في الجوائز"
    ]},
    "2-1-3-2": {"title": "الشراكة المجتمعية", "witnesses": [
        "1- شراكات مع شركات تجارية",
        "2- شراكات مع جهات خيرية",
        "3- خدمة مجتمعية (تطوع) النظام في المدرسة (طلاب)",
        "4- مساهمة أولياء الأمور في جوائز المدرسة",
        "5- حملات توعوية للحفاظ على البيئة",
        "6- نشرات صحية على قروبات المدرسة",
        "7- درس عمل للمجتمع المحلي"
    ]},
    "1-4-1-1": {"title": "الكادر التعليمي", "witnesses": [
        "1- بيانات المعلمين",
        "2- الرخص المهنية",
        "3- تكاليف المعلمين والمعلمات",
        "4- تكاليف المعلمين للعضوية",
        "5- الدورات",
        "6- شهادات الشكر",
        "7- وثائق تخرج",
        "8- مشاركة معلم في إخراج"
    ]},
    "1-4-1-3": {"title": "الميزانية والصرف", "witnesses": [
        "1- فريق الميزانية",
        "2- صندوق الصرف",
        "3- عقود تجارية",
        "4- شراكة مجتمعية أولياء الأمور",
        "5- تكريم الطلاب",
        "6- تكريم المعلمين",
        "7- فواتير الصرف"
    ]},
    "1-4-1-4": {"title": "الرخص المهنية والتطوير", "witnesses": [
        "1- حث المعلمين على دخول الدورات عبر المنصات",
        "2- حصر أسماء في سجل تخصص الرخص",
        "3- حصر الرتب",
        "4- توفير دورات ورقية - مدرب رئيسي",
        "5- تكريم الحاصلين على الرخص المهنية"
    ]},
    "2-5-4-1": {"title": "التطوير المهني", "witnesses": [
        "1- سجل النمو المهني",
        "2- تبادل الزيارات",
        "3- المجتمع التعليمي",
        "4- كوت المعلم",
        "5- دروس تطبيقية",
        "6- دورات وورش تعلم",
        "7- الأداء الوظيفي",
        "8- حصر احتياج المعلمين للتدريب",
        "9- نواتج التعلم"
    ]},
    "1-4-2-1": {"title": "التقويم الذاتي", "witnesses": [
        "1- وجود فريق تقويم",
        "2- سجل التقويم الذاتي",
        "3- كل لجنة التميز",
        "4- ورش تدريب الفريق",
        "5- نشر ثقافة التقويم الذاتي للطلاب",
        "6- ورش للمعلمين",
        "7- تقرير التقويم الخارجي"
    ]},
    "1-4-1-7": {"title": "خطة التحسين", "witnesses": [
        "1- وضع خطة تحسين",
        "2- سجل متابعة التنفيذ",
        "3- شواهد على الخطة"
    ]},
    "16-1-2-1": {"title": "فرص متكافئة", "witnesses": [
        "1- سجل توزيع الكتب",
        "2- تنوع أساليب التدريس والأنشطة",
        "3- مشاركة في الأنشطة",
        "4- تكريم الطلاب المتفوقين",
        "5- تكريم الطلاب ذات السلوك الإيجابي",
        "6- نزاع المسابقات على قروب الواتس التعليمي",
        "7- وجود أولياء الأمور في التليجرام",
        "8- لجنة كشوف المتابعة"
    ]},
    "2-1-1-2": {"title": "تدعيم المدرسة والمتابعة", "witnesses": [
        "1- سجل متابعة المنصة",
        "2- خطة الأسبوعية للمعلمين",
        "3- خطة المنهج",
        "4- سجل زيارة الإدارة للمعلمين لمطابقة الأمان مع الخطط",
        "5- تنفيذ توصيات الزائر",
        "6- سجل الكشوف",
        "7- دورة من استراتيجيات التدريس",
        "8- دورة في استخدام التقنية",
        "9- توفير استراتيجيات للمعلمين",
        "10- سجل زيارات المعلمين",
        "11- استمارة توثيق الزيارة",
        "12- المجتمع التعليمي",
        "13- الخطط الأسبوعية"
    ]},
    "2-1-1-4": {"title": "المنصات الإلكترونية", "witnesses": [
        "1- واجبات المنصة",
        "2- الإثراءات على المنصة",
        "3- الاختبارات الإلكترونية",
        "4- ألعاب تعليمية إلكترونية",
        "5- منصة تميز",
        "6- استخدام الكتاب",
        "7- جدول المنصة",
        "8- سجل متابعة المنصة",
        "9- مختبرات افتراضية",
        "10- برامج مسابقات",
        "11- حصر دخول الطلاب للمنصة – نسبة إنجاز"
    ]},
    "2-1-1-5": {"title": "الأنشطة التعليمية التطبيقية", "witnesses": [
        "1- تنفيذ أنشطة تعليمية تطبيقية للطلاب (مثل: كواكب الأرض، المجموعة الشمسية، حساب زاوية السقوط)",
        "2- التجارب العملية",
        "3- مهارات قراءات في الإذاعة",
        "4- سجل المتابعة"
    ]},
    "2-1-1-9": {"title": "دافعية التعلم", "witnesses": [
        "1- مجلس الطلاب",
        "2- مشاركة الطلاب في الأنشطة الصيفية",
        "3- تكليف الطلاب بالمهام القيادية",
        "4- استمارة قياس رضا الطالب (المعلم)",
        "5- احتواء الطالب وتقديم الأمان (المناوبة)",
        "6- المعلم الصغير",
        "7- أعمال فنية متعلقة بالحياة العملية",
        "8- التكريم"
    ]},
    "2-2-1-1": {"title": "استراتيجيات التدريس", "witnesses": [
        "1- استخدام استراتيجيات متنوعة",
        "2- أوراق عمل - اختبارات إلكترونية - ورقية",
        "3- مهام أدائية",
        "4- المعلم الصغير",
        "5- ألعاب تعليمية",
        "6- نشر الثقافة بأعمال المدرسة"
    ]},
    "2-2-1-3": {"title": "تحليل النتائج", "witnesses": [
        "1- تحليل نتائج",
        "2- نسبة النجاح والرسوب",
        "3- تحليل توزيع الدرجات حسب المستويات",
        "4- شواهد تقرير النجاح",
        "5- معالجة الفجوة",
        "6- الخطط الإجرائية"
    ]},
    "2-2-1-4": {"title": "التقييم والمتابعة", "witnesses": [
        "1- سجل الكتابة",
        "2- الكتاب المدرسي والتعليقات",
        "3- الدفتر",
        "4- نتائج الاختبارات",
        "5- مشاركة ولي الأمر",
        "6- الخطط الأسبوعية",
        "7- شهادات الشكر والانجاز"
    ]},
    "2-1-1-1": {"title": "خطط نافس والدعم", "witnesses": [
        "1- خطط نافس",
        "2- تنفيذ المعلمين للحصص الداعمة",
        "3- مجلس الآباء",
        "4- شواهد الاختبارات المحاكية",
        "5- شواهد التكريم",
        "6- القيم الإسلامية",
        "7- الخطة التشغيلية المتعلقة",
        "8- مشاركة الطلاب",
        "9- الصلاة",
        "10- أعمال تراثية"
    ]},
    "4-1-1-3": {"title": "معالجة الفاقد القرائي", "witnesses": [
        "1- تقرير من منصة نافس بين السنوات السابقة يوضح مهارات الضعف في أي جانب",
        "2- رصد فجوة القراءة",
        "3- اختبارات دورية",
        "4- خطة معالجة الفاقد القرائي تنفيذ حصص إضافية للمهارات",
        "5- نادي القراءة توثيق نشاط طلاب للقراءة يشهده الطلاب الضعاف",
        "6- مبادرة مسابقة القراءة الذهبية وقت",
        "7- بطاقة متابعة الطلاب من الضعف إلى الإتقان",
        "8- تلخيص القصص",
        "9- شهادة شكر",
        "10- التحدث في الإذاعة"
    ]},
    "2-1-1-5": {"title": "الرياضيات والعلوم", "witnesses": [
        "1- رسم منحنى النمو الرياضي",
        "2- تحليل الفاقد التعليمي",
        "3- اختبارات محاكية",
        "4- سجل المجتمعات المهنية توثيق تعاون المعلمين طرق التدريس",
        "5- سجل أولمبياد الرياضيات",
        "6- ملف التربية الرياضية التطبيقية نماذج إعداد طلابية تحول الرياضيات للواقع",
        "7- سجل الدعم التعليمي الفردي",
        "8- مراجعة خطة التحسين",
        "9- إحصائية الواجبات الرقمية"
    ]},
    "3-2-11": {"title": "الاعتزاز بالهوية الوطنية", "witnesses": [
        "1- أداء النشيد الوطني مقاطع فيديو",
        "2- ارتداء الزي الوطني",
        "3- لوحات ولاء وانتماء جداريات",
        "4- بحوث عن رؤية 2030 ومشاريع الرؤية",
        "5- بطاقة (هويتي وطني) معلومات عن تاريخ الدولة السعودية أئمتها وملوكها",
        "6- زيارات المعالم التاريخية",
        "7- مسابقات الرسم الوطنية",
        "8- تفعيل المناسبات الوطنية"
    ]},
    "2-1-2-2": {"title": "الإيجابية والتنمر", "witnesses": [
        "1- مبادرة (شكراً زميلي) صناديق أو لوحات يتبادل فيها الطلاب رسائل الشكر والتقدير",
        "2- لوحة (مبدع الأسبوع) تكريم الطلاب بناءً على تميزهم الشخصي وليس الدراسي فقط",
        "3- ورشة (الحد من التنمر)",
        "4- حوار الطلاب",
        "5- استبيان المناخ النفسي، تظهر شعور الطلاب بالأمان والقبول",
        "6- دمج ذوي الإعاقة التفاعل الإيجابي بين الطلاب العاديين وذوي الإعاقة"
    ]},
    "2-2-1-2": {"title": "الممارسات الصحية", "witnesses": [
        "1- تقرير من الوحدة الصحية",
        "2- الفحص الطبي",
        "3- مبادرة (ارتقاء) تشجيع الطلاب",
        "4- النشاط الرياضي اليومي التمارين الصباحية وحصة التربية البدنية",
        "5- حملة مدينة بلا تدخين، منشورات وورش عمل توعوية حول أضرار التدخين",
        "6- دوري يوم الصحة العالمي",
        "7- جداريات صحتي في غذائي",
        "8- حملة لا للسهر",
        "9- مسابقة أفضل فطور صحي"
    ]},
    "2-2-1-4": {"title": "الأعمال التطوعية", "witnesses": [
        "1- سجل ساعات التطوع",
        "2- تطوع الطلاب والمعلمين للمدرسة",
        "3- مساندة طلاب ذوي الإعاقة",
        "4- مدرسة نظيفة",
        "5- امشِ في نفس",
        "6- المساندة الدراسية (مساندة الطلاب بعضهم لبعض)"
    ]},
    "2-2-1-5": {"title": "قواعد السلوك", "witnesses": [
        "1- سجل الغياب والتأخير",
        "2- الانضباط المدرسي",
        "3- ميثاق الانضباط السلوكي",
        "4- كل صف في لغات",
        "5- تعديل السلوك",
        "6- شهادات شكر",
        "7- تحمل الالتزام بالسلوك المعرفي",
        "8- تحسين سلوك الطالب"
    ]},
    "2-1-6": {"title": "الخبرة والبحث", "witnesses": [
        "1- البحث الإلكتروني تصميم من أعمال الطلاب",
        "2- مبادرة المعلم الصغير",
        "3- مهارات اختيار الطلاب للدورات من الإنترنت",
        "4- ورش إدارة الوقت والمعلومات",
        "5- مباراة الملحنين والخرائط الذهنية",
        "6- سجل زيارة المكتبة"
    ]},
    "2-2-1-7": {"title": "الاعتزاز بالتراث", "witnesses": [
        "1- تراثنا الأصيل معرض",
        "2- يوم اللغة العربية",
        "3- القهوة السعودية",
        "4- تاريخ العمارة السعودية",
        "5- الرحلات السياحية والوطنية",
        "6- مسابقة الشعر والأدب الشعبي",
        "7- مهرجان الثقافات ملتقى مدرسة تعرض فيها ثقافات المملكة المختلفة (الزي – المأكل – اللهجة)"
    ]},
    "4-1-1-1": {"title": "البيئة المدرسية والسلامة", "witnesses": [
        "1- توفير بيئة يسودها الهدوء",
        "2- سجل الصيانة",
        "3- مهارات نظام المدرسة",
        "4- جزء من المصلى (جاهزية المصلى)",
        "5- سجل لوحات الطوارئ والإرشادات",
        "6- استبانة رضا مرفق التحسين"
    ]},
    "4-1-1-2": {"title": "المرافق والخدمات", "witnesses": [
        "1- مخطط المدرسة",
        "2- صور المنحدرات",
        "3- سجل توزيع الطلاب",
        "4- تقرير عن مواقع ذوي الاحتياجات",
        "5- مجموعة دورات المياه لذوي الإعاقة",
        "6- خطط الإخلاء"
    ]},
    "4-1-1-3": {"title": "المعامل والمرافق التعليمية", "witnesses": [
        "1- سجل جرد المعامل والعلوم",
        "2- تقرير سلامة المعامل",
        "3- توفر طفايات الحريق",
        "4- جدول استخدام المعامل",
        "5- تقرير المعمل الحاسب",
        "6- سجل الإنترنت"
    ]},
    "4-1-1-4": {"title": "المنشآت الرياضية والداعمة", "witnesses": [
        "1- الملاعب الرياضية",
        "2- غرفة المصادر",
        "3- نادي الموهبة",
        "4- ملاءمة البيئة المدرسية",
        "5- سجل حافلات النقل المدرسي",
        "6- غرفة الموجه الطلابي"
    ]},
    "4-2-1-1": {"title": "متطلبات السلامة", "witnesses": [
        "1- توفير بيئة بمتطلبات السلامة",
        "2- سجل أدوات الإطفاء",
        "3- تقرير تجربة الإخلاء",
        "4- لوحات مخارج الطوارئ",
        "5- كاشف الدخان والإنذار",
        "6- قرار تشكيل لجنة الطوارئ",
        "7- تقرير خطة الطوارئ",
        "8- صور مخارج الطوارئ",
        "9- استبيان الوعي بالأمن والسلامة",
        "10- نشر ثقافة الأمن والسلامة"
    ]}
}
# ============ دوال قاعدة البيانات ============
def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  full_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS evidences
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  element_id INTEGER,
                  element_title TEXT,
                  witness_id INTEGER,
                  witness_text TEXT,
                  image_path TEXT,
                  image_url TEXT,
                  synced INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # إضافة جدول صلاحيات المراقبين
    c.execute('''CREATE TABLE IF NOT EXISTS user_permissions
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                element_id TEXT,
                can_access INTEGER DEFAULT 1,
                UNIQUE(username, element_id))''')
    # إضافة 11 مستخدم (مدير + 10 مراقبين)
    users = [
        ('admin', '1', 'مدير النظام'),
        ('adl', '123', 'المراقب الأول'),
        ('has', '123', 'المراقب الثاني'),
        ('3', '123', 'المراقب الثالث'),
        ('observer4', 'pass123', 'المراقب الرابع'),
        ('observer5', 'pass123', 'المراقب الخامس'),
        ('observer6', 'pass123', 'المراقب السادس'),
        ('observer7', 'pass123', 'المراقب السابع'),
        ('observer8', 'pass123', 'المراقب الثامن'),
        ('observer9', 'pass123', 'المراقب التاسع'),
        ('observer10', 'pass123', 'المراقب العاشر')
    ]
    
    for username, password, full_name in users:
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
                      (username, password, full_name))
    conn.commit()
    conn.close()

init_local_db()

# ============ دوال Supabase ============
def upload_to_supabase(image_bytes, filename):
    """رفع صورة إلى Supabase Storage"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'image/jpeg'
        }
        
        # رفع إلى Supabase Storage
        url = f"{SUPABASE_URL}/storage/v1/object/evidence/{filename}"
        response = requests.post(url, headers=headers, data=image_bytes)
        
        if response.status_code in [200, 201]:
            # الحصول على الرابط العام
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/evidence/{filename}"
            return public_url
    except Exception as e:
        print(f"خطأ في رفع الصورة: {e}")
    return None

def sync_to_supabase():
    """مزامنة جميع البيانات المحلية إلى Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {'success': False, 'error': 'Supabase غير مهيأ'}
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM evidences WHERE synced = 0")
    rows = c.fetchall()
    
    synced_count = 0
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    for row in rows:
        try:
            # رفع الصورة إذا كانت موجودة محلياً
            image_url = None
            if row[6] and os.path.exists(row[6]):
                with open(row[6], 'rb') as f:
                    image_bytes = f.read()
                    filename = os.path.basename(row[6])
                    image_url = upload_to_supabase(image_bytes, filename)
            
            # حفظ البيانات في Supabase
            data = {
                'username': row[1],
                'element_id': row[2],
                'element_title': row[3],
                'witness_id': row[4],
                'witness_text': row[5],
                'image_url': image_url or row[6],
                'created_at': row[7] if len(row) > 7 else datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/evidences",
                headers=headers,
                json=data
            )
            
            if response.status_code in [200, 201]:
                # تحديث حالة المزامنة محلياً
                c.execute("UPDATE evidences SET synced = 1 WHERE id = ?", (row[0],))
                synced_count += 1
        except Exception as e:
            print(f"خطأ في مزامنة {row[0]}: {e}")
    
    conn.commit()
    conn.close()
    return {'success': True, 'synced': synced_count}

def sync_from_supabase():
    """جلب البيانات من Supabase إلى المحلي"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {'success': False, 'error': 'Supabase غير مهيأ'}
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    }
    
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/evidences",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            for item in data:
                # التحقق من عدم وجود البيانات مسبقاً
                c.execute("SELECT id FROM evidences WHERE image_url = ?", (item.get('image_url', ''),))
                if not c.fetchone():
                    c.execute('''INSERT INTO evidences 
                                 (username, element_id, element_title, witness_id, witness_text, image_url, synced)
                                 VALUES (?, ?, ?, ?, ?, ?, 1)''',
                              (item['username'], item['element_id'], item['element_title'],
                               item['witness_id'], item['witness_text'], item.get('image_url', '')))
            
            conn.commit()
            conn.close()
            return {'success': True, 'synced': len(data)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    return {'success': False, 'synced': 0}
def get_file_preview(file_url, file_type):
    """إنشاء معاينة للملف (صورة مصغرة)"""
    try:
        # تحميل الملف من الرابط
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            return None
        
        file_bytes = io.BytesIO(response.content)
        
        # معالجة حسب نوع الملف
        if file_type == 'application/pdf':
            # محاولة استخراج الصفحة الأولى كصورة (يتطلب pdf2image)
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(response.content, first_page=1, last_page=1)
                if images:
                    img_io = io.BytesIO()
                    images[0].save(img_io, 'PNG')
                    img_io.seek(0)
                    return base64.b64encode(img_io.getvalue()).decode('utf-8')
            except:
                return None
                
        elif 'word' in file_type or 'document' in file_type:
            # ملف Word - إرجاع أيقونة
            return None
            
        elif 'spreadsheet' in file_type or 'excel' in file_type:
            # ملف Excel - إرجاع أيقونة
            return None
            
        elif 'presentation' in file_type or 'powerpoint' in file_type:
            # ملف PowerPoint - إرجاع أيقونة
            return None
            
        return None
    except Exception as e:
        print(f"خطأ في إنشاء المعاينة: {e}")
        return None
@app.route('/api/admin/permissions', methods=['GET'])
def admin_get_permissions():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, element_id, can_access FROM user_permissions")
    rows = c.fetchall()
    conn.close()
    
    permissions = [{'username': r[0], 'element_id': r[1], 'can_access': r[2]} for r in rows]
    return jsonify({'success': True, 'data': permissions})

@app.route('/api/admin/set-permission', methods=['POST'])
def admin_set_permission():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    username = data.get('username')
    element_id = data.get('element_id')
    can_access = data.get('can_access', 1)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_permissions (username, element_id, can_access)
                 VALUES (?, ?, ?)''', (username, element_id, can_access))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'تم تحديث الصلاحية'})

@app.route('/api/admin/get-user-elements', methods=['GET'])
def admin_get_user_elements():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    username = request.args.get('username')
    if not username:
        return jsonify({'success': False, 'error': 'اسم المستخدم مطلوب'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT element_id FROM user_permissions WHERE username=? AND can_access=1", (username,))
    rows = c.fetchall()
    conn.close()
    
    elements = [r[0] for r in rows]
    return jsonify({'success': True, 'data': elements})

@app.route('/api/admin/all-elements', methods=['GET'])
def admin_all_elements():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    return jsonify({'success': True, 'elements': ELEMENTS})
@app.route('/api/get-my-elements', methods=['GET'])
def get_my_elements():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT element_id FROM user_permissions WHERE username=? AND can_access=1", (session['username'],))
    rows = c.fetchall()
    conn.close()
    
    allowed_elements = [r[0] for r in rows]
    
    # إذا لم تكن هناك صلاحيات محددة، أعطِ جميع العناصر
    if not allowed_elements:
        allowed_elements = list(ELEMENTS.keys())
    
    return jsonify({'success': True, 'data': allowed_elements})

@app.route('/api/get-file-preview', methods=['GET'])
def get_file_preview_api():
    """API للحصول على معاينة الملف"""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    file_url = request.args.get('url')
    file_type = request.args.get('type', '')
    
    if not file_url:
        return jsonify({'success': False, 'error': 'رابط غير صالح'})
    
    preview = get_file_preview(file_url, file_type)
    if preview:
        return jsonify({'success': True, 'preview': f'data:image/png;base64,{preview}'})
    
    return jsonify({'success': False, 'error': 'لا يمكن إنشاء معاينة لهذا الملف'})
# ============ صفحات HTML مدمجة ============
LOGIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الدخول</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a2a6c,#b21f1f,#fdbb4d);min-height:100vh;display:flex;justify-content:center;align-items:center}
.login-container{background:rgba(255,255,255,0.95);border-radius:20px;padding:40px;width:90%;max-width:400px;box-shadow:0 25px 45px rgba(0,0,0,0.2)}
.logo{text-align:center;font-size:64px;margin-bottom:20px}h1{text-align:center;color:#333;margin-bottom:30px}
input{width:100%;padding:14px;margin:10px 0;border:2px solid #e0e0e0;border-radius:10px;font-size:16px}
input:focus{border-color:#667eea;outline:none}
button{width:100%;padding:14px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;border-radius:10px;font-size:18px;font-weight:bold;cursor:pointer}
button:hover{transform:translateY(-2px);box-shadow:0 5px 15px rgba(0,0,0,0.2)}
.error{background:#fee;color:#c00;padding:10px;border-radius:8px;margin-top:15px;text-align:center;display:none}
.info{text-align:center;margin-top:25px;color:#666;font-size:14px}
</style>
</head>
<body>
<div class="login-container"><div class="logo">📸</div><h1>نظام توثيق الشواهد</h1>
<form id="loginForm"><input type="text" id="username" placeholder="اسم المستخدم" required><input type="password" id="password" placeholder="كلمة السر" required><button type="submit">دخول</button></form>
<div class="error" id="errorMsg"></div><div class="info">🔐HF2026 المطوع</div></div>
<script>
document.getElementById('loginForm').addEventListener('submit',async(e)=>{
e.preventDefault();const u=document.getElementById('username').value,p=document.getElementById('password').value;
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
const d=await r.json();if(d.success){if(d.is_admin)window.location.href='/admin';else window.location.href='/dashboard';}
else{document.getElementById('errorMsg').textContent=d.error||'خطأ في تسجيل الدخول';document.getElementById('errorMsg').style.display='block';}});
</script>
</body>
</html>
'''

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة التوثيق</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:#f0f2f5}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100%;background:linear-gradient(180deg,#1a2a6c,#b21f1f);color:white;padding:20px;box-shadow:-2px 0 10px rgba(0,0,0,0.1);z-index:100}
.sidebar h3{text-align:center;margin-bottom:30px;padding-bottom:15px;border-bottom:2px solid rgba(255,255,255,0.3)}
.nav-item{padding:12px 15px;margin:8px 0;border-radius:12px;cursor:pointer;background:rgba(255,255,255,0.1);transition:0.3s}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,0.25);transform:translateX(-5px)}
.logout-btn{width:100%;margin-top:40px;background:rgba(255,255,255,0.2);border:none;color:white;padding:12px;border-radius:10px;cursor:pointer}
.main-content{margin-right:260px;padding:20px;min-height:100vh}
.header{background:white;border-radius:15px;padding:20px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,0.1);display:flex;justify-content:space-between;align-items:center}
.elements-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px}
.element-card{background:white;border-radius:15px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);transition:0.3s}
.element-card:hover{transform:translateY(-5px);box-shadow:0 5px 25px rgba(0,0,0,0.15)}
.element-title{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:15px;font-weight:bold}
.witnesses-list{padding:15px;max-height:400px;overflow-y:auto}
.witness-item{background:#f8f9fa;margin:8px 0;padding:10px;border-radius:10px;display:flex;justify-content:space-between;align-items:center}
.witness-text{flex:1;font-size:13px;margin-left:10px}
.camera-icon{font-size:24px;cursor:pointer;padding:5px;border-radius:50%;transition:0.2s}
.camera-icon:hover{background:#e0e0e0}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:1000}
.modal-content{position:relative;width:90%;max-width:500px;margin:50px auto;background:white;border-radius:20px;padding:20px}
video{width:100%;border-radius:15px}
.capture-btn{background:#28a745;color:white;padding:12px;border:none;border-radius:10px;margin-top:15px;width:100%;cursor:pointer}
.close-modal{background:#dc3545;margin-top:10px}
.history-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:15px}
.history-card{background:white;border-radius:10px;padding:10px;text-align:center}
.history-card img{width:100%;height:150px;object-fit:cover;border-radius:8px}
@media(max-width:768px){.sidebar{width:200px}.main-content{margin-right:200px}.elements-grid{grid-template-columns:1fr}}
@media(min-width:769px){.sidebar{display:block !important}.main-content{margin-right:260px}#menuToggleBtn{display:none}}
@media(max-width:768px){.sidebar{position:fixed;right:0;top:0;width:200px;height:100%;z-index:200}.main-content{margin-right:0 !important}}
</style>
</head>
<body>
<div class="sidebar" id="sidebar" style="display:none;"><h3>📸 نظام التوثيق</h3>
<div class="nav-item active" onclick="showSection('dashboard');toggleSidebar()"><span style="margin-left:10px;">📋</span> لوحة التوثيق</div>
<div class="nav-item" onclick="showSection('stats');toggleSidebar()"><span style="margin-left:10px;">📊</span> إحصائياتي</div>
<div class="nav-item" onclick="showSection('history');toggleSidebar()"><span style="margin-left:10px;">🖼️</span> توثيقاتي السابقة</div>
<button class="logout-btn" onclick="showChangePasswordModal()" style="margin-bottom:10px;">🔑 تغيير كلمة السر</button>
<button class="logout-btn" onclick="logout()">🚪 تسجيل خروج</button></div>
<div class="main-content">
<div style="display:flex; align-items:center; margin-bottom:10px;">
    <button id="menuToggleBtn" style="background:#667eea; color:white; border:none; border-radius:8px; padding:10px 15px; font-size:16px; cursor:pointer; margin-left:10px;">☰ القائمة</button>
</div><div class="header"><h2>مرحباً <span id="usernameDisplay">{{ username }}</span></h2><div>📅 <span id="dateDisplay"></span></div></div>
<div id="dashboardSection"><div class="elements-grid" id="elementsGrid"></div></div>
<div id="statsSection" style="display:none;"><div style="background:white;border-radius:15px;padding:20px;"><h3>📊 إحصائيات التوثيقات</h3><div id="statsNumbers" style="margin-top:20px;"></div></div></div>
<div id="historySection" style="display:none;"><div style="background:white;border-radius:15px;padding:20px;"><h3>🖼️ توثيقاتي السابقة</h3><div id="historyGrid" class="history-grid"></div></div></div></div>
<div id="cameraModal" class="modal"><div class="modal-content"><video id="video" autoplay playsinline></video><div style="display:flex; gap:10px; margin-top:15px;"><button class="capture-btn" id="switchCameraBtn" style="background:#17a2b8; flex:1;">🔄 تبديل الكاميرا</button><button class="capture-btn" id="uploadImageBtn" style="background:#6c757d; flex:1;">📁 اختيار من المعرض</button></div><button class="capture-btn" onclick="capturePhoto()" style="margin-top:10px;">📷 التقاط صورة</button><button class="capture-btn close-modal" onclick="closeCamera()" style="margin-top:10px; background:#dc3545;">إلغاء</button></div></div>
<canvas id="canvas" style="display:none"></canvas>
<div id="changePasswordModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:3000; justify-content:center; align-items:center;">
    <div style="background:white; border-radius:15px; padding:25px; width:90%; max-width:400px;">
        <h3 style="margin-bottom:15px;">🔑 تغيير كلمة السر</h3>
        <input type="password" id="oldPassword" placeholder="كلمة السر الحالية" style="width:100%; padding:10px; margin:10px 0; border:1px solid #ddd; border-radius:8px;">
        <input type="password" id="newPassword" placeholder="كلمة السر الجديدة" style="width:100%; padding:10px; margin:10px 0; border:1px solid #ddd; border-radius:8px;">
        <input type="password" id="confirmPassword" placeholder="تأكيد كلمة السر الجديدة" style="width:100%; padding:10px; margin:10px 0; border:1px solid #ddd; border-radius:8px;">
        <div style="display:flex; gap:10px; margin-top:15px;">
            <button onclick="changePassword()" style="flex:1; background:#28a745; color:white; padding:10px; border:none; border-radius:8px;">تأكيد</button>
            <button onclick="closeChangePasswordModal()" style="flex:1; background:#dc3545; color:white; padding:10px; border:none; border-radius:8px;">إلغاء</button>
        </div>
        <div id="passwordMsg" style="color:#c00; margin-top:10px; text-align:center;"></div>
    </div>
</div>
<script>
let elements = {};
let allowedElements = [];

async function loadAllowedElements() {
    const response = await fetch('/api/get-my-elements');
    const data = await response.json();
    if (data.success) {
        allowedElements = data.data;
        // تصفية العناصر المسموحة فقط
        const allElements = {{ elements | tojson }};
        elements = {};
        for (const [id, element] of Object.entries(allElements)) {
            if (allowedElements.includes(id)) {
                elements[id] = element;
            }
        }
        displayElements();
    } else {
        // في حالة الخطأ، عرض جميع العناصر
        elements = {{ elements | tojson }};
        displayElements();
    }
}
let currentElementId=null,currentWitnessId=null,stream=null;
let currentFacingMode = 'environment';
function showSection(section){
    document.getElementById('dashboardSection').style.display=section==='dashboard'?'block':'none';
    document.getElementById('statsSection').style.display=section==='stats'?'block':'none';
    document.getElementById('historySection').style.display=section==='history'?'block':'none';
    if(section==='stats')loadStats();
    if(section==='history')loadHistory();
}
function displayElements(){
    const grid=document.getElementById('elementsGrid');grid.innerHTML='';
    for(const[id,element]of Object.entries(elements)){
        const card=document.createElement('div');card.className='element-card';
        card.innerHTML=`<div class="element-title">📚 العنصر ${id}: ${element.title}</div><div class="witnesses-list" id="witnesses-${id}"></div>`;
        grid.appendChild(card);
        const list=document.getElementById(`witnesses-${id}`);
        element.witnesses.forEach((text,idx)=>{
            const div=document.createElement('div');div.className='witness-item';
            div.innerHTML=`<span class="witness-text" style="cursor:pointer; flex:1;" onclick="showWitnessEvidences('${id}',${idx+1},'${text.replace(/'/g, "\\'")}')">${idx+1}. ${text}</span><span class="camera-icon" onclick="openCamera('${id}',${idx+1})">📷</span>`;
            list.appendChild(div);
        });
    }
}
async function openCamera(elementId,witnessId){
    currentElementId=elementId;currentWitnessId=witnessId;
    document.getElementById('cameraModal').style.display='block';
    currentFacingMode = 'environment';
    const constraints = {
        video: {
            facingMode: { exact: currentFacingMode }
        }
    };
    try{
        if(stream) stream.getTracks().forEach(track => track.stop());
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        document.getElementById('video').srcObject = stream;
    } catch(err){
        console.warn("Back camera failed, trying default camera", err);
        try{
            if(stream) stream.getTracks().forEach(track => track.stop());
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            document.getElementById('video').srcObject = stream;
            currentFacingMode = 'environment';
        } catch(e){
            alert('لا يمكن الوصول إلى الكاميرا: '+e.message);
        }
    }
}
async function capturePhoto(){
    const video=document.getElementById('video');const canvas=document.getElementById('canvas');
    if(video.videoWidth && video.videoHeight){
        // عرض الصورة للمعاينة
        canvas.width=video.videoWidth;canvas.height=video.videoHeight;
        canvas.getContext('2d').drawImage(video,0,0);
        const imageData=canvas.toDataURL('image/jpeg',0.9);
        
        // إظهار معاينة الصورة
        const previewDiv = document.createElement('div');
        previewDiv.style.position = 'fixed';
        previewDiv.style.top = '0';
        previewDiv.style.left = '0';
        previewDiv.style.width = '100%';
        previewDiv.style.height = '100%';
        previewDiv.style.backgroundColor = 'rgba(0,0,0,0.9)';
        previewDiv.style.zIndex = '2000';
        previewDiv.style.display = 'flex';
        previewDiv.style.flexDirection = 'column';
        previewDiv.style.justifyContent = 'center';
        previewDiv.style.alignItems = 'center';
        
        const img = document.createElement('img');
        img.src = imageData;
        img.style.maxWidth = '90%';
        img.style.maxHeight = '70%';
        img.style.borderRadius = '10px';
        previewDiv.appendChild(img);
        
        // أزرار التأكيد والإلغاء
        const btnContainer = document.createElement('div');
        btnContainer.style.marginTop = '20px';
        btnContainer.style.display = 'flex';
        btnContainer.style.gap = '10px';
        
        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = '✅ تأكيد الرفع';
        confirmBtn.style.padding = '10px 20px';
        confirmBtn.style.backgroundColor = '#28a745';
        confirmBtn.style.color = 'white';
        confirmBtn.style.border = 'none';
        confirmBtn.style.borderRadius = '8px';
        confirmBtn.style.cursor = 'pointer';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '❌ إلغاء';
        cancelBtn.style.padding = '10px 20px';
        cancelBtn.style.backgroundColor = '#dc3545';
        cancelBtn.style.color = 'white';
        cancelBtn.style.border = 'none';
        cancelBtn.style.borderRadius = '8px';
        cancelBtn.style.cursor = 'pointer';
        
        btnContainer.appendChild(confirmBtn);
        btnContainer.appendChild(cancelBtn);
        previewDiv.appendChild(btnContainer);
        
        // شريط التقدم
        const progressBar = document.createElement('div');
        progressBar.style.width = '80%';
        progressBar.style.height = '10px';
        progressBar.style.backgroundColor = '#ddd';
        progressBar.style.borderRadius = '5px';
        progressBar.style.marginTop = '20px';
        progressBar.style.display = 'none';
        const progressFill = document.createElement('div');
        progressFill.style.width = '0%';
        progressFill.style.height = '100%';
        progressFill.style.backgroundColor = '#28a745';
        progressFill.style.borderRadius = '5px';
        progressBar.appendChild(progressFill);
        previewDiv.appendChild(progressBar);
        
        document.body.appendChild(previewDiv);
        
        // وظيفة الرفع
        const uploadImage = async () => {
            confirmBtn.disabled = true;
            cancelBtn.disabled = true;
            progressBar.style.display = 'block';
            
            let progress = 0;
            const interval = setInterval(() => {
                progress += 10;
                progressFill.style.width = progress + '%';
                if(progress >= 100) clearInterval(interval);
            }, 200);
            
            try {
                const response = await fetch('/api/save-evidence',{
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({element_id:currentElementId,witness_id:currentWitnessId,image:imageData})
                });
                const result = await response.json();
                if(result.success){
                    alert('✅ تم التوثيق بنجاح!');
                    previewDiv.remove();
                    closeCamera();
                    if(document.getElementById('statsSection').style.display==='block')loadStats();
                    if(document.getElementById('historySection').style.display==='block')loadHistory();
                } else {
                    alert('❌ خطأ: '+result.error);
                    previewDiv.remove();
                }
            } catch(err) {
                alert('❌ خطأ في الرفع: '+err.message);
                previewDiv.remove();
            }
        };
        
        confirmBtn.onclick = uploadImage;
        cancelBtn.onclick = () => previewDiv.remove();
        
    } else {
        alert('❌ لم يتم التقاط الصورة، تأكد من تشغيل الكاميرا');
    }
}


function closeCamera(){
    if(stream){
        stream.getTracks().forEach(track=>track.stop());
        stream=null;
    }
    document.getElementById('cameraModal').style.display='none';
}
function switchCamera(){
    if(currentFacingMode === 'environment'){
        currentFacingMode = 'user';
    } else {
        currentFacingMode = 'environment';
    }
    // إعادة تشغيل الكاميرا بالوضع الجديد
    if(stream){
        stream.getTracks().forEach(track => track.stop());
    }
    navigator.mediaDevices.getUserMedia({
        video: { facingMode: { exact: currentFacingMode } }
    }).then(newStream => {
        stream = newStream;
        document.getElementById('video').srcObject = stream;
    }).catch(err => {
        // إذا فشلت الكاميرا المحددة، جرب الكاميرا الافتراضية
        navigator.mediaDevices.getUserMedia({ video: true }).then(fallbackStream => {
            stream = fallbackStream;
            document.getElementById('video').srcObject = stream;
            currentFacingMode = 'environment';
        }).catch(e => {
            alert('لا يمكن تبديل الكاميرا: ' + e.message);
        });
    });
}

function uploadFromGallery(){
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '*/*';  // قبول جميع أنواع الملفات
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if(file){
            // عرض معاينة الملف قبل الرفع
            const previewDiv = document.createElement('div');
            previewDiv.style.position = 'fixed';
            previewDiv.style.top = '0';
            previewDiv.style.left = '0';
            previewDiv.style.width = '100%';
            previewDiv.style.height = '100%';
            previewDiv.style.backgroundColor = 'rgba(0,0,0,0.9)';
            previewDiv.style.zIndex = '2000';
            previewDiv.style.display = 'flex';
            previewDiv.style.flexDirection = 'column';
            previewDiv.style.justifyContent = 'center';
            previewDiv.style.alignItems = 'center';
            
            // عرض معلومات الملف
            const fileInfo = document.createElement('div');
            fileInfo.style.backgroundColor = 'white';
            fileInfo.style.padding = '20px';
            fileInfo.style.borderRadius = '15px';
            fileInfo.style.textAlign = 'center';
            fileInfo.style.maxWidth = '90%';
            
            const fileIcon = document.createElement('div');
            fileIcon.style.fontSize = '64px';
            // أيقونة حسب نوع الملف
            if(file.type.startsWith('image/')) fileIcon.textContent = '🖼️';
            else if(file.type === 'application/pdf') fileIcon.textContent = '📕';
            else if(file.type.includes('word')) fileIcon.textContent = '📘';
            else if(file.type.includes('excel') || file.type.includes('spreadsheet')) fileIcon.textContent = '📗';
            else if(file.type.includes('powerpoint')) fileIcon.textContent = '📙';
            else if(file.type.startsWith('text/')) fileIcon.textContent = '📄';
            else fileIcon.textContent = '📎';
            fileInfo.appendChild(fileIcon);
            
            const fileName = document.createElement('p');
            fileName.textContent = file.name;
            fileName.style.margin = '10px 0';
            fileName.style.wordBreak = 'break-all';
            fileInfo.appendChild(fileName);
            
            const fileSize = document.createElement('p');
            fileSize.textContent = `الحجم: ${(file.size / 1024).toFixed(2)} KB`;
            fileSize.style.color = '#666';
            fileInfo.appendChild(fileSize);
            
            // معاينة الصورة إذا كانت صورة
            if(file.type.startsWith('image/')){
                const imgPreview = document.createElement('img');
                imgPreview.style.maxWidth = '300px';
                imgPreview.style.maxHeight = '200px';
                imgPreview.style.marginTop = '10px';
                imgPreview.style.borderRadius = '8px';
                const readerPreview = new FileReader();
                readerPreview.onload = (e) => { imgPreview.src = e.target.result; };
                readerPreview.readAsDataURL(file);
                fileInfo.appendChild(imgPreview);
            }
            
            previewDiv.appendChild(fileInfo);
            
            // أزرار التأكيد والإلغاء
            const btnContainer = document.createElement('div');
            btnContainer.style.marginTop = '20px';
            btnContainer.style.display = 'flex';
            btnContainer.style.gap = '10px';
            
            const confirmBtn = document.createElement('button');
            confirmBtn.textContent = '✅ تأكيد الرفع';
            confirmBtn.style.padding = '10px 20px';
            confirmBtn.style.backgroundColor = '#28a745';
            confirmBtn.style.color = 'white';
            confirmBtn.style.border = 'none';
            confirmBtn.style.borderRadius = '8px';
            confirmBtn.style.cursor = 'pointer';
            
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = '❌ إلغاء';
            cancelBtn.style.padding = '10px 20px';
            cancelBtn.style.backgroundColor = '#dc3545';
            cancelBtn.style.color = 'white';
            cancelBtn.style.border = 'none';
            cancelBtn.style.borderRadius = '8px';
            cancelBtn.style.cursor = 'pointer';
            
            btnContainer.appendChild(confirmBtn);
            btnContainer.appendChild(cancelBtn);
            previewDiv.appendChild(btnContainer);
            
            // شريط التقدم
            const progressBar = document.createElement('div');
            progressBar.style.width = '80%';
            progressBar.style.height = '10px';
            progressBar.style.backgroundColor = '#ddd';
            progressBar.style.borderRadius = '5px';
            progressBar.style.marginTop = '20px';
            progressBar.style.display = 'none';
            const progressFill = document.createElement('div');
            progressFill.style.width = '0%';
            progressFill.style.height = '100%';
            progressFill.style.backgroundColor = '#28a745';
            progressFill.style.borderRadius = '5px';
            progressBar.appendChild(progressFill);
            previewDiv.appendChild(progressBar);
            
            document.body.appendChild(previewDiv);
            
            // وظيفة الرفع
            const uploadFile = async () => {
                confirmBtn.disabled = true;
                cancelBtn.disabled = true;
                progressBar.style.display = 'block';
                
                let progress = 0;
                const interval = setInterval(() => {
                    progress += 10;
                    progressFill.style.width = progress + '%';
                    if(progress >= 100) clearInterval(interval);
                }, 200);
                
                try {
                    const reader = new FileReader();
                    reader.onload = async (event) => {
                        const fileData = event.target.result;
                        const response = await fetch('/api/save-evidence',{
                            method:'POST',
                            headers:{'Content-Type':'application/json'},
                            body:JSON.stringify({
                                element_id:currentElementId,
                                witness_id:currentWitnessId,
                                image:fileData,
                                filename:file.name,
                                filetype:file.type
                            })
                        });
                        const result = await response.json();
                        if(result.success){
                            alert('✅ تم رفع الملف بنجاح!');
                            previewDiv.remove();
                            closeCamera();
                            if(document.getElementById('statsSection').style.display==='block')loadStats();
                            if(document.getElementById('historySection').style.display==='block')loadHistory();
                        } else {
                            alert('❌ خطأ: '+result.error);
                            previewDiv.remove();
                        }
                    };
                    reader.readAsDataURL(file);
                } catch(err) {
                    alert('❌ خطأ في الرفع: '+err.message);
                    previewDiv.remove();
                }
            };
            
            confirmBtn.onclick = uploadFile;
            cancelBtn.onclick = () => previewDiv.remove();
        }
    };
    input.click();
}
async function loadStats(){
    const response=await fetch('/api/get-my-evidences');
    const data=await response.json();
    if(data.success){
        const stats={};
        data.data.forEach(item=>{const el=`العنصر ${item.element_id}`;stats[el]=(stats[el]||0)+1;});
        const html=Object.entries(stats).map(([k,v]) => `<p><strong>${k}:</strong> ${v} توثيق</p>`).join('');
        document.getElementById('statsNumbers').innerHTML=html||'<p>لا توجد توثيقات بعد</p>';
    }
}
function gregorianToHijri(date){
    const gDate = new Date(date);
    const gYear = gDate.getFullYear();
    const gMonth = gDate.getMonth() + 1;
    const gDay = gDate.getDate();
    const hijriDate = new Intl.DateTimeFormat('ar-TN-u-ca-islamic', {year:'numeric', month:'long', day:'numeric'}).format(gDate);
    return hijriDate;
}
async function loadHistory(){
    const response=await fetch('/api/get-my-evidences');
    const data=await response.json();
    const grid=document.getElementById('historyGrid');
    if(data.success && data.data.length>0){
        grid.innerHTML=data.data.map((item,idx)=>{
            const miladiDate = new Date(item.created_at);
            const formattedMiladi = miladiDate.toLocaleDateString('ar-SA');
            const hijriDate = gregorianToHijri(item.created_at);
            return `<div class="history-card" style="position:relative; background:white; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="background:linear-gradient(135deg,#1a2a6c,#b21f1f); color:white; padding:8px 12px; font-size:12px; display:flex; justify-content:space-between; flex-wrap:wrap;">
                    <span>📅 ${formattedMiladi}</span>
                    <span>🕌 ${hijriDate}</span>
                    <span>📌 العنصر ${item.element_id} - الشاهد ${item.witness_id}</span>
                    <button onclick="deleteEvidence('${item.id}')" style="background:#dc3545; color:white; border:none; border-radius:50%; width:24px; height:24px; cursor:pointer; font-size:14px;">✖</button>
                </div>
                <div style="width:100%; height:180px; background:#f0f2f5; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer;" onclick="showEvidenceDetails('${item.id}')">
${item.file_type && item.file_type.startsWith('image/') ? 
    `<img src="${item.image_url}" style="width:100%; height:140px; object-fit:cover;" onerror="this.src='https://via.placeholder.com/300x140?text=صورة+غير+متوفرة'">` :
    `<div style="font-size:64px;">
        ${item.file_type === 'application/pdf' ? '📕' : 
          item.file_type?.includes('word') ? '📘' :
          item.file_type?.includes('excel') ? '📗' :
          item.file_type?.includes('powerpoint') ? '📙' :
          item.file_type?.startsWith('text/') ? '📄' : '📎'}
     </div>
     <div style="font-size:12px; margin-top:5px; color:#666; text-align:center; word-break:break-all; padding:0 5px;">${item.filename || 'ملف'}</div>`
}
    <div style="margin-top:10px; display:flex; gap:5px; pointer-events:auto;">
        <a href="${item.image_url}" target="_blank" style="background:#667eea; color:white; padding:4px 8px; border-radius:5px; text-decoration:none; font-size:11px;" onclick="event.stopPropagation();">📂 فتح</a>
        <a href="${item.image_url}" download style="background:#28a745; color:white; padding:4px 8px; border-radius:5px; text-decoration:none; font-size:11px;" onclick="event.stopPropagation();">⬇️ تحميل</a>
    </div>
</div>
                <div style="padding:10px;">
                    <p style="font-size:12px; color:#555; margin:0;">${item.element_title.substring(0,50)}</p>
                    <p style="font-size:11px; color:#888; margin-top:5px;">${item.witness_text.substring(0,60)}...</p>
                </div>
            </div>`;
        }).join('');
    }else{grid.innerHTML='<p style="text-align:center; padding:20px;">📭 لا توجد توثيقات سابقة</p>';}
}
async function logout(){
    if(confirm('هل أنت متأكد من تسجيل الخروج؟')){
        await fetch('/api/logout',{method:'POST'});
        window.location.href='/';
    }
}
document.getElementById('dateDisplay').innerText=new Date().toLocaleDateString('ar-SA');
document.getElementById('usernameDisplay').innerText='{{ username }}';
loadAllowedElements();
function toggleSidebar(){
    var sidebar = document.getElementById('sidebar');
    if(sidebar.style.display === 'none'){
        sidebar.style.display = 'block';
        document.querySelector('.main-content').style.marginRight = '260px';
    } else {
        sidebar.style.display = 'none';
        document.querySelector('.main-content').style.marginRight = '0px';
    }
}
document.getElementById('menuToggleBtn').onclick = toggleSidebar;
document.getElementById('switchCameraBtn').onclick = switchCamera;
document.getElementById('uploadImageBtn').onclick = uploadFromGallery;
async function deleteEvidence(id){
    if(confirm('هل أنت متأكد من حذف هذا التوثيق؟')){
        const response = await fetch('/api/delete-evidence',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({id:id})
        });
        const result = await response.json();
        if(result.success){
            alert('✅ تم الحذف بنجاح');
            loadHistory();
            loadStats();
        } else {
            alert('❌ خطأ: '+result.error);
        }
    }
}
function showChangePasswordModal(){
    document.getElementById('changePasswordModal').style.display = 'flex';
}
function closeChangePasswordModal(){
    document.getElementById('changePasswordModal').style.display = 'none';
    document.getElementById('oldPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';
    document.getElementById('passwordMsg').innerText = '';
}
async function changePassword(){
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    if(!oldPassword || !newPassword || !confirmPassword){
        document.getElementById('passwordMsg').innerText = '❌ الرجاء ملء جميع الحقول';
        return;
    }
    if(newPassword !== confirmPassword){
        document.getElementById('passwordMsg').innerText = '❌ كلمة السر الجديدة غير متطابقة';
        return;
    }
    if(newPassword.length < 4){
        document.getElementById('passwordMsg').innerText = '❌ كلمة السر يجب أن تكون 4 أحرف على الأقل';
        return;
    }
    const response = await fetch('/api/change-password',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({old_password:oldPassword, new_password:newPassword})
    });
    const result = await response.json();
    if(result.success){
        alert('✅ تم تغيير كلمة السر بنجاح');
        closeChangePasswordModal();
    } else {
        document.getElementById('passwordMsg').innerText = '❌ ' + result.error;
    }
}
async function showEvidenceDetails(id){
    const response = await fetch(`/api/get-evidence-by-id?id=${id}`);
    const result = await response.json();
    if(result.success){
        const item = result.data;
        const miladiDate = new Date(item.created_at);
        const formattedMiladi = miladiDate.toLocaleDateString('ar-SA');
        const hijriDate = gregorianToHijri(item.created_at);
        
        // إنشاء نافذة منبثقة
        const modalDiv = document.createElement('div');
        modalDiv.style.position = 'fixed';
        modalDiv.style.top = '0';
        modalDiv.style.left = '0';
        modalDiv.style.width = '100%';
        modalDiv.style.height = '100%';
        modalDiv.style.backgroundColor = 'rgba(0,0,0,0.85)';
        modalDiv.style.zIndex = '3000';
        modalDiv.style.display = 'flex';
        modalDiv.style.justifyContent = 'center';
        modalDiv.style.alignItems = 'center';
        
        const contentDiv = document.createElement('div');
        contentDiv.style.backgroundColor = 'white';
        contentDiv.style.borderRadius = '20px';
        contentDiv.style.maxWidth = '500px';
        contentDiv.style.width = '90%';
        contentDiv.style.maxHeight = '90vh';
        contentDiv.style.overflow = 'auto';
        contentDiv.style.padding = '20px';
        contentDiv.style.direction = 'rtl';
        
        // عرض الملف أو الصورة
        let fileHtml = '';
        if(item.file_type && item.file_type.startsWith('image/')){
            fileHtml = `<img src="${item.image_url}" style="width:100%; max-height:300px; object-fit:contain; border-radius:10px; margin-bottom:15px;">`;
        } else {
            let fileIcon = '📎';
            if(item.file_type === 'application/pdf') fileIcon = '📕';
            else if(item.file_type?.includes('word')) fileIcon = '📘';
            else if(item.file_type?.includes('excel')) fileIcon = '📗';
            else if(item.file_type?.includes('powerpoint')) fileIcon = '📙';
            else if(item.file_type?.startsWith('text/')) fileIcon = '📄';
            
            fileHtml = `
                <div style="text-align:center; padding:20px; background:#f0f2f5; border-radius:15px; margin-bottom:15px;">
                    <div style="font-size:80px;">${fileIcon}</div>
                    <div style="font-size:14px; color:#666; margin-top:10px; word-break:break-all;">${item.file_name || 'ملف'}</div>
                    ${item.file_size ? `<div style="font-size:12px; color:#999;">الحجم: ${(item.file_size/1024).toFixed(2)} KB</div>` : ''}
                    <div style="margin-top:15px; display:flex; gap:10px; justify-content:center;">
                        <a href="${item.image_url}" target="_blank" style="background:#667eea; color:white; padding:8px 16px; border-radius:8px; text-decoration:none;">📂 فتح الملف</a>
                        <a href="${item.image_url}" download style="background:#28a745; color:white; padding:8px 16px; border-radius:8px; text-decoration:none;">⬇️ تحميل</a>
                    </div>
                </div>
            `;
        }
        
        contentDiv.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #eee; padding-bottom:10px;">
                <h3 style="margin:0;">📋 تفاصيل التوثيق</h3>
                <button id="closeModalBtn" style="background:#dc3545; color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer; font-size:16px;">✖</button>
            </div>
            ${fileHtml}
            <div style="background:#f8f9fa; padding:12px; border-radius:10px; margin-bottom:10px;">
                <p><strong>📌 العنصر:</strong> ${item.element_title}</p>
                <p><strong>📝 الشاهد:</strong> ${item.witness_text}</p>
                <p><strong>👤 المراقب:</strong> ${item.username}</p>
                <p><strong>📅 التاريخ الميلادي:</strong> ${formattedMiladi}</p>
                <p><strong>🕌 التاريخ الهجري:</strong> ${hijriDate}</p>
            </div>
            <div style="display:flex; gap:10px; margin-top:15px;">
                <button id="closeBtn" style="flex:1; background:#667eea; color:white; padding:10px; border:none; border-radius:8px; cursor:pointer;">إغلاق</button>
            </div>
        `;
        
        modalDiv.appendChild(contentDiv);
        document.body.appendChild(modalDiv);
        
        const closeModal = () => modalDiv.remove();
        contentDiv.querySelector('#closeModalBtn').onclick = closeModal;
        contentDiv.querySelector('#closeBtn').onclick = closeModal;
        modalDiv.onclick = (e) => { if(e.target === modalDiv) closeModal(); };
    } else {
        alert('❌ خطأ في تحميل البيانات');
    }
}
async function showWitnessEvidences(elementId, witnessId, witnessText){
    const response = await fetch(`/api/get-evidences-by-witness?element_id=${encodeURIComponent(elementId)}&witness_id=${witnessId}`);
    const result = await response.json();
    
    if(result.success && result.data.length > 0){
        const modalDiv = document.createElement('div');
        modalDiv.style.position = 'fixed';
        modalDiv.style.top = '0';
        modalDiv.style.left = '0';
        modalDiv.style.width = '100%';
        modalDiv.style.height = '100%';
        modalDiv.style.backgroundColor = 'rgba(0,0,0,0.85)';
        modalDiv.style.zIndex = '3000';
        modalDiv.style.display = 'flex';
        modalDiv.style.justifyContent = 'center';
        modalDiv.style.alignItems = 'center';
        modalDiv.style.overflow = 'auto';
        
        const contentDiv = document.createElement('div');
        contentDiv.style.backgroundColor = 'white';
        contentDiv.style.borderRadius = '20px';
        contentDiv.style.maxWidth = '600px';
        contentDiv.style.width = '90%';
        contentDiv.style.margin = '20px auto';
        contentDiv.style.maxHeight = '90vh';
        contentDiv.style.overflow = 'auto';
        contentDiv.style.padding = '20px';
        contentDiv.style.direction = 'rtl';
        
        let filesHtml = '<div style="display:flex; flex-direction:column; gap:15px;">';
        for(const item of result.data){
            let fileIcon = '📎';
            let previewHtml = '';
            if(item.file_type && item.file_type.startsWith('image/')){
                previewHtml = `<img src="${item.image_url}" style="width:100%; height:120px; object-fit:cover; border-radius:8px;">`;
            } else {
                if(item.file_type === 'application/pdf') fileIcon = '📕';
                else if(item.file_type?.includes('word')) fileIcon = '📘';
                else if(item.file_type?.includes('excel')) fileIcon = '📗';
                else if(item.file_type?.includes('powerpoint')) fileIcon = '📙';
                else if(item.file_type?.startsWith('text/')) fileIcon = '📄';
                
                previewHtml = `<div style="text-align:center; font-size:48px;">${fileIcon}</div>`;
            }
            
            const itemDate = new Date(item.created_at);
            const formattedDate = itemDate.toLocaleDateString('ar-SA');
            
            filesHtml += `
                <div style="background:#f8f9fa; border-radius:12px; padding:12px; cursor:pointer;" onclick="showEvidenceDetails('${item.id}')">
                    ${previewHtml}
                    <div style="margin-top:8px;">
                        <div style="font-size:12px; color:#666;">${item.file_name || 'ملف'}</div>
                        <div style="font-size:11px; color:#999;">${formattedDate}</div>
                    </div>
                    <div style="margin-top:8px; display:flex; gap:8px;">
                        <a href="${item.image_url}" target="_blank" style="background:#667eea; color:white; padding:4px 8px; border-radius:5px; text-decoration:none; font-size:11px;" onclick="event.stopPropagation();">📂 فتح</a>
                        <a href="${item.image_url}" download style="background:#28a745; color:white; padding:4px 8px; border-radius:5px; text-decoration:none; font-size:11px;" onclick="event.stopPropagation();">⬇️ تحميل</a>
                    </div>
                </div>
            `;
        }
        filesHtml += '</div>';
        
        contentDiv.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #eee; padding-bottom:10px;">
                <h3 style="margin:0;">📁 ملفات الشاهد: ${witnessText.substring(0,50)}...</h3>
                <button id="closeModalBtn" style="background:#dc3545; color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer; font-size:16px;">✖</button>
            </div>
            <p style="margin-bottom:15px; color:#666;">عدد الملفات المرفوعة: ${result.data.length}</p>
            ${filesHtml}
            <div style="margin-top:15px;">
                <button id="closeBtn" style="width:100%; background:#667eea; color:white; padding:10px; border:none; border-radius:8px; cursor:pointer;">إغلاق</button>
            </div>
        `;
        
        modalDiv.appendChild(contentDiv);
        document.body.appendChild(modalDiv);
        
        const closeModal = () => modalDiv.remove();
        contentDiv.querySelector('#closeModalBtn').onclick = closeModal;
        contentDiv.querySelector('#closeBtn').onclick = closeModal;
        modalDiv.onclick = (e) => { if(e.target === modalDiv) closeModal(); };
    } else {
        alert('📭 لا توجد ملفات مرفوعة لهذا الشاهد');
    }
}
</script>
</body>
</html>
'''

ADMIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة المدير - نظام توثيق الشواهد</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:#f0f2f5}
.sidebar{position:fixed;right:0;top:0;width:280px;height:100%;background:linear-gradient(180deg,#1a2a6c,#b21f1f);color:white;padding:20px;overflow-y:auto}
.sidebar h3{text-align:center;margin-bottom:30px;padding-bottom:15px;border-bottom:2px solid rgba(255,255,255,0.3)}
.nav-item{padding:12px 15px;margin:8px 0;border-radius:12px;cursor:pointer;background:rgba(255,255,255,0.1);transition:0.3s}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,0.25);transform:translateX(-5px)}
.main-content{margin-right:280px;padding:20px;min-height:100vh}
.header{background:white;border-radius:15px;padding:20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:white;padding:20px;border-radius:15px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.stat-number{font-size:32px;font-weight:bold;color:#667eea}
.sync-buttons,.action-buttons{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.btn{padding:10px 20px;border:none;border-radius:8px;cursor:pointer;font-size:14px}
.btn-primary{background:#667eea;color:white}
.btn-success{background:#28a745;color:white}
.btn-danger{background:#dc3545;color:white}
.btn-warning{background:#ffc107;color:#333}
.btn-info{background:#17a2b8;color:white}
table{width:100%;background:white;border-radius:15px;overflow:hidden}
th,td{padding:12px;text-align:right;border-bottom:1px solid #eee}
th{background:#f8f9fa}
.evidence-img{width:50px;height:50px;object-fit:cover;border-radius:8px;cursor:pointer}
.logout-btn{background:rgba(255,255,255,0.2);border:none;color:white;padding:10px;border-radius:8px;cursor:pointer;width:100%;margin-top:20px}
.sync-status{background:#e9ecef;padding:10px;border-radius:8px;margin-bottom:20px;display:none}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;justify-content:center;align-items:center}
.modal-content{background:white;border-radius:15px;padding:25px;width:90%;max-width:500px}
.modal-content input,.modal-content select{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:8px}
.modal-buttons{display:flex;gap:10px;margin-top:20px}
.modal-buttons button{flex:1}
.search-box{width:100%;padding:10px;margin-bottom:15px;border:1px solid #ddd;border-radius:8px;font-size:14px}
.filter-bar{display:flex;gap:10px;margin-bottom:15px;flex-wrap:wrap}
.filter-bar select,.filter-bar input{padding:8px;border:1px solid #ddd;border-radius:8px}
.pagination{display:flex;justify-content:center;gap:5px;margin-top:15px}
.pagination button{padding:5px 10px;background:#667eea;color:white;border:none;border-radius:5px;cursor:pointer}
.pagination button:hover{background:#5a67d8}
/* التحكم في ظهور القائمة الجانبية حسب حجم الشاشة */
@media(min-width:769px){
    .sidebar{display:block !important}
    .main-content{margin-right:280px}
    #menuToggleBtn{display:none}
}
@media(max-width:768px){
    .sidebar{position:fixed;right:0;top:0;width:220px;height:100%;z-index:200;background:linear-gradient(180deg,#1a2a6c,#b21f1f);overflow-y:auto}
    .main-content{margin-right:0 !important}
}
</style>
</head>
<body>
<div class="sidebar" id="sidebar" style="display:none;"><h3>👑 لوحة المدير المتقدمة</h3>
<div class="nav-item active" onclick="showSection('dashboard', event);toggleSidebar()">📊 لوحة التحكم</div>
<div class="nav-item" onclick="showSection('evidences', event);toggleSidebar()">📋 إدارة التوثيقات</div>
<div class="nav-item" onclick="showSection('users', event);toggleSidebar()">👥 إدارة المستخدمين</div>
<div class="nav-item" onclick="showSection('permissions', event);toggleSidebar()">🔐 صلاحيات العناصر</div>
<div class="nav-item" onclick="showSection('sync', event);toggleSidebar()">🔄 المزامنة</div>
<div class="nav-item" onclick="showSection('reports', event);toggleSidebar()">📈 التقارير والإحصائيات</div>
<button class="logout-btn" onclick="logout()">🚪 خروج</button></div>
<div class="main-content">
<div style="display:flex; align-items:center; margin-bottom:10px;">
    <button id="menuToggleBtn" style="background:#667eea; color:white; border:none; border-radius:8px; padding:10px 15px; font-size:16px; cursor:pointer; margin-left:10px;">☰ القائمة</button>
</div>
<div class="header"><h2>لوحة تحكم المدير المتقدمة</h2><div id="dateDisplay"></div></div>

<!-- Dashboard Section -->
<div id="dashboardSection">
<div class="stats"><div class="stat-card"><div class="stat-number" id="totalCount">0</div><div>إجمالي التوثيقات</div></div>
<div class="stat-card"><div class="stat-number" id="usersCount">0</div><div>عدد المراقبين</div></div>
<div class="stat-card"><div class="stat-number" id="todayCount">0</div><div>توثيقات اليوم</div></div>
<div class="stat-card"><div class="stat-number" id="weekCount">0</div><div>آخر 7 أيام</div></div></div>
<canvas id="activityChart" width="800" height="300" style="max-width:100%; background:white; border-radius:15px; padding:15px;"></canvas>
</div>

<!-- Evidences Section -->
<div id="evidencesSection" style="display:none;">
<div style="background:white; border-radius:15px; padding:20px;">
<div class="filter-bar"><input type="text" id="searchInput" class="search-box" placeholder="🔍 بحث في التوثيقات..."><select id="filterUser"><option value="">جميع المراقبين</option></select><select id="filterElement"><option value="">جميع العناصر</option></select><input type="date" id="filterDate"></div>
<div class="action-buttons"><button class="btn btn-primary" onclick="exportCSV()">📥 تصدير CSV</button><button class="btn btn-success" onclick="exportExcel()">📊 تصدير Excel</button><button class="btn btn-info" onclick="refreshData()">🔄 تحديث</button><button class="btn btn-danger" onclick="deleteSelected()">🗑️ حذف المحدد</button></div>
<div style="overflow-x:auto;"><table id="dataTable"><thead><tr><th><input type="checkbox" id="selectAll"></th><th>#</th><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>الصورة</th><th>التاريخ</th><th>إجراءات</th></tr></thead><tbody id="tableBody"></tbody></table></div>
<div class="pagination" id="pagination"></div>
</div></div>

<!-- Users Section -->
<div id="usersSection" style="display:none;">
<div class="action-buttons"><button class="btn btn-success" onclick="showAddUserModal()">➕ إضافة مستخدم جديد</button><button class="btn btn-primary" onclick="loadUsers()">🔄 تحديث القائمة</button></div>
<div style="overflow-x:auto; margin-top:20px;">
<table style="width:100%; background:white; border-radius:15px; overflow:hidden;">
<thead>
<tr>
<th style="padding:12px; text-align:right;">#</th>
<th style="padding:12px; text-align:right;">اسم المستخدم</th>
<th style="padding:12px; text-align:right;">الاسم الكامل</th>
<th style="padding:12px; text-align:right;">النوع</th>
<th style="padding:12px; text-align:right;">عدد التوثيقات</th>
<th style="padding:12px; text-align:right;">آخر نشاط</th>
<th style="padding:12px; text-align:right;">الإجراءات</th>
</tr>
</thead>
<tbody id="usersTableBody"></tbody>
</table>
</div>
</div>

<!-- Sync Section -->
<div id="syncSection" style="display:none;">
<div class="sync-status" id="syncStatus"></div>
<div class="sync-buttons"><button class="btn btn-primary" onclick="syncToCloud()">☁️ مزامنة إلى السحابة</button><button class="btn btn-success" onclick="syncFromCloud()">📥 جلب من السحابة</button></div>
<div style="background:white;border-radius:15px;padding:20px;margin-top:20px;">
<h4>ℹ️ معلومات المزامنة</h4><p><span id="syncInfo">جاري التحميل...</span></p>
<hr><h4>📊 سجل المزامنة</h4><div id="syncLog" style="max-height:200px; overflow-y:auto; font-size:12px;"></div>
</div></div>

<!-- Permissions Section (في المكان الصحيح، خارج الشريط الجانبي) -->
<div id="permissionsSection" style="display:none;">
<div style="background:white; border-radius:15px; padding:20px;">
    <h3>🔐 إدارة صلاحيات العناصر للمراقبين</h3>
    <div class="filter-bar" style="margin-top:15px;">
        <select id="permUserSelect" onchange="loadUserElements()">
            <option value="">--- اختر المراقب ---</option>
        </select>
        <button class="btn btn-primary" onclick="loadUserElements()">📋 عرض العناصر المسموحة</button>
        <button class="btn btn-success" onclick="saveAllPermissions()">💾 حفظ جميع الصلاحيات</button>
    </div>
    <div id="elementsPermissionsGrid" style="display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px; margin-top:20px; max-height:500px; overflow-y:auto; padding:10px; background:#f8f9fa; border-radius:15px;">
    </div>
    <div id="permMessage" style="margin-top:15px; padding:10px; border-radius:8px; display:none;"></div>
</div>
</div>

<!-- Reports Section -->
<div id="reportsSection" style="display:none;">
<div style="background:white;border-radius:15px;padding:20px;">
<h3>تقرير أداء المراقبين</h3>
<canvas id="userChart" width="800" height="300" style="max-width:100%;"></canvas>
<div id="rankings" style="margin-top:20px;"></div>
<button class="btn btn-success" onclick="exportReport()" style="margin-top:15px;">📊 تصدير تقرير PDF</button>
</div></div>

<!-- Modals -->
<div id="addUserModal" class="modal"><div class="modal-content"><h3>➕ إضافة مستخدم جديد</h3><input type="text" id="newUsername" placeholder="اسم المستخدم" required><input type="text" id="newFullName" placeholder="الاسم الكامل"><input type="password" id="newPassword" placeholder="كلمة السر" value="pass123"><div class="modal-buttons"><button class="btn btn-success" onclick="addUser()">إضافة</button><button class="btn btn-danger" onclick="closeAddUserModal()">إلغاء</button></div></div></div>
<div id="editUserModal" class="modal"><div class="modal-content"><h3>✏️ تعديل مستخدم</h3><input type="hidden" id="editUserId"><input type="text" id="editUsername" placeholder="اسم المستخدم"><input type="text" id="editFullName" placeholder="الاسم الكامل"><input type="password" id="editPassword" placeholder="كلمة سر جديدة"><div class="modal-buttons"><button class="btn btn-primary" onclick="updateUser()">حفظ</button><button class="btn btn-danger" onclick="closeEditUserModal()">إلغاء</button></div></div></div>
<div id="viewImageModal" class="modal"><div class="modal-content" style="max-width:700px;"><img id="modalImage" style="width:100%; border-radius:10px;"><div class="modal-buttons"><button class="btn btn-danger" onclick="closeImageModal()">إغلاق</button></div></div></div>

<script>
let allData=[], filteredData=[], currentPage=1, rowsPerPage=20, activityChart=null, userChart=null;
let syncLogs = [];

function logSync(message){
    syncLogs.unshift(`[${new Date().toLocaleString()}] ${message}`);
    if(syncLogs.length>20) syncLogs.pop();
    document.getElementById('syncLog').innerHTML = syncLogs.map(l=>`<div>${l}</div>`).join('');
}

async function refreshData(){
    const response=await fetch('/api/admin/all-evidences');
    const data=await response.json();
    if(data.success){
        allData=data.data;
        applyFilters();
        updateStats();
        updateFilters();
        drawActivityChart();
        loadUsers(); 
    }
}

function applyFilters(){
    filteredData=[...allData];
    const searchTerm=document.getElementById('searchInput').value.toLowerCase();
    const filterUser=document.getElementById('filterUser').value;
    const filterElement=document.getElementById('filterElement').value;
    const filterDate=document.getElementById('filterDate').value;
    if(searchTerm) filteredData=filteredData.filter(e=>e.witness_text?.toLowerCase().includes(searchTerm)||e.username?.toLowerCase().includes(searchTerm));
    if(filterUser) filteredData=filteredData.filter(e=>e.username===filterUser);
    if(filterElement) filteredData=filteredData.filter(e=>e.element_id===filterElement);
    if(filterDate) filteredData=filteredData.filter(e=>e.created_at?.startsWith(filterDate));
    renderTable();
}

function renderTable(){
    const start=(currentPage-1)*rowsPerPage;
    const paginated=filteredData.slice(start,start+rowsPerPage);
    const tbody=document.getElementById('tableBody');
    if(paginated.length===0){tbody.innerHTML='<tr><td colspan="8" style="text-align:center;">لا توجد توثيقات<\/td></tr>';document.getElementById('pagination').innerHTML='';return;}
    tbody.innerHTML=paginated.map((item,i)=>`<tr><td><input type="checkbox" class="selectItem" value="${item.id}"><\/td><td>${start+i+1}<\/td><td>${item.username}<\/td><td>${item.element_id}<\/td><td style="max-width:300px;">${item.witness_text?.substring(0,50)}...<\/td><td>${item.image_url?`<img src="${item.image_url}" class="evidence-img" onclick="showImage('${item.image_url}')">`:'لا توجد'}<\/td><td>${item.created_at?.substring(0,10)}<\/td><td><button class="btn btn-danger" style="padding:5px 10px;" onclick="deleteEvidence('${item.id}')">🗑️<\/button><\/td><\/tr>`).join('');
    const totalPages=Math.ceil(filteredData.length/rowsPerPage);
    let paginationHtml='';
    for(let i=1;i<=totalPages;i++) paginationHtml+=`<button onclick="goToPage(${i})" style="${i===currentPage?'background:#5a67d8':''}">${i}<\/button>`;
    document.getElementById('pagination').innerHTML=paginationHtml;
    document.getElementById('selectAll').onclick=function(e){document.querySelectorAll('.selectItem').forEach(cb=>cb.checked=e.target.checked);};
}

function goToPage(page){currentPage=page;renderTable();}
function updateStats(){
    const users=[...new Set(allData.map(e=>e.username))];
    const today=new Date().toISOString().split('T')[0];
    const weekAgo=new Date();weekAgo.setDate(weekAgo.getDate()-7);
    document.getElementById('totalCount').innerText=allData.length;
    document.getElementById('usersCount').innerText=users.length;
    document.getElementById('todayCount').innerText=allData.filter(e=>e.created_at?.startsWith(today)).length;
    document.getElementById('weekCount').innerText=allData.filter(e=>new Date(e.created_at)>weekAgo).length;
}
function updateFilters(){
    const users=[...new Set(allData.map(e=>e.username))];
    const userSelect=document.getElementById('filterUser');
    userSelect.innerHTML='<option value="">جميع المراقبين</option>'+users.map(u=>`<option value="${u}">${u}<\/option>`).join('');
    const elements=[...new Set(allData.map(e=>e.element_id))];
    const elementSelect=document.getElementById('filterElement');
    elementSelect.innerHTML='<option value="">جميع العناصر</option>'+elements.map(el=>`<option value="${el}">العنصر ${el}<\/option>`).join('');
}
async function deleteEvidence(id){
    if(confirm('حذف هذا التوثيق؟')){
        const response=await fetch('/api/delete-evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
        const result=await response.json();
        if(result.success){alert('تم الحذف');refreshData();loadUsers();}else alert('خطأ: '+result.error);
    }
}
function deleteSelected(){
    const selected=[...document.querySelectorAll('.selectItem:checked')].map(cb=>cb.value);
    if(selected.length===0){alert('اختر عناصر للحذف');return;}
    if(confirm(`حذف ${selected.length} عنصر؟`)){
        Promise.all(selected.map(id=>fetch('/api/delete-evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}))).then(()=>{alert('تم الحذف');refreshData();loadUsers();});
    }
}
async function loadUsers(){
    try {
        const response = await fetch('/api/admin/users');
        const data = await response.json();
        
        if(data.success){
            // حساب إحصائيات كل مستخدم من التوثيقات
            const userStats = {};
            const lastActivity = {};
            
            allData.forEach(e => {
                // عدد التوثيقات لكل مستخدم
                userStats[e.username] = (userStats[e.username] || 0) + 1;
                // آخر نشاط لكل مستخدم
                if(!lastActivity[e.username] || e.created_at > lastActivity[e.username]){
                    lastActivity[e.username] = e.created_at;
                }
            });
            
            const tbody = document.getElementById('usersTableBody');
            if(!tbody) return;
            
            if(data.data && data.data.length > 0){
                tbody.innerHTML = data.data.map((user, i) => `
                    <tr>
                        <td>${i+1}</td>
                        <td>${user.username || '-'}</td>
                        <td>${user.full_name || '-'}</td>
                        <td>${user.username === 'admin' ? 'مدير' : 'مراقب'}</td>
                        <td>${userStats[user.username] || 0}</td>
                        <td>${lastActivity[user.username] ? lastActivity[user.username].substring(0,10) : '-'}</td>
                        <td>${user.username !== 'admin' ? `<button class="btn btn-warning" onclick="showEditUserModal(${user.id},'${user.username}','${user.full_name || ''}')" style="margin-left:5px;">✏️</button><button class="btn btn-danger" onclick="deleteUser(${user.id},'${user.username}')">🗑️</button><button class="btn btn-info" onclick="resetPassword(${user.id})">🔑</button>` : 'لا يمكن تعديل'}</td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">لا يوجد مستخدمين</td></tr>';
            }
            
            // تحديث الرسوم البيانية
            if(typeof drawUserChart === 'function') drawUserChart(userStats);
            if(typeof updateRankings === 'function') updateRankings(userStats);
        } else {
            console.error('خطأ في جلب المستخدمين:', data.error);
        }
    } catch(e) {
        console.error('خطأ في loadUsers:', e);
    }
}
function drawActivityChart(){
    const last7Days=[];
    for(let i=6;i>=0;i--){const d=new Date();d.setDate(d.getDate()-i);last7Days.push(d.toISOString().split('T')[0]);}
    const counts=last7Days.map(day=>allData.filter(e=>e.created_at?.startsWith(day)).length);
    if(activityChart)activityChart.destroy();
    const ctx=document.getElementById('activityChart').getContext('2d');
    activityChart=new Chart(ctx,{type:'line',data:{labels:last7Days.map(d=>d.substring(5)),datasets:[{label:'عدد التوثيقات',data:counts,borderColor:'#667eea',backgroundColor:'rgba(102,126,234,0.1)',fill:true,tension:0.3}]},options:{responsive:true,maintainAspectRatio:true}});
}
function drawUserChart(userStats){
    const sorted=Object.entries(userStats).sort((a,b)=>b[1]-a[1]).slice(0,10);
    if(userChart)userChart.destroy();
    const ctx=document.getElementById('userChart').getContext('2d');
    userChart=new Chart(ctx,{type:'bar',data:{labels:sorted.map(s=>s[0]),datasets:[{label:'عدد التوثيقات',data:sorted.map(s=>s[1]),backgroundColor:'#667eea',borderRadius:8}]},options:{responsive:true,maintainAspectRatio:true}});
}
function updateRankings(userStats){
    const sorted=Object.entries(userStats).sort((a,b)=>b[1]-a[1]);
    const medals=['🥇','🥈','🥉'];
    document.getElementById('rankings').innerHTML=`<h4>🏆 ترتيب المراقبين</h4>`+sorted.map(([user,count],i)=>`<p>${medals[i]||`${i+1}.`} <strong>${user}<\/strong>: ${count} توثيق<\/p>`).join('');
}
async function syncToCloud(){
    const status=document.getElementById('syncStatus');
    status.style.display='block';status.innerHTML='⏳ جاري المزامنة...';
    const response=await fetch('/api/sync-to-cloud',{method:'POST'});
    const result=await response.json();
    if(result.success){status.innerHTML=`✅ تمت المزامنة! ${result.synced} عنصر.`;logSync(`✅ مزامنة إلى السحابة: ${result.synced} عنصر`);}else{status.innerHTML=`❌ خطأ: ${result.error}`;logSync(`❌ فشل المزامنة: ${result.error}`);}
    setTimeout(()=>status.style.display='none',3000);
    refreshData();
}
async function syncFromCloud(){
    const status=document.getElementById('syncStatus');
    status.style.display='block';status.innerHTML='⏳ جاري الجلب...';
    const response=await fetch('/api/sync-from-cloud',{method:'POST'});
    const result=await response.json();
    if(result.success){status.innerHTML=`✅ تم الجلب! ${result.synced} عنصر.`;logSync(`✅ جلب من السحابة: ${result.synced} عنصر`);}else{status.innerHTML=`❌ خطأ: ${result.error}`;logSync(`❌ فشل الجلب: ${result.error}`);}
    setTimeout(()=>status.style.display='none',3000);
    refreshData();
}
function exportCSV(){
    let csv="المراقب,رقم العنصر,رقم الشاهد,نص الشاهد,التاريخ,رابط الصورة\\n";
    filteredData.forEach(e=>{csv+=`"${e.username}","${e.element_id}","${e.witness_id}","${e.witness_text}","${e.created_at}","${e.image_url}"\\n`;});
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`evidences_${new Date().toISOString().split('T')[0]}.csv`;link.click();
}
function exportExcel(){
    let html=`<html><head><meta charset="UTF-8"><title>التوثيقات</title><style>th,td{border:1px solid #ddd;padding:8px;text-align:right}</style></head><body><table border="1"><tr><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>التاريخ</th></tr>`;
    filteredData.forEach(e=>{html+=`<tr><td>${e.username}</td><td>${e.element_id}</td><td>${e.witness_text}</td><td>${e.created_at}</td></tr>`;});
    html+=`</table></body></html>`;
    const blob=new Blob([html],{type:'application/vnd.ms-excel'});
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`evidences_${new Date().toISOString().split('T')[0]}.xls`;link.click();
}
function exportReport(){
    const reportWindow=window.open('','_blank');
    reportWindow.document.write(`<html><head><meta charset="UTF-8"><title>تقرير التوثيقات</title><style>body{font-family:Arial;} th,td{border:1px solid #ddd;padding:8px;text-align:right}</style></head><body><h1>تقرير التوثيقات</h1><p>التاريخ: ${new Date().toLocaleDateString('ar-SA')}</p><p>إجمالي التوثيقات: ${allData.length}</p><p>عدد المراقبين: ${[...new Set(allData.map(e=>e.username))].length}</p><table border="1"><tr><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>التاريخ</th></tr>`);
    filteredData.forEach(e=>{reportWindow.document.write(`<tr><td>${e.username}</td><td>${e.element_id}</td><td>${e.witness_text}</td><td>${e.created_at}</td></tr>`);});
    reportWindow.document.write(`</table></body></html>`);
    reportWindow.document.close();reportWindow.print();
}
function showImage(url){document.getElementById('modalImage').src=url;document.getElementById('viewImageModal').style.display='flex';}
function closeImageModal(){document.getElementById('viewImageModal').style.display='none';}
function showAddUserModal(){document.getElementById('addUserModal').style.display='flex';}
function closeAddUserModal(){document.getElementById('addUserModal').style.display='none';document.getElementById('newUsername').value='';document.getElementById('newFullName').value='';document.getElementById('newPassword').value='pass123';}
async function addUser(){
    const username=document.getElementById('newUsername').value;
    const full_name=document.getElementById('newFullName').value;
    const password=document.getElementById('newPassword').value;
    if(!username){alert('يرجى إدخال اسم المستخدم');return;}
    const response=await fetch('/api/admin/add-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,full_name})});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);closeAddUserModal();loadUsers();}else{alert('❌ '+result.error);}
}
let currentEditId=null,currentEditUsername=null;
function showEditUserModal(id,username,full_name){
    currentEditId=id;currentEditUsername=username;
    document.getElementById('editUserId').value=id;
    document.getElementById('editUsername').value=username;
    document.getElementById('editFullName').value=full_name||'';
    document.getElementById('editPassword').value='';
    document.getElementById('editUserModal').style.display='flex';
}
function closeEditUserModal(){document.getElementById('editUserModal').style.display='none';currentEditId=null;currentEditUsername=null;}
async function updateUser(){
    const username=document.getElementById('editUsername').value;
    const full_name=document.getElementById('editFullName').value;
    const password=document.getElementById('editPassword').value;
    const body={id:currentEditId, old_username:currentEditUsername};
    if(username && username !== currentEditUsername) body.username=username;
    if(full_name) body.full_name=full_name;
    if(password) body.password=password;
    const response=await fetch('/api/admin/update-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);closeEditUserModal();loadUsers();}else{alert('❌ '+result.error);}
}
async function deleteUser(id,username){
    if(confirm(`حذف المستخدم "${username}"؟`)){
        const response=await fetch('/api/admin/delete-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,username})});
        const result=await response.json();
        if(result.success){alert('✅ '+result.message);loadUsers();refreshData();}else{alert('❌ '+result.error);}
    }
}
async function resetPassword(id){
    const newPassword=prompt('كلمة السر الجديدة (اتركها فارغة للافتراضي pass123)');
    if(newPassword===null)return;
    const response=await fetch('/api/admin/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,new_password:newPassword||'pass123'})});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);}else{alert('❌ '+result.error);}
}
async function loadPermissionsUsers(){
    const response = await fetch('/api/admin/users');
    const data = await response.json();
    if(data.success){
        const select = document.getElementById('permUserSelect');
        select.innerHTML = '<option value="">--- اختر المراقب ---</option>';
        data.data.forEach(user => {
            if(user.username !== 'admin'){
                select.innerHTML += `<option value="${user.username}">${user.username} - ${user.full_name || ''}</option>`;
            }
        });
    }
    // تنظيف الـ grid عند التبديل بين المستخدمين
    document.getElementById('elementsPermissionsGrid').innerHTML = '';
    changedPermissions = {};
}

async function loadUserElements(){
    const username = document.getElementById('permUserSelect').value;
    if(!username){
        document.getElementById('permMessage').innerHTML = '<div style="color:#c00;">❌ الرجاء اختيار مراقب</div>';
        document.getElementById('permMessage').style.display = 'block';
        setTimeout(()=>document.getElementById('permMessage').style.display='none',2000);
        return;
    }
    
    // جلب الصلاحيات الحالية للمستخدم
    const permResponse = await fetch(`/api/admin/get-user-elements?username=${encodeURIComponent(username)}`);
    const permData = await permResponse.json();
    const allowedElements = permData.success ? permData.data : [];
    
    // جلب جميع العناصر من الخادم (API جديد)
    const elementsResponse = await fetch('/api/admin/all-elements');
    const elementsData = await elementsResponse.json();
    
    if(elementsData.success){
        const grid = document.getElementById('elementsPermissionsGrid');
        grid.innerHTML = `<div style="grid-column:1/-1; background:#e9ecef; padding:10px; border-radius:10px; margin-bottom:10px;">
                            <strong>👤 المراقب: ${username}</strong>
                            <span style="margin-right:20px;">✅ اختر العناصر المسموح له بتوثيقها</span>
                         </div>`;
        
        for(const [id, element] of Object.entries(elementsData.elements)){
            const isChecked = allowedElements.includes(id);
            grid.innerHTML += `
                <div style="background:white; border-radius:10px; padding:12px; box-shadow:0 1px 3px rgba(0,0,0,0.1); display:flex; align-items:center; gap:10px;">
                    <input type="checkbox" id="perm_${id.replace(/[^a-zA-Z0-9]/g,'_')}" value="${id}" ${isChecked ? 'checked' : ''} 
                           onchange="markPermissionChanged('${username}','${id.replace(/'/g, "\\'")}',this.checked)">
                    <label style="flex:1; cursor:pointer;" for="perm_${id.replace(/[^a-zA-Z0-9]/g,'_')}">
                        <strong>📌 ${id}</strong> - ${element.title.substring(0,60)}
                    </label>
                </div>
            `;
        }
        
        // تخزين username الحالي للاستخدام في الحفظ
        grid.setAttribute('data-current-user', username);
    } else {
        grid.innerHTML = '<p style="color:#c00;">❌ فشل تحميل العناصر</p>';
    }
}

let changedPermissions = {};

function markPermissionChanged(username, elementId, isChecked){
    if(!changedPermissions[username]) changedPermissions[username] = {};
    changedPermissions[username][elementId] = isChecked;
}

async function saveAllPermissions(){
    const username = document.getElementById('permUserSelect').value;
    if(!username){
        alert('❌ الرجاء اختيار مراقب أولاً');
        return;
    }
    
    if(!changedPermissions[username] || Object.keys(changedPermissions[username]).length === 0){
        alert('⚠️ لا توجد تغييرات لحفظها');
        return;
    }
    
    const promises = [];
    for(const [elementId, canAccess] of Object.entries(changedPermissions[username])){
        promises.push(fetch('/api/admin/set-permission', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, element_id: elementId, can_access: canAccess ? 1 : 0})
        }));
    }
    
    const results = await Promise.all(promises);
    let successCount = results.filter(r => r.ok).length;
    
    if(successCount === promises.length){
        alert(`✅ تم حفظ ${successCount} صلاحية للمراقب ${username}`);
        delete changedPermissions[username];
        // إعادة تحميل الصلاحيات للتحديث
        loadUserElements();
    } else {
        alert(`⚠️ تم حفظ ${successCount} من ${promises.length} صلاحية. حاول مرة أخرى.`);
    }
}
function showSection(section, evt){
    document.getElementById('dashboardSection').style.display=section==='dashboard'?'block':'none';
    document.getElementById('evidencesSection').style.display=section==='evidences'?'block':'none';
    document.getElementById('usersSection').style.display=section==='users'?'block':'none';
    document.getElementById('permissionsSection').style.display=section==='permissions'?'block':'none';
    document.getElementById('syncSection').style.display=section==='sync'?'block':'none';
    document.getElementById('reportsSection').style.display=section==='reports'?'block':'none';
    document.querySelectorAll('.nav-item').forEach(item=>item.classList.remove('active'));
    if(evt && evt.target) evt.target.classList.add('active');
    if(section==='users') loadUsers();
    if(section==='permissions') loadPermissionsUsers();
}
async function logout(){
    await fetch('/api/logout',{method:'POST'});
    window.location.href='/';
}
document.getElementById('dateDisplay').innerText=new Date().toLocaleDateString('ar-SA');
document.getElementById('searchInput').addEventListener('input',()=>{currentPage=1;applyFilters();});
document.getElementById('filterUser').addEventListener('change',()=>{currentPage=1;applyFilters();});
document.getElementById('filterElement').addEventListener('change',()=>{currentPage=1;applyFilters();});
document.getElementById('filterDate').addEventListener('change',()=>{currentPage=1;applyFilters();});
function toggleSidebar(){
    var sidebar = document.getElementById('sidebar');
    if(sidebar.style.display === 'none'){
        sidebar.style.display = 'block';
        document.querySelector('.main-content').style.marginRight = '260px';
    } else {
        sidebar.style.display = 'none';
        document.querySelector('.main-content').style.marginRight = '0px';
    }
}
document.getElementById('menuToggleBtn').onclick = toggleSidebar;
refreshData();
const script=document.createElement('script');script.src='https://cdn.jsdelivr.net/npm/chart.js';document.head.appendChild(script);
</script>
</body>
</html>
'''

# ============ Routes API ============
@app.route('/')
def index():
    return render_template_string(LOGIN_PAGE)
@app.route('/api/change-password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'success': False, 'error': 'الرجاء إدخال كلمة السر الحالية والجديدة'})
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'error': 'كلمة السر الجديدة قصيرة جداً (4 أحرف على الأقل)'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # التحقق من كلمة السر الحالية
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (session['username'], old_password))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'كلمة السر الحالية غير صحيحة'})
    
    # تحديث كلمة السر
    c.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, session['username']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'تم تغيير كلمة السر بنجاح'})
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template_string(DASHBOARD_PAGE, elements=ELEMENTS, username=session['username'])

@app.route('/admin')
def admin_panel():
    if 'username' not in session or session.get('username') != 'admin':
        return redirect(url_for('index'))
    return render_template_string(ADMIN_PAGE)

@app.route('/api/delete-evidence', methods=['POST'])
def delete_evidence():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    data = request.json
    evidence_id = data.get('id')
    
    if not evidence_id:
        return jsonify({'success': False, 'error': 'معرف غير صالح'})
    
    try:
        # حذف من Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            # حذف من جدول evidences
            response = requests.delete(
                f"{SUPABASE_URL}/rest/v1/evidences?id=eq.{evidence_id}",
                headers=headers
            )
            if response.status_code not in [200, 204]:
                return jsonify({'success': False, 'error': 'فشل حذف البيانات من Supabase'})
        
        # حذف من قاعدة البيانات المحلية
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM evidences WHERE id = ? AND username = ?", (evidence_id, session['username']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'تم الحذف بنجاح'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['username'] = username
        session['full_name'] = user[3] if len(user) > 3 else username
        return jsonify({'success': True, 'user': username, 'is_admin': username == 'admin'})
    return jsonify({'success': False, 'error': 'اسم المستخدم أو كلمة السر غير صحيحة'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/save-evidence', methods=['POST'])
def save_evidence():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    data = request.json
    element_id = data.get('element_id')
    witness_id = int(data.get('witness_id'))
    file_data = data.get('image')
    filename = data.get('filename', f"file_{uuid.uuid4().hex}")
    file_type = data.get('filetype', 'application/octet-stream')
    
    # تحويل element_id إلى str للوصول إلى ELEMENTS
    element_id_str = str(element_id)
    if element_id_str not in ELEMENTS:
        return jsonify({'success': False, 'error': 'عنصر غير موجود'})
    
    witness_text = ELEMENTS[element_id_str]['witnesses'][witness_id - 1]
    element_title = ELEMENTS[element_id_str]['title']
    
    # استخراج الامتداد من اسم الملف أو من نوع الملف
    if '.' in filename:
        ext = filename.split('.')[-1]
    else:
        ext_map = {
            'application/pdf': 'pdf',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'application/vnd.ms-powerpoint': 'ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
            'text/plain': 'txt'
        }
        ext = ext_map.get(file_type, 'file')
    
    new_filename = f"{session['username']}_{element_id}_{witness_id}_{uuid.uuid4().hex}.{ext}"
    
    if 'base64,' in file_data:
        file_data = file_data.split('base64,')[1]
    
    file_bytes = base64.b64decode(file_data)
    
    # التحقق من إعدادات Supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({'success': False, 'error': 'Supabase غير مهيأ'})
    
    try:
        # 1. التأكد من وجود Bucket في Supabase Storage
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        # محاولة إنشاء bucket إذا لم يكن موجوداً
        bucket_url = f"{SUPABASE_URL}/storage/v1/bucket/evidence"
        bucket_response = requests.get(bucket_url, headers=headers)
        
        if bucket_response.status_code == 404:
            bucket_data = {
                'id': 'evidence',
                'name': 'evidence',
                'public': True
            }
            create_bucket_response = requests.post(
                f"{SUPABASE_URL}/storage/v1/bucket",
                headers=headers,
                json=bucket_data
            )
            if create_bucket_response.status_code not in [200, 201, 409]:
                return jsonify({'success': False, 'error': 'فشل إنشاء مجلد التخزين'})
        
        # 2. رفع الملف إلى Supabase Storage
        upload_headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': file_type
        }
        
        file_upload_url = f"{SUPABASE_URL}/storage/v1/object/evidence/{new_filename}"
        file_response = requests.post(file_upload_url, headers=upload_headers, data=file_bytes)
        
        if file_response.status_code not in [200, 201]:
            return jsonify({'success': False, 'error': f'فشل رفع الملف: {file_response.status_code} - {file_response.text}'})
        
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/evidence/{new_filename}"
        
        # 3. حفظ البيانات في Supabase Table
        db_headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        evidence_data = {
            'username': session['username'],
            'element_id': str(element_id),
            'element_title': element_title,
            'witness_id': witness_id,
            'witness_text': witness_text,
            'image_url': file_url,
            'file_name': filename,
            'file_type': file_type,
            'file_size': len(file_bytes),
            'created_at': datetime.now().isoformat()
        }
        
        # إضافة أعمدة جديدة إذا لم تكن موجودة في الجدول
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("ALTER TABLE evidences ADD COLUMN file_name TEXT")
        except: pass
        try:
            c.execute("ALTER TABLE evidences ADD COLUMN file_type TEXT")
        except: pass
        try:
            c.execute("ALTER TABLE evidences ADD COLUMN file_size INTEGER")
        except: pass
        conn.commit()
        conn.close()
        
        db_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/evidences",
            headers=db_headers,
            json=evidence_data
        )
        
        if db_response.status_code not in [200, 201]:
            error_detail = db_response.text
            print(f"Supabase Error: {error_detail}")
            return jsonify({'success': False, 'error': f'فشل حفظ البيانات: {db_response.status_code} - {error_detail}'})
        
        # 4. أيضاً حفظ محلياً كنسخة احتياطية
        try:
            local_file_path = os.path.join(STATIC_IMAGES_DIR, new_filename)
            with open(local_file_path, 'wb') as f:
                f.write(file_bytes)
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO evidences (username, element_id, element_title, witness_id, witness_text, image_path, image_url, synced, file_name, file_type, file_size)
                         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)''',
                      (session['username'], element_id, element_title, witness_id, witness_text, local_file_path, file_url, filename, file_type, len(file_bytes)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"تحذير: فشل الحفظ المحلي: {e}")
        
        return jsonify({'success': True, 'file_url': file_url, 'file_name': filename})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}) 

@app.route('/api/get-my-evidences', methods=['GET'])
def get_my_evidences():
    if 'username' not in session:
        return jsonify({'success': False, 'data': []})
    
    # محاولة الجلب من Supabase أولاً
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/evidences?username=eq.{session['username']}&order=created_at.desc",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                # تنسيق البيانات لتتناسب مع ما يتوقعه التطبيق
                formatted_data = []
                for item in data:
                    formatted_data.append({
                        'id': item.get('id'),
                        'username': item.get('username'),
                        'element_id': item.get('element_id'),
                        'element_title': item.get('element_title'),
                        'witness_id': item.get('witness_id'),
                        'witness_text': item.get('witness_text'),
                        'image_url': item.get('image_url'),
                        'created_at': item.get('created_at')
                    })
                return jsonify({'success': True, 'data': formatted_data})
        except Exception as e:
            print(f"خطأ في جلب البيانات من Supabase: {e}")
    
    # الرجوع إلى قاعدة البيانات المحلية كنسخة احتياطية
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences WHERE username=? ORDER BY created_at DESC''', (session['username'],))
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        image_url = r[7] if r[7] else (f"/static/images/{os.path.basename(r[6])}" if r[6] else None)
        data.append({
            'id': r[0], 'username': r[1], 'element_id': r[2], 'element_title': r[3],
            'witness_id': r[4], 'witness_text': r[5], 'image_url': image_url, 'created_at': r[8]
        })
    return jsonify({'success': True, 'data': data})

@app.route('/api/admin/all-evidences', methods=['GET'])
def admin_all_evidences():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    # محاولة الجلب من Supabase أولاً
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/evidences?order=created_at.desc",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                # تنسيق البيانات لتتناسب مع ما يتوقعه تطبيق سطح المكتب
                formatted_data = []
                for item in data:
                    # التأكد من أن رابط الصورة هو رابط كامل لـ Supabase
                    image_url = item.get('image_url')
                    if not image_url:
                        # إذا لم يكن موجوداً، حاول إنشاؤه من معرف الصورة
                        # معرف الصورة مخزن كـ 'id' في Supabase
                        filename = f"{item['username']}_{item['element_id']}_{item['witness_id']}_"
                        # البحث في قاعدة البيانات عن رابط قديم (حل احتياطي)
                        image_url = None
                    
                    formatted_data.append({
                        'id': item.get('id'),
                        'username': item.get('username'),
                        'element_id': item.get('element_id'),
                        'element_title': item.get('element_title'),
                        'witness_id': item.get('witness_id'),
                        'witness_text': item.get('witness_text'),
                        'image_path': image_url,  # مفتاح image_path يستخدمه تطبيق المكتبي
                        'image_url': image_url,   # مفتاح image_url للمرونة
                        'created_at': item.get('created_at')
                    })
                # طباعة أول عنصر للتأكد من البيانات (في سجلات Render)
                if formatted_data:
                    print(f"First evidence from Supabase: {formatted_data[0]}")
                return jsonify({'success': True, 'data': formatted_data})
        except Exception as e:
            print(f"خطأ في جلب البيانات من Supabase: {e}")
    
    # الرجوع إلى قاعدة البيانات المحلية كنسخة احتياطية
    # ... (الكود القديم للنسخة الاحتياطية)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences ORDER BY created_at DESC''')
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        # استخدام image_url من قاعدة البيانات المحلية إذا كان موجوداً
        image_url = r[7] if r[7] else None
        if not image_url and r[6]:
            # محاولة إنشاء رابط Supabase بناءً على اسم الملف المحلي
            filename = os.path.basename(r[6])
            image_url = f"{SUPABASE_URL}/storage/v1/object/public/evidence/{filename}" if SUPABASE_URL else None
        
        data.append({
            'id': r[0], 'username': r[1], 'element_id': r[2], 'element_title': r[3],
            'witness_id': r[4], 'witness_text': r[5], 'image_path': image_url,
            'image_url': image_url, 'created_at': r[8]
        })
    return jsonify({'success': True, 'data': data})

@app.route('/api/sync-to-cloud', methods=['POST'])
def api_sync_to_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    result = sync_to_supabase()
    return jsonify(result)
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'running',
        'supabase_configured': bool(SUPABASE_URL and SUPABASE_KEY),
        'database_path': DB_PATH
    })
@app.route('/api/sync-from-cloud', methods=['POST'])
def api_sync_from_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    result = sync_from_supabase()
    return jsonify(result)

@app.route('/api/get-evidence-by-id', methods=['GET'])
def get_evidence_by_id():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    evidence_id = request.args.get('id')
    if not evidence_id:
        return jsonify({'success': False, 'error': 'معرف غير صالح'})
    
    # محاولة الجلب من Supabase أولاً
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/evidences?id=eq.{evidence_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    item = data[0]
                    return jsonify({
                        'success': True,
                        'data': {
                            'id': item.get('id'),
                            'username': item.get('username'),
                            'element_id': item.get('element_id'),
                            'element_title': item.get('element_title'),
                            'witness_id': item.get('witness_id'),
                            'witness_text': item.get('witness_text'),
                            'image_url': item.get('image_url'),
                            'file_name': item.get('file_name', 'ملف'),
                            'file_type': item.get('file_type', ''),
                            'file_size': item.get('file_size', 0),
                            'created_at': item.get('created_at')
                        }
                    })
        except Exception as e:
            print(f"خطأ في جلب البيانات من Supabase: {e}")
    
    # الرجوع إلى قاعدة البيانات المحلية
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences WHERE id = ? AND username = ?''', (evidence_id, session['username']))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            'success': True,
            'data': {
                'id': row[0], 'username': row[1], 'element_id': row[2], 'element_title': row[3],
                'witness_id': row[4], 'witness_text': row[5], 'image_url': row[7], 'created_at': row[8]
            }
        })
    
    return jsonify({'success': False, 'error': 'التوثيق غير موجود'})

@app.route('/api/get-evidences-by-witness', methods=['GET'])
def get_evidences_by_witness():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    element_id = request.args.get('element_id')
    witness_id = request.args.get('witness_id')
    
    if not element_id or not witness_id:
        return jsonify({'success': False, 'error': 'بيانات غير مكتملة'})
    
    # محاولة الجلب من Supabase أولاً
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/evidences?username=eq.{session['username']}&element_id=eq.{element_id}&witness_id=eq.{witness_id}&order=created_at.desc",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                formatted_data = []
                for item in data:
                    formatted_data.append({
                        'id': item.get('id'),
                        'image_url': item.get('image_url'),
                        'file_name': item.get('file_name', 'ملف'),
                        'file_type': item.get('file_type', ''),
                        'file_size': item.get('file_size', 0),
                        'created_at': item.get('created_at'),
                        'element_title': item.get('element_title'),
                        'witness_text': item.get('witness_text')
                    })
                return jsonify({'success': True, 'data': formatted_data})
        except Exception as e:
            print(f"خطأ في جلب البيانات من Supabase: {e}")
    
    # الرجوع إلى قاعدة البيانات المحلية
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences WHERE username=? AND element_id=? AND witness_id=? ORDER BY created_at DESC''',
              (session['username'], element_id, witness_id))
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        data.append({
            'id': r[0],
            'image_url': r[7],
            'created_at': r[8],
            'element_title': r[3],
            'witness_text': r[5]
        })
    
    return jsonify({'success': True, 'data': data})


# ============ تشغيل التطبيق ============
if __name__ == '__main__':
    init_local_db()
    print("=" * 60)
    print("📸 نظام توثيق الشواهد المدرسية - الإصدار المتكامل")
    print("=" * 60)
    print(f"✅ قاعدة البيانات: {DB_PATH}")
    print(f"✅ مجلد الصور: {STATIC_IMAGES_DIR}")
    print(f"✅ Supabase: {'متصل' if SUPABASE_URL and SUPABASE_KEY else 'غير مهيأ'}")
    print("=" * 60)
    print("🔐 بيانات الدخول:")
    #print("   admin / admin123 (مدير)")
    #print("   observer1 / password123 (مراقب 1)")
    #print("   observer2-10 / pass123 (مراقبين)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=10000, debug=False)
