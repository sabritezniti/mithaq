import streamlit as st
import sqlite3
import hashlib
import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="MyIndustryAI — منصة الاستشارات",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
DB_PATH   = "platform.db"
BASE_KEY  = 22459129071981

def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    con = _conn(); cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            access_key  TEXT    UNIQUE NOT NULL,
            is_paid     INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS services (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            service_type TEXT    NOT NULL,
            details      TEXT,
            address      TEXT,
            phone        TEXT,
            created_at   TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            project_name      TEXT,
            market_study      REAL DEFAULT 0,
            team_experience   REAL DEFAULT 0,
            capital_stability REAL DEFAULT 0,
            innovation_score  REAL DEFAULT 0,
            legal_compliance  REAL DEFAULT 0,
            final_score       REAL DEFAULT 0,
            advice            TEXT,
            created_at        TEXT DEFAULT (datetime('now'))
        );
    """)
    con.commit(); con.close()

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _gen_key():
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]; con.close()
    return str(BASE_KEY + n)

def db_register(email, password):
    con = _conn(); cur = con.cursor()
    try:
        key = _gen_key()
        cur.execute("INSERT INTO users (email,password,access_key) VALUES (?,?,?)",
                    (email, _hash(password), key))
        con.commit()
        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        user = dict(cur.fetchone())
        return {"ok": True, "user": user, "key": key}
    except sqlite3.IntegrityError:
        return {"ok": False, "err": "البريد الإلكتروني مسجل مسبقاً"}
    finally:
        con.close()

def db_login(email, password):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, _hash(password)))
    row = cur.fetchone(); con.close()
    if row:
        return {"ok": True, "user": dict(row)}
    return {"ok": False, "err": "البريد أو كلمة المرور غير صحيحة"}

def db_get_user(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    row = cur.fetchone(); con.close()
    return dict(row) if row else None

def db_activate(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("UPDATE users SET is_paid=1 WHERE id=?", (uid,))
    con.commit(); con.close()

def db_save_service(uid, stype, details="", address="", phone=""):
    con = _conn(); cur = con.cursor()
    cur.execute("INSERT INTO services (user_id,service_type,details,address,phone) VALUES (?,?,?,?,?)",
                (uid, stype, details, address, phone))
    con.commit(); con.close()

def db_save_project(uid, name, scores, final, advice):
    con = _conn(); cur = con.cursor()
    cur.execute("""INSERT INTO projects
        (user_id,project_name,market_study,team_experience,capital_stability,
         innovation_score,legal_compliance,final_score,advice)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (uid, name,
         scores.get("market_study",0), scores.get("team_experience",0),
         scores.get("capital_stability",0), scores.get("innovation_score",0),
         scores.get("legal_compliance",0), final, advice))
    con.commit(); con.close()

def db_get_projects(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (uid,))
    rows = [dict(r) for r in cur.fetchall()]; con.close()
    return rows

# ═══════════════════════════════════════════════════════════════════════════════
#  EMAIL
# ═══════════════════════════════════════════════════════════════════════════════
RECIPIENT  = "postmaster@myindustryai.tn"
SMTP_HOST  = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")

def _html_email(title, rows):
    trs = "".join(
        f"<tr><td style='padding:8px 12px;font-weight:600;color:#555;border-bottom:1px solid #eee'>{k}</td>"
        f"<td style='padding:8px 12px;color:#222;border-bottom:1px solid #eee'>{v}</td></tr>"
        for k,v in rows)
    return f"""<html><body style='font-family:Arial,sans-serif;background:#f4f6f9'>
    <div style='max-width:580px;margin:30px auto;background:#fff;border-radius:10px;
                box-shadow:0 2px 12px rgba(0,0,0,.1);overflow:hidden'>
      <div style='background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px 28px'>
        <h1 style='margin:0;color:#d4a843;font-size:20px'>MyIndustryAI</h1>
        <p style='margin:4px 0 0;color:#94a3b8;font-size:12px'>منصة الاستشارات البارامترية</p>
      </div>
      <div style='padding:24px 28px'>
        <h2 style='color:#1a1a2e;font-size:16px'>{title}</h2>
        <table style='width:100%;border-collapse:collapse'>{trs}</table>
        <p style='margin-top:16px;font-size:11px;color:#aaa'>{datetime.now().strftime('%Y-%m-%d %H:%M')} — إشعار تلقائي</p>
      </div>
    </div></body></html>"""

def _send_email(subject, html):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL-DEV] {subject}")   # dev mode — no crash
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"MyIndustryAI <{SMTP_USER}>"
        msg["To"]      = RECIPIENT
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.ehlo(); s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, RECIPIENT, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL-ERR] {e}")
        return False

def email_new_user(email, key, uid):
    return _send_email(
        f"[MyIndustryAI] تسجيل جديد – {email}",
        _html_email("🆕 تسجيل مستخدم جديد",
            [("المعرّف", uid), ("البريد", email),
             ("مفتاح الوصول", f"<code>{key}</code>"), ("حالة الدفع","غير مفعّل")]))

def email_expert(user_email, address, phone, details):
    return _send_email(
        "[MyIndustryAI] طلب خبير معاينة",
        _html_email("🔧 طلب خبير معاينة",
            [("المستخدم", user_email), ("العنوان", address),
             ("الهاتف", phone), ("التفاصيل", details)]))

def email_payment(user_email, key, amount="N/A"):
    return _send_email(
        f"[MyIndustryAI] دفع ناجح – {user_email}",
        _html_email("💳 إتمام دفع بنجاح",
            [("المستخدم", user_email), ("مفتاح الوصول", f"<code>{key}</code>"),
             ("المبلغ", amount), ("الحالة","<span style='color:green'>مفعّل ✓</span>")]))

# ═══════════════════════════════════════════════════════════════════════════════
#  SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
WEIGHTS = {
    "market_study":      0.25,
    "team_experience":   0.25,
    "capital_stability": 0.25,
    "innovation_score":  0.15,
    "legal_compliance":  0.10,
}
LABELS = {
    "market_study":      "دراسة السوق",
    "team_experience":   "خبرة الفريق",
    "capital_stability": "استقرار رأس المال",
    "innovation_score":  "مستوى الابتكار",
    "legal_compliance":  "الامتثال القانوني",
}

@dataclass
class ScoreResult:
    raw: dict
    weighted: dict
    final: float
    grade: str
    color: str
    summary: str
    advice: list
    risks: list

def _grade(s):
    if s >= 8.5: return "ممتاز",        "#22c55e"
    if s >= 7.0: return "جيد جداً",     "#84cc16"
    if s >= 5.5: return "جيد",          "#f59e0b"
    if s >= 4.0: return "مقبول",        "#f97316"
    return            "ضعيف",           "#ef4444"

def score_project(scores):
    w   = {k: scores[k] * WEIGHTS[k] for k in WEIGHTS}
    fin = round(sum(w.values()), 2)
    grade, color = _grade(fin)
    advice, risks = [], []

    tips = [
        ("market_study",      7, 4,
         "✅ دراسة السوق قوية — ادعم هذا بتحليل تنافسي دوري.",
         "⚠️ دراسة السوق متوسطة — أجرِ مقابلات مع عملاء مستهدفين.",
         "🚨 دراسة السوق ضعيفة جداً — الاستثمار دون بيانات مجازفة عالية."),
        ("team_experience",   7, 4,
         "✅ فريق ذو خبرة — تأكد من تكامل المهارات.",
         "⚠️ خبرة متوسطة — استقطب مستشاراً أو شريكاً تقنياً.",
         "🚨 خبرة منخفضة — من أكبر أسباب فشل الشركات الناشئة."),
        ("capital_stability", 7, 4,
         "✅ رأس المال مستقر — خطط لتدفق نقدي للـ 18 شهراً القادمة.",
         "⚠️ رأس المال متوسط — استكشف خيارات تمويل إضافية مبكراً.",
         "🚨 رأس المال غير كافٍ — خطر توقف مالي خلال 6 أشهر."),
        ("innovation_score",  7, 4,
         "✅ ابتكار مرتفع — سجّل براءة اختراع إن أمكن.",
         "⚠️ ابتكار متوسط — حدد عرضاً فريداً للقيمة (USP).",
         "⚠️ منتجك يشبه المنافسين — ركّز على تمييز واضح."),
        ("legal_compliance",  7, 4,
         "✅ امتثال قانوني ممتاز — تابع التشريعات الجديدة.",
         "⚠️ وضع قانوني متوسط — استشر محامياً متخصصاً.",
         "🚨 مخاطر قانونية — تسوية الوضع القانوني أولوية."),
    ]
    for key, hi, mid, a_hi, a_mid, risk in tips:
        v = scores[key]
        if v >= hi:   advice.append(a_hi)
        elif v >= mid: advice.append(a_mid)
        else:          risks.append(risk)

    if fin >= 7:
        summary = f"مشروعك يمتلك أساساً جيداً ({fin}/10). مع التحسينات الموصى بها، فرص النجاح مرتفعة."
    elif fin >= 4:
        summary = f"مشروعك في المنطقة المتوسطة ({fin}/10). يحتاج تعزيز النقاط الضعيفة قبل الإطلاق."
    else:
        summary = f"النتيجة ({fin}/10) تشير إلى مخاطر عالية. راجع المشروع جذرياً قبل الاستثمار."

    return ScoreResult(raw=scores, weighted=w, final=fin,
                       grade=grade, color=color,
                       summary=summary, advice=advice, risks=risks)

# ═══════════════════════════════════════════════════════════════════════════════
#  GLOBAL CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');
html,body,[class*="css"]{font-family:'Cairo',sans-serif;direction:rtl}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f172a,#1e293b);border-left:3px solid #d4a843}
section[data-testid="stSidebar"] *{color:#e2e8f0!important}
.card{background:#fff;border-radius:14px;padding:22px 26px;
      box-shadow:0 4px 20px rgba(0,0,0,.07);margin-bottom:18px;border-right:4px solid #d4a843}
.warn{background:linear-gradient(135deg,#7f1d1d,#991b1b);color:#fef2f2;
      padding:14px 22px;border-radius:10px;font-size:16px;font-weight:700;
      text-align:center;margin-bottom:22px;border:2px solid #ef4444}
.stButton>button{background:linear-gradient(135deg,#d4a843,#b8922e);
  color:#1a1a2e;font-weight:700;border:none;border-radius:8px;
  padding:10px 22px;font-size:15px;font-family:'Cairo',sans-serif;transition:all .2s}
.stButton>button:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(212,168,67,.4)}
#MainMenu,footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
init_db()
for k, v in {"user": None, "page": "home", "proj": {}}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── helpers ───────────────────────────────────────────────────────────────────
def logged_in():
    return st.session_state.user is not None

def me():
    return st.session_state.user

def refresh_me():
    if logged_in():
        u = db_get_user(me()["id"])
        if u: st.session_state.user = u

def go(page):
    st.session_state.page = page
    st.rerun()

def require_login():
    if not logged_in():
        st.warning("⚠️ يجب تسجيل الدخول أولاً.")
        st.stop()

def require_paid():
    require_login(); refresh_me()
    if not me().get("is_paid"):
        st.error("🔒 هذه الخدمة للمشتركين فقط. أتمّ عملية الدفع لتفعيل حسابك.")
        if st.button("💳 الذهاب إلى الاشتراك"):
            go("payment")
        st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:16px 0 20px'>
      <div style='font-size:34px'>🏭</div>
      <h2 style='color:#d4a843;margin:6px 0 2px;font-size:18px'>MyIndustryAI</h2>
      <p style='color:#64748b;font-size:11px;margin:0'>منصة الاستشارات البارامترية</p>
    </div>""", unsafe_allow_html=True)

    if logged_in():
        u = me()
        badge = "✅ مشترك" if u.get("is_paid") else "⏳ غير مشترك"
        st.markdown(f"""
        <div style='background:#1e3a5f;padding:10px 14px;border-radius:10px;margin-bottom:16px'>
          <p style='margin:0;font-size:12px;color:#94a3b8'>مرحباً،</p>
          <p style='margin:2px 0;font-weight:700;font-size:13px'>{u['email']}</p>
          <p style='margin:0;font-size:11px;color:#d4a843'>{badge}</p>
        </div>""", unsafe_allow_html=True)

    nav = [
        ("🏠 الرئيسية",          "home"),
        ("📊 تقييم المشروع",      "scoring"),
        ("📄 تحليل العقود",       "contracts"),
        ("👷 طلب خبير",           "expert"),
        ("💳 الاشتراك",           "payment"),
        ("📁 سجل مشاريعي",        "history"),
    ]
    if not logged_in():
        nav = [("🔐 تسجيل الدخول","login"),("📝 إنشاء حساب","register")] + nav

    for label, pid in nav:
        if st.button(label, key=f"n_{pid}", use_container_width=True):
            go(pid)

    if logged_in():
        st.markdown("---")
        if st.button("🚪 خروج", use_container_width=True):
            st.session_state.user = None
            go("home")

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════════════════════════════════════════
pg = st.session_state.page

# ── HOME ──────────────────────────────────────────────────────────────────────
if pg == "home":
    st.markdown('<div class="warn">⚠️ &nbsp; نصيحة: لا تشترك قبل أن يكون لديك مشروع حقيقي &nbsp; ⚠️</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0f172a,#1e293b);padding:22px 28px;
                border-radius:14px;margin-bottom:24px'>
      <h1 style='color:#d4a843;margin:0;font-size:24px'>🏭 MyIndustryAI</h1>
      <p style='color:#94a3b8;margin:4px 0 0;font-size:13px'>منصة الاستشارات البارامترية للمشاريع الصناعية</p>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc in zip(
        [c1,c2,c3],
        ["📊","📄","👷"],
        ["محرك التقييم","تحليل العقود","خبير معاينة"],
        ["قيّم مشروعك برياضيات دقيقة على 5 محاور واحصل على توصيات فورية.",
         "تحليل قانوني أولي لعقودك التجارية. للمشتركين.",
         "خبير ميداني يزور موقعك ويقدم تقريراً تفصيلياً. للمشتركين."]):
        with col:
            st.markdown(f"""
            <div class="card" style='text-align:center'>
              <div style='font-size:30px'>{icon}</div>
              <h4 style='color:#d4a843;margin:8px 0 6px'>{title}</h4>
              <p style='font-size:13px;color:#64748b;margin:0'>{desc}</p>
            </div>""", unsafe_allow_html=True)

    if not logged_in():
        st.markdown("---")
        ca, cb = st.columns(2)
        with ca:
            if st.button("📝 إنشاء حساب", use_container_width=True): go("register")
        with cb:
            if st.button("🔐 تسجيل الدخول", use_container_width=True): go("login")

# ── REGISTER ──────────────────────────────────────────────────────────────────
elif pg == "register":
    st.markdown("## 📝 إنشاء حساب جديد")
    st.markdown('<div class="warn">⚠️ &nbsp; نصيحة: لا تشترك قبل أن يكون لديك مشروع حقيقي &nbsp; ⚠️</div>',
                unsafe_allow_html=True)
    with st.form("reg"):
        email   = st.text_input("📧 البريد الإلكتروني")
        pw      = st.text_input("🔒 كلمة المرور",         type="password")
        pw2     = st.text_input("🔒 تأكيد كلمة المرور",   type="password")
        sub     = st.form_submit_button("إنشاء الحساب ←", use_container_width=True)
    if sub:
        if not email or not pw:
            st.error("يرجى تعبئة جميع الحقول.")
        elif pw != pw2:
            st.error("كلمتا المرور غير متطابقتان.")
        elif len(pw) < 6:
            st.error("كلمة المرور 6 أحرف على الأقل.")
        else:
            with st.spinner("جارٍ إنشاء الحساب..."):
                r = db_register(email, pw)
            if r["ok"]:
                st.success(f"✅ تم إنشاء الحساب! مفتاح وصولك: **{r['key']}**")
                email_new_user(email, r["key"], r["user"]["id"])
                time.sleep(1)
                st.session_state.user = r["user"]
                go("home")
            else:
                st.error(r["err"])

# ── LOGIN ─────────────────────────────────────────────────────────────────────
elif pg == "login":
    st.markdown("## 🔐 تسجيل الدخول")
    with st.form("lgn"):
        email = st.text_input("📧 البريد الإلكتروني")
        pw    = st.text_input("🔒 كلمة المرور", type="password")
        sub   = st.form_submit_button("دخول ←", use_container_width=True)
    if sub:
        r = db_login(email, pw)
        if r["ok"]:
            st.session_state.user = r["user"]
            st.success("✅ تم تسجيل الدخول!")
            time.sleep(0.7); go("home")
        else:
            st.error(r["err"])
    st.markdown("---")
    if st.button("إنشاء حساب جديد"): go("register")

# ── SCORING ───────────────────────────────────────────────────────────────────
elif pg == "scoring":
    require_login()
    st.markdown("## 📊 محرك تقييم المشروع")
    st.markdown("""
    <div class="card">
      <p style='margin:0;font-size:12px;color:#64748b'>المعادلة</p>
      <p style='margin:4px 0 0;font-weight:700;color:#1e293b;font-size:14px'>
        النتيجة = (دراسة السوق×0.25) + (خبرة الفريق×0.25) +
        (رأس المال×0.25) + (الابتكار×0.15) + (الامتثال×0.10)
      </p>
    </div>""", unsafe_allow_html=True)

    with st.form("sc"):
        name = st.text_input("🏷️ اسم المشروع",
                             value=st.session_state.proj.get("name",""))
        st.markdown("### أدخل القيم من 0 إلى 10")
        c1, c2 = st.columns(2)
        sliders = {}
        for i,(k,lbl) in enumerate(LABELS.items()):
            col = c1 if i%2==0 else c2
            with col:
                sliders[k] = st.slider(
                    f"{lbl}  ({int(WEIGHTS[k]*100)}%)",
                    0.0, 10.0,
                    float(st.session_state.proj.get(k, 5.0)),
                    0.5, key=f"s_{k}")
        sub = st.form_submit_button("🔍 احسب التقييم", use_container_width=True)

    if sub:
        if not name:
            st.error("يرجى إدخال اسم المشروع.")
        else:
            res = score_project(sliders)
            st.session_state.proj = {"name": name, **sliders}
            db_save_project(me()["id"], name, sliders, res.final,
                            "\n".join(res.advice + res.risks))
            st.markdown("---")
            st.markdown("## 🎯 نتائج التقييم")
            cs, cg = st.columns([1,2])
            with cs:
                st.markdown(f"""
                <div style='text-align:center'>
                  <div style='font-size:56px;font-weight:900;color:{res.color};
                       background:{res.color}18;border:3px solid {res.color};
                       border-radius:14px;padding:10px 28px;display:inline-block'>
                    {res.final}
                  </div>
                  <p style='color:{res.color};font-weight:700;font-size:17px;margin-top:8px'>
                    {res.grade}
                  </p>
                </div>""", unsafe_allow_html=True)
            with cg:
                st.markdown(f'<div class="card"><p>{res.summary}</p></div>',
                            unsafe_allow_html=True)

            st.markdown("### التفصيل")
            bcols = st.columns(len(WEIGHTS))
            for col,(k,lbl) in zip(bcols, LABELS.items()):
                with col:
                    st.metric(lbl, f"{sliders[k]}/10",
                              f"+{res.weighted[k]:.2f}")
                    st.progress(sliders[k]/10)

            ca, cr = st.columns(2)
            with ca:
                if res.advice:
                    st.markdown("### 💡 توصيات")
                    for t in res.advice: st.markdown(f"- {t}")
            with cr:
                if res.risks:
                    st.markdown("### ⚠️ مخاطر")
                    for r in res.risks: st.markdown(f"- {r}")
            st.success("✅ تم حفظ التقييم في سجل مشاريعك.")

# ── CONTRACTS ─────────────────────────────────────────────────────────────────
elif pg == "contracts":
    require_paid()
    st.markdown("## 📄 تحليل العقود")
    st.markdown('<div class="card"><h4 style="color:#d4a843;margin-top:0">🔒 خدمة للمشتركين</h4>'
                '<p>أرسل عقدك للتحليل القانوني والتقني. تقرير مفصّل خلال 48 ساعة.</p></div>',
                unsafe_allow_html=True)
    with st.form("ct"):
        ctype   = st.selectbox("نوع العقد",
                    ["عقد توريد","عقد مقاولة","عقد شراكة","عقد إيجار صناعي","عقد خدمات","أخرى"])
        details = st.text_area("📋 تفاصيل العقد أو النص الجوهري", height=180)
        concerns= st.text_area("❓ نقاط القلق", height=100)
        sub     = st.form_submit_button("📤 إرسال للتحليل", use_container_width=True)
    if sub:
        if not details:
            st.error("يرجى إدخال تفاصيل العقد.")
        else:
            db_save_service(me()["id"], "contract",
                            f"نوع:{ctype}\nتفاصيل:{details}\nقلق:{concerns}")
            st.success("✅ تم استلام طلبك. سيتواصل معك الفريق خلال 48 ساعة.")

# ── EXPERT ────────────────────────────────────────────────────────────────────
elif pg == "expert":
    require_paid()
    st.markdown("## 👷 طلب خبير معاينة ميدانية")
    st.markdown('<div class="card"><h4 style="color:#d4a843;margin-top:0">خبراء معتمدون</h4>'
                '<p>سيتوجه الخبير لموقعك خلال 3-5 أيام عمل بتقرير فني شامل.</p></div>',
                unsafe_allow_html=True)
    with st.form("ex"):
        c1,c2 = st.columns(2)
        with c1: address = st.text_input("📍 عنوان الموقع الصناعي")
        with c2: phone   = st.text_input("📞 رقم الهاتف")
        etype   = st.selectbox("نوع الخبرة",
                    ["هندسة ميكانيكية","هندسة كهربائية","هندسة صناعية",
                     "سلامة وصحة مهنية","مراقبة الجودة","أخرى"])
        details = st.text_area("📝 وصف ما تحتاجه", height=130)
        date    = st.date_input("📅 التاريخ المفضل")
        sub     = st.form_submit_button("📤 إرسال طلب الخبير", use_container_width=True)
    if sub:
        if not address or not phone:
            st.error("يرجى إدخال العنوان والهاتف.")
        else:
            full = f"نوع:{etype}\nتفاصيل:{details}\nتاريخ:{date}"
            db_save_service(me()["id"], "expert", full, address, phone)
            email_expert(me()["email"], address, phone, full)
            st.success("✅ تم إرسال طلبك! سيتواصل معك الخبير قريباً.")
            st.balloons()

# ── PAYMENT ───────────────────────────────────────────────────────────────────
elif pg == "payment":
    require_login(); refresh_me(); u = me()
    st.markdown("## 💳 الاشتراك والدفع")

    if u.get("is_paid"):
        st.success("✅ حسابك مفعّل — تمتع بجميع الخدمات.")
        st.markdown('<div class="card"><h4 style="color:#22c55e">عضويتك نشطة ✓</h4>'
                    '<p>لديك وصول كامل إلى: تحليل العقود، طلب الخبراء، وجميع الخدمات.</p></div>',
                    unsafe_allow_html=True)
    else:
        c1,c2,c3 = st.columns(3)
        plans = [
            ("🥉 أساسي",  "99 دينار",  ["تقييم المشروع","تقرير PDF","دعم بريد"],      False),
            ("🥇 مهني",  "249 دينار", ["كل الأساسي","تحليل عقد","خبير/شهر","أولوية"],True),
            ("🏆 مؤسسات","599 دينار", ["كل المهني","عقود غير محدودة","خبراء∞"],      False),
        ]
        for col,(name,price,feats,hot) in zip([c1,c2,c3],plans):
            bdr = "#d4a843" if hot else "#e2e8f0"
            bg  = "#fffbeb" if hot else "#fff"
            fi  = "".join(f"<li>✓ {f}</li>" for f in feats)
            with col:
                st.markdown(f"""
                <div style='border:2px solid {bdr};background:{bg};border-radius:14px;
                     padding:20px;text-align:center;min-height:260px'>
                  <h3 style='color:#1e293b;margin:0 0 6px'>{name}</h3>
                  <div style='font-size:28px;font-weight:900;color:#d4a843'>{price}</div>
                  <div style='font-size:11px;color:#64748b;margin-bottom:14px'>/شهري</div>
                  <ul style='text-align:right;font-size:12px;color:#475569;padding-right:14px'>
                    {fi}
                  </ul>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### طريقة الدفع")
        t1, t2 = st.tabs(["💵 دفع محلي", "💳 Stripe"])

        with t1:
            st.info("حوّل المبلغ عبر d17 أو بنكياً ثم أدخل رقم المرجع.")
            with st.form("pay_local"):
                ref    = st.text_input("🧾 رقم مرجع الدفع")
                amount = st.selectbox("المبلغ", ["99 دينار","249 دينار","599 دينار"])
                sub    = st.form_submit_button("✅ تأكيد الدفع", use_container_width=True)
            if sub:
                if not ref:
                    st.error("يرجى إدخال رقم المرجع.")
                else:
                    db_activate(u["id"]); refresh_me()
                    email_payment(u["email"], u["access_key"], amount)
                    st.success("🎉 تم التفعيل! يمكنك الآن الوصول لجميع الخدمات.")
                    st.balloons(); time.sleep(1); st.rerun()

        with t2:
            st.markdown('<div class="card"><h4 style="color:#d4a843;margin-top:0">⚡ Stripe</h4>'
                        '<p>بعد الدفع يُعاد توجيهك وتُفعَّل عضويتك فوراً عبر webhook.</p></div>',
                        unsafe_allow_html=True)
            sk = st.text_input("🔑 Stripe Publishable Key", type="password")
            if st.button("🔗 انتقل للدفع", use_container_width=True):
                if not sk:
                    st.warning("أدخل مفتاح Stripe أولاً.")
                else:
                    st.info("في الإنتاج: سيتم توجيهك لـ Stripe Checkout.")
            with st.expander("🧪 تفعيل تجريبي — للتطوير فقط"):
                if st.button("تفعيل تجريبي"):
                    db_activate(u["id"]); refresh_me()
                    email_payment(u["email"], u["access_key"], "TEST")
                    st.success("تم!"); time.sleep(1); st.rerun()

# ── HISTORY ───────────────────────────────────────────────────────────────────
elif pg == "history":
    require_login()
    st.markdown("## 📁 سجل مشاريعي")
    projs = db_get_projects(me()["id"])
    if not projs:
        st.info("لا توجد مشاريع بعد.")
        if st.button("📊 ابدأ التقييم"): go("scoring")
    else:
        st.markdown(f"**إجمالي المشاريع:** {len(projs)}")
        for p in projs:
            _, c = _grade(p["final_score"])
            with st.expander(f"📋 {p['project_name']}  —  {p['final_score']}/10  |  {p['created_at'][:10]}"):
                mc = st.columns(5)
                for col,(lbl,val) in zip(mc,[
                    ("دراسة السوق",      p["market_study"]),
                    ("خبرة الفريق",      p["team_experience"]),
                    ("رأس المال",        p["capital_stability"]),
                    ("الابتكار",         p["innovation_score"]),
                    ("الامتثال",         p["legal_compliance"]),
                ]):
                    with col: st.metric(lbl, f"{val}/10")
                st.markdown(f"""
                <div style='text-align:center;margin:12px 0'>
                  <span style='font-size:38px;font-weight:900;color:{c}'>{p['final_score']}/10</span>
                </div>""", unsafe_allow_html=True)
                if p.get("advice"):
                    for line in p["advice"].split("\n"):
                        if line.strip(): st.markdown(f"- {line}")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#94a3b8;font-size:11px;padding:10px 0'>
  🏭 MyIndustryAI © 2025 — منصة الاستشارات البارامترية الصناعية
</div>""", unsafe_allow_html=True)
