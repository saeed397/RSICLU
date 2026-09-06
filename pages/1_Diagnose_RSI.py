# -*- coding: utf-8 -*-
"""
pages/1_Diagnose_RSI.py
========================
نسخه‌ی وب (Streamlit) اسکریپت تشخیصی — فقط RSI خام، بدون منطق واگرایی.
این فایل باید داخل پوشه‌ای به اسم "pages" (کنار app.py، نه داخل همون
پوشه‌ی روت به تنهایی) قرار بگیره تا Streamlit به‌صورت خودکار به‌عنوان
یک صفحه‌ی جدید (Multipage App) نشونش بده.

ساختار نهایی ریپازیتوری گیت‌هاب شما باید این‌شکلی بشه:

    your-repo/
    ├── app.py
    ├── data_feed.py
    ├── rsi_div_core.py
    ├── requirements.txt
    └── pages/
        └── 1_Diagnose_RSI.py   <-- همین فایل

بعد از push کردن، در پنل Streamlit Cloud یک منوی کشویی (سمت چپ بالا،
آیکون ☰ در گوشی) ظاهر می‌شه که می‌تونید بین "app" و "Diagnose RSI"
جابه‌جا بشید.
"""

import numpy as np
import pandas as pd
import streamlit as st

from data_feed import fetch_ohlcv
from rsi_div_core import wilder_rsi

st.set_page_config(page_title="Diagnose RSI", layout="wide")
st.title("🔍 تشخیص خام RSI (بدون منطق واگرایی)")
st.caption(
    "هدف این صفحه فقط بررسیِ درستیِ محاسبه‌ی RSI و داده‌ی دریافتی است — "
    "هیچ منطق واگرایی/همگرایی اینجا اجرا نمی‌شود."
)

col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.text_input("نماد", value="BTC/USDT")
with col2:
    timeframe = st.selectbox(
        "تایم‌فریم", ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"], index=5
    )
with col3:
    limit = st.number_input("تعداد کندل", min_value=100, max_value=1000, value=500, step=50)

col4, col5 = st.columns(2)
with col4:
    ob = st.number_input("Upper Band (ob)", value=70.0)
with col5:
    os_level = st.number_input("Lower Band (os)", value=30.0)

rsi_len = st.number_input("RSI Length", value=14, min_value=1)

if st.button("دریافت و بررسی", type="primary"):
    try:
        with st.spinner("در حال دریافت داده..."):
            df, source = fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=int(limit))
        st.success(f"داده از صرافی «{source}» دریافت شد | تعداد کندل: {len(df)}")
        st.write(
            f"اولین کندل: **{df['timestamp'].iloc[0]}**   |   "
            f"آخرین کندل: **{df['timestamp'].iloc[-1]}**"
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"خطا در دریافت داده: {e}")
        st.stop()

    rsi = wilder_rsi(df["close"].to_numpy(dtype=float), int(rsi_len))
    df["rsi"] = rsi

    # ------------------------------------------------------------
    # پیدا کردن بازه‌های پیوسته‌ی زیر os / بالای ob
    # ------------------------------------------------------------
    def find_excursions(mask: np.ndarray):
        n = len(mask)
        i = 0
        rows = []
        while i < n:
            if mask[i]:
                j = i
                while j < n and mask[j]:
                    j += 1
                rows.append((i, j - 1))
                i = j
            else:
                i += 1
        return rows

    below_os = (df["rsi"] < os_level).to_numpy()
    above_ob = (df["rsi"] > ob).to_numpy()

    below_ranges = find_excursions(below_os)
    above_ranges = find_excursions(above_ob)

    def ranges_to_df(ranges, label):
        rows = []
        for s, e in ranges:
            rows.append(
                {
                    "نوع": label,
                    "کندل شروع (#)": s,
                    "تاریخ شروع": df["timestamp"].iloc[s],
                    "کندل پایان (#)": e,
                    "تاریخ پایان": df["timestamp"].iloc[e],
                    "طول (کندل)": e - s + 1,
                    "RSI شروع": round(float(df["rsi"].iloc[s]), 2),
                    "RSI پایان": round(float(df["rsi"].iloc[e]), 2),
                }
            )
        return pd.DataFrame(rows)

    st.subheader(f"دوره‌های RSI زیر {os_level:.0f} (oversold)")
    df_below = ranges_to_df(below_ranges, "oversold")
    st.dataframe(df_below, use_container_width=True)

    st.subheader(f"دوره‌های RSI بالای {ob:.0f} (overbought)")
    df_above = ranges_to_df(above_ranges, "overbought")
    st.dataframe(df_above, use_container_width=True)

    # ------------------------------------------------------------
    # نمودار RSI برای مقایسه‌ی چشمی سریع
    # ------------------------------------------------------------
    st.subheader("نمودار RSI")
    st.line_chart(df.set_index("timestamp")["rsi"])

    # ------------------------------------------------------------
    # دانلود کامل جدول برای بررسی دقیق‌تر / ارسال به من
    # ------------------------------------------------------------
    csv = df[["timestamp", "open", "high", "low", "close", "rsi"]].to_csv(
        index=False
    ).encode("utf-8-sig")
    st.download_button(
        "⬇️ دانلود کل جدول (CSV)", data=csv, file_name="rsi_debug.csv", mime="text/csv"
    )

    st.info(
        "این جداول بالا و نمودار RSI رو با تاریخ‌های دقیق فلش‌های روی عکس "
        "TradingView مقایسه کنید (یا اسکرین‌شات همین صفحه رو برام بفرستید)."
    )
else:
    st.info("پارامترها را تنظیم کرده و روی «دریافت و بررسی» کلیک کنید.")
