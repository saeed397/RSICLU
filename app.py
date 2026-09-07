# -*- coding: utf-8 -*-
"""
app.py
======
اپلیکیشن Streamlit: تبدیل دقیق اندیکاتور Pine Script "RSI Tops and Bottoms"
(LonesomeTheBlue) به پایتون + دریافت آنلاین دیتا (BingX با فال‌بک خودکار)
+ گزارش آخرین همگرایی (bottom/سبز) و آخرین واگرایی (top/قرمز).

نسخه‌ی اصلاح‌شده: شامل تبدیل Heikin Ashi (در صورت فعال بودن گزینه‌ی
مربوطه) قبل از محاسبه‌ی RSI — دقیقاً مطابق رفتار TradingView وقتی نوع
کندل چارت را روی Heikin Ashi می‌گذارید. همچنین یک باگ در تشخیص "کندل
پایان" فلش رفع شده: قبلاً کندل تأیید (bar_index) گزارش می‌شد، حالا خودِ
کندل کف/سقف واقعی RSI گزارش می‌شود — این با مقایسه‌ی عددی دقیق روی داده‌ی
واقعی کاربر (BTC/USDT 4H) اعتبارسنجی شده است.

اجرا در GitHub + Streamlit Cloud:
    1) این پوشه (app.py, rsi_div_core.py, data_feed.py, requirements.txt)
       را در یک ریپازیتوری گیت‌هاب قرار دهید.
    2) در share.streamlit.io ریپازیتوری را وصل کرده و app.py را به‌عنوان
       فایل اصلی انتخاب کنید.
"""

import numpy as np
import pandas as pd
import streamlit as st

from data_feed import fetch_ohlcv
from rsi_div_core import detect_rsi_tops_bottoms, wilder_rsi, DivEvent
from heikin_ashi import to_heikin_ashi

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa_num(n: int) -> str:
    return str(int(n)).translate(PERSIAN_DIGITS)


def describe_event(ev: DivEvent, last_bar_index: int) -> str:
    """
    خروجی دقیقاً مطابق فرمت خواسته‌شده:
    'همگرایی از کندل ۳۶ قبلی شروع و در کندل ۲۷ قبلی به پایان رسیده است.'
    """
    label = "همگرایی" if ev.kind == "bottom" else "واگرایی"
    start_ago = last_bar_index - ev.start_bar
    end_ago = last_bar_index - ev.end_bar
    return (
        f"{label} از کندل {to_fa_num(start_ago)} قبلی شروع و در کندل "
        f"{to_fa_num(end_ago)} قبلی به پایان رسیده است."
    )


st.set_page_config(page_title="RSI Tops & Bottoms (Divergence)", layout="wide")
st.title("📉 RSI Tops & Bottoms — تبدیل دقیق از Pine Script")
st.caption(
    "بازنویسی خط‌به‌خط اندیکاتور Pine Script «RSI Tops and Bottoms» "
    "(LonesomeTheBlue) — بدون هیچ تغییر در فلسفه یا فرمول محاسباتی."
)

with st.sidebar:
    st.header("تنظیمات")
    symbol = st.text_input("نماد (Symbol)", value="BTC/USDT")
    timeframe = st.selectbox(
        "تایم‌فریم",
        ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        index=4,  # پیش‌فرض 4h (مطابق تست‌های انجام‌شده)
    )
    limit = st.slider("تعداد کندل دریافتی", min_value=200, max_value=1000, value=500, step=50)
    use_heikin_ashi = st.checkbox(
        "استفاده از کندل Heikin Ashi (طبق تنظیمات چارت شما)", value=True
    )

    st.divider()
    st.subheader("پارامترهای اندیکاتور (دقیقاً مطابق Pine)")
    rsi_len = st.number_input("RSI Length", value=14, min_value=1)
    ob = st.number_input("Upper Band (ob)", value=70.0)
    os_level = st.number_input("Lower Band (os)", value=30.0)
    prd = st.number_input("Max Bars in OB/OS (prd)", value=10, min_value=1)
    mindis = st.number_input("Min Bars between Tops/Bottoms (mindis)", value=5, min_value=0)
    maxdis = st.number_input("Max Bars between Tops/Bottoms (maxdis)", value=100, min_value=1)

    run = st.button("دریافت داده و محاسبه", type="primary")

if run:
    try:
        with st.spinner("در حال دریافت داده آنلاین..."):
            df, source_exchange = fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        st.success(f"داده با موفقیت از صرافی «{source_exchange}» دریافت شد. "
                    f"تعداد کندل: {len(df)}")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطا در دریافت داده: {e}")
        st.stop()

    # اگر کاربر روی چارت TradingView از کندل Heikin Ashi استفاده می‌کند،
    # باید RSI و منطق واگرایی هم دقیقاً روی همان OHLC هایکین‌آشی محاسبه شود
    # (نه OHLC واقعی بازار) — این دقیقاً همان چیزی است که TradingView
    # وقتی نوع کندل چارت را عوض می‌کنید انجام می‌دهد.
    calc_df = to_heikin_ashi(df) if use_heikin_ashi else df

    rsi = wilder_rsi(calc_df["close"].to_numpy(dtype=float), int(rsi_len))
    df["rsi"] = rsi
    calc_df["rsi"] = rsi

    events = detect_rsi_tops_bottoms(
        calc_df,
        rsi_len=int(rsi_len),
        ob=float(ob),
        os_level=float(os_level),
        prd=int(prd),
        mindis=int(mindis),
        maxdis=int(maxdis),
    )

    last_bar_index = len(df) - 1
    bottoms = [e for e in events if e.kind == "bottom"]
    tops = [e for e in events if e.kind == "top"]

    st.subheader("📌 نتیجه (فقط آخرین سیگنال‌ها — بدون تاریخچه)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**آخرین همگرایی (Bottom / سبز):**")
        if bottoms:
            last_bottom = bottoms[-1]
            st.info(describe_event(last_bottom, last_bar_index))
            st.caption(
                f"کندل شروع: {df['timestamp'].iloc[last_bottom.start_bar]} | "
                f"کندل پایان: {df['timestamp'].iloc[last_bottom.end_bar]}"
            )
        else:
            st.write("در بازه‌ی داده‌ی فعلی هیچ همگرایی یافت نشد.")

    with col2:
        st.markdown("**آخرین واگرایی (Top / قرمز):**")
        if tops:
            last_top = tops[-1]
            st.info(describe_event(last_top, last_bar_index))
            st.caption(
                f"کندل شروع: {df['timestamp'].iloc[last_top.start_bar]} | "
                f"کندل پایان: {df['timestamp'].iloc[last_top.end_bar]}"
            )
        else:
            st.write("در بازه‌ی داده‌ی فعلی هیچ واگرایی یافت نشد.")

    # ------------------------------------------------------------
    # نمودار RSI (بدون وابستگی به plotly - فقط با کتابخانه‌ی داخلی
    # Streamlit تا از خطای ماژول نصب‌نشده جلوگیری شود)
    # ------------------------------------------------------------
    st.subheader("نمودار RSI")
    rsi_chart_df = df[["timestamp", "rsi"]].set_index("timestamp").copy()
    rsi_chart_df["Upper Band"] = float(ob)
    rsi_chart_df["Lower Band"] = float(os_level)
    st.line_chart(rsi_chart_df)

    st.subheader("نمودار قیمت (Close)")
    price_label = "Close (Heikin Ashi)" if use_heikin_ashi else "Close"
    price_chart_df = pd.DataFrame(
        {price_label: calc_df["close"].to_numpy()}, index=df["timestamp"]
    )
    st.line_chart(price_chart_df)

    with st.expander("مشاهده‌ی داده خام (تعداد کل رویدادهای تاریخی، صرفاً جهت اعتبارسنجی کد)"):
        st.write(f"تعداد کل همگرایی‌های یافت‌شده در کل تاریخچه: {len(bottoms)}")
        st.write(f"تعداد کل واگرایی‌های یافت‌شده در کل تاریخچه: {len(tops)}")
        st.dataframe(df.tail(50))
else:
    st.info("پارامترها را تنظیم کرده و روی «دریافت داده و محاسبه» کلیک کنید.")
