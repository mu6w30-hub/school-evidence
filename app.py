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
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-12345'
CORS(app)

# ============ إعدادات Supabase (اختيارية - تستخدم فقط عند المزامنة) ============
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

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

# ============ قاعدة بيانات محلية (SQLite) ============
def init_local_db():
    conn = sqlite3.connect('data/evidence.db')
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
    
    # إضافة مستخدمين (11 مستخدم: admin + 10 مراقبين)
    users = [
        ('admin', 'admin123', 'مدير النظام'),
        ('observer1', 'password123', 'المراقب الأول'),
        ('observer2', 'pass123', 'المراقب الثاني'),
        ('observer3', 'pass123', 'المراقب الثالث'),
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

# ============ دوال مساعدة للمزامنة مع Supabase ============
def sync_to_cloud(username=None):
    """مزامنة البيانات المحلية إلى السحابة"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {'success': False, 'error': 'Supabase غير مهيأ'}
    
    conn = sqlite3.connect('data/evidence.db')
    c = conn.cursor()
    
    if username:
        c.execute("SELECT * FROM evidences WHERE username=?", (username,))
    else:
        c.execute("SELECT * FROM evidences")
    
    rows = c.fetchall()
    conn.close()
    
    synced = 0
    for row in rows:
        try:
            # رفع الصورة إلى Supabase Storage
            if os.path.exists(row[6]):
                with open(row[6], 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                # هنا نرسل البيانات إلى Supabase API
                headers = {
                    'apikey': SUPABASE_KEY,
                    'Authorization': f'Bearer {SUPABASE_KEY}',
                    'Content-Type': 'application/json'
                }
                
                # حفظ في جدول evidences في Supabase
                data = {
                    'username': row[1],
                    'element_id': row[2],
                    'element_title': row[3],
                    'witness_id': row[4],
                    'witness_text': row[5],
                    'image_base64': image_data,
                    'created_at': row[7]
                }
                
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/evidences",
                    headers=headers,
                    json=data
                )
                
                if response.status_code in [200, 201]:
                    synced += 1
        except Exception as e:
            print(f"خطأ في المزامنة: {e}")
    
    return {'success': True, 'synced': synced}

def sync_from_cloud():
    """جلب البيانات من السحابة إلى المحلي"""
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
            conn = sqlite3.connect('data/evidence.db')
            c = conn.cursor()
            
            for item in data:
                # حفظ الصورة محلياً
                if 'image_base64' in item:
                    os.makedirs('static/images', exist_ok=True)
                    filename = f"cloud_{item['username']}_{item['element_id']}_{item['witness_id']}_{uuid.uuid4().hex}.jpg"
                    filepath = os.path.join('static/images', filename)
                    
                    image_bytes = base64.b64decode(item['image_base64'])
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    
                    # حفظ في قاعدة البيانات المحلية
                    c.execute('''INSERT OR REPLACE INTO evidences 
                                 (username, element_id, element_title, witness_id, witness_text, image_path, created_at)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (item['username'], item['element_id'], item['element_title'],
                               item['witness_id'], item['witness_text'], filepath, item['created_at']))
            
            conn.commit()
            conn.close()
            return {'success': True, 'synced': len(data)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    return {'success': False, 'synced': 0}

# ============ واجهات API ============
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
    
    conn = sqlite3.connect('data/evidence.db')
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
    
    os.makedirs('static/images', exist_ok=True)
    filename = f"{session['username']}_{element_id}_{witness_id}_{uuid.uuid4().hex}.jpg"
    filepath = os.path.join('static/images', filename)
    
    if 'base64,' in image_data:
        image_data = image_data.split('base64,')[1]
    
    image_bytes = base64.b64decode(image_data)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    conn = sqlite3.connect('data/evidence.db')
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
    
    conn = sqlite3.connect('data/evidence.db')
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
    
    conn = sqlite3.connect('data/evidence.db')
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
    
    result = sync_to_cloud()
    return jsonify(result)

@app.route('/api/sync-from-cloud', methods=['POST'])
def api_sync_from_cloud():
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح'})
    
    result = sync_from_cloud()
    return jsonify(result)

# ============ صفحات HTML مدمجة ============
LOGIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - نظام توثيق الشواهد</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb4d);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            box-shadow: 0 25px 45px rgba(0,0,0,0.2);
            padding: 40px;
            width: 90%;
            max-width: 400px;
            backdrop-filter: blur(10px);
        }
        h1 { text-align: center; color: #333; margin-bottom: 30px; font-size: 28px; }
        .logo { text-align: center; font-size: 64px; margin-bottom: 20px; }
        input {
            width: 100%;
            padding: 14px;
            margin: 10px 0;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: 0.3s;
        }
        input:focus { border-color: #667eea; outline: none; }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        .error { background: #fee; color: #c00; padding: 10px; border-radius: 8px; margin-top: 15px; text-align: center; display: none; }
        .info { text-align: center; margin-top: 25px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">📸</div>
        <h1>نظام توثيق الشواهد</h1>
        <form id="loginForm">
            <input type="text" id="username" placeholder="اسم المستخدم" required>
            <input type="password" id="password" placeholder="كلمة السر" required>
            <button type="submit">دخول</button>
        </form>
        <div class="error" id="errorMsg"></div>
        <div class="info">
            🔐 admin / admin123<br>
            🔐 observer1 / password123<br>
            🔐 observer2-10 / pass123
        </div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json();
            if (data.success) {
                if (data.is_admin) window.location.href = '/admin';
                else window.location.href = '/dashboard';
            } else {
                const errorDiv = document.getElementById('errorMsg');
                errorDiv.textContent = data.error || 'خطأ في تسجيل الدخول';
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التوثيق - نظام الشواهد</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f0f2f5;
        }
        /* الشريط الجانبي */
        .sidebar {
            position: fixed;
            right: 0;
            top: 0;
            width: 280px;
            height: 100%;
            background: linear-gradient(180deg, #1a2a6c 0%, #b21f1f 100%);
            color: white;
            padding: 20px;
            box-shadow: -2px 0 10px rgba(0,0,0,0.1);
            z-index: 100;
            overflow-y: auto;
        }
        .sidebar h3 {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(255,255,255,0.3);
        }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 12px;
            cursor: pointer;
            transition: 0.3s;
            background: rgba(255,255,255,0.1);
        }
        .nav-item:hover, .nav-item.active {
            background: rgba(255,255,255,0.25);
            transform: translateX(-5px);
        }
        .nav-icon { font-size: 24px; margin-left: 12px; }
        .nav-text { font-size: 14px; font-weight: 500; }
        .logout-btn {
            margin-top: 40px;
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 12px;
            border-radius: 10px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        }
        .logout-btn:hover { background: rgba(255,255,255,0.3); }
        /* المحتوى الرئيسي */
        .main-content {
            margin-right: 280px;
            padding: 20px;
            min-height: 100vh;
        }
        .header {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .elements-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .element-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: 0.3s;
        }
        .element-card:hover { transform: translateY(-5px); box-shadow: 0 5px 25px rgba(0,0,0,0.15); }
        .element-title {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            font-weight: bold;
            font-size: 16px;
        }
        .witnesses-list { padding: 15px; max-height: 400px; overflow-y: auto; }
        .witness-item {
            background: #f8f9fa;
            margin: 8px 0;
            padding: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .witness-text { flex: 1; font-size: 13px; margin-left: 10px; }
        .camera-icon {
            font-size: 24px;
            cursor: pointer;
            padding: 5px;
            border-radius: 50%;
            transition: 0.2s;
        }
        .camera-icon:hover { background: #e0e0e0; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
        }
        .modal-content {
            position: relative;
            width: 90%;
            max-width: 500px;
            margin: 50px auto;
            background: white;
            border-radius: 20px;
            padding: 20px;
        }
        video { width: 100%; border-radius: 15px; }
        .capture-btn {
            background: #28a745;
            color: white;
            padding: 12px;
            border: none;
            border-radius: 10px;
            margin-top: 15px;
            width: 100%;
            cursor: pointer;
        }
        .close-modal { background: #dc3545; margin-top: 10px; }
        @media (max-width: 768px) {
            .sidebar { width: 220px; }
            .main-content { margin-right: 220px; }
            .elements-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>📸 نظام التوثيق</h3>
        <div class="nav-item active" onclick="showSection('dashboard')">
            <span class="nav-icon">📋</span>
            <span class="nav-text">لوحة التوثيق</span>
        </div>
        <div class="nav-item" onclick="showSection('stats')">
            <span class="nav-icon">📊</span>
            <span class="nav-text">إحصائياتي</span>
        </div>
        <div class="nav-item" onclick="showSection('history')">
            <span class="nav-icon">🖼️</span>
            <span class="nav-text">توثيقاتي السابقة</span>
        </div>
        <button class="logout-btn" onclick="logout()">🚪 تسجيل خروج</button>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>مرحباً <span id="usernameDisplay">{{ username }}</span></h2>
            <div>📅 <span id="dateDisplay"></span></div>
        </div>

        <div id="dashboardSection">
            <div class="elements-grid" id="elementsGrid"></div>
        </div>

        <div id="statsSection" style="display:none;">
            <div style="background:white; border-radius:15px; padding:20px;">
                <h3>📊 إحصائيات التوثيقات</h3>
                <canvas id="statsChart" width="400" height="200"></canvas>
                <div id="statsNumbers" style="margin-top:20px;"></div>
            </div>
        </div>

        <div id="historySection" style="display:none;">
            <div style="background:white; border-radius:15px; padding:20px;">
                <h3>🖼️ توثيقاتي السابقة</h3>
                <div id="historyGrid" style="display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:15px; margin-top:20px;"></div>
            </div>
        </div>
    </div>

    <div id="cameraModal" class="modal">
        <div class="modal-content">
            <video id="video" autoplay playsinline></video>
            <button class="capture-btn" onclick="capturePhoto()">📷 التقاط صورة</button>
            <button class="capture-btn close-modal" onclick="closeCamera()">إلغاء</button>
        </div>
    </div>
    <canvas id="canvas" style="display:none"></canvas>

    <script>
        const elements = {{ elements | tojson }};
        let currentElementId = null, currentWitnessId = null, stream = null;
        
        function showSection(section) {
            document.getElementById('dashboardSection').style.display = section === 'dashboard' ? 'block' : 'none';
            document.getElementById('statsSection').style.display = section === 'stats' ? 'block' : 'none';
            document.getElementById('historySection').style.display = section === 'history' ? 'block' : 'none';
            if (section === 'stats') loadStats();
            if (section === 'history') loadHistory();
        }
        
        function displayElements() {
            const grid = document.getElementById('elementsGrid');
            grid.innerHTML = '';
            for (const [id, element] of Object.entries(elements)) {
                const card = document.createElement('div');
                card.className = 'element-card';
                card.innerHTML = `
                    <div class="element-title">📚 العنصر ${id}: ${element.title}</div>
                    <div class="witnesses-list" id="witnesses-${id}"></div>
                `;
                grid.appendChild(card);
                const witnessesList = document.getElementById(`witnesses-${id}`);
                element.witnesses.forEach((text, index) => {
                    const witnessDiv = document.createElement('div');
                    witnessDiv.className = 'witness-item';
                    witnessDiv.innerHTML = `
                        <span class="witness-text">${index + 1}. ${text}</span>
                        <span class="camera-icon" onclick="openCamera(${id}, ${index + 1})">📷</span>
                    `;
                    witnessesList.appendChild(witnessDiv);
                });
            }
        }
        
        async function openCamera(elementId, witnessId) {
            currentElementId = elementId;
            currentWitnessId = witnessId;
            document.getElementById('cameraModal').style.display = 'block';
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                document.getElementById('video').srcObject = stream;
            } catch(err) { alert('لا يمكن الوصول إلى الكاميرا'); }
        }
        
        async function capturePhoto() {
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const imageData = canvas.toDataURL('image/jpeg', 0.9);
            const response = await fetch('/api/save-evidence', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ element_id: currentElementId, witness_id: currentWitnessId, image: imageData })
            });
            const result = await response.json();
            if (result.success) { alert('✅ تم التوثيق بنجاح!'); closeCamera(); }
            else alert('❌ خطأ: ' + (result.error || 'فشل الحفظ'));
        }
        
        function closeCamera() {
            if (stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
            document.getElementById('cameraModal').style.display = 'none';
        }
        
        async function loadStats() {
            const response = await fetch('/api/get-my-evidences');
            const data = await response.json();
            if (data.success) {
                const stats = {};
                data.data.forEach(item => {
                    const el = `العنصر ${item.element_id}`;
                    stats[el] = (stats[el] || 0) + 1;
                });
                document.getElementById('statsNumbers').innerHTML = Object.entries(stats).map(([k,v]) => `<p><strong>${k}:</strong> ${v} توثيق</p>`).join('');
            }
        }
        
        async function loadHistory() {
            const response = await fetch('/api/get-my-evidences');
            const data = await response.json();
            const grid = document.getElementById('historyGrid');
            if (data.success && data.data.length > 0) {
                grid.innerHTML = data.data.map(item => `
                    <div style="background:#f8f9fa; border-radius:10px; padding:10px; text-align:center;">
                        <img src="/${item.image_path}" style="width:100%; height:150px; object-fit:cover; border-radius:8px;">
                        <p style="margin-top:8px; font-size:12px;">${item.element_title.substring(0,30)}</p>
                        <small>${new Date(item.created_at).toLocaleDateString('ar-SA')}</small>
                    </div>
                `).join('');
            } else { grid.innerHTML = '<p>لا توجد توثيقات سابقة</p>'; }
        }
        
        async function logout() { await fetch('/api/logout', { method: 'POST' }); window.location.href = '/'; }
        document.getElementById('dateDisplay').innerText = new Date().toLocaleDateString('ar-SA');
        displayElements();
    </script>
</body>
</html>
'''

ADMIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم المدير</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f0f2f5;
        }
        .sidebar {
            position: fixed;
            right: 0;
            top: 0;
            width: 280px;
            height: 100%;
            background: linear-gradient(180deg, #1a2a6c 0%, #b21f1f 100%);
            color: white;
            padding: 20px;
        }
        .sidebar h3 { text-align: center; margin-bottom: 30px; }
        .nav-item {
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 12px;
            cursor: pointer;
            background: rgba(255,255,255,0.1);
        }
        .nav-item:hover, .nav-item.active { background: rgba(255,255,255,0.25); }
        .main-content { margin-right: 280px; padding: 20px; }
        .header {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        .stat-number { font-size: 32px; font-weight: bold; color: #667eea; }
        .sync-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; }
        .btn-primary { background: #667eea; color: white; }
        .btn-success { background: #28a745; color: white; }
        .sync-status { background: #e9ecef; padding: 10px; border-radius: 8px; margin-bottom: 20px; display: none; }
        table { width: 100%; background: white; border-radius: 15px; overflow: hidden; }
        th, td { padding: 12px; text-align: right; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; }
        .evidence-img { width: 50px; height: 50px; object-fit: cover; border-radius: 8px; cursor: pointer; }
        .logout-btn { background: rgba(255,255,255,0.2); border: none; color: white; padding: 10px; border-radius: 8px; cursor: pointer; }
        @media (max-width: 768px) { .sidebar { width: 200px; } .main-content { margin-right: 200px; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>👑 لوحة المدير</h3>
        <div class="nav-item active" onclick="showSection('all')">📋 جميع التوثيقات</div>
        <div class="nav-item" onclick="showSection('sync')">🔄 المزامنة</div>
        <div class="nav-item" onclick="showSection('users')">👥 المستخدمين</div>
        <button class="logout-btn" style="margin-top:40px;" onclick="logout()">🚪 خروج</button>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>لوحة تحكم المدير</h2>
            <div id="dateDisplay"></div>
        </div>

        <div class="stats">
            <div class="stat-card"><div class="stat-number" id="totalCount">0</div><div>إجمالي التوثيقات</div></div>
            <div class="stat-card"><div class="stat-number" id="usersCount">0</div><div>عدد المراقبين</div></div>
            <div class="stat-card"><div class="stat-number" id="todayCount">0</div><div>توثيقات اليوم</div></div>
        </div>

        <div id="allSection">
            <div class="sync-buttons">
                <button class="btn btn-primary" onclick="exportCSV()">📥 تصدير CSV</button>
                <button class="btn btn-primary" onclick="refreshData()">🔄 تحديث</button>
            </div>
            <div style="overflow-x:auto;"><table id="dataTable"><thead><tr><th>#</th><th>المراقب</th><th>العنصر</th><th>الشاهد</th><th>الصورة</th><th>التاريخ</th></tr></thead><tbody id="tableBody"></tbody></table></div>
        </div>

        <div id="syncSection" style="display:none;">
            <div class="sync-status" id="syncStatus"></div>
            <div class="sync-buttons">
                <button class="btn btn-primary" onclick="syncToCloud()">☁️ مزامنة إلى السحابة</button>
                <button class="btn btn-success" onclick="syncFromCloud()">📥 جلب من السحابة</button>
            </div>
            <div style="background:white; border-radius:15px; padding:20px; margin-top:20px;">
                <h4>ℹ️ حول المزامنة</h4>
                <p>• عند الضغط على "مزامنة إلى السحابة": يتم رفع جميع التوثيقات المحلية إلى Supabase</p>
                <p>• عند الضغط على "جلب من السحابة": يتم تحميل التوثيقات من Supabase إلى الجهاز المحلي</p>
                <p>• ملاحظة: يجب إعداد متغيرات SUPABASE_URL و SUPABASE_KEY في ملف .env أولاً</p>
            </div>
        </div>

        <div id="usersSection" style="display:none;">
            <div style="background:white; border-radius:15px; padding:20px;">
                <h4>المستخدمين المسجلين</h4>
                <table><thead><tr><th>المستخدم</th><th>الاسم الكامل</th><th>النوع</th></tr></thead>
                <tbody id="usersTableBody"></tbody></table>
            </div>
        </div>
    </div>

    <script>
        let allData = [];
        async function refreshData() {
            const response = await fetch('/api/admin/all-evidences');
            const data = await response.json();
            if (data.success) {
                allData = data.data;
                document.getElementById('totalCount').innerText = allData.length;
                const users = [...new Set(allData.map(e => e.username))];
                document.getElementById('usersCount').innerText = users.length;
                const today = allData.filter(e => new Date(e.created_at).toDateString() === new Date().toDateString()).length;
                document.getElementById('todayCount').innerText = today;
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = allData.map((item, i) => `
                    <tr><td>${i+1}</td><td>${item.username}</td><td>العنصر ${item.element_id}</td><td>${item.witness_text.substring(0,30)}...</td>
                    <td><img src="/${item.image_path}" class="evidence-img" onclick="window.open('/${item.image_path}')"></td>
                    <td>${new Date(item.created_at).toLocaleDateString('ar-SA')}</td></tr>
                `).join('');
            }
        }
        async function syncToCloud() {
            const statusDiv = document.getElementById('syncStatus');
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '⏳ جاري المزامنة إلى السحابة...';
            const response = await fetch('/api/sync-to-cloud', { method: 'POST' });
            const result = await response.json();
            if (result.success) statusDiv.innerHTML = `✅ تم المزامنة بنجاح! ${result.synced} توثيق.`;
            else statusDiv.innerHTML = `❌ خطأ: ${result.error}`;
            setTimeout(() => { statusDiv.style.display = 'none'; }, 3000);
        }
        async function syncFromCloud() {
            const statusDiv = document.getElementById('syncStatus');
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '⏳ جاري الجلب من السحابة...';
            const response = await fetch('/api/sync-from-cloud', { method: 'POST' });
            const result = await response.json();
            if (result.success) statusDiv.innerHTML = `✅ تم الجلب بنجاح! ${result.synced} توثيق.`;
            else statusDiv.innerHTML = `❌ خطأ: ${result.error}`;
            setTimeout(() => { statusDiv.style.display = 'none'; }, 3000);
            refreshData();
        }
        function exportCSV() {
            let csv = "المراقب,رقم العنصر,رقم الشاهد,نص الشاهد,التاريخ\n";
            allData.forEach(e => { csv += `"${e.username}","${e.element_id}","${e.witness_id}","${e.witness_text}","${e.created_at}"\n`; });
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `evidences_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();
        }
        function showSection(section) {
            document.getElementById('allSection').style.display = section === 'all' ? 'block' : 'none';
            document.getElementById('syncSection').style.display = section === 'sync' ? 'block' : 'none';
            document.getElementById('usersSection').style.display = section === 'users' ? 'block' : 'none';
            if (section === 'users') loadUsers();
        }
        async function loadUsers() {
            // عرض المستخدمين (يمكن إضافتها من قاعدة البيانات)
            document.getElementById('usersTableBody').innerHTML = `
                <tr><td>admin</td><td>مدير النظام</td><td>مدير</td></tr>
                <tr><td>observer1</td><td>المراقب الأول</td><td>مراقب</td></tr>
                <tr><td>observer2-10</td><td>مراقبين</td><td>مراقب</td></tr>
            `;
        }
        async function logout() { await fetch('/api/logout', { method: 'POST' }); window.location.href = '/'; }
        document.getElementById('dateDisplay').innerText = new Date().toLocaleDateString('ar-SA');
        refreshData();
    </script>
</body>
</html>
'''

# ============ تشغيل التطبيق ============
if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    init_local_db()
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║     📸 نظام توثيق الشواهد المدرسية - الإصدار المتكامل               ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  رابط التطبيق: http://127.0.0.1:5000                                 ║
    ║                                                                      ║
    ║  بيانات الدخول:                                                      ║
    ║     المدير: admin / admin123                                         ║
    ║     المراقب 1: observer1 / password123                               ║
    ║     المراقب 2-10: observer2 / pass123 ... observer10 / pass123       ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ✨ المميزات:                                                        ║
    ║     • واجهة Windows 11 بشريط جانبي                                  ║
    ║     • توثيق بالكاميرا                                               ║
    ║     • إحصائيات وتاريخ التوثيقات                                     ║
    ║     • لوحة تحكم للمدير                                              ║
    ║     • مزامنة مع Supabase (عند التهيئة)                              ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=5000, debug=True)