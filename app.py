# -*- coding: utf-8 -*-
"""
app.py
======
اپلیکیشن Streamlit: تبدیل دقیق اندیکاتور Pine Script "RSI Tops and Bottoms"
(LonesomeTheBlue) به پایتون + دریافت آنلاین دیتا (BingX با فال‌بک خودکار)
+ گزارش آخرین همگرایی (bottom/سبز) و آخرین واگرایی (top/قرمز).

اجرا در GitHub + Streamlit Cloud:
    1) این پوشه (app.py, rsi_div_core.py, data_feed.py, requirements.txt)
       را در یک ریپازیتوری گیت‌هاب قرار دهید.
    2) در share.streamlit.io ریپازیتوری را وصل کرده و app.py را به‌عنوان
       فایل اصلی انتخاب کنید.
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_feed import fetch_ohlcv
from rsi_div_core import detect_rsi_tops_bottoms, wilder_rsi, DivEvent

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
    symbol = st.text_input("نماد (Symbol)", value="DASH/USDT")
    timeframe = st.selectbox(
        "تایم‌فریم",
        ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        index=6,  # پیش‌فرض 1d طبق درخواست
    )
    limit = st.slider("تعداد کندل دریافتی", min_value=200, max_value=1000, value=500, step=50)

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

    rsi = wilder_rsi(df["close"].to_numpy(dtype=float), int(rsi_len))
    df["rsi"] = rsi

    events = detect_rsi_tops_bottoms(
        df,
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
    # چارت (قیمت + RSI) با نمایش فلش‌های آخرین سیگنال هر نوع
    # ------------------------------------------------------------
    st.subheader("نمودار")
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4],
        vertical_spacing=0.03,
        subplot_titles=(symbol, "RSI Tops & Bottoms"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Price",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["rsi"], line=dict(color="#8E1599"), name="RSI"),
        row=2, col=1,
    )
    fig.add_hline(y=float(ob), line_dash="dot", line_color="gray", row=2, col=1)
    fig.add_hline(y=float(os_level), line_dash="dot", line_color="gray", row=2, col=1)

    def add_arrow(ev: DivEvent, color: str):
        fig.add_trace(
            go.Scatter(
                x=[df["timestamp"].iloc[ev.start_bar], df["timestamp"].iloc[ev.end_bar]],
                y=[ev.start_rsi, ev.end_rsi],
                mode="lines+markers",
                line=dict(color=color, width=3),
                marker=dict(size=8),
                showlegend=False,
            ),
            row=2, col=1,
        )

    if bottoms:
        add_arrow(bottoms[-1], "lime")
    if tops:
        add_arrow(tops[-1], "red")

    fig.update_layout(height=750, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("مشاهده‌ی داده خام (تعداد کل رویدادهای تاریخی، صرفاً جهت اعتبارسنجی کد)"):
        st.write(f"تعداد کل همگرایی‌های یافت‌شده در کل تاریخچه: {len(bottoms)}")
        st.write(f"تعداد کل واگرایی‌های یافت‌شده در کل تاریخچه: {len(tops)}")
        st.dataframe(df.tail(50))
else:
    st.info("پارامترها را تنظیم کرده و روی «دریافت داده و محاسبه» کلیک کنید.")
