# -*- coding: utf-8 -*-
"""
data_feed.py
============
دریافت آنلاین دیتای OHLCV با ccxt.
طبق درخواست کاربر:
  - صرافی اصلی: BingX  (اسپات)
  - صرافی پشتیبان (fallback خودکار در صورت قطعی/خطای اتصال): KuCoin
    (هر دو، پوشش وسیعی از بازار کریپتو دارند و اندپوینت‌های آن‌ها به
    دلیل تحریم ایران برای Binance مسدود نمی‌شوند - Binance عمداً استفاده
    نشده است).
  - در صورت نیاز می‌توانید لیست FALLBACK_EXCHANGES را تغییر دهید.
"""

from __future__ import annotations
import pandas as pd
import ccxt
from typing import Optional, Tuple, List

PRIMARY_EXCHANGE = "bingx"
FALLBACK_EXCHANGES: List[str] = ["kucoin", "okx", "gateio"]


def _make_exchange(exchange_id: str):
    klass = getattr(ccxt, exchange_id)
    return klass({"enableRateLimit": True})


def fetch_ohlcv(
    symbol: str = "DASH/USDT",
    timeframe: str = "1d",
    limit: int = 500,
) -> Tuple[pd.DataFrame, str]:
    """
    تلاش برای دریافت دیتا از BingX؛ در صورت هر نوع خطا (قطعی شبکه،
    نماد پیدا نشد، ریت‌لیمیت و ...) به صورت خودکار سراغ صرافی(های)
    پشتیبان می‌رود.

    خروجی: (DataFrame با ستون‌های open/high/low/close/volume و ایندکس
    datetime صعودی از قدیم به جدید، نام صرافی که دیتا از آن گرفته شد)
    """
    tried = []
    for exchange_id in [PRIMARY_EXCHANGE] + FALLBACK_EXCHANGES:
        try:
            ex = _make_exchange(exchange_id)
            ex.load_markets()
            if symbol not in ex.symbols:
                # برخی صرافی‌ها فرمت نماد را کمی متفاوت می‌خواهند
                alt = symbol.replace("/", "")
                candidates = [s for s in ex.symbols if s.replace("/", "") == alt]
                if not candidates:
                    raise ValueError(f"نماد {symbol} در {exchange_id} یافت نشد")
                symbol_use = candidates[0]
            else:
                symbol_use = symbol

            raw = ex.fetch_ohlcv(symbol_use, timeframe=timeframe, limit=limit)
            if not raw or len(raw) < 50:
                raise ValueError("داده‌ی کافی برگردانده نشد")

            df = pd.DataFrame(
                raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df, exchange_id
        except Exception as e:  # noqa: BLE001
            tried.append(f"{exchange_id}: {e}")
            continue

    raise ConnectionError(
        "دریافت داده از هیچ‌کدام از صرافی‌ها ممکن نشد.\n" + "\n".join(tried)
    )
