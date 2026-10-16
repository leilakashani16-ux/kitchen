# -*- coding: utf-8 -*-
"""تولید PDF فارسی با پشتیبانی راست‌چین"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import arabic_reshaper
from bidi.algorithm import get_display
import os
from io import BytesIO
from datetime import datetime

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_REG = os.path.join(FONT_DIR, "Vazirmatn-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf")

def reshape(text):
    """آماده‌سازی متن فارسی برای نمایش صحیح در PDF"""
    if text is None:
        return ""
    text = str(text)
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

class PersianPDF(FPDF):
    def __init__(self, title="گزارش"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.title_text = title
        if os.path.exists(FONT_REG):
            self.add_font("Vazir", "", FONT_REG)
            self.add_font("Vazir", "B", FONT_BOLD if os.path.exists(FONT_BOLD) else FONT_REG)
            self.font_name = "Vazir"
        else:
            self.font_name = "Helvetica"
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        self._header()

    def _header(self):
        self.set_font(self.font_name, "B", 16)
        self.cell(0, 12, reshape(self.title_text), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(self.font_name, "", 10)
        self.cell(0, 8, reshape(f"تاریخ چاپ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        # خط جداکننده
        self.set_draw_color(20, 150, 140)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def add_table(self, headers, rows, col_widths=None):
        """جدول ساده راست‌چین"""
        if not rows:
            self.set_font(self.font_name, "", 11)
            self.cell(0, 10, reshape("داده‌ای برای نمایش وجود ندارد"), align="C")
            return

        n = len(headers)
        if col_widths is None:
            usable = 190
            col_widths = [usable / n] * n

        # هدر
        self.set_fill_color(15, 118, 110)
        self.set_text_color(255, 255, 255)
        self.set_font(self.font_name, "B", 9)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 9, reshape(str(h)), border=1, align="C", fill=True)
        self.ln()

        # ردیف‌ها
        self.set_text_color(0, 0, 0)
        self.set_font(self.font_name, "", 8)
        fill = False
        for row in rows:
            if self.get_y() > 270:
                self.add_page()
                self._header()
                self.set_fill_color(15, 118, 110)
                self.set_text_color(255, 255, 255)
                self.set_font(self.font_name, "B", 9)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 9, reshape(str(h)), border=1, align="C", fill=True)
                self.ln()
                self.set_text_color(0, 0, 0)
                self.set_font(self.font_name, "", 8)

            self.set_fill_color(240, 253, 250) if fill else self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 8, reshape(str(cell) if cell is not None else ""), border=1, align="C", fill=True)
            self.ln()
            fill = not fill

    def add_summary_box(self, items):
        """جعبه خلاصه آمار"""
        self.set_font(self.font_name, "B", 11)
        self.cell(0, 8, reshape("خلاصه آماری"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(self.font_name, "", 10)
        for label, value in items:
            self.cell(0, 7, reshape(f"{label}: {value}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

def generate_stock_pdf(stock_df, title="گزارش موجودی مواد اولیه"):
    pdf = PersianPDF(title)
    headers = ["کد", "نام ماده", "واحد", "اولیه", "ورود", "مصرف", "ضایعات", "فعلی", "وضعیت"]
    rows = []
    for _, r in stock_df.iterrows():
        status = "تمام" if r.get("current_stock", 0) <= 0 else ("کم" if r.get("current_stock", 0) <= r.get("min_stock", 0) else "عادی")
        rows.append([
            r.get("code", ""),
            r.get("name", ""),
            r.get("unit", ""),
            f"{r.get('initial_stock', 0):.1f}",
            f"{r.get('total_in', 0):.1f}",
            f"{r.get('total_out', 0):.1f}",
            f"{r.get('total_waste', 0):.1f}",
            f"{r.get('current_stock', 0):.1f}",
            status
        ])
    # عرض ستون‌ها
    widths = [18, 32, 18, 18, 18, 18, 18, 20, 20]
    pdf.add_table(headers, rows, widths)
    return bytes(pdf.output())

def generate_report_pdf(title, headers, rows, summary_items=None, col_widths=None):
    pdf = PersianPDF(title)
    if summary_items:
        pdf.add_summary_box(summary_items)
    pdf.add_table(headers, rows, col_widths)
    return bytes(pdf.output())
