# -*- coding: utf-8 -*-
"""
heikin_ashi.py
==============
تبدیل کندل معمولی (OHLC واقعی بازار) به کندل Heikin Ashi.

فرمول استاندارد (دقیقاً همانی که TradingView استفاده می‌کند):

    HA_Close[i] = (Open[i] + High[i] + Low[i] + Close[i]) / 4
    HA_Open[0]  = (Open[0] + Close[0]) / 2
    HA_Open[i]  = (HA_Open[i-1] + HA_Close[i-1]) / 2      برای i > 0
    HA_High[i]  = max(High[i], HA_Open[i], HA_Close[i])
    HA_Low[i]   = min(Low[i],  HA_Open[i], HA_Close[i])

این تبدیل با ۱۰ کندل واقعی که کاربر مستقیماً از Data Window تردینگ‌ویو
(روی چارت Heikin Ashi، BTC/USDT، 4H، BingX، UTC) استخراج کرده validate
شده و خروجی‌ها دقیقاً (تا ۲ رقم اعشار) یکسان بودند.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    df باید ستون‌های 'open', 'high', 'low', 'close' داشته باشد (به ترتیب
    زمانی صعودی: قدیمی -> جدید).

    خروجی: یک DataFrame جدید با همان ایندکس/timestamp ولی ستون‌های
    open/high/low/close جایگزین‌شده با مقادیر Heikin Ashi. سایر ستون‌ها
    (مثل timestamp, volume) بدون تغییر کپی می‌شوند.
    """
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    n = len(df)

    ha_open = np.empty(n)
    ha_close = np.empty(n)
    ha_high = np.empty(n)
    ha_low = np.empty(n)

    for i in range(n):
        ha_close[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0
        if i == 0:
            ha_open[i] = (o[i] + c[i]) / 2.0
        else:
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
        ha_high[i] = max(h[i], ha_open[i], ha_close[i])
        ha_low[i] = min(l[i], ha_open[i], ha_close[i])

    out = df.copy()
    out["open"] = ha_open
    out["high"] = ha_high
    out["low"] = ha_low
    out["close"] = ha_close
    return out
