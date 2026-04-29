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

# ============ بيانات العناصر ============
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
    ]
    
    for username, password, full_name in users:
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
                      (username, password, full_name))
    conn.commit()
    conn.close()

init_local_db()

# ============ صفحات HTML مدمجة ============
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
<div class="error" id="errorMsg"></div><div class="info">🔐 admin/admin123<br>🔐 observer1/password123</div></div>
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

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة التوثيق</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:#f0f2f5;padding:20px}
.header{background:white;border-radius:15px;padding:20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.elements-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px}
.element-card{background:white;border-radius:15px;overflow:hidden}
.element-title{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:15px}
.witness-item{background:#f8f9fa;margin:8px;padding:10px;border-radius:10px;display:flex;justify-content:space-between}
.camera-icon{font-size:24px;cursor:pointer}.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:1000}
.modal-content{width:90%;max-width:500px;margin:50px auto;background:white;border-radius:20px;padding:20px}
video{width:100%;border-radius:15px}.capture-btn{background:#28a745;color:white;padding:12px;border:none;border-radius:10px;margin-top:15px;width:100%;cursor:pointer}
.close-modal{background:#dc3545;margin-top:10px}.logout-btn{background:#dc3545;border:none;color:white;padding:8px 16px;border-radius:8px;cursor:pointer}
</style>
</head>
<body>
<div class="header"><h2>📸 لوحة التوثيق - مرحباً {{ username }}</h2><button class="logout-btn" onclick="logout()">🚪 خروج</button></div>
<div class="elements-grid" id="elementsGrid"></div>
<div id="cameraModal" class="modal"><div class="modal-content"><video id="video" autoplay playsinline></video><button class="capture-btn" onclick="capturePhoto()">📷 التقاط صورة</button><button class="capture-btn close-modal" onclick="closeCamera()">إلغاء</button></div></div>
<canvas id="canvas" style="display:none"></canvas>
<script>
const elements = {{ elements | tojson }};
let currentElementId=null,currentWitnessId=null,stream=null;
function displayElements(){
    const grid=document.getElementById('elementsGrid');grid.innerHTML='';
    for(const[id,element]of Object.entries(elements)){
        const card=document.createElement('div');card.className='element-card';
        card.innerHTML=`<div class="element-title">📚 العنصر ${id}: ${element.title}</div><div class="witnesses-list" id="witnesses-${id}"></div>`;
        grid.appendChild(card);
        const list=document.getElementById(`witnesses-${id}`);
        element.witnesses.forEach((text,idx)=>{
            const div=document.createElement('div');div.className='witness-item';
            div.innerHTML=`<span>${idx+1}. ${text}</span><span class="camera-icon" onclick="openCamera(${id},${idx+1})">📷</span>`;
            list.appendChild(div);
        });
    }
}
async function openCamera(elementId,witnessId){
    currentElementId=elementId;currentWitnessId=witnessId;
    document.getElementById('cameraModal').style.display='block';
    try{stream=await navigator.mediaDevices.getUserMedia({video:true});document.getElementById('video').srcObject=stream;}
    catch(err){alert('لا يمكن الوصول إلى الكاميرا');}
}
async function capturePhoto(){
    const video=document.getElementById('video');const canvas=document.getElementById('canvas');
    canvas.width=video.videoWidth;canvas.height=video.videoHeight;
    canvas.getContext('2d').drawImage(video,0,0);
    const imageData=canvas.toDataURL('image/jpeg',0.9);
    const response=await fetch('/api/save-evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({element_id:currentElementId,witness_id:currentWitnessId,image:imageData})});
    const result=await response.json();
    if(result.success){alert('✅ تم التوثيق بنجاح!');closeCamera();}
    else alert('❌ خطأ: '+result.error);
}
function closeCamera(){if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}document.getElementById('cameraModal').style.display='none';}
async function logout(){await fetch('/api/logout',{method:'POST'});window.location.href='/';}
displayElements();
</script>
</body>
</html>
'''

ADMIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة المدير</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:#f0f2f5;padding:20px}
.header{background:white;border-radius:15px;padding:20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:white;padding:20px;border-radius:15px;text-align:center}
.stat-number{font-size:32px;font-weight:bold;color:#667eea}
table{width:100%;background:white;border-radius:15px;overflow:hidden}
th,td{padding:12px;text-align:right;border-bottom:1px solid #eee}
th{background:#f8f9fa}
.evidence-img{width:50px;height:50px;object-fit:cover;border-radius:8px;cursor:pointer}
.logout-btn{background:#dc3545;border:none;color:white;padding:8px 16px;border-radius:8px;cursor:pointer}
.btn{background:#667eea;color:white;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;margin-left:10px}
</style>
</head>
<body>
<div class="header"><h2>👑 لوحة تحكم المدير</h2><button class="logout-btn" onclick="logout()">🚪 خروج</button></div>
<div class="stats"><div class="stat-card"><div class="stat-number" id="totalCount">0</div><div>إجمالي التوثيقات</div></div>
<div class="stat-card"><div class="stat-number" id="usersCount">0</div><div>عدد المراقبين</div></div></div>
<button class="btn" onclick="exportCSV()">📥 تصدير CSV</button><button class="btn" onclick="refreshData()">🔄 تحديث</button>
<div style="overflow-x:auto;margin-top:20px;"><table><thead><tr><th>#</th><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>الصورة</th><th>التاريخ</th></tr></thead><tbody id="tableBody"></tbody></table></div>
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
        const tbody=document.getElementById('tableBody');
        tbody.innerHTML=allData.map((item,i)=>`<tr><td>${i+1}</td><td>${item.username}</td><td>العنصر ${item.element_id}</td><td>${item.witness_text.substring(0,40)}...</td><td>${item.image_path?'✅':'❌'}</td><td>${new Date(item.created_at).toLocaleDateString('ar-SA')}</td></tr>`).join('');
    }
}
function exportCSV(){
    let csv="المراقب,رقم العنصر,رقم الشاهد,نص الشاهد,التاريخ\n";
    allData.forEach(e=>{csv+=`"${e.username}","${e.element_id}","${e.witness_id}","${e.witness_text}","${e.created_at}"\n`;});
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);
    link.download=`evidences_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
}
async function logout(){await fetch('/api/logout',{method:'POST'});window.location.href='/';}
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
        return jsonify({'success': True, 'user': username, 'is_admin': username == 'admin'})
    return jsonify({'success': False, 'error': 'بيانات غير صحيحة'})

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
    data = [{'id':r[0],'username':r[1],'element_id':r[2],'element_title':r[3],'witness_id':r[4],'witness_text':r[5],'image_path':r[6],'created_at':r[7]} for r in rows]
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
    data = [{'id':r[0],'username':r[1],'element_id':r[2],'element_title':r[3],'witness_id':r[4],'witness_text':r[5],'image_path':r[6],'created_at':r[7]} for r in rows]
    return jsonify({'success': True, 'data': data})

if __name__ == '__main__':
    init_local_db()
    print(f"✅ قاعدة البيانات في: {DB_PATH}")
    print(f"✅ الصور في: {STATIC_IMAGES_DIR}")
    print("✅ التطبيق يعمل على Render")
    app.run(host='0.0.0.0', port=10000, debug=False)
