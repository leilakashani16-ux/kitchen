# -*- coding: utf-8 -*-
"""
سیستم مدیریت کترینگ - نسخه Supabase (کامل و آماده دیپلوی)
چندکاربره | Auth واقعی | Realtime-ready | PDF + Excel | نقش‌محور
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import os

# ==================== تنظیمات Supabase ====================
# این مقادیر را از Project Settings → API در Supabase بردارید
# در Streamlit Cloud از Secrets استفاده کنید

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))

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
</style>
""", unsafe_allow_html=True)

# ==================== اتصال Supabase ====================
@st.cache_resource
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def sb():
    client = get_supabase()
    if client is None:
        st.error("⚠️ تنظیمات Supabase یافت نشد. لطفاً SUPABASE_URL و SUPABASE_KEY را در Secrets تنظیم کنید.")
        st.stop()
    return client

# ==================== توابع کمکی ====================
def to_excel(df, sheet_name="Sheet1"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def role_allowed(required_roles):
    if 'user' not in st.session_state or not st.session_state.user:
        return False
    return st.session_state.user.get('role') in required_roles or st.session_state.user.get('role') == 'admin'

def get_current_stock():
    """محاسبه موجودی از view یا با query"""
    try:
        # اول سعی می‌کنیم از view استفاده کنیم
        res = sb().table("current_stock").select("*").execute()
        if res.data:
            return pd.DataFrame(res.data)
    except Exception:
        pass

    # روش دستی
    mats = sb().table("materials").select("*").execute().data or []
    inbound = sb().table("inbound").select("material_name, quantity").execute().data or []
    production = sb().table("production").select("material_name, material_weight").execute().data or []
    waste = sb().table("waste").select("material_name, quantity").execute().data or []

    from collections import defaultdict
    total_in = defaultdict(float)
    total_out = defaultdict(float)
    total_waste = defaultdict(float)
    for r in inbound:
        total_in[r["material_name"]] += float(r["quantity"] or 0)
    for r in production:
        total_out[r["material_name"]] += float(r["material_weight"] or 0)
    for r in waste:
        total_waste[r["material_name"]] += float(r["quantity"] or 0)

    rows = []
    for m in mats:
        name = m["name"]
        init = float(m.get("initial_stock") or 0)
        curr = init + total_in[name] - total_out[name] - total_waste[name]
        rows.append({
            "code": m["code"],
            "name": name,
            "unit": m.get("unit"),
            "initial_stock": init,
            "min_stock": float(m.get("min_stock") or 0),
            "total_in": total_in[name],
            "total_out": total_out[name],
            "total_waste": total_waste[name],
            "current_stock": curr,
            "description": m.get("description")
        })
    return pd.DataFrame(rows)

def try_pdf_stock(stock_df, title="گزارش موجودی"):
    try:
        from pdf_utils import generate_stock_pdf
        return generate_stock_pdf(stock_df, title)
    except Exception as e:
        st.caption(f"PDF در دسترس نیست: {e}")
        return None

def try_pdf_report(title, headers, rows):
    try:
        from pdf_utils import generate_report_pdf
        return generate_report_pdf(title, headers, rows)
    except Exception as e:
        st.caption(f"PDF: {e}")
        return None

# ==================== صفحه ورود (Supabase Auth) ====================
def page_login():
    st.markdown('<div class="main-header"><h1>🍳 سیستم مدیریت کترینگ</h1><p>ورود با حساب Supabase</p></div>', unsafe_allow_html=True)

    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("""
        **تنظیمات Supabase انجام نشده است.**

        در Streamlit Cloud از منوی ⋮ → Settings → Secrets این مقادیر را وارد کنید:

        ```toml
        SUPABASE_URL = "https://xxxx.supabase.co"
        SUPABASE_KEY = "eyJhbGciOi..."
        ```
        """)
        st.stop()

    tab1, tab2 = st.tabs(["ورود", "ثبت‌نام کاربر جدید"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("ایمیل")
            password = st.text_input("رمز عبور", type="password")
            if st.form_submit_button("ورود", use_container_width=True):
                try:
                    res = sb().auth.sign_in_with_password({"email": email, "password": password})
                    user = res.user
                    # گرفتن نقش از profiles
                    profile = sb().table("profiles").select("*").eq("id", user.id).execute()
                    role = "viewer"
                    full_name = email
                    if profile.data:
                        role = profile.data[0].get("role", "viewer")
                        full_name = profile.data[0].get("full_name") or email
                    st.session_state.user = {
                        "id": user.id,
                        "email": email,
                        "full_name": full_name,
                        "role": role
                    }
                    st.session_state.logged_in = True
                    st.session_state.access_token = res.session.access_token
                    st.success(f"خوش آمدید {full_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"خطا در ورود: {e}")

    with tab2:
        st.info("ثبت‌نام فقط برای ساخت حساب. نقش پیش‌فرض «مشاهده‌گر» است. مدیر باید نقش را تغییر دهد.")
        with st.form("signup_form"):
            email = st.text_input("ایمیل", key="su_email")
            password = st.text_input("رمز عبور (حداقل ۶ کاراکتر)", type="password", key="su_pass")
            full_name = st.text_input("نام کامل", key="su_name")
            if st.form_submit_button("ثبت‌نام"):
                try:
                    res = sb().auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {"data": {"full_name": full_name, "role": "viewer"}}
                    })
                    st.success("ثبت‌نام موفق! اگر تأیید ایمیل فعال باشد، لینک را چک کنید. سپس وارد شوید.")
                except Exception as e:
                    st.error(f"خطا: {e}")

# ==================== داشبورد ====================
def page_dashboard():
    st.markdown('<div class="main-header"><h1>داشبورد مدیریتی</h1></div>', unsafe_allow_html=True)

    stock_df = get_current_stock()

    # آمار
    try:
        prod = sb().table("production").select("material_weight, quantity, duration_min").execute().data or []
        inbound_count = len(sb().table("inbound").select("id", count="exact").execute().data or [])
        waste_data = sb().table("waste").select("quantity").execute().data or []
        waste_total = sum(float(r["quantity"] or 0) for r in waste_data)
        total_weight = sum(float(r["material_weight"] or 0) for r in prod)
        total_qty = sum(float(r["quantity"] or 0) for r in prod)
    except Exception as e:
        st.warning(f"خطا در خواندن آمار: {e}")
        prod, inbound_count, waste_total, total_weight, total_qty = [], 0, 0, 0, 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("رکورد تولید", f"{len(prod)}")
    c2.metric("وزن مصرفی (کیلو)", f"{total_weight:.1f}")
    c3.metric("تعداد محصولات", f"{total_qty:.0f}")
    c4.metric("ورود مواد", f"{inbound_count}")
    c5.metric("کل ضایعات", f"{waste_total:.1f}")

    st.markdown("---")
    st.subheader("📦 موجودی فعلی مواد اولیه")

    if not stock_df.empty:
        stock_df["وضعیت"] = stock_df.apply(
            lambda r: "🔴 تمام" if r["current_stock"] <= 0 else ("⚠️ کم" if r["current_stock"] <= r["min_stock"] else "✅ عادی"), axis=1)
        disp = stock_df[["code", "name", "unit", "initial_stock", "total_in", "total_out", "total_waste", "current_stock", "min_stock", "وضعیت"]].copy()
        disp.columns = ["کد", "نام", "واحد", "اولیه", "ورود", "مصرف", "ضایعات", "فعلی", "حداقل", "وضعیت"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("📥 اکسل موجودی", to_excel(disp), "mojoodi.xlsx")
        with col2:
            pdf_b = try_pdf_stock(stock_df)
            if pdf_b:
                st.download_button("📄 PDF موجودی", pdf_b, "mojoodi.pdf", "application/pdf")
        with col3:
            if st.button("🔄 بروزرسانی"):
                st.rerun()

        low = stock_df[stock_df["current_stock"] <= stock_df["min_stock"]]
        if not low.empty:
            st.warning(f"⚠️ {len(low)} ماده به حد هشدار رسیده")
            for _, r in low.iterrows():
                st.write(f"- **{r['name']}**: {r['current_stock']:.2f} (حداقل {r['min_stock']})")

        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(stock_df, x="name", y="current_stock", color="current_stock", title="موجودی فعلی", color_continuous_scale="Teal")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            try:
                perf_data = sb().table("production").select("producer, quantity").execute().data or []
                if perf_data:
                    pdf = pd.DataFrame(perf_data)
                    pdf = pdf.groupby("producer", as_index=False)["quantity"].sum().sort_values("quantity", ascending=False)
                    pdf.columns = ["نام", "تعداد"]
                    fig2 = px.bar(pdf, x="نام", y="تعداد", title="عملکرد پرسنل", color="تعداد")
                    st.plotly_chart(fig2, use_container_width=True)
            except Exception:
                pass
    else:
        st.info("هنوز داده موجودی وجود ندارد. ابتدا seed data را وارد کنید.")

# ==================== مواد اولیه ====================
def page_materials():
    if not role_allowed(["admin"]):
        st.error("فقط مدیر")
        return
    st.header("🥩 مدیریت مواد اولیه")
    tab1, tab2 = st.tabs(["لیست", "افزودن"])

    with tab1:
        stock = get_current_stock()
        if not stock.empty:
            stock["وضعیت"] = stock.apply(lambda r: "کم" if r["current_stock"] <= r["min_stock"] else "عادی", axis=1)
            disp = stock[["code", "name", "unit", "initial_stock", "total_in", "total_out", "total_waste", "current_stock", "min_stock", "وضعیت"]]
            disp.columns = ["کد", "نام", "واحد", "اولیه", "ورود", "مصرف", "ضایعات", "فعلی", "حداقل", "وضعیت"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل", to_excel(disp), "materials.xlsx")

    with tab2:
        with st.form("add_mat"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد")
            name = c2.text_input("نام")
            unit = c1.selectbox("واحد", ["کیلوگرم", "عدد", "گرم"])
            init = c2.number_input("موجودی اولیه", min_value=0.0, value=0.0)
            min_s = c1.number_input("حداقل هشدار", min_value=0.0, value=5.0)
            desc = c2.text_input("توضیحات")
            if st.form_submit_button("ذخیره"):
                try:
                    sb().table("materials").insert({
                        "code": code, "name": name, "unit": unit,
                        "initial_stock": init, "min_stock": min_s, "description": desc
                    }).execute()
                    st.success("اضافه شد")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ==================== پرسنل ====================
def page_personnel():
    if not role_allowed(["admin"]):
        st.error("فقط مدیر")
        return
    st.header("👥 مدیریت پرسنل")
    tab1, tab2 = st.tabs(["لیست", "افزودن"])
    with tab1:
        data = sb().table("personnel").select("*").execute().data or []
        if data:
            df = pd.DataFrame(data)[["code", "name", "role", "active"]]
            df.columns = ["کد", "نام", "سمت", "فعال"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل", to_excel(df), "personnel.xlsx")
    with tab2:
        with st.form("add_p"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد")
            name = c2.text_input("نام")
            role = c1.text_input("سمت")
            if st.form_submit_button("ذخیره") and code and name:
                try:
                    sb().table("personnel").insert({"code": code, "name": name, "role": role, "active": True}).execute()
                    st.success("اضافه شد")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ==================== محصولات ====================
def page_products():
    if not role_allowed(["admin"]):
        st.error("فقط مدیر")
        return
    st.header("🍢 انواع محصول")
    tab1, tab2 = st.tabs(["لیست", "افزودن"])
    with tab1:
        data = sb().table("products").select("*").execute().data or []
        if data:
            df = pd.DataFrame(data)
            cols = [c for c in ["code", "name", "weight_per_unit", "material_name", "remainder_type", "description"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل", to_excel(df[cols]), "products.xlsx")
    with tab2:
        mats = [m["name"] for m in (sb().table("materials").select("name").execute().data or [])]
        with st.form("add_pr"):
            c1, c2 = st.columns(2)
            code = c1.text_input("کد")
            name = c2.text_input("نام")
            weight = c1.number_input("وزن هر عدد (گرم)", value=100.0)
            mat = c2.selectbox("ماده اولیه", mats) if mats else c2.text_input("ماده اولیه")
            rem = c1.selectbox("نوع باقیمانده", ["حمل به روز بعد", "برگشت به مواد"])
            desc = c2.text_input("توضیحات")
            if st.form_submit_button("ذخیره") and code and name:
                try:
                    sb().table("products").insert({
                        "code": code, "name": name, "weight_per_unit": weight,
                        "material_name": mat, "description": desc, "active": True,
                        "remainder_type": rem, "remainder_note": ""
                    }).execute()
                    st.success("اضافه شد")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ==================== ورود + ضایعات ====================
def page_inbound():
    if not role_allowed(["admin", "inbound"]):
        st.error("اجازه ثبت ورود ندارید")
        return
    st.header("📥 ثبت ورود مواد و ضایعات")
    tab1, tab2, tab3 = st.tabs(["ثبت ورود", "ثبت ضایعات", "تاریخچه"])

    mats = [m["name"] for m in (sb().table("materials").select("name").execute().data or [])]

    with tab1:
        with st.form("add_in"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value=datetime.now().strftime("%Y/%m/%d"))
            mat = c2.selectbox("ماده اولیه", mats, key="in_mat") if mats else c2.text_input("ماده")
            qty = c3.number_input("مقدار", min_value=0.01, value=10.0)
            supplier = c1.text_input("تأمین‌کننده")
            inv = c2.text_input("فاکتور")
            notes = c3.text_input("توضیحات")
            if st.form_submit_button("💾 ثبت ورود"):
                try:
                    sb().table("inbound").insert({
                        "date": dt, "material_name": mat, "quantity": qty,
                        "supplier": supplier, "invoice_no": inv, "notes": notes,
                        "recorded_by": st.session_state.user.get("full_name")
                    }).execute()
                    st.success(f"ورود {qty} {mat} ثبت شد")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.info("ضایعات از موجودی به صورت خودکار کسر می‌شود.")
        with st.form("add_waste"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value=datetime.now().strftime("%Y/%m/%d"), key="wdt")
            mat = c2.selectbox("ماده", mats, key="wmat") if mats else c2.text_input("ماده", key="wmat2")
            qty = c3.number_input("مقدار ضایعات", min_value=0.01, value=1.0)
            reason = c1.selectbox("علت", ["خراب شدن", "تاریخ گذشته", "اشتباه تولید", "حمل و نقل", "سایر"])
            notes = c2.text_input("یادداشت")
            if st.form_submit_button("ثبت ضایعات"):
                try:
                    sb().table("waste").insert({
                        "date": dt, "material_name": mat, "quantity": qty,
                        "reason": reason, "notes": notes,
                        "recorded_by": st.session_state.user.get("full_name")
                    }).execute()
                    st.success("ضایعات ثبت و از موجودی کسر شد")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab3:
        data_in = sb().table("inbound").select("*").order("id", desc=True).limit(100).execute().data or []
        if data_in:
            df = pd.DataFrame(data_in)
            show_cols = [c for c in ["date", "material_name", "quantity", "supplier", "invoice_no", "notes"] if c in df.columns]
            st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل ورود", to_excel(df[show_cols]), "inbound.xlsx")
        data_w = sb().table("waste").select("*").order("id", desc=True).limit(50).execute().data or []
        if data_w:
            st.subheader("ضایعات")
            dfw = pd.DataFrame(data_w)
            st.dataframe(dfw, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل ضایعات", to_excel(dfw), "waste.xlsx")

# ==================== تولید ====================
def page_production():
    if not role_allowed(["admin", "production"]):
        st.error("اجازه ثبت تولید ندارید")
        return
    st.header("🏭 ثبت تولید روزانه")
    tab1, tab2 = st.tabs(["ثبت تولید", "تاریخچه"])

    products = sb().table("products").select("*").eq("active", True).execute().data or []
    personnel = [p["name"] for p in (sb().table("personnel").select("name").eq("active", True).execute().data or [])]
    prod_names = [p["name"] for p in products]
    prod_map = {p["name"]: p for p in products}

    with tab1:
        with st.form("add_prod"):
            c1, c2, c3 = st.columns(3)
            dt = c1.text_input("تاریخ", value=datetime.now().strftime("%Y/%m/%d"))
            prod_name = c2.selectbox("محصول", prod_names) if prod_names else c2.text_input("محصول")
            qty = c3.number_input("تعداد", min_value=0.1, value=10.0)

            pinfo = prod_map.get(prod_name, {})
            auto_w = round((float(pinfo.get("weight_per_unit") or 100) * qty) / 1000.0, 3)
            st.info(f"وزن محاسبه‌شده: **{auto_w} کیلو**")
            mat_weight = st.number_input("وزن مصرفی (کیلو)", value=float(auto_w), step=0.01)
            mats = [m["name"] for m in (sb().table("materials").select("name").execute().data or [])]
            default_mat = pinfo.get("material_name")
            mat_name = st.selectbox("ماده اولیه", mats, index=mats.index(default_mat) if default_mat in mats else 0) if mats else st.text_input("ماده")

            c4, c5, c6 = st.columns(3)
            shift = c4.text_input("کد شیفت")
            start_t = c5.text_input("ساعت شروع")
            end_t = c6.text_input("ساعت پایان")
            duration = st.number_input("مدت (دقیقه)", min_value=0.0, value=0.0)
            producer = st.selectbox("تولیدکننده", personnel) if personnel else st.text_input("تولیدکننده")
            rem_type = st.selectbox("نوع باقیمانده", ["حمل به روز بعد", "برگشت به مواد"])
            rem_qty = st.number_input("تعداد باقیمانده", value=0.0)
            rem_w = st.number_input("وزن باقیمانده", value=0.0)
            notes = st.text_input("توضیحات")

            if st.form_submit_button("💾 ثبت تولید"):
                try:
                    sb().table("production").insert({
                        "date": dt, "product_name": prod_name, "quantity": qty,
                        "material_weight": mat_weight, "material_name": mat_name,
                        "shift_code": shift or None, "start_time": start_t or None,
                        "end_time": end_t or None, "duration_min": duration or None,
                        "producer": producer, "remainder_qty": rem_qty,
                        "remainder_weight": rem_w, "remainder_type": rem_type,
                        "notes": notes or None,
                        "recorded_by": st.session_state.user.get("full_name")
                    }).execute()
                    st.success(f"تولید ثبت شد | مصرف: {mat_weight} کیلو")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        data = sb().table("production").select("*").order("id", desc=True).limit(100).execute().data or []
        if data:
            df = pd.DataFrame(data)
            show = [c for c in ["date", "product_name", "quantity", "material_weight", "material_name", "producer", "duration_min", "remainder_type"] if c in df.columns]
            st.dataframe(df[show], use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل تولید", to_excel(df[show]), "production.xlsx")

# ==================== گزارش‌ها ====================
def page_reports():
    st.header("📊 گزارش‌گیری")
    tab1, tab2, tab3, tab4 = st.tabs(["موجودی", "تولید", "عملکرد پرسنل", "ورود و ضایعات"])

    with tab1:
        stock = get_current_stock()
        if not stock.empty:
            stock["درصد مصرف"] = ((stock["total_out"] + stock["total_waste"]) /
                                  (stock["total_in"] + stock["initial_stock"] + 0.0001) * 100).round(1)
            stock["وضعیت"] = stock.apply(lambda r: "تمام" if r["current_stock"] <= 0 else ("کم" if r["current_stock"] <= r["min_stock"] else "عادی"), axis=1)
            disp = stock[["code", "name", "initial_stock", "total_in", "total_out", "total_waste", "current_stock", "درصد مصرف", "وضعیت"]]
            disp.columns = ["کد", "نام", "اولیه", "ورود", "مصرف", "ضایعات", "فعلی", "٪ مصرف", "وضعیت"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل", to_excel(disp), "report_stock.xlsx")
            pdf_b = try_pdf_stock(stock, "گزارش تفصیلی موجودی")
            if pdf_b:
                st.download_button("📄 PDF", pdf_b, "report_stock.pdf", "application/pdf")
            fig = px.pie(stock, values="total_out", names="name", title="سهم مصرف")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        data = sb().table("production").select("date, quantity, material_weight, product_name").execute().data or []
        if data:
            df = pd.DataFrame(data)
            daily = df.groupby("date", as_index=False).agg(رکورد=("quantity", "count"), تعداد=("quantity", "sum"), وزن_کیلو=("material_weight", "sum"))
            st.dataframe(daily, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل روزانه", to_excel(daily), "report_daily.xlsx")
            by_prod = df.groupby("product_name", as_index=False).agg(تعداد=("quantity", "sum"), وزن=("material_weight", "sum")).sort_values("تعداد", ascending=False)
            st.subheader("بر اساس محصول")
            st.dataframe(by_prod, use_container_width=True, hide_index=True)

    with tab3:
        data = sb().table("production").select("producer, quantity, material_weight, duration_min").execute().data or []
        if data:
            df = pd.DataFrame(data)
            df = df[df["producer"].notna() & (df["producer"] != "")]
            perf = df.groupby("producer", as_index=False).agg(
                رکوردها=("quantity", "count"),
                مجموع_تعداد=("quantity", "sum"),
                مجموع_وزن=("material_weight", "sum"),
                مجموع_دقیقه=("duration_min", "sum")
            )
            perf["میانگین_زمان"] = (perf["مجموع_دقیقه"] / perf["رکوردها"]).round(1)
            perf = perf.sort_values("مجموع_تعداد", ascending=False)
            st.dataframe(perf, use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل عملکرد", to_excel(perf), "report_personnel.xlsx")
            rows = [[r["producer"], r["رکوردها"], r["مجموع_تعداد"], round(r["مجموع_وزن"], 2), round(r["مجموع_دقیقه"] or 0, 1), r["میانگین_زمان"]] for _, r in perf.iterrows()]
            pdf_b = try_pdf_report("گزارش عملکرد پرسنل", ["پرسنل", "رکورد", "تعداد", "وزن", "دقیقه", "میانگین"], rows)
            if pdf_b:
                st.download_button("📄 PDF عملکرد", pdf_b, "report_personnel.pdf", "application/pdf")

    with tab4:
        data_in = sb().table("inbound").select("date, material_name, quantity, supplier").order("date", desc=True).execute().data or []
        if data_in:
            st.dataframe(pd.DataFrame(data_in), use_container_width=True, hide_index=True)
            st.download_button("📥 اکسل ورود", to_excel(pd.DataFrame(data_in)), "report_inbound.xlsx")
        data_w = sb().table("waste").select("*").order("date", desc=True).execute().data or []
        if data_w:
            st.subheader("ضایعات")
            st.dataframe(pd.DataFrame(data_w), use_container_width=True, hide_index=True)

# ==================== مدیریت کاربران (نقش) ====================
def page_users():
    if not role_allowed(["admin"]):
        st.error("فقط مدیر")
        return
    st.header("👤 مدیریت نقش کاربران")
    st.info("کاربران از طریق Auth Supabase ساخته می‌شوند. اینجا فقط نقش آن‌ها را تغییر می‌دهید.")

    data = sb().table("profiles").select("*").execute().data or []
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("تغییر نقش")
        emails = {d.get("full_name") or d.get("username") or d["id"]: d["id"] for d in data}
        sel = st.selectbox("کاربر", list(emails.keys()))
        new_role = st.selectbox("نقش جدید", ["admin", "inbound", "production", "viewer"])
        if st.button("ذخیره نقش"):
            try:
                sb().table("profiles").update({"role": new_role}).eq("id", emails[sel]).execute()
                st.success("نقش به‌روز شد")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        st.warning("هنوز پروفایلی ثبت نشده. اول یک کاربر ثبت‌نام کند.")

# ==================== تنظیمات ====================
def page_settings():
    st.header("⚙️ راهنمای اتصال و تنظیمات")
    st.markdown("""
### وضعیت اتصال
""")
    if SUPABASE_URL:
        st.success(f"متصل به: `{SUPABASE_URL[:40]}...`")
    else:
        st.error("SUPABASE_URL تنظیم نشده")

    st.markdown("""
### مراحل راه‌اندازی کامل

1. در [supabase.com](https://supabase.com) پروژه بسازید
2. فایل `supabase_schema.sql` را در **SQL Editor** اجرا کنید
3. فایل `supabase_seed.sql` را اجرا کنید (داده‌های مهر ۱۴۰۵)
4. از **Authentication → Providers** ایمیل را فعال کنید
5. یک کاربر با ایمیل خودتان ثبت‌نام کنید
6. در Table Editor جدول `profiles` نقش آن کاربر را `admin` کنید
7. در Streamlit Cloud → Secrets این دو مقدار را بگذارید:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

8. اپ را Deploy کنید و وارد شوید
    """)

# ==================== اصلی ====================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None

    if not st.session_state.logged_in:
        page_login()
        return

    user = st.session_state.user
    role = user.get("role", "viewer")

    st.sidebar.title("🍳 منوی سیستم")
    st.sidebar.markdown(f"**{user.get('full_name', user.get('email'))}**")
    role_labels = {"admin": "مدیر", "inbound": "ثبت ورود", "production": "ثبت تولید", "viewer": "مشاهده‌گر"}
    st.sidebar.markdown(f'<span class="role-badge badge-{role}">{role_labels.get(role, role)}</span>', unsafe_allow_html=True)
    st.sidebar.markdown("---")

    pages = {"🏠 داشبورد": page_dashboard}
    if role in ["admin", "inbound"]:
        pages["📥 ورود و ضایعات"] = page_inbound
    if role in ["admin", "production"]:
        pages["🏭 تولید روزانه"] = page_production
    pages["📊 گزارش‌ها"] = page_reports
    if role == "admin":
        pages["🥩 مواد اولیه"] = page_materials
        pages["👥 پرسنل"] = page_personnel
        pages["🍢 انواع محصول"] = page_products
        pages["👤 مدیریت نقش‌ها"] = page_users
        pages["⚙️ راهنما و تنظیمات"] = page_settings

    choice = st.sidebar.radio("صفحه:", list(pages.keys()))
    if st.sidebar.button("خروج"):
        try:
            sb().auth.sign_out()
        except Exception:
            pass
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    st.sidebar.caption("نسخه Supabase | چندکاربره واقعی")
    pages[choice]()

if __name__ == "__main__":
    main()
