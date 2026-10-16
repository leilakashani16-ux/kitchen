-- =====================================================
-- اسکیمای کامل برای Supabase (Postgres)
-- کپی کنید و در SQL Editor پروژه Supabase اجرا کنید
-- =====================================================

-- فعال‌سازی UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- جدول کاربران (برای نقش‌ها - در کنار Auth خود Supabase)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'inbound', 'production', 'viewer')),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- مواد اولیه
CREATE TABLE IF NOT EXISTS materials (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    initial_stock NUMERIC(12,3) DEFAULT 0,
    min_stock NUMERIC(12,3) DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- پرسنل
CREATE TABLE IF NOT EXISTS personnel (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT,
    active BOOLEAN DEFAULT true
);

-- محصولات
CREATE TABLE IF NOT EXISTS products (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    weight_per_unit NUMERIC(10,2),
    material_name TEXT REFERENCES materials(name),
    description TEXT,
    active BOOLEAN DEFAULT true,
    remainder_type TEXT,
    remainder_note TEXT
);

-- ورود مواد
CREATE TABLE IF NOT EXISTS inbound (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    material_name TEXT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL,
    supplier TEXT,
    invoice_no TEXT,
    notes TEXT,
    recorded_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- تولید
CREATE TABLE IF NOT EXISTS production (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL,
    material_weight NUMERIC(12,3) NOT NULL,
    material_name TEXT NOT NULL,
    shift_code TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_min NUMERIC(10,2),
    producer TEXT,
    remainder_qty NUMERIC(12,3) DEFAULT 0,
    remainder_weight NUMERIC(12,3) DEFAULT 0,
    remainder_type TEXT,
    notes TEXT,
    recorded_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ضایعات
CREATE TABLE IF NOT EXISTS waste (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    material_name TEXT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL,
    reason TEXT,
    recorded_by TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- برگشت به مواد
CREATE TABLE IF NOT EXISTS returns (
    id BIGSERIAL PRIMARY KEY,
    date TEXT,
    product_name TEXT,
    remainder_qty NUMERIC(12,3),
    return_weight NUMERIC(12,3),
    target_material TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ایندکس‌ها برای سرعت
CREATE INDEX IF NOT EXISTS idx_inbound_date ON inbound(date);
CREATE INDEX IF NOT EXISTS idx_inbound_material ON inbound(material_name);
CREATE INDEX IF NOT EXISTS idx_production_date ON production(date);
CREATE INDEX IF NOT EXISTS idx_production_material ON production(material_name);
CREATE INDEX IF NOT EXISTS idx_waste_material ON waste(material_name);

-- View موجودی فعلی
CREATE OR REPLACE VIEW current_stock AS
SELECT 
    m.code,
    m.name,
    m.unit,
    m.initial_stock,
    m.min_stock,
    COALESCE(SUM(i.quantity), 0) AS total_in,
    COALESCE((SELECT SUM(p.material_weight) FROM production p WHERE p.material_name = m.name), 0) AS total_out,
    COALESCE((SELECT SUM(w.quantity) FROM waste w WHERE w.material_name = m.name), 0) AS total_waste,
    m.initial_stock 
        + COALESCE(SUM(i.quantity), 0)
        - COALESCE((SELECT SUM(p.material_weight) FROM production p WHERE p.material_name = m.name), 0)
        - COALESCE((SELECT SUM(w.quantity) FROM waste w WHERE w.material_name = m.name), 0) AS current_stock
FROM materials m
LEFT JOIN inbound i ON i.material_name = m.name
GROUP BY m.code, m.name, m.unit, m.initial_stock, m.min_stock;

-- Row Level Security (نمونه ساده - می‌توانید سخت‌گیرانه‌تر کنید)
ALTER TABLE materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbound ENABLE ROW LEVEL SECURITY;
ALTER TABLE production ENABLE ROW LEVEL SECURITY;
ALTER TABLE waste ENABLE ROW LEVEL SECURITY;
ALTER TABLE personnel ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- سیاست‌های نمونه: همه کاربران احراز هویت‌شده می‌توانند بخوانند
CREATE POLICY "Allow read for authenticated" ON materials FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read for authenticated" ON inbound FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read for authenticated" ON production FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read for authenticated" ON waste FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read for authenticated" ON personnel FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read for authenticated" ON products FOR SELECT TO authenticated USING (true);

-- نوشتن: فقط authenticated (نقش را در سطح اپ چک می‌کنیم)
CREATE POLICY "Allow insert for authenticated" ON inbound FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Allow insert for authenticated" ON production FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Allow insert for authenticated" ON waste FOR INSERT TO authenticated WITH CHECK (true);

-- برای مدیریت کامل‌تر می‌توانید از function و claims نقش استفاده کنید.

-- تریگر برای ساخت پروفایل هنگام ثبت‌نام
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, username, full_name, role)
  VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name', COALESCE(NEW.raw_user_meta_data->>'role', 'viewer'));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
