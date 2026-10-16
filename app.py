# -*- coding: utf-8 -*-
"""
سیستم مدیریت گردش مواد اولیه و تولید کترینگ - نسخه ۲.۰
چندکاربره | نقش‌محور | خروجی اکسل | ثبت ضایعات | گزارش‌گیری پیشرفته
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import hashlib
import os
from pdf_utils import generate_stock_pdf, generate_report_pdf

# ==================== تنظیمات ====================
DB_PATH = os.getenv("DB_PATH", "kitchen_management.db")

st.set_page_config(
    page_title="سیستم مدیریت کترینگ",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Vazirmatn', Tahoma, sans-serif !important;
        direction: rtl;
        text-align: right;
    }
    .main-header {
        background: linear-gradient(90deg, #0f766e, #14b8a6);
        padding: 1rem 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 1.2rem;
    }
    .role-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-admin { background: #dc2626; color: white; }
    .badge-inbound { background: #2563eb; color: white; }
    .badge-production { background: #7c3aed; color: white; }
    .badge-viewer { background: #64748b; color: white; }
    div[data-testid="stSidebar"] { background: #0f172a; }
    .stButton>button { border-radius: 8px; }
    @media print {
        .stSidebar, .stButton, header { display: none !important; }
    }
</style>
""", unsafe_allow_html=True)

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def run_query(query, params=None):
    conn = get_conn()
    try:
        if params:
            df = pd.read_sql_query(query, conn, params=params)
        else:
            df = pd.read_sql_query(query, conn)
        return df
    finally:
        conn.close()

def execute(query, params=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def check_login(username, password):
    df = run_query("SELECT * FROM users WHERE username=? AND active=1", (username,))
    if df.empty:
        return None
    row = df.iloc[0]
    if row['password'] == password or row['password'] == hash_pass(password):
        return dict(row)
    return None

def get_current_stock():
    q = """
    SELECT 
        m.code, m.name, m.unit, m.initial_stock, m.min_stock, m.description,
        COALESCE((SELECT SUM(quantity) FROM inbound WHERE material_name = m.name), 0) as total_in,
        COALESCE((SELECT SUM(material_weight) FROM production WHERE material_name = m.name), 0) as total_out,
        COALESCE((SELECT SUM(quantity) FROM waste WHERE material_name = m.name), 0) as total_waste,
        m.initial_stock 
            + COALESCE((SELECT SUM(quantity) FROM inbound WHERE material_name = m.name), 0)
            - COALESCE((SELECT SUM(material_weight) FROM production WHERE material_name = m.name), 0)
            - COALESCE((SELECT SUM(quantity) FROM waste WHERE material_name = m.name), 0) as current_stock
    FROM materials m
    ORDER BY m.code
    """
    return run_query(q)

def to_excel(df, sheet_name="Sheet1"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def role_allowed(required_roles):
    if 'user' not in st.session_state:
        return False
    return st.session_state.user['role'] in required_roles or st.session_state.user['role'] == 'admin'

def page_login():
    st.markdown('<div class="main-header"><h1>🍳 سیستم مدیریت کترینگ</h1><p>ورود به سامانه</p></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("ورود کاربران")
            username = st.text_input("نام کاربری")
            password = st.text_input("رمز عبور", type="password")
            submit = st.form_submit_button("ورود", use_container_width=True)
            if submit:
                user = check_login(username, password)
                if user:
                    st.session_state.user = user
                    st.session_state.logged_in = True
                    st.success(f"خوش آمدید {user['full_name']}!")
                    st.rerun()
                else:
                    st.error("نام کاربری یا رمز عبور اشتباه است")
        st.info("""
        **حساب‌های پیش‌فرض:**
        - مدیر: `admin` / `admin123`
        - کاربر ورود: `vorood` / `1234`
        - کاربر تولید: `tolid` / `1234`
        """)

def page_dashboard():
    st.markdown('<div class="main-header"><h1>داشبورد مدیریتی</h1></div>', unsafe_allow_html=True)
    stock_df = get_current_stock()
    prod_stats = run_query("""
        SELECT COUNT(*) as records, COALESCE(SUM(material_weight),0) as total_weight,
               COALESCE(SUM(quantity),0) as total_qty, COALESCE(SUM(duration_min),0) as total_min
        FROM production
    """)
    inbound_count = run_query("SELECT COUNT(*) as c FROM inbound").iloc[0]['c']
    waste_total = run_query("SELECT COALESCE(SUM(quantity),0) as w FROM waste").iloc[0]['w']
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("رکورد تولید", f"{int(prod_stats.iloc[0]['records'])}")
    c2.metric("وزن مصرفی (کیلو)", f"{prod_stats.iloc[0]['total_weight']:.1f}")
    c3.metric("تعداد محصولات", f"{prod_stats.iloc[0]['total_qty']:.0f}")
    c4.metric("ورود مواد", f"{int(inbound_count)}")
    c5.metric("کل ضایعات (کیلو)", f"{waste_total:.1f}")
    
    st.markdown("---")
    st.subheader("📦 موجودی فعلی مواد اولیه")
    stock_df['وضعیت'] = stock_df.apply(
        lambda r: "🔴 تمام" if r['current_stock'] <= 0 else ("⚠️ کم" if r['current_stock'] <= r['min_stock'] else "✅ عادی"), axis=1)
    disp = stock_df[['code','name','unit','initial_stock','total_in','total_out','total_waste','current_stock','min_stock','وضعیت']].copy()
    disp.columns = ['کد','نام','واحد','اولیه','ورود','مصرف','ضایعات','فعلی','حداقل','وضعیت']
    st.dataframe(disp, use_container_width=True, hide_index=True)
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.download_button("📥 خروجی اکسل موجودی", to_excel(disp, "موجودی"), "mojoodi.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col_d2:
        try:
            pdf_bytes = generate_stock_pdf(stock_df, "گزارش موجودی مواد اولیه کترینگ")
            st.download_button("📄 دانلود PDF موجودی", pdf_bytes, "mojoodi.pdf", "application/pdf")
        except Exception as e:
            st.caption(f"PDF: {e}")
    with col_d3:
        if st.button("🖨️ آماده‌سازی چاپ مرورگر"):
            st.info("از منوی مرورگر گزینه Print را انتخاب کنید (Ctrl+P)")
    
    low = stock_df[stock_df['current_stock'] <= stock_df['min_stock']]
    if not low.empty:
        st.warning(f"⚠️ {len(low)} ماده به حد هشدار رسیده:")
        for _, r in low.iterrows():
            st.write(f"- **{r['name']}**: {r['current_stock']:.2f} {r['unit']} (حداقل {r['min_stock']})")
    
    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(stock_df, x='name', y='current_stock', color='current_stock',
                     title='موجودی فعلی', color_continuous_scale='Teal')
        fig.update_layout(font_family="Vazirmatn")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        perf = run_query("""
            SELECT producer as نام, SUM(quantity) as تعداد
            FROM production WHERE producer IS NOT NULL AND producer != ''
            GROUP BY producer ORDER BY تعداد DESC
        """)
        if not perf.empty:
            fig2 = px.bar(perf, x='نام', y='تعداد', title='عملکرد پرسنل', color='تعداد')
            fig2.update_layout(font_family="Vazirmatn")
            st.plotly_chart(fig2, use_container_width=True)

def page_materials():
    if not role_allowed(['admin']):
        st.error("فقط مدیر می‌تواند مواد اولیه را مدیریت کند.")
        return
    st.header("🥩 مدیریت مواد اولیه")
    tab1, tab2 = st.tabs(["لیست و موجودی", "افزودن / ویرایش"])
    with tab1:
        stock = get_current_stock()
        stock['وضعیت'] = stock.apply(lambda r: "کم" if r['current_stock'] <= r['min_stock'] else "عادی", axis=1)
        disp = stock[['code','name','unit','initial_stock','total_in','total_out','total_waste','current_stock','min_stock','وضعیت']]
        disp.columns = ['کد','نام','واحد','اولیه','ورود','مصرف','ضایعات','فعلی','حداقل','وضعیت']
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل", to_excel(disp), "materials.xlsx")
    with tab2:
        with st.form("add_mat"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد (M00X)")
            name = c2.text_input("نام ماده")
            unit = c1.selectbox("واحد", ["کیلوگرم", "عدد", "گرم"])
            init = c2.number_input("موجودی اولیه", min_value=0.0, value=0.0)
            min_s = c1.number_input("حداقل هشدار", min_value=0.0, value=5.0)
            desc = c2.text_input("توضیحات")
            if st.form_submit_button("ذخیره"):
                if code and name:
                    execute("INSERT INTO materials (code,name,unit,initial_stock,min_stock,description) VALUES (?,?,?,?,?,?)",
                            (code, name, unit, init, min_s, desc))
                    st.success("اضافه شد")
                    st.rerun()
        st.subheader("ویرایش")
        mats = run_query("SELECT name FROM materials")['name'].tolist()
        sel = st.selectbox("ماده", mats)
        if sel:
            row = run_query("SELECT * FROM materials WHERE name=?", (sel,)).iloc[0]
            with st.form("edit_mat"):
                new_init = st.number_input("موجودی اولیه", value=float(row['initial_stock']))
                new_min = st.number_input("حداقل", value=float(row['min_stock']))
                new_desc = st.text_input("توضیحات", value=row['description'] or "")
                if st.form_submit_button("به‌روزرسانی"):
                    execute("UPDATE materials SET initial_stock=?, min_stock=?, description=? WHERE name=?",
                            (new_init, new_min, new_desc, sel))
                    st.success("به‌روز شد")
                    st.rerun()

def page_personnel():
    if not role_allowed(['admin']):
        st.error("دسترسی محدود به مدیر")
        return
    st.header("👥 مدیریت پرسنل")
    tab1, tab2 = st.tabs(["لیست", "افزودن"])
    with tab1:
        df = run_query("SELECT code as کد, name as نام, role as سمت, CASE active WHEN 1 THEN 'بله' ELSE 'خیر' END as فعال FROM personnel")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل", to_excel(df), "personnel.xlsx")
    with tab2:
        with st.form("add_p"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد")
            name = c2.text_input("نام")
            role = c1.text_input("سمت")
            if st.form_submit_button("ذخیره") and code and name:
                execute("INSERT INTO personnel (code,name,role,active) VALUES (?,?,?,1)", (code, name, role))
                st.success("اضافه شد")
                st.rerun()

def page_products():
    if not role_allowed(['admin']):
        st.error("دسترسی محدود به مدیر")
        return
    st.header("🍢 انواع محصول")
    tab1, tab2 = st.tabs(["لیست", "افزودن"])
    with tab1:
        df = run_query("""
            SELECT code as کد, name as نام, weight_per_unit as 'وزن (گرم)', material_name as ماده,
                   remainder_type as 'نوع باقیمانده', description as توضیحات
            FROM products WHERE name IS NOT NULL AND name != ''
        """)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل", to_excel(df), "products.xlsx")
    with tab2:
        mats = run_query("SELECT name FROM materials")['name'].tolist()
        with st.form("add_pr"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد")
            name = c2.text_input("نام")
            weight = c1.number_input("وزن هر عدد (گرم)", value=100.0)
            mat = c2.selectbox("ماده اولیه", mats)
            rem = c1.selectbox("نوع باقیمانده", ["حمل به روز بعد", "برگشت به مواد"])
            desc = c2.text_input("توضیحات")
            if st.form_submit_button("ذخیره") and code and name:
                execute("""INSERT INTO products (code,name,weight_per_unit,material_name,description,active,remainder_type,remainder_note)
                           VALUES (?,?,?,?,?,1,?,?)""", (code, name, weight, mat, desc, rem, ""))
                st.success("اضافه شد")
                st.rerun()

def page_inbound():
    if not role_allowed(['admin', 'inbound']):
        st.error("شما اجازه ثبت ورود ندارید.")
        return
    st.header("📥 ثبت ورود مواد و ضایعات")
    tab1, tab2, tab3 = st.tabs(["ثبت ورود جدید", "ثبت ضایعات", "تاریخچه ورود و ضایعات"])
    mats = run_query("SELECT name FROM materials")['name'].tolist()
    
    with tab1:
        with st.form("add_in"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value="1405/07/21")
            mat = c2.selectbox("ماده اولیه", mats, key="in_mat")
            qty = c3.number_input("مقدار ورود", min_value=0.01, value=10.0, step=0.1)
            supplier = c1.text_input("تأمین‌کننده")
            inv = c2.text_input("شماره فاکتور")
            notes = c3.text_input("توضیحات")
            if st.form_submit_button("💾 ثبت ورود"):
                execute("INSERT INTO inbound (date, material_name, quantity, supplier, invoice_no, notes) VALUES (?,?,?,?,?,?)",
                        (dt, mat, qty, supplier, inv, notes))
                st.success(f"ورود {qty} {mat} ثبت شد")
                st.rerun()
    
    with tab2:
        st.info("ضایعات از موجودی ماده اولیه به صورت خودکار کسر می‌شود.")
        with st.form("add_waste"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value="1405/07/21", key="w_dt")
            mat = c2.selectbox("ماده اولیه", mats, key="w_mat")
            qty = c3.number_input("مقدار ضایعات", min_value=0.01, value=1.0, step=0.1)
            reason = c1.selectbox("علت", ["خراب شدن", "تاریخ گذشته", "اشتباه تولید", "حمل و نقل", "سایر"])
            notes = c2.text_input("یادداشت")
            if st.form_submit_button("ثبت ضایعات"):
                user_name = st.session_state.user.get('full_name', st.session_state.user['username'])
                execute("INSERT INTO waste (date, material_name, quantity, reason, recorded_by, notes) VALUES (?,?,?,?,?,?)",
                        (dt, mat, qty, reason, user_name, notes))
                st.success(f"ضایعات {qty} واحد از {mat} ثبت و از موجودی کسر شد")
                st.rerun()
    
    with tab3:
        st.subheader("تاریخچه ورود")
        df_in = run_query("""
            SELECT date as تاریخ, material_name as ماده, quantity as مقدار, supplier as تأمین‌کننده,
                   invoice_no as فاکتور, notes as توضیحات FROM inbound ORDER BY date DESC, id DESC
        """)
        st.dataframe(df_in, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل ورودها", to_excel(df_in), "inbound.xlsx")
        
        st.subheader("تاریخچه ضایعات")
        df_w = run_query("""
            SELECT date as تاریخ, material_name as ماده, quantity as مقدار, reason as علت,
                   recorded_by as ثبت‌کننده, notes as یادداشت FROM waste ORDER BY id DESC
        """)
        if not df_w.empty:
            st.dataframe(df_w, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل ضایعات", to_excel(df_w), "waste.xlsx")
        else:
            st.info("ضایعاتی ثبت نشده")
        
        if role_allowed(['admin']):
            st.subheader("حذف رکورد (فقط مدیر)")
            ids_in = run_query("SELECT id, date || ' - ' || material_name || ' (' || quantity || ')' as label FROM inbound ORDER BY id DESC LIMIT 30")
            if not ids_in.empty:
                sel = st.selectbox("حذف ورود", ids_in['label'].tolist())
                if st.button("حذف ورود انتخاب‌شده"):
                    rid = int(ids_in[ids_in['label']==sel]['id'].iloc[0])
                    execute("DELETE FROM inbound WHERE id=?", (rid,))
                    st.success("حذف شد")
                    st.rerun()

def page_production():
    if not role_allowed(['admin', 'production']):
        st.error("شما اجازه ثبت تولید ندارید.")
        return
    st.header("🏭 ثبت تولید روزانه")
    tab1, tab2 = st.tabs(["ثبت تولید جدید", "تاریخچه تولید"])
    products = run_query("SELECT name, weight_per_unit, material_name, remainder_type FROM products WHERE active=1 AND name IS NOT NULL AND name != ''")
    personnel = run_query("SELECT name FROM personnel WHERE active=1")['name'].tolist()
    
    with tab1:
        with st.form("add_prod"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value="1405/07/21")
            prod_name = c2.selectbox("محصول", products['name'].tolist())
            pinfo = products[products['name']==prod_name].iloc[0]
            qty = c3.number_input("تعداد تولید", min_value=0.1, value=10.0)
            auto_w = round((pinfo['weight_per_unit'] * qty) / 1000.0, 3)
            st.info(f"وزن محاسبه‌شده: **{auto_w} کیلو** (بر اساس {pinfo['weight_per_unit']} گرم هر عدد)")
            mat_weight = st.number_input("وزن مصرفی (کیلو) - قابل ویرایش", value=float(auto_w), step=0.01)
            mat_name = st.selectbox("ماده اولیه", [pinfo['material_name']] + run_query("SELECT name FROM materials")['name'].tolist())
            c4, c5, c6 = st.columns(3)
            shift = c4.text_input("کد شیفت")
            start_t = c5.text_input("ساعت شروع")
            end_t = c6.text_input("ساعت پایان")
            duration = st.number_input("مدت (دقیقه)", min_value=0.0, value=0.0)
            producer = st.selectbox("تولیدکننده", personnel)
            rem_type = st.selectbox("نوع باقیمانده", ["حمل به روز بعد", "برگشت به مواد"],
                                    index=0 if pinfo['remainder_type']=='حمل به روز بعد' else 1)
            rem_qty = st.number_input("تعداد باقیمانده", value=0.0)
            rem_w = st.number_input("وزن باقیمانده", value=0.0)
            notes = st.text_input("توضیحات")
            if st.form_submit_button("💾 ثبت تولید"):
                execute("""INSERT INTO production 
                    (date, product_name, quantity, material_weight, material_name, shift_code, start_time, end_time,
                     duration_min, producer, remainder_qty, remainder_weight, remainder_type, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (dt, prod_name, qty, mat_weight, mat_name, shift or None, start_t or None, end_t or None,
                     duration or None, producer, rem_qty, rem_w, rem_type, notes or None))
                st.success(f"تولید ثبت شد | مصرف: {mat_weight} کیلو {mat_name}")
                st.rerun()
    
    with tab2:
        df = run_query("""
            SELECT date as تاریخ, product_name as محصول, quantity as تعداد, material_weight as 'وزن مصرفی',
                   material_name as ماده, producer as تولیدکننده, duration_min as 'مدت', remainder_type as باقیمانده
            FROM production ORDER BY date DESC, id DESC
        """)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل تولید", to_excel(df), "production.xlsx")
        if role_allowed(['admin']):
            st.subheader("حذف (فقط مدیر)")
            ids = run_query("SELECT id, date || ' | ' || product_name || ' ×' || quantity as label FROM production ORDER BY id DESC LIMIT 40")
            if not ids.empty:
                sel = st.selectbox("انتخاب", ids['label'].tolist())
                if st.button("حذف"):
                    rid = int(ids[ids['label']==sel]['id'].iloc[0])
                    execute("DELETE FROM production WHERE id=?", (rid,))
                    st.success("حذف شد")
                    st.rerun()

def page_reports():
    st.header("📊 گزارش‌گیری پیشرفته")
    tab1, tab2, tab3, tab4 = st.tabs(["موجودی و مصرف", "تولید", "عملکرد پرسنل", "ورود و ضایعات"])
    
    with tab1:
        stock = get_current_stock()
        stock['درصد مصرف'] = ((stock['total_out'] + stock['total_waste']) / 
                              (stock['total_in'] + stock['initial_stock'] + 0.0001) * 100).round(1)
        stock['وضعیت'] = stock.apply(lambda r: "تمام" if r['current_stock']<=0 else ("کم" if r['current_stock']<=r['min_stock'] else "عادی"), axis=1)
        disp = stock[['code','name','initial_stock','total_in','total_out','total_waste','current_stock','درصد مصرف','وضعیت']]
        disp.columns = ['کد','نام','اولیه','ورود','مصرف','ضایعات','فعلی','٪ مصرف','وضعیت']
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل موجودی تفصیلی", to_excel(disp), "report_stock.xlsx")
        try:
            pdf_b = generate_stock_pdf(stock, "گزارش تفصیلی موجودی و مصرف")
            st.download_button("📄 PDF موجودی تفصیلی", pdf_b, "report_stock.pdf", "application/pdf")
        except Exception as e:
            st.caption(str(e))
        fig = px.pie(stock, values='total_out', names='name', title='سهم مصرف مواد')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        daily = run_query("""
            SELECT date as تاریخ, COUNT(*) as رکورد, SUM(quantity) as تعداد, 
                   ROUND(SUM(material_weight),2) as وزن_کیلو
            FROM production GROUP BY date ORDER BY date
        """)
        st.dataframe(daily, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل تولید روزانه", to_excel(daily), "report_daily_prod.xlsx")
        if not daily.empty:
            fig = px.line(daily, x='تاریخ', y='وزن_کیلو', markers=True, title='روند مصرف روزانه')
            st.plotly_chart(fig, use_container_width=True)
        by_prod = run_query("""
            SELECT product_name as محصول, SUM(quantity) as تعداد, ROUND(SUM(material_weight),2) as وزن
            FROM production GROUP BY product_name ORDER BY تعداد DESC
        """)
        st.subheader("بر اساس محصول")
        st.dataframe(by_prod, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل بر اساس محصول", to_excel(by_prod), "report_by_product.xlsx")
    
    with tab3:
        perf = run_query("""
            SELECT producer as پرسنل, COUNT(*) as رکوردها,
                   SUM(quantity) as مجموع_تعداد,
                   ROUND(SUM(material_weight),2) as مجموع_وزن,
                   ROUND(SUM(duration_min),1) as مجموع_دقیقه,
                   ROUND(AVG(duration_min),1) as میانگین_زمان
            FROM production WHERE producer IS NOT NULL AND producer != ''
            GROUP BY producer ORDER BY مجموع_تعداد DESC
        """)
        st.dataframe(perf, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل عملکرد پرسنل", to_excel(perf), "report_personnel.xlsx")
        try:
            headers = ["پرسنل", "رکوردها", "مجموع تعداد", "مجموع وزن", "مجموع دقیقه", "میانگین زمان"]
            rows = [[r["پرسنل"], r["رکوردها"], r["مجموع_تعداد"], r["مجموع_وزن"], r["مجموع_دقیقه"], r["میانگین_زمان"]] for _, r in perf.iterrows()]
            pdf_b = generate_report_pdf("گزارش عملکرد پرسنل", headers, rows)
            st.download_button("📄 PDF عملکرد پرسنل", pdf_b, "report_personnel.pdf", "application/pdf")
        except Exception as e:
            st.caption(str(e))
        if not perf.empty:
            fig = px.bar(perf, x='پرسنل', y='مجموع_تعداد', title='تعداد تولید پرسنل', color='مجموع_تعداد')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("ورودها")
        df_in = run_query("""
            SELECT date as تاریخ, material_name as ماده, quantity as مقدار, supplier as تأمین‌کننده
            FROM inbound ORDER BY date DESC
        """)
        st.dataframe(df_in, use_container_width=True, hide_index=True)
        st.download_button("📥 اکسل ورود", to_excel(df_in), "report_inbound.xlsx")
        st.subheader("ضایعات")
        df_w = run_query("""
            SELECT date as تاریخ, material_name as ماده, quantity as مقدار, reason as علت, recorded_by as ثبت‌کننده
            FROM waste ORDER BY date DESC
        """)
        if not df_w.empty:
            st.dataframe(df_w, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل ضایعات", to_excel(df_w), "report_waste.xlsx")
        else:
            st.info("ضایعاتی ثبت نشده")

def page_users():
    if not role_allowed(['admin']):
        st.error("فقط مدیر")
        return
    st.header("👤 مدیریت کاربران سیستم")
    df = run_query("SELECT id, username as نام‌کاربری, full_name as نام‌کامل, role as نقش, CASE active WHEN 1 THEN 'فعال' ELSE 'غیرفعال' END as وضعیت FROM users")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.subheader("افزودن کاربر جدید")
    with st.form("add_user"):
        c1, c2 = st.columns(2)
        uname = c1.text_input("نام کاربری")
        fname = c2.text_input("نام کامل")
        pwd = c1.text_input("رمز عبور", type="password")
        role = c2.selectbox("نقش", ["admin", "inbound", "production", "viewer"])
        if st.form_submit_button("ایجاد کاربر"):
            if uname and pwd:
                try:
                    execute("INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)",
                            (uname, pwd, fname, role))
                    st.success("کاربر ایجاد شد")
                    st.rerun()
                except Exception as e:
                    st.error(f"خطا: {e}")

def page_settings():
    st.header("⚙️ تنظیمات و پشتیبان‌گیری")
    st.subheader("دانلود پایگاه داده")
    try:
        with open(DB_PATH, "rb") as f:
            st.download_button("⬇️ دانلود فایل SQLite", f, file_name="kitchen_backup.db")
    except:
        st.warning("فایل دیتابیس در دسترس نیست")
    
    st.markdown("---")
    st.subheader("راهنمای استقرار چندکاربره آنلاین")
    st.markdown("""
### گزینه ۱ (ساده‌ترین): Streamlit Cloud + Turso
1. حساب رایگان در [turso.tech](https://turso.tech)
2. دیتابیس بسازید و فایل را آپلود کنید
3. در Streamlit Cloud ریپو را وصل کنید

### گزینه ۲ (قوی‌ترین): Supabase
- دیتابیس Postgres + Auth + Realtime رایگان
- برای چندکاربره واقعی عالی

### گزینه ۳: PocketBase
- SQLite + Auth آماده
- روی Render یا Fly.io رایگان
    """)

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
    
    if not st.session_state.logged_in:
        page_login()
        return
    
    user = st.session_state.user
    role = user['role']
    
    st.sidebar.title("🍳 منوی سیستم")
    st.sidebar.markdown(f"**{user.get('full_name', user['username'])}**")
    role_labels = {'admin': 'مدیر', 'inbound': 'ثبت ورود', 'production': 'ثبت تولید', 'viewer': 'مشاهده‌گر'}
    badge_class = f"badge-{role}"
    st.sidebar.markdown(f'<span class="role-badge {badge_class}">{role_labels.get(role, role)}</span>', unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    pages = {"🏠 داشبورد": page_dashboard}
    if role in ['admin', 'inbound']:
        pages["📥 ورود و ضایعات"] = page_inbound
    if role in ['admin', 'production']:
        pages["🏭 تولید روزانه"] = page_production
    pages["📊 گزارش‌ها"] = page_reports
    if role == 'admin':
        pages["🥩 مواد اولیه"] = page_materials
        pages["👥 پرسنل"] = page_personnel
        pages["🍢 انواع محصول"] = page_products
        pages["👤 کاربران سیستم"] = page_users
        pages["⚙️ تنظیمات"] = page_settings
    
    choice = st.sidebar.radio("صفحه:", list(pages.keys()))
    if st.sidebar.button("خروج از حساب"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.caption("نسخه ۲.۰ | چندکاربره")
    pages[choice]()

if __name__ == "__main__":
    main()
