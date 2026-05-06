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
    """تعديل مستخدم (كلمة السر أو الاسم)"""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    data = request.json
    user_id = data.get('id')
    password = data.get('password')
    full_name = data.get('full_name')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    updates = []
    values = []
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
    1: {"title": "تعزيز القيم الإسلامية والهوية الوطنية", "witnesses": [
        "تُذاع إذاعة مدرسية صباحية تتضمن فقرة عن قصة وطنية أو قيمة إسلامية أسبوعياً",
        "ينظم المعلم مسابقة داخل الصف عن أسماء ملوك أو قادة البلاد",
        "يردد المتعلمون النشيد الوطني باحترام ووقوف في طابور الصباح",
        "يذكر المعلم مناسبات وطنية (مثل اليوم الوطني) وينفذ نشاطاً فنياً عنها",
        "يروي المعلم قصة قصيرة عن تضحيات رجال الأمن أو الجيش للمحافظة على الوطن",
        "يكتب المتعلمون عبارات تعبر عن حب الوطن على لوحة الإعلانات الصفية",
        "تُعرض في المدرسة صور أو رسومات تعبر عن القيم الإسلامية (الصدق، الأمانة، التعاون)"
    ]},
    2: {"title": "مناخ آمن للتعلم", "witnesses": [
        "يلتزم المعلم بعدم استخدام أي عبارات سخرية أو تنميط تجاه المتعلمين",
        "تُطبق المدرسة نظام إحالة للحالات النفسية إلى المرشد خلال 24 ساعة",
        "يشعر المتعلمون بالأمان عند التعبير عن رأيهم دون خوف من العقاب",
        "يتوفر في الصف جدار للتواصل (اقتراحات، شكاوى) يكتب فيه المتعلمون بحرية",
        "يعرف المتعلمون مكان المرشد الطلابي ويسهل الوصول إليه",
        "يلاحظ المراقب غياب التنمر اللفظي أو الجسدي بين المتعلمين",
        "يطبق المعلم خطة إخلاء واضحة عند الطوارئ ويدرب المتعلمين عليها"
    ]},
    3: {"title": "مصادر وأنشطة متنوعة تلبي احتياجات المتعلمين", "witnesses": [
        "يتوفر في الصف كتاب بطريقة برايل أو نسخ إلكترونية صوتية لذوي الإعاقة البصرية",
        "يخصص المعلم مهام إثرائية إضافية للمتعلمين الموهوبين",
        "يُستخدم جهاز تضخيم الصوت أو سماعات للمتعلمين ضعاف السمع",
        "تتوفر أوراق عمل بخط كبير ومبسط لذوي صعوبات التعلم",
        "يُتاح للمتعلم ذي الإعاقة الحركية مكان جلوس مناسب بالقرب من المدخل",
        "يوظف المعلم سبورة تفاعلية أو أجهزة لوحية لتنوع المصادر",
        "تُقدم أنشطة حركية أو حسية تناسب مختلف أنماط التعلم"
    ]},
    4: {"title": "إدارة الوقت بفاعلية", "witnesses": [
        "يخصص المعلم 5 دقائق إضافية للطالب ذي الإعاقة الحركية لإنهاء النشاط الكتابي",
        "يوزع المعلم وقت الحصة بوضوح (تمهيد 5 د، عرض 15 د، تطبيق 10 د، ختام 5 د)",
        "يُعطى المتعلمون إشارات زمنية (مثل: تبقى 3 دقائق) لتنظيم عملهم",
        "ينتهي المعلم من الأنشطة قبل نهاية الحصة بوقت كاف لإعطاء التغذية الراجعة",
        "ينتقل المعلم بين الأنشطة بسلاسة دون وقت ضائع في التنظيم أو التوجيه",
        "يراعى وقت الحصة عند تصميم الأنشطة بحيث لا تطول أو تقصر عن المطلوب",
        "يُتاح وقت إضافي للموهوبين لاستكشاف موضوع أعمق والضعفاء لإنجاز الأساسيات"
    ]},
    5: {"title": "فرص متكافئة في الأنشطة والمناقشة", "witnesses": [
        "يدعو المعلم المتعلمين بالتبادل عبر بطاقات الأسماء، وليس فقط من يرفع يده أولاً",
        "يسمح المعلم للمتعلمين في الخلف أو الأطراف بالمشاركة بقدر من في المقدمة",
        "تتنقل المعلمة بين جميع المجموعات بالتساوي أثناء الأنشطة الجماعية",
        "يُتيح الجهاز اللوحي أو الكمبيوتر لجميع المتعلمين بالتناوب وليس لشخص واحد",
        "تُوزع أدوات التعلم (سبورة، أقلام، مجسمات) بالعدل دون تمييز",
        "يحرص المعلم على توجيه أسئلة للإناث والذكور وللطلاب ذوي المستويات المختلفة",
        "يتاح للجميع الاقتراب من السبورة أو المجسم لعرض أفكارهم"
    ]},
    6: {"title": "مصادر تعلم متنوعة تدعم المناهج", "witnesses": [
        "توجد في المدرسة مجسمات، خرائط، أدوات معمل، وقصص رقمية توازي كل وحدة دراسية",
        "تتوفر مكتبة صفية تحتوي على مراجع إضافية للبحث والاستزادة",
        "يستخدم المعلم أجهزة عرض البيانات (داتاشو) لعرض فيديوهات تعليمية",
        "يُمكن الوصول إلى منصة تعليمية رقمية (مثل Classroom، Teams) تحتوي على محتوى المنهج",
        "تُوفر المدرسة أقراصاً تعليمية أو كتباً إلكترونية لجميع المواد",
        "يوجد في الصف وسائل تعليمية يدوية الصنع من إعداد المعلم أو المتعلمين",
        "تتنوع المصادر بين سمعية وبصرية وملموسة ورقمية لتغطية كل نواتج التعلم"
    ]},
    7: {"title": "أنشطة واستراتيجيات تدريس تحقق نواتج التعلم", "witnesses": [
        "يكتب المعلم ناتج التعلم على السبورة، ثم يصمم نشاطاً يثبت هذا الناتج",
        "يرتبط كل نشاط يقوم به المتعلمون بشكل مباشر بهدف الحصة",
        "في نهاية الحصة، يستطيع المتعلم التعبير عما تعلمه بنفس لفظ ناتج التعلم",
        "لا يوجد نشاط في الحصة خارج نطاق نواتج التعلم المعلنة",
        "يُقيّم المعلم مدى تحقيق النشاط لناتج التعلم بشكل علني",
        "تتنوع الأنشطة لتحقيق أبعاد مختلفة من نواتج التعلم (معرفي، مهاري، وجداني)",
        "يعيد المعلم صياغة ناتج التعلم بلغة المتعلمين قبل بدء النشاط"
    ]},
    8: {"title": "تنوع استراتيجيات التدريس وفق قدرات المتعلمين", "witnesses": [
        "يوجه المعلم سؤالاً مختلفاً لكل مجموعة (حفظ للمبتدئين، فهم للمتوسطين، تطبيق للمتفوقين)",
        "يستخدم المعلم أكثر من استراتيجية في الحصة الواحدة (حوار، لعب أدوار، عمل جماعي، عصف ذهني)",
        "يُقدم النشاط الواحد بطريقتين (كتابي وشفهي أو يدوي ورقمي) لمراعاة الفروق",
        "يسمح المعلم للمتعلم السريع بالانتقال إلى نشاط إضافي بينما يتابع البقية",
        "يُلحق المعلم مهام داعمة للضعفاء ومهام توسعة للمتفوقين بنفس الدرس",
        "يراعي المعلم الفروق في طريقة الشرح (بصري، سمعي، حركي) خلال الحصة",
        "يغير المعلم شكل المجموعات (ثنائية، فردية، جماعية) حسب قدرات المتعلمين"
    ]},
    9: {"title": "استخدام مصادر تعلم رقمية", "witnesses": [
        "يوظف المعلم رابط فيديو قصيراً + لعبة تفاعلية (مثل Kahoot أو Quizizz) في الحصة",
        "يتيح المعلم خيار القراءة الرقمية أو الورقية حسب رغبة المتعلم",
        "يستخدم المعلم السبورة التفاعلية لعرض الصور والمقاطع المرئية",
        "يوفر المعلم تطبيقاً تعليمياً على الجهاز اللوحي يسمح باختيار مستوى الصعوبة",
        "يعرض المعلم محاكاة رقمية (محاكي) لتجربة علمية بدلاً من المجسمات التقليدية",
        "يستخدم المعلم رمز QR سريعاً للوصلة إلى مصدر إضافي للطلاب المتقدمين",
        "يتيح المعلم لذوي صعوبات القراءة الاستماع إلى النص عبر مكبر الصوت"
    ]},
    10: {"title": "تطبيقات عملية مرتبطة بحياة المتعلمين", "witnesses": [
        "ينفذ المتعلمون محاكاة لشراء السلع باستخدام حسابات النسبة المئوية للخصم",
        "يطلب المعلم من المتعلمين إحصاء عدد زملائهم في الصف كتطبيق على عملية الجمع",
        "يصمم المتعلمون جدولاً لحصصهم الأسبوعية باستخدام برنامج إلكتروني",
        "يكتب المتعلمون رسالة شكر لأحد العمال في المدرسة (تطبيق على فن الكتابة)",
        "يحسب المتعلمون استهلاك الماء أو الكهرباء في المنزل ضمن مادة العلوم",
        "ينفذ المعلم نشاط إعادة تدوير علب الكرتون ضمن مادة التربية الفنية",
        "يطبق المتعلمون آداب الحوار أثناء مناقشة مشكلة حقيقية في الصف (مثل تأخر الواجبات)"
    ]},
    11: {"title": "تنمية مهارات القراءة والكتابة", "witnesses": [
        "يقرأ كل متعلم فقرة بصوت منخفض، ثم يكتب تعليقاً من سطرين في دفتر التفاعل",
        "تتوفر في ركن القراءة كتب قصصية وقصائد ومجلات مناسبة لأعمارهم",
        "يكتب المتعلمون تلخيصاً يومياً للحصة في جملتين في نهاية اليوم",
        "ينظم المعلم مسابقة إملاء أو قراءة سريعة بين المجموعات",
        "يخصص المعلم 10 دقائق أسبوعياً للقراءة الحرة يليها تسجيل في سجل القراءة",
        "تُعرض على جدار الصف جمل أو فقرات أسبوعية يقرؤها المتعلمون عند الدخول",
        "يستخدم المعلم بطاقات الكلمات لتدريب المتعلمين الضعفاء على القراءة"
    ]},
    12: {"title": "تنمية المهارات العددية (الحساب)", "witnesses": [
        "يستخدم المعلم عدادات رقمية أو مكعبات صغيرة لحل مسائل الجمع والطرح يومياً",
        "يبدأ المعلم الحصة بمسألة حسابية قصيرة على السبورة يحلها الجميع",
        "يتوفر في الصف ركن الرياضيات يحتوي على مجسمات هندسية وأعداد",
        "يطلب المعلم من المتعلمين حساب عدد الطلاب الحاضرين والغائبين شفوياً",
        "يستخدم المعلم أسئلة سريعة (مثل: كم ربعاً في الواحد الصحيح؟) يومياً",
        "ينظم المعلم لعبة بنك الأرقام (تجميع بطاقات الأرقام لإكمال معادلة)",
        "يستخدم المتعلمون السبورة الصغيرة لحل مسائل الحساب الذهني وتصحيحها جماعياً"
    ]},
    13: {"title": "تنمية مهارات التفكير والبحث والابتكار", "witnesses": [
        "يطرح المعلم سؤالاً مفتوحاً (مثل: كيف يمكننا حل مشكلة التلوث في الحي؟) دون إجابة جاهزة",
        "يُعطي المعلم وقتاً صامتاً للتفكير قبل الإجابة (3-5 ثوانٍ)",
        "يطلب المعلم من المتعلمين البحث عن إجابة سؤال عبر الإنترنت أو الموسوعة المدرسية",
        "يُشجع المعلم المتعلمين على اقتراح حلول غير تقليدية للمشكلات",
        "ينظم المعلم مسابقة أفضل اختراع أو فكرة إبداعية في نهاية الوحدة",
        "يستخدم المعلم خرائط التفكير (مثل خريطة المفاهيم) لتنظيم الأفكار",
        "يوجه المعلم أسئلة (ماذا لو؟ كيف يمكن تحسين؟) لتوليد أفكار جديدة"
    ]},
    14: {"title": "تنمية المهارات العاطفية والاجتماعية", "witnesses": [
        "يستخدم المعلم بطاقات المشاعر (سعيد، حزين، متحمس، خائف) ليختار كل متعلم ما يشعر به بداية الحصة",
        "يُخصص المعلم 5 دقائق للحوار الحر حول موقف عاطفي مر به أحد المتعلمين",
        "يشجع المعلم المتعلمين على الاعتذار لبعضهم البعض بعد خلاف",
        "يوزع المعلم أدواراً في الأنشطة الجماعية (قائد، كاتب، مقرر) لتعزيز العمل الجماعي",
        "يُدرّب المعلم المتعلمين على عبارات التعاطف (مثل: أشعر بك، كيف أساعدك؟)",
        "ينظم المعلم جلسة \"كيف كنت اليوم\" يعبر فيها الجميع عن يومهم",
        "يبارك المعلم للمتعلم في مناسبة سعيدة (نجاح، عيد، مناسبة عائلية)"
    ]},
    15: {"title": "أساليب تحفيز تعزز الدافعية", "witnesses": [
        "يمنح المعلم ملصق شكر أو نجمة ذهبية لكل متعلم ينهي مهمة صعبة بشكل صحيح",
        "يستخدم المعلم لوحة شرف أسبوعية تُعرض عليها أسماء المجتهدين",
        "يقدم المعلم مكافأة رمزية (قلم، ممحاة) للمتعلم صاحب أفضل إجابة",
        "يُخرج المعلم صفارة تشجيع أو تصفيق جماعي لكل مشاركة صحيحة",
        "يخصص المعلم رصيد نقاط يتحول إلى دقائق لعب في نهاية الأسبوع",
        "يذكر المعلم المتعلم باسمه ويشيد به أمام الجميع عند الإجابة الجيدة",
        "يستخدم المعلم عبارات تحفيزية مكتوبة على بطاقات (ممتاز، رائع، أبدعت)"
    ]},
    16: {"title": "مشاركة المتعلمين في الأنشطة بفاعلية", "witnesses": [
        "يظهر على المتعلمين الحماس والابتسام والتنافس الإيجابي أثناء اللعبة التعليمية",
        "يطلب المتعلمون من المعلم تكرار النشاط لأنه ممتع",
        "يتطوع المتعلمون للمشاركة دون إحراج أو خوف",
        "يصغي المتعلمون بانتباه لشرح المعلم أثناء النشاط التفاعلي",
        "يضحك المتعلمون ويصفقون لزملائهم أثناء عروضهم",
        "لا يظهر على المتعلمين علامات الملل أو التثاؤب أو الانشغال بأمور أخرى",
        "يتحدث المتعلمون عن النشاط مع زملائهم بعد الحصة بحماس"
    ]},
    17: {"title": "أساليب تقويم متنوعة للكشف عن الفروق الفردية", "witnesses": [
        "يبدأ المعلم بثلاث أسئلة تشخيصية لمعرفة مستوى المتعلمين القديم",
        "يستخدم المعلم الملاحظة أثناء عمل المجموعات كأداة تقويم بنائي",
        "ينهي المعلم الحصة ببطاقة خروج (سؤال أو اثنان يقيسان الفهم)",
        "يوجه المعلم أسئلة شفهية متفاوتة الصعوبة للمتعلمين أثناء الحصة",
        "يستخدم المعلم قائمة رصد لتحديد نقاط القوة والضعف لكل متعلم",
        "يحتفظ المعلم بمحفظة إنجاز واحدة لكل متعلم تجمع أعماله",
        "يقوم المعلم ذاتياً (ينتقد أداء تعليمه) بناءً على نتائج التقويم"
    ]},
    18: {"title": "قياس مستوى تحقق نواتج التعلم", "witnesses": [
        "يطلب المعلم من كل متعلم كتابة إجابة سؤال ناتج التعلم الرئيسي على ورقة مصغرة ويجمعها",
        "يصمم المعلم اختباراً قصيراً من فقرات تغطي كل نواتج التعلم",
        "يوجه المعلم سؤالاً شفهياً لكل متعلم يقيس ناتج تعلم معين",
        "يستخدم المعلم مشروعاً أو عرضاً تقديمياً كأداة تقويم ختامي",
        "يُخرج المعلم ورقة عمل ختامية تحوي أنشطة تطابق نواتج التعلم",
        "يحلل المعلم نتائج التقويم لمعرفة النواتج التي لم تتحقق جيداً",
        "يطلب المعلم من المتعلم أن يقيم نفسه وفق نواتج التعلم (تقويم ذاتي)"
    ]},
    19: {"title": "تغذية راجعة متنوعة لتحسين الأداء", "witnesses": [
        "لا يكتفي المعلم بعبارة \"خطأ\"، بل يقول: \"حاول أن تبدأ بالقانون قبل التعويض بالأرقام\"",
        "يقدم المعلم تغذية راجعة فورية بعد إجابة كل متعلم",
        "يستخدم المعلم إشارات غير لفظية (إبهام، تصفيق هادئ) كتغذية راجعة سريعة",
        "يكتب المعلم ملاحظات إيجابية وتصحيحية على دفتر المتعلم بدلاً من علامة فقط",
        "يجلس المعلم بجانب المتعلم الضعيف ليعطيه تغذية راجعة فردية خاصة",
        "يعيد المعلم صياغة إجابة المتعلم بطريقة أصح أمام الجميع كتغذية راجعة جماعية",
        "يخصص المعلم دقيقتين في نهاية الحصة للتعليق على أبرز الأخطاء وتصحيحها"
    ]},
    20: {"title": "الاعتزاز بالقيم والهوية الوطنية", "witnesses": [
        "يتطوع المتعلمون بتحية العلم بفخر ويقفون بخشوع أثناء النشيد الوطني",
        "يذكر المتعلمون أسماء قادة البلاد بتقدير واحترام عند الحديث عنهم",
        "يرتدي المتعلمون الزي الوطني في المناسبات الوطنية بفخر واعتزاز",
        "ينشد المتعلمون الأناشيد الوطنية بتلقائية في الإذاعة المدرسية أو داخل الصف",
        "يعبر المتعلمون في رسوماتهم أو كتاباتهم عن حب الوطن وفخره به",
        "يشارك المتعلمون في الفعاليات الوطنية (كاليوم الوطني) دون إجبار",
        "يتحدث المتعلمون بإيجابية عن تاريخ بلدهم وإنجازاته عند سؤالهم عنه"
    ]},
    21: {"title": "الاتجاهات الإيجابية نحو الذوات والآخرين", "witnesses": [
        "يشجع المتعلم زميله بعد إجابة خاطئة بعبارة: \"محاولة جيدة، ستنجح المرة القادمة\"",
        "يثني المتعلم على زميله بعبارة \"أحسنت\" أو \"رائع\" دون طلب من المعلم",
        "يقدم المتعلم المساعدة لزميله دون أن يطلب منه المعلم ذلك",
        "يقبل المتعلم النقد البناء من المعلم أو الزملاء دون انزعاج أو انسحاب",
        "يُظهر المتعلم ثقته بنفسه عند الإجابة على الأسئلة",
        "لا يسخر المتعلمون من زميل أخطأ أو تأخر في الإجابة",
        "يفرح المتعلمون بنجاحات زملائهم ويشاركونهم الاحتفال بها"
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
    
    # إضافة 11 مستخدم (مدير + 10 مراقبين)
    users = [
        ('admin', 'admin123', 'مدير النظام'),
        ('عادل', '123', 'المراقب الأول'),
        ('حسن', '123', 'المراقب الثاني'),
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
<div class="error" id="errorMsg"></div><div class="info">🔐 </div></div>
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
</style>
</head>
<body>
<div class="sidebar"><h3>📸 نظام التوثيق</h3>
<div class="nav-item active" onclick="showSection('dashboard')"><span style="margin-left:10px;">📋</span> لوحة التوثيق</div>
<div class="nav-item" onclick="showSection('stats')"><span style="margin-left:10px;">📊</span> إحصائياتي</div>
<div class="nav-item" onclick="showSection('history')"><span style="margin-left:10px;">🖼️</span> توثيقاتي السابقة</div>
<button class="logout-btn" onclick="logout()">🚪 تسجيل خروج</button></div>
<div class="main-content"><div class="header"><h2>مرحباً <span id="usernameDisplay">{{ username }}</span></h2><div>📅 <span id="dateDisplay"></span></div></div>
<div id="dashboardSection"><div class="elements-grid" id="elementsGrid"></div></div>
<div id="statsSection" style="display:none;"><div style="background:white;border-radius:15px;padding:20px;"><h3>📊 إحصائيات التوثيقات</h3><div id="statsNumbers" style="margin-top:20px;"></div></div></div>
<div id="historySection" style="display:none;"><div style="background:white;border-radius:15px;padding:20px;"><h3>🖼️ توثيقاتي السابقة</h3><div id="historyGrid" class="history-grid"></div></div></div></div>
<div id="cameraModal" class="modal"><div class="modal-content"><video id="video" autoplay playsinline></video><div style="display:flex; gap:10px; margin-top:15px;"><button class="capture-btn" id="switchCameraBtn" style="background:#17a2b8; flex:1;">🔄 تبديل الكاميرا</button><button class="capture-btn" id="uploadImageBtn" style="background:#6c757d; flex:1;">📁 اختيار من المعرض</button></div><button class="capture-btn" onclick="capturePhoto()" style="margin-top:10px;">📷 التقاط صورة</button><button class="capture-btn close-modal" onclick="closeCamera()" style="margin-top:10px; background:#dc3545;">إلغاء</button></div></div>
<canvas id="canvas" style="display:none"></canvas>
<script>
const elements = {{ elements | tojson }};
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
            div.innerHTML=`<span class="witness-text">${idx+1}. ${text}</span><span class="camera-icon" onclick="openCamera(${id},${idx+1})">📷</span>`;
            list.appendChild(div);
        });
    }
}
async function openCamera(elementId,witnessId){
    currentElementId=elementId;currentWitnessId=witnessId;
    document.getElementById('cameraModal').style.display='block';
    try{stream=await navigator.mediaDevices.getUserMedia({video:true});document.getElementById('video').srcObject=stream;}
    catch(err){alert('لا يمكن الوصول إلى الكاميرا: '+err.message);}
}
async function capturePhoto(){
    const video=document.getElementById('video');const canvas=document.getElementById('canvas');
    if(video.videoWidth && video.videoHeight){
        canvas.width=video.videoWidth;canvas.height=video.videoHeight;
        canvas.getContext('2d').drawImage(video,0,0);
        const imageData=canvas.toDataURL('image/jpeg',0.9);
        const response=await fetch('/api/save-evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({element_id:currentElementId,witness_id:currentWitnessId,image:imageData})});
        const result=await response.json();
        if(result.success){alert('✅ تم التوثيق بنجاح!');closeCamera();if(document.getElementById('statsSection').style.display==='block')loadStats();if(document.getElementById('historySection').style.display==='block')loadHistory();}
        else alert('❌ خطأ: '+result.error);
    } else {
        alert('❌ لم يتم التقاط الصورة، تأكد من تشغيل الكاميرا');
    }
}

function uploadFromGallery(){
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if(file){
            const reader = new FileReader();
            reader.onload = async (event) => {
                const imageData = event.target.result;
                const response = await fetch('/api/save-evidence',{
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({element_id:currentElementId,witness_id:currentWitnessId,image:imageData})
                });
                const result = await response.json();
                if(result.success){alert('✅ تم التوثيق بنجاح!');closeCamera();if(document.getElementById('statsSection').style.display==='block')loadStats();if(document.getElementById('historySection').style.display==='block')loadHistory();}
                else alert('❌ خطأ: '+result.error);
            };
            reader.readAsDataURL(file);
        }
    };
    input.click();
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
async function loadHistory(){
    const response=await fetch('/api/get-my-evidences');
    const data=await response.json();
    const grid=document.getElementById('historyGrid');
    if(data.success && data.data.length>0){
        grid.innerHTML=data.data.map(item=>`<div class="history-card"><img src="/${item.image_path}" onerror="this.src='https://via.placeholder.com/150?text=صورة'"><p style="margin-top:8px;font-size:12px;">${item.element_title.substring(0,30)}</p><small>${new Date(item.created_at).toLocaleDateString('ar-SA')}</small></div>`).join('');
    }else{grid.innerHTML='<p>لا توجد توثيقات سابقة</p>';}
}
async function logout(){await fetch('/api/logout',{method:'POST'});window.location.href='/';}
document.getElementById('dateDisplay').innerText=new Date().toLocaleDateString('ar-SA');
document.getElementById('usernameDisplay').innerText='{{ username }}';
displayElements();
document.getElementById('switchCameraBtn').onclick = switchCamera;
document.getElementById('uploadImageBtn').onclick = uploadFromGallery;
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
.modal-content{background:white;border-radius:15px;padding:25px;width:90%;max-width:400px}
.modal-content input{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:8px}
.modal-buttons{display:flex;gap:10px;margin-top:20px}
.modal-buttons button{flex:1}
@media(max-width:768px){.sidebar{width:220px}.main-content{margin-right:220px}}
</style>
</head>
<body>
<div class="sidebar"><h3>👑 لوحة المدير</h3>
<div class="nav-item active" onclick="showSection('all')">📋 جميع التوثيقات</div>
<div class="nav-item" onclick="showSection('users')">👥 إدارة المستخدمين</div>
<div class="nav-item" onclick="showSection('sync')">🔄 المزامنة</div>
<button class="logout-btn" onclick="logout()">🚪 خروج</button></div>
<div class="main-content"><div class="header"><h2>لوحة تحكم المدير</h2><div id="dateDisplay"></div></div>
<div class="stats"><div class="stat-card"><div class="stat-number" id="totalCount">0</div><div>إجمالي التوثيقات</div></div>
<div class="stat-card"><div class="stat-number" id="usersCount">0</div><div>عدد المراقبين</div></div>
<div class="stat-card"><div class="stat-number" id="todayCount">0</div><div>توثيقات اليوم</div></div></div>
<div id="allSection"><div class="action-buttons"><button class="btn btn-primary" onclick="exportCSV()">📥 تصدير CSV</button><button class="btn btn-primary" onclick="refreshData()">🔄 تحديث</button></div>
<div style="overflow-x:auto;"><table><thead><tr><th>#</th><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>الصورة</th><th>التاريخ</th></tr></thead><tbody id="tableBody"></tbody></table></div></div>
<div id="usersSection" style="display:none;"><div class="sync-buttons"><button class="btn btn-success" onclick="showAddUserModal()">➕ إضافة مستخدم جديد</button><button class="btn btn-primary" onclick="loadUsers()">🔄 تحديث القائمة</button></div>
<div style="overflow-x:auto;margin-top:20px;"><table><thead><tr><th>#</th><th>اسم المستخدم</th><th>الاسم الكامل</th><th>النوع</th><th>الإجراءات</th></tr></thead><tbody id="usersTableBody"></tbody></table></div></div>
<div id="syncSection" style="display:none;"><div class="sync-status" id="syncStatus"></div><div class="sync-buttons"><button class="btn btn-primary" onclick="syncToCloud()">☁️ مزامنة إلى السحابة</button><button class="btn btn-success" onclick="syncFromCloud()">📥 جلب من السحابة</button></div>
<div style="background:white;border-radius:15px;padding:20px;margin-top:20px;"><h4>ℹ️ حول المزامنة</h4><p>• "مزامنة إلى السحابة": رفع التوثيقات المحلية إلى Supabase</p><p>• "جلب من السحابة": تحميل التوثيقات من Supabase إلى الجهاز</p><p>• ملاحظة: يجب إعداد Supabase أولاً في متغيرات البيئة</p></div></div></div>
<div id="addUserModal" class="modal"><div class="modal-content"><h3>➕ إضافة مستخدم جديد</h3><input type="text" id="newUsername" placeholder="اسم المستخدم" required><input type="text" id="newFullName" placeholder="الاسم الكامل"><input type="password" id="newPassword" placeholder="كلمة السر" value="pass123"><div class="modal-buttons"><button class="btn btn-success" onclick="addUser()">إضافة</button><button class="btn btn-danger" onclick="closeAddUserModal()">إلغاء</button></div></div></div>
<div id="editUserModal" class="modal"><div class="modal-content"><h3>✏️ تعديل مستخدم</h3><input type="hidden" id="editUserId"><input type="text" id="editFullName" placeholder="الاسم الكامل"><input type="password" id="editPassword" placeholder="كلمة سر جديدة (اتركها فارغة إذا لا تريد تغييرها)"><div class="modal-buttons"><button class="btn btn-primary" onclick="updateUser()">حفظ التغييرات</button><button class="btn btn-danger" onclick="closeEditUserModal()">إلغاء</button></div></div></div>
<script>
let allData=[];
async function refreshData(){
    const response=await fetch('/api/admin/all-evidences');
    const data=await response.json();
    if(data.success){
        allData=data.data;
        document.getElementById('totalCount').innerText=allData.length;
        const users=[...new Set(allData.map(e=>e.username))];
        document.getElementById('usersCount').innerText=users.length;
        const today=allData.filter(e=>new Date(e.created_at).toDateString()===new Date().toDateString()).length;
        document.getElementById('todayCount').innerText=today;
        const tbody=document.getElementById('tableBody');
        if(allData.length===0){tbody.innerHTML='<tr><td colspan="6" style="text-align:center;">لا توجد توثيقات بعد</td></tr>';}
        else{tbody.innerHTML=allData.map((item,i)=>`<tr><td>${i+1}</td><td>${item.username}</td><td>العنصر ${item.element_id}</td><td>${item.witness_text.substring(0,40)}...</td><td><img src="/${item.image_path}" class="evidence-img" onerror="this.src='https://via.placeholder.com/50?text=لا+صورة'" onclick="window.open('/${item.image_path}')"></td><td>${new Date(item.created_at).toLocaleDateString('ar-SA')}</td></tr>`).join('');}
    }
}
async function loadUsers(){
    const response=await fetch('/api/admin/users');
    const data=await response.json();
    if(data.success){
        const tbody=document.getElementById('usersTableBody');
        tbody.innerHTML=data.data.map((user,i)=>`<tr><td>${i+1}</td><td>${user.username}</td><td>${user.full_name||'-'}</td><td>${user.type==='admin'?'مدير':'مراقب'}</td><td>${user.username!=='admin'?`<button class="btn btn-warning" onclick="showEditUserModal(${user.id},'${user.username}','${user.full_name||''}')" style="margin-left:5px;">✏️ تعديل</button><button class="btn btn-danger" onclick="deleteUser(${user.id},'${user.username}')">🗑️ حذف</button><button class="btn btn-info" onclick="resetPassword(${user.id})">🔑 إعادة تعيين</button>`:'<span style="color:#999;">لا يمكن تعديل المدير</span>'}</td></tr>`).join('');
    }
}
function showAddUserModal(){document.getElementById('addUserModal').style.display='flex';}
function closeAddUserModal(){document.getElementById('addUserModal').style.display='none';document.getElementById('newUsername').value='';document.getElementById('newFullName').value='';document.getElementById('newPassword').value='pass123';}
async function addUser(){
    const username=document.getElementById('newUsername').value;
    const full_name=document.getElementById('newFullName').value;
    const password=document.getElementById('newPassword').value;
    if(!username){alert('يرجى إدخال اسم المستخدم');return;}
    const response=await fetch('/api/admin/add-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,full_name})});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);closeAddUserModal();loadUsers();refreshData();}
    else{alert('❌ '+result.error);}
}
let currentEditId=null,currentEditUsername=null;
function showEditUserModal(id,username,full_name){
    currentEditId=id;currentEditUsername=username;
    document.getElementById('editUserId').value=id;
    document.getElementById('editFullName').value=full_name||'';
    document.getElementById('editPassword').value='';
    document.getElementById('editUserModal').style.display='flex';
}
function closeEditUserModal(){document.getElementById('editUserModal').style.display='none';currentEditId=null;currentEditUsername=null;}
async function updateUser(){
    const full_name=document.getElementById('editFullName').value;
    const password=document.getElementById('editPassword').value;
    const body={id:currentEditId};
    if(full_name)body.full_name=full_name;
    if(password)body.password=password;
    const response=await fetch('/api/admin/update-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);closeEditUserModal();loadUsers();refreshData();}
    else{alert('❌ '+result.error);}
}
async function deleteUser(id,username){
    if(confirm(`هل أنت متأكد من حذف المستخدم "${username}"؟ سيتم حذف جميع توثيقاته أيضاً.`)){
        const response=await fetch('/api/admin/delete-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,username})});
        const result=await response.json();
        if(result.success){alert('✅ '+result.message);loadUsers();refreshData();}
        else{alert('❌ '+result.error);}
    }
}
async function resetPassword(id){
    const newPassword=prompt('أدخل كلمة السر الجديدة (اتركها فارغة لاستخدام الافتراضي pass123)');
    if(newPassword===null)return;
    const response=await fetch('/api/admin/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,new_password:newPassword||'pass123'})});
    const result=await response.json();
    if(result.success){alert('✅ '+result.message);}
    else{alert('❌ '+result.error);}
}
async function syncToCloud(){
    const status=document.getElementById('syncStatus');
    status.style.display='block';status.innerHTML='⏳ جاري المزامنة إلى السحابة...';
    const response=await fetch('/api/sync-to-cloud',{method:'POST'});
    const result=await response.json();
    if(result.success){status.innerHTML=`✅ تم المزامنة بنجاح! ${result.synced} توثيق.`;refreshData();}
    else{status.innerHTML=`❌ خطأ: ${result.error||'فشل المزامنة'}`;}
    setTimeout(()=>status.style.display='none',3000);
}
async function syncFromCloud(){
    const status=document.getElementById('syncStatus');
    status.style.display='block';status.innerHTML='⏳ جاري الجلب من السحابة...';
    const response=await fetch('/api/sync-from-cloud',{method:'POST'});
    const result=await response.json();
    if(result.success){status.innerHTML=`✅ تم الجلب بنجاح! ${result.synced} توثيق.`;refreshData();loadUsers();}
    else{status.innerHTML=`❌ خطأ: ${result.error||'فشل الجلب'}`;}
    setTimeout(()=>status.style.display='none',3000);
}
function exportCSV(){
    let csv="المراقب,رقم العنصر,رقم الشاهد,نص الشاهد,التاريخ\n";
    allData.forEach(e=>{csv+=`"${e.username}","${e.element_id}","${e.witness_id}","${e.witness_text}","${e.created_at}"\n`;});
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);
    link.download=`evidences_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
}
function showSection(section){
    document.getElementById('allSection').style.display=section==='all'?'block':'none';
    document.getElementById('usersSection').style.display=section==='users'?'block':'none';
    document.getElementById('syncSection').style.display=section==='sync'?'block':'none';
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach((item)=>{
        item.classList.remove('active');
        if(item.getAttribute('onclick') === `showSection('${section}')`){
            item.classList.add('active');
        }
    });
    if(section==='users')loadUsers();
}
async function logout(){await fetch('/api/logout',{method:'POST'});window.location.href='/';}
document.getElementById('dateDisplay').innerText=new Date().toLocaleDateString('ar-SA');
refreshData();
</script>
</body>
</html>
'''

# ============ Routes API ============
@app.route('/')
def index():
    return render_template_string(LOGIN_PAGE)

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
    element_id = int(data.get('element_id'))
    witness_id = int(data.get('witness_id'))
    image_data = data.get('image')
    
    witness_text = ELEMENTS[element_id]['witnesses'][witness_id - 1]
    element_title = ELEMENTS[element_id]['title']
    
    filename = f"{session['username']}_{element_id}_{witness_id}_{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(STATIC_IMAGES_DIR, filename)
    
    if 'base64,' in image_data:
        image_data = image_data.split('base64,')[1]
    
    image_bytes = base64.b64decode(image_data)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    # محاولة رفع إلى Supabase إذا كان مهيأ
    image_url = None
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            image_url = upload_to_supabase(image_bytes, filename)
        except Exception as e:
            print(f"خطأ في رفع الصورة: {e}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO evidences (username, element_id, element_title, witness_id, witness_text, image_path, image_url, synced)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (session['username'], element_id, element_title, witness_id, witness_text, filepath, image_url, 1 if image_url else 0))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'image_path': filepath})

@app.route('/api/get-my-evidences', methods=['GET'])
def get_my_evidences():
    if 'username' not in session:
        return jsonify({'success': False, 'data': []})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences WHERE username=? ORDER BY created_at DESC''', (session['username'],))
    rows = c.fetchall()
    conn.close()
    
    data = [{'id': r[0], 'username': r[1], 'element_id': r[2], 'element_title': r[3],
             'witness_id': r[4], 'witness_text': r[5], 'image_path': r[6], 'created_at': r[8]} for r in rows]
    return jsonify({'success': True, 'data': data})

@app.route('/api/admin/all-evidences', methods=['GET'])
def admin_all_evidences():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM evidences ORDER BY created_at DESC''')
    rows = c.fetchall()
    conn.close()
    
    data = [{'id': r[0], 'username': r[1], 'element_id': r[2], 'element_title': r[3],
             'witness_id': r[4], 'witness_text': r[5], 'image_path': r[6], 'created_at': r[8]} for r in rows]
    return jsonify({'success': True, 'data': data})

@app.route('/api/sync-to-cloud', methods=['POST'])
def api_sync_to_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    result = sync_to_supabase()
    return jsonify(result)

@app.route('/api/sync-from-cloud', methods=['POST'])
def api_sync_from_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    result = sync_from_supabase()
    return jsonify(result)

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
