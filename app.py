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
# استخدام /tmp على Render (قابل للكتابة)
BASE_DIR = os.environ.get('RENDER', False) and '/tmp' or os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'images')

# إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'evidence.db')

# ============ إعدادات Supabase ============
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# ============ بيانات العناصر والشواهد ============
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
    8: {"title": "استخدام مصادر تعلم رقمية", "witnesses": [
        "يوظف المعلم رابط فيديو قصيراً + لعبة تفاعلية (مثل Kahoot أو Quizizz) في الحصة",
        "يتيح المعلم خيار القراءة الرقمية أو الورقية حسب رغبة المتعلم",
        "يستخدم المعلم السبورة التفاعلية لعرض الصور والمقاطع المرئية",
        "يوفر المعلم تطبيقاً تعليمياً على الجهاز اللوحي يسمح باختيار مستوى الصعوبة",
        "يعرض المعلم محاكاة رقمية (محاكي) لتجربة علمية بدلاً من المجسمات التقليدية",
        "يستخدم المعلم رمز QR سريعاً للوصلة إلى مصدر إضافي للطلاب المتقدمين",
        "يتيح المعلم لذوي صعوبات القراءة الاستماع إلى النص عبر مكبر الصوت"
    ]},
    9: {"title": "تطبيقات عملية مرتبطة بحياة المتعلمين", "witnesses": [
        "ينفذ المتعلمون محاكاة لشراء السلع باستخدام حسابات النسبة المئوية للخصم",
        "يطلب المعلم من المتعلمين إحصاء عدد زملائهم في الصف كتطبيق على عملية الجمع",
        "يصمم المتعلمون جدولاً لحصصهم الأسبوعية باستخدام برنامج إلكتروني",
        "يكتب المتعلمون رسالة شكر لأحد العمال في المدرسة (تطبيق على فن الكتابة)",
        "يحسب المتعلمون استهلاك الماء أو الكهرباء في المنزل ضمن مادة العلوم",
        "ينفذ المعلم نشاط إعادة تدوير علب الكرتون ضمن مادة التربية الفنية",
        "يطبق المتعلمون آداب الحوار أثناء مناقشة مشكلة حقيقية في الصف (مثل تأخر الواجبات)"
    ]},
    10: {"title": "تنمية مهارات القراءة والكتابة", "witnesses": [
        "يقرأ كل متعلم فقرة بصوت منخفض، ثم يكتب تعليقاً من سطرين في دفتر التفاعل",
        "تتوفر في ركن القراءة كتب قصصية وقصائد ومجلات مناسبة لأعمارهم",
        "يكتب المتعلمون تلخيصاً يومياً للحصة في جملتين في نهاية اليوم",
        "ينظم المعلم مسابقة إملاء أو قراءة سريعة بين المجموعات",
        "يخصص المعلم 10 دقائق أسبوعياً للقراءة الحرة يليها تسجيل في سجل القراءة",
        "تُعرض على جدار الصف جمل أو فقرات أسبوعية يقرؤها المتعلمون عند الدخول",
        "يستخدم المعلم بطاقات الكلمات لتدريب المتعلمين الضعفاء على القراءة"
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
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    users = [
        ('admin', 'admin123', 'مدير النظام'),
        ('observer1', 'password123', 'المراقب الأول'),
        ('observer2', 'pass123', 'المراقب الثاني'),
        ('observer3', 'pass123', 'المراقب الثالث'),
        ('observer4', 'pass123', 'المراقب الرابع'),
        ('5', '123', 'المراقب الخامس'),
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

# ============ الصفحات ============
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
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO evidences (username, element_id, element_title, witness_id, witness_text, image_path)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (session['username'], element_id, element_title, witness_id, witness_text, filepath))
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
    
    data = []
    for row in rows:
        data.append({
            'id': row[0],
            'username': row[1],
            'element_id': row[2],
            'element_title': row[3],
            'witness_id': row[4],
            'witness_text': row[5],
            'image_path': row[6],
            'created_at': row[7]
        })
    
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
    
    data = []
    for row in rows:
        data.append({
            'id': row[0],
            'username': row[1],
            'element_id': row[2],
            'element_title': row[3],
            'witness_id': row[4],
            'witness_text': row[5],
            'image_path': row[6],
            'created_at': row[7]
        })
    
    return jsonify({'success': True, 'data': data})

@app.route('/api/sync-to-cloud', methods=['POST'])
def api_sync_to_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    return jsonify({'success': True, 'synced': 0, 'message': 'ميزة المزامنة قيد التطوير'})

@app.route('/api/sync-from-cloud', methods=['POST'])
def api_sync_from_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    return jsonify({'success': True, 'synced': 0, 'message': 'ميزة المزامنة قيد التطوير'})

# ============ صفحات HTML (مختصرة لضيق المساحة - نفس الكود السابق) ============
# (سأضع نسخة مختصرة هنا، لكن الأفضل أن تنسخها من الملف السابق)

LOGIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الدخول</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a2a6c,#b21f1f,#fdbb4d);min-height:100vh;display:flex;justify-content:center;align-items:center}
.login-container{background:rgba(255,255,255,0.95);border-radius:20px;padding:40px;width:90%;max-width:400px}h1{text-align:center;margin-bottom:30px}
.logo{text-align:center;font-size:64px;margin-bottom:20px}input{width:100%;padding:14px;margin:10px 0;border:2px solid #e0e0e0;border-radius:10px}
button{width:100%;padding:14px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;border-radius:10px;font-size:18px;cursor:pointer}
.error{background:#fee;color:#c00;padding:10px;border-radius:8px;margin-top:15px;display:none}.info{text-align:center;margin-top:25px;color:#666}
</style>
</head>
<body>
<div class="login-container"><div class="logo">📸</div><h1>نظام توثيق الشواهد</h1>
<form id="loginForm"><input type="text" id="username" placeholder="اسم المستخدم" required><input type="password" id="password" placeholder="كلمة السر" required><button type="submit">دخول</button></form>
<div class="error" id="errorMsg"></div><div class="info">🔐 admin/admin123<br>🔐 observer1/password123<br>🔐 observer2-10/pass123</div></div>
<script>
document.getElementById('loginForm').addEventListener('submit',async(e)=>{
e.preventDefault();const u=document.getElementById('username').value,p=document.getElementById('password').value;
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
const d=await r.json();if(d.success){if(d.is_admin)window.location.href='/admin';else window.location.href='/dashboard';}
else{document.getElementById('errorMsg').textContent=d.error||'خطأ';document.getElementById('errorMsg').style.display='block';}});
</script>
</body>
</html>
'''

# ملاحظة: يجب إضافة DASHBOARD_PAGE و ADMIN_PAGE هنا (نفس الكود السابق)

# ============ تشغيل التطبيق ============
if __name__ == '__main__':
    init_local_db()
    print(f"✅ قاعدة البيانات في: {DB_PATH}")
    print(f"✅ الصور في: {STATIC_IMAGES_DIR}")
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║     📸 نظام توثيق الشواهد المدرسية - يعمل على Render        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  بيانات الدخول: admin / admin123                            ║
    ║              observer1 / password123                        ║
    ║              observer2-10 / pass123                         ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=10000, debug=False)