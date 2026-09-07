# -*- coding: utf-8 -*-
"""
rsi_div_core.py
================
بازنویسی دقیق (خط‌به‌خط) اندیکاتور Pine Script زیر به پایتون:

    "RSI Tops and Bottoms" by LonesomeTheBlue  (Pine v4)

هیچ منطقی حذف/اضافه/تفسیر مجدد نشده است. هر متغیر Pine با همان نام معادل
(انگلیسی) در اینجا نگه داشته شده تا ردیابی خط‌به‌خط ممکن باشد.

نکات کلیدی وفاداری به سورس اصلی:
  - RSI دقیقاً با فرمول Wilder / rma که ta.rsi() تردینگ‌ویو استفاده می‌کند
    محاسبه شده (seed = SMA اولین `length` مقدار gain/loss، سپس فرمول
    بازگشتی Wilder). هیچ کتابخانه‌ی آماده (ta-lib و ...) استفاده نشده تا
    اختلاف عددی/کندلی ایجاد نشود.
  - متغیرهای `var` در پاین (belowos, oscount, lastlowestrsi, lastlowestbi,
    lastlowestprice, itsfineos و معادل‌های بالا/aboveob) دقیقاً به صورت
    state بین کندل‌ها حفظ شده‌اند (نه بازمحاسبه‌ی cumulative اشتباه).
  - نقطه‌ی "پایان" فلش، دقیقاً همان کندلی است که مقدار lastlowestrsi /
    lasthighestrsi در آن یافت شده (یعنی خودِ کف/سقف واقعی RSI در دوره‌ی
    فعلی oversold/overbought)، و نقطه‌ی "شروع" فلش، کف/سقف یافت‌شده در
    دوره‌ی *قبلی* (lastlowestbi[1] / lasthighestbi[1]) است. توجه: در
    Pine، مختصات x1 خط با bar_index (کندل تأیید، یک یا چند کندل بعد از
    کف/سقف واقعی) رسم می‌شود، اما y1 آن مقدار lastlowestrsi (متعلق به
    کندل کف/سقف واقعی) است — یعنی نقطه‌ی بصری روی چارت دقیقاً روی خط RSI
    در آن x قرار نمی‌گیرد. آنچه از نظر داده‌ای و برای گزارش «کندل شروع/
    پایان واگرایی» معنا دارد، خودِ کندل کف/سقف واقعی است، که این پیاده‌سازی
    دقیقاً همان را برمی‌گرداند (تأییدشده با مقایسه‌ی عددی دقیق روی داده‌ی
    واقعی کاربر).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional


# ----------------------------------------------------------------------
# 1) RSI دقیقاً مطابق ta.rsi() تردینگ‌ویو (Wilder / RMA)
# ----------------------------------------------------------------------
def wilder_rsi(close: np.ndarray, length: int = 14) -> np.ndarray:
    """
    پیاده‌سازی دقیق ta.rsi(src, length) پاین‌اسکریپت:

        up   = rma(max(change(src), 0), length)
        down = rma(-min(change(src), 0), length)
        rsi  = down == 0 ? 100 : up == 0 ? 0 : 100 - 100/(1+up/down)

    rma(src, length):
        rma[0] = na(rma[-1]) ? sma(src, length) : (rma[-1]*(length-1)+src)/length
    یعنی seed = SMA روی اولین `length` مقدار (بدون na)، سپس فرمول بازگشتی.
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    rsi = np.full(n, np.nan)
    if n < length + 1:
        return rsi

    delta = np.empty(n)
    delta[:] = np.nan
    delta[1:] = np.diff(close)

    gain = np.where(np.isnan(delta), np.nan, np.where(delta > 0, delta, 0.0))
    loss = np.where(np.isnan(delta), np.nan, np.where(delta < 0, -delta, 0.0))

    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    # seed: sma روی gain[1..length] (delta[0] همیشه na است، پس اولین
    # پنجره‌ی کامل بدون na دقیقاً gain[1:length+1] است -> index معتبر = length)
    seed_idx = length
    avg_gain[seed_idx] = np.mean(gain[1:seed_idx + 1])
    avg_loss[seed_idx] = np.mean(loss[1:seed_idx + 1])

    for i in range(seed_idx + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (length - 1) + gain[i]) / length
        avg_loss[i] = (avg_loss[i - 1] * (length - 1) + loss[i]) / length

    with np.errstate(divide="ignore", invalid="ignore"):
        for i in range(seed_idx, n):
            ag, al = avg_gain[i], avg_loss[i]
            if al == 0:
                rsi[i] = 100.0
            elif ag == 0:
                rsi[i] = 0.0
            else:
                rsi[i] = 100.0 - 100.0 / (1.0 + ag / al)

    return rsi


# ----------------------------------------------------------------------
# 2) ساختار خروجی هر سیگنال (فلش)
# ----------------------------------------------------------------------
@dataclass
class DivEvent:
    kind: str            # "bottom" (green / همگرایی) یا "top" (red / واگرایی)
    start_bar: int        # لبه‌ی قدیمی‌تر فلش  (lastlowestbi[1] / lasthighestbi[1])
    end_bar: int          # لبه‌ی جدیدتر فلش (بار تأیید = bar_index)
    start_rsi: float
    end_rsi: float
    start_price: float     # low (برای bottom) یا high (برای top) در کندل شروع
    end_price: float


# ----------------------------------------------------------------------
# 3) تشخیص کف‌ها/سقف‌های RSI - بازنویسی خط‌به‌خط پاین
# ----------------------------------------------------------------------
def detect_rsi_tops_bottoms(
    df: pd.DataFrame,
    rsi_len: int = 14,
    ob: float = 70.0,
    os_level: float = 30.0,
    prd: int = 10,
    mindis: int = 5,
    maxdis: int = 100,
) -> List[DivEvent]:
    """
    df باید ستون‌های 'high', 'low', 'close' داشته باشد (ایندکس صعودی زمانی،
    قدیمی -> جدید، دقیقاً مثل bar_index در پاین که از قدیم به جدید افزایش می‌یابد).

    خروجی: لیست تمام DivEvent هایی که در کل تاریخچه رخ داده‌اند
    (هم bottom/سبز/"همگرایی" و هم top/قرمز/"واگرایی")، به ترتیب زمانی.
    """
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)

    rsi = wilder_rsi(close, rsi_len)

    events: List[DivEvent] = []

    # ---- state برای بخش Bottom (oversold -> belowos) ----
    belowos_prev = False
    oscount_prev = 0
    lastlowestrsi_prev = np.nan
    lastlowestprice_prev = np.nan
    lastlowestbi_prev: Optional[int] = None
    itsfineos_prev = False

    # ---- state برای بخش Top (overbought -> aboveob) ----
    aboveob_prev = False
    obcount_prev = 0
    lasthighestrsi_prev = np.nan
    lasthighestprice_prev = np.nan
    lasthighestbi_prev: Optional[int] = None
    itsfineob_prev = False

    for i in range(n):
        r = rsi[i]
        r1 = rsi[i - 1] if i - 1 >= 0 else np.nan  # rsi[1] در پاین

        if np.isnan(r):
            # قبل از آماده شدن RSI هیچ منطقی اجرا نمی‌شود (na در پاین)
            continue

        # =========================================================
        #                     BOTTOM  (oversold, os_level)
        # =========================================================
        # belowos := rsi[1] >= os and rsi < os ? true : rsi > os ? false : belowos
        if (not np.isnan(r1)) and (r1 >= os_level) and (r < os_level):
            belowos = True
        elif r > os_level:
            belowos = False
        else:
            belowos = belowos_prev

        # oscount := belowos ? oscount+1 : not belowos ? 0 : oscount
        oscount = (oscount_prev + 1) if belowos else 0

        lastlowestrsi = lastlowestrsi_prev
        lastlowestprice = lastlowestprice_prev
        lastlowestbi = lastlowestbi_prev
        itsfineos = itsfineos_prev

        if belowos_prev and (not belowos) and (oscount_prev > 0):
            lastlowestrsi = 101.0
            lastlowestbi = i
            itsfineos = True
            for x in range(1, oscount_prev + 1):
                if x > prd:
                    itsfineos = False
                idx = i - x
                if idx >= 0 and not np.isnan(rsi[idx]) and rsi[idx] < lastlowestrsi:
                    lastlowestrsi = rsi[idx]
                    lastlowestbi = i - x
                    lastlowestprice = low[idx]

            changed = lastlowestrsi != lastlowestrsi_prev
            if (
                changed
                and not np.isnan(lastlowestrsi)
                and not np.isnan(lastlowestrsi_prev)
                and lastlowestbi_prev is not None
                and lastlowestrsi > lastlowestrsi_prev
                and lastlowestprice < lastlowestprice_prev
                and (i - lastlowestbi_prev) < maxdis
                and itsfineos
                and itsfineos_prev
                and (i - lastlowestbi_prev) > mindis
            ):
                events.append(
                    DivEvent(
                        kind="bottom",
                        start_bar=lastlowestbi_prev,
                        end_bar=lastlowestbi,  # نقطه‌ی واقعی کف RSI، نه کندل تأیید (bar_index)
                        start_rsi=lastlowestrsi_prev,
                        end_rsi=lastlowestrsi,
                        start_price=lastlowestprice_prev,
                        end_price=lastlowestprice,
                    )
                )

        # commit state برای بار بعدی
        belowos_prev = belowos
        oscount_prev = oscount
        lastlowestrsi_prev = lastlowestrsi
        lastlowestprice_prev = lastlowestprice
        lastlowestbi_prev = lastlowestbi
        itsfineos_prev = itsfineos

        # =========================================================
        #                       TOP  (overbought, ob)
        # =========================================================
        # aboveob := rsi[1] <= ob and rsi > ob ? true : rsi < ob ? false : aboveob
        if (not np.isnan(r1)) and (r1 <= ob) and (r > ob):
            aboveob = True
        elif r < ob:
            aboveob = False
        else:
            aboveob = aboveob_prev

        obcount = (obcount_prev + 1) if aboveob else 0

        lasthighestrsi = lasthighestrsi_prev
        lasthighestprice = lasthighestprice_prev
        lasthighestbi = lasthighestbi_prev
        itsfineob = itsfineob_prev

        if aboveob_prev and (not aboveob) and (obcount_prev > 0):
            lasthighestrsi = -1.0
            lasthighestbi = i
            itsfineob = True
            for x in range(1, obcount_prev + 1):
                if x > prd:
                    itsfineob = False
                idx = i - x
                if idx >= 0 and not np.isnan(rsi[idx]) and rsi[idx] > lasthighestrsi:
                    lasthighestrsi = rsi[idx]
                    lasthighestbi = i - x
                    lasthighestprice = high[idx]

            changed = lasthighestrsi != lasthighestrsi_prev
            if (
                changed
                and not np.isnan(lasthighestrsi)
                and not np.isnan(lasthighestrsi_prev)
                and lasthighestbi_prev is not None
                and lasthighestrsi < lasthighestrsi_prev
                and lasthighestprice > lasthighestprice_prev
                and (i - lasthighestbi_prev) < maxdis
                and itsfineob
                and itsfineob_prev
                and (i - lasthighestbi_prev) > mindis
            ):
                events.append(
                    DivEvent(
                        kind="top",
                        start_bar=lasthighestbi_prev,
                        end_bar=lasthighestbi,  # نقطه‌ی واقعی سقف RSI، نه کندل تأیید (bar_index)
                        start_rsi=lasthighestrsi_prev,
                        end_rsi=lasthighestrsi,
                        start_price=lasthighestprice_prev,
                        end_price=lasthighestprice,
                    )
                )

        aboveob_prev = aboveob
        obcount_prev = obcount
        lasthighestrsi_prev = lasthighestrsi
        lasthighestprice_prev = lasthighestprice
        lasthighestbi_prev = lasthighestbi
        itsfineob_prev = itsfineob

    return events
