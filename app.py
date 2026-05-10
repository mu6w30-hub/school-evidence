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
import pandas as pd
from flask import send_file
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
        
        # حفظ في Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
            
            user_data = {
                'username': username,
                'password': password,
                'full_name': full_name or ''
            }
            
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/users",
                headers=headers,
                json=user_data
            )
            
            if response.status_code not in [200, 201]:
                print(f"⚠️ فشل حفظ المستخدم {username} في Supabase: {response.status_code}")
        
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
        
        # تحديث في Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
            
            update_data = {}
            if username and username != old_username:
                update_data['username'] = username
            if password:
                update_data['password'] = password
            if full_name:
                update_data['full_name'] = full_name
            
            if update_data:
                response = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/users?username=eq.{old_username}",
                    headers=headers,
                    json=update_data
                )
                if response.status_code not in [200, 204]:
                    print(f"⚠️ فشل تحديث المستخدم {old_username} في Supabase: {response.status_code}")
        
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
        
        # حذف من Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.delete(
                f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}",
                headers=headers
            )
            if response.status_code not in [200, 204]:
                print(f"⚠️ فشل حذف المستخدم {username} من Supabase: {response.status_code}")
        
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
        # جلب اسم المستخدم أولاً
        c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        username = row[0] if row else None
        
        c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        
        # تحديث في Supabase
        if username and SUPABASE_URL and SUPABASE_KEY:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}",
                headers=headers,
                json={'password': new_password}
            )
            if response.status_code not in [200, 204]:
                print(f"⚠️ فشل تحديث كلمة سر {username} في Supabase: {response.status_code}")
        
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
    # محاولة استعادة البيانات من Supabase أولاً
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            # جلب العناصر من Supabase
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/elements",
                headers=headers
            )
            
            if response.status_code == 200:
                supabase_elements = response.json()
                
                # إذا وجدت عناصر في Supabase، قم بحفظها في قاعدة البيانات المحلية
                if supabase_elements:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    
                    for element in supabase_elements:
                        c.execute("""
                            INSERT OR REPLACE INTO elements 
                            (element_id, title, witnesses, appendix, criteria, indicators)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            element.get('element_id'),
                            element.get('title'),
                            element.get('witnesses'),
                            element.get('appendix', ''),
                            element.get('criteria', ''),
                            element.get('indicators', '')
                        ))
                    
                    conn.commit()
                    conn.close()
                    print(f"✅ تم استعادة {len(supabase_elements)} عنصر من Supabase")
                    return
        except Exception as e:
            print(f"⚠️ خطأ في استعادة البيانات من Supabase: {e}")
    
    # إذا لم ينجح الاستعادة من Supabase، قم بإنشاء الجداول من ELEMENTS الثابتة
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
    # إضافة جدول صلاحيات المراقبين (معدل ليشمل witness_id)
    c.execute('''CREATE TABLE IF NOT EXISTS user_permissions
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                element_id TEXT,
                witness_id INTEGER,
                can_access INTEGER DEFAULT 1,
                UNIQUE(username, element_id, witness_id))''')
    # إضافة جدول العناصر
    c.execute('''CREATE TABLE IF NOT EXISTS elements
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                element_id TEXT UNIQUE,
                title TEXT,
                witnesses TEXT,
                appendix TEXT,
                criteria TEXT,
                indicators TEXT)''')
    
    # ترحيل البيانات من ELEMENTS الثابتة إلى قاعدة البيانات إذا كان الجدول فارغاً
    c.execute("SELECT COUNT(*) FROM elements")
    count = c.fetchone()[0]
    if count == 0:
        for element_id, element_data in ELEMENTS.items():
            witnesses_json = json.dumps(element_data['witnesses'], ensure_ascii=False)
            # تقسيم element_id إلى أجزاء
            parts = element_id.split('-')
            appendix_val = parts[1] if len(parts) > 1 else ''
            criteria_val = parts[2] if len(parts) > 2 else ''
            indicators_val = parts[3] if len(parts) > 3 else ''
            c.execute("INSERT OR IGNORE INTO elements (element_id, title, witnesses, appendix, criteria, indicators) VALUES (?, ?, ?, ?, ?, ?)",
                      (element_id, element_data['title'], witnesses_json, appendix_val, criteria_val, indicators_val))
    # محاولة استعادة المستخدمين من Supabase أولاً
    users_restored = False
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/users",
                headers=headers
            )
            
            if response.status_code == 200:
                supabase_users = response.json()
                if supabase_users:
                    for user in supabase_users:
                        c.execute("INSERT OR REPLACE INTO users (id, username, password, full_name) VALUES (?, ?, ?, ?)",
                                  (user.get('id'), user.get('username'), user.get('password'), user.get('full_name', '')))
                    print(f"✅ تم استعادة {len(supabase_users)} مستخدم من Supabase")
                    users_restored = True
        except Exception as e:
            print(f"⚠️ خطأ في استعادة المستخدمين من Supabase: {e}")
    
    # إضافة المستخدمين الافتراضيين فقط إذا لم يتم استعادة أي مستخدم
    if not users_restored:
        users = [
            ('admin', '123', 'مدير النظام'),
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
def migrate_database():
    """إضافة الأعمدة الجديدة إلى جدول elements إذا لم تكن موجودة"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # التحقق من وجود الأعمدة وإضافتها إذا لم تكن موجودة
    try:
        c.execute("ALTER TABLE elements ADD COLUMN appendix TEXT")
        print("✅ تم إضافة عمود appendix")
    except sqlite3.OperationalError:
        print("⚠️ عمود appendix موجود مسبقاً")
    
    try:
        c.execute("ALTER TABLE elements ADD COLUMN criteria TEXT")
        print("✅ تم إضافة عمود criteria")
    except sqlite3.OperationalError:
        print("⚠️ عمود criteria موجود مسبقاً")
    
    try:
        c.execute("ALTER TABLE elements ADD COLUMN indicators TEXT")
        print("✅ تم إضافة عمود indicators")
    except sqlite3.OperationalError:
        print("⚠️ عمود indicators موجود مسبقاً")
    
    # تحديث الصفوف القديمة بقيم افتراضية من element_id (فقط إذا كانت القيم فارغة أو أرقاماً)
    c.execute("SELECT element_id, id, appendix, criteria, indicators FROM elements")
    rows = c.fetchall()
    updated_count = 0
    for row in rows:
        element_id = row[0]
        element_id_parts = element_id.split('-')
        current_appendix = row[2] or ''
        current_criteria = row[3] or ''
        current_indicators = row[4] or ''
        
        # التحقق مما إذا كانت القيم الحالية هي أرقام (1,2,3...) أو فارغة
        needs_update = False
        
        # إذا كان الملحق فارغاً أو عبارة عن رقم (من element_id)
        if not current_appendix or (current_appendix.isdigit() and len(current_appendix) == 1):
            appendix_val = element_id_parts[1] if len(element_id_parts) > 1 else ''
            needs_update = True
        else:
            appendix_val = current_appendix
            
        # إذا كانت المعايير فارغة أو عبارة عن رقم (من element_id)
        if not current_criteria or (current_criteria.isdigit() and len(current_criteria) == 1):
            criteria_val = element_id_parts[2] if len(element_id_parts) > 2 else ''
            needs_update = True
        else:
            criteria_val = current_criteria
            
        # إذا كانت المؤشرات فارغة أو عبارة عن رقم (من element_id)
        if not current_indicators or (current_indicators.isdigit() and len(current_indicators) == 1):
            indicators_val = element_id_parts[3] if len(element_id_parts) > 3 else ''
            needs_update = True
        else:
            indicators_val = current_indicators
        
        if needs_update:
            c.execute("UPDATE elements SET appendix=?, criteria=?, indicators=? WHERE id=?",
                      (appendix_val, criteria_val, indicators_val, row[1]))
            updated_count += 1
    
    print(f"✅ تم تحديث {updated_count} عنصر بقيم appendix, criteria, indicators (مع الحفاظ على النصوص)")
    
    conn.commit()
    conn.close()
    print(f"✅ تم تحديث {len(rows)} عنصر بقيم appendix, criteria, indicators")

# استدعاء دالة الترحيل بعد إنشاء الجداول
init_local_db()
migrate_database()

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
    c.execute("SELECT username, element_id, witness_id, can_access FROM user_permissions")
    rows = c.fetchall()
    conn.close()

    permissions = [{'username': r[0], 'element_id': r[1], 'witness_id': r[2], 'can_access': r[3]} for r in rows]
    return jsonify({'success': True, 'data': permissions})

@app.route('/api/admin/set-permission', methods=['POST'])
def admin_set_permission():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    username = data.get('username')
    element_id = data.get('element_id')
    witness_id = data.get('witness_id')  # <-- جديد
    can_access = data.get('can_access', 1)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_permissions (username, element_id, witness_id, can_access)
                 VALUES (?, ?, ?, ?)''', (username, element_id, witness_id, can_access))
    
    # حفظ في Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        perm_data = {
            'username': username,
            'element_id': element_id,
            'witness_id': witness_id,
            'can_access': can_access
        }
        
        # التحقق من وجود الصلاحية مسبقاً
        check_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/user_permissions?username=eq.{username}&element_id=eq.{element_id}&witness_id=eq.{witness_id}",
            headers=headers
        )
        
        if check_response.status_code == 200 and check_response.json():
            # تحديث
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/user_permissions?username=eq.{username}&element_id=eq.{element_id}&witness_id=eq.{witness_id}",
                headers=headers,
                json=perm_data
            )
        else:
            # إضافة جديدة
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/user_permissions",
                headers=headers,
                json=perm_data
            )
        
        if response.status_code not in [200, 201, 204]:
            print(f"⚠️ فشل حفظ الصلاحية في Supabase: {response.status_code}")
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'تم تحديث الصلاحية'})

@app.route('/api/admin/get-user-witnesses', methods=['GET'])
def admin_get_user_witnesses():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})

    username = request.args.get('username')
    if not username:
        return jsonify({'success': False, 'error': 'اسم المستخدم مطلوب'})

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # جلب جميع الصلاحيات (element_id و witness_id) لهذا المستخدم
    c.execute("SELECT element_id, witness_id FROM user_permissions WHERE username=? AND can_access=1", (username,))
    rows = c.fetchall()
    conn.close()

    # تنظيم البيانات على شكل {element_id: [witness_id1, witness_id2]}
    user_witnesses = {}
    for element_id, witness_id in rows:
        if element_id not in user_witnesses:
            user_witnesses[element_id] = []
        user_witnesses[element_id].append(witness_id)

    return jsonify({'success': True, 'data': user_witnesses})

@app.route('/api/admin/all-elements', methods=['GET'])
def admin_all_elements():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    # جلب من قاعدة البيانات أولاً
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS elements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  element_id TEXT UNIQUE,
                  title TEXT,
                  witnesses TEXT)''')
    conn.commit()
    
    c.execute("SELECT element_id, title, witnesses, appendix, criteria, indicators FROM elements")
    rows = c.fetchall()
    conn.close()
    
    if rows:
        elements = {}
        for row in rows:
            try:
                witnesses = json.loads(row[2]) if row[2] else {}
            except:
                witnesses = {}
            elements[row[0]] = {"title": row[1], "witnesses": witnesses, "appendix": row[3] or '', "criteria": row[4] or '', "indicators": row[5] or ''}
        return jsonify({'success': True, 'elements': elements})
    else:
        # إذا كانت قاعدة البيانات فارغة، استخدم الثوابت القديمة
        return jsonify({'success': True, 'elements': ELEMENTS})

@app.route('/api/admin/get-all-elements-db', methods=['GET'])
def admin_get_all_elements_db():
    """جلب جميع العناصر من قاعدة البيانات (جدول elements)"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # إنشاء جدول elements إذا لم يكن موجوداً
    c.execute('''CREATE TABLE IF NOT EXISTS elements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  element_id TEXT UNIQUE,
                  title TEXT,
                  witnesses TEXT)''')
    
    # التحقق من وجود الأعمدة الجديدة وإضافتها إذا لزم الأمر
    try:
        c.execute("ALTER TABLE elements ADD COLUMN appendix TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE elements ADD COLUMN criteria TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE elements ADD COLUMN indicators TEXT")
    except: pass
    
    conn.commit()
    
    # جلب جميع الأعمدة
    c.execute("SELECT element_id, title, witnesses, appendix, criteria, indicators FROM elements ORDER BY element_id")
    rows = c.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        try:
            witnesses = json.loads(row[2]) if row[2] else {}
        except:
            witnesses = {}
        data.append({
            'element_id': row[0], 
            'title': row[1], 
            'witnesses': witnesses, 
            'appendix': row[3] if row[3] is not None else '', 
            'criteria': row[4] if row[4] is not None else '', 
            'indicators': row[5] if row[5] is not None else ''
        })
    
    return jsonify({'success': True, 'data': data})

@app.route('/api/admin/add-element', methods=['POST'])
def admin_add_element():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    element_id = data.get('element_id')
    title = data.get('title')
    witnesses = data.get('witnesses', [])
    
    if not element_id or not title:
        return jsonify({'success': False, 'error': 'رقم العنصر والعنوان مطلوبان'})
    
    # تقسيم element_id لتحديد الملحق والمعايير والمؤشرات
    parts = element_id.split('-')
    appendix = parts[1] if len(parts) > 1 else ''
    criteria = parts[2] if len(parts) > 2 else ''
    indicators = parts[3] if len(parts) > 3 else ''
    
    # تحويل قائمة الشواهد إلى قاموس مرقم
    witnesses_dict = {str(i+1): w for i, w in enumerate(witnesses)}
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # التحقق من عدم وجود العنصر
    c.execute("SELECT element_id FROM elements WHERE element_id=?", (element_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'رقم العنصر موجود مسبقاً'})
    
    try:
        c.execute("INSERT INTO elements (element_id, title, witnesses, appendix, criteria, indicators) VALUES (?, ?, ?, ?, ?, ?)",
                  (element_id, title, json.dumps(witnesses_dict, ensure_ascii=False), appendix, criteria, indicators))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم إضافة العنصر'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/update-element', methods=['POST'])
def admin_update_element():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    old_element_id = data.get('old_element_id')
    new_element_id = data.get('element_id')
    title = data.get('title')
    witnesses = data.get('witnesses', [])
    
    witnesses_dict = {str(i+1): w for i, w in enumerate(witnesses)}
    
    # تقسيم element_id الجديد
    parts = new_element_id.split('-')
    appendix = parts[1] if len(parts) > 1 else ''
    criteria = parts[2] if len(parts) > 2 else ''
    indicators = parts[3] if len(parts) > 3 else ''
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        if old_element_id != new_element_id:
            # التحقق من عدم وجود الرقم الجديد
            c.execute("SELECT element_id FROM elements WHERE element_id=?", (new_element_id,))
            if c.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'رقم العنصر الجديد موجود مسبقاً'})
            # تحديث في جدول evidences أيضاً
            c.execute("UPDATE evidences SET element_id=? WHERE element_id=?", (new_element_id, old_element_id))
            c.execute("UPDATE user_permissions SET element_id=? WHERE element_id=?", (new_element_id, old_element_id))
        
        c.execute("UPDATE elements SET element_id=?, title=?, witnesses=?, appendix=?, criteria=?, indicators=? WHERE element_id=?",
                  (new_element_id, title, json.dumps(witnesses_dict, ensure_ascii=False), appendix, criteria, indicators, old_element_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم تحديث العنصر'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete-element', methods=['POST'])
def admin_delete_element():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    element_id = data.get('element_id')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # حذف التوثيقات المرتبطة
        c.execute("DELETE FROM evidences WHERE element_id=?", (element_id,))
        # حذف صلاحيات المرتبطة
        c.execute("DELETE FROM user_permissions WHERE element_id=?", (element_id,))
        # حذف العنصر
        c.execute("DELETE FROM elements WHERE element_id=?", (element_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم حذف العنصر'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-my-elements', methods=['GET'])
def get_my_elements():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'غير مسجل دخول'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # جلب جميع الصلاحيات لهذا المستخدم (عنصر + شاهد)
    c.execute("SELECT element_id, witness_id FROM user_permissions WHERE username=? AND can_access=1", (session['username'],))
    rows = c.fetchall()
    conn.close()

    # تنظيم البيانات لإرسالها للمراقب
    allowed_witnesses = {}
    for element_id, witness_id in rows:
        if element_id not in allowed_witnesses:
            allowed_witnesses[element_id] = []
        allowed_witnesses[element_id].append(witness_id)

    # إذا لم تكن هناك صلاحيات محددة، نرسل قاموساً فارغاً ولن يرى أي شيء
    return jsonify({'success': True, 'data': allowed_witnesses})

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
# ... (LOGIN_PAGE, DASHBOARD_PAGE, ADMIN_PAGE - نفس المحتوى السابق، لم يتغير)
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

# ============ باقي المحتوى (DASHBOARD_PAGE, ADMIN_PAGE) ============
# ... (محذوف للاختصار، لكن يجب إبقاؤه كما هو في الكود الأصلي)

# ============ Routes API ============
@app.route('/')
def index():
    return render_template_string(LOGIN_PAGE)

# ... (باقي Routes API كما هي في الكود الأصلي)

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
    app.run(host='0.0.0.0', port=10000, debug=False)
