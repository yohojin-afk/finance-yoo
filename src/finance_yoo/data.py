"""Price/volume history + moving averages + RSI for a US ticker, via yfinance."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf


@dataclass
class NewsItem:
    title_en: str
    publisher: str
    link: str


@dataclass
class TickerData:
    ticker: str
    history: pd.DataFrame  # Open/High/Low/Close/Volume + sma20/sma60/sma120/rsi14/avg_volume20
    news: list[NewsItem] = field(default_factory=list)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def fetch_ticker_data(ticker: str) -> TickerData:
    t = yf.Ticker(ticker)
    hist = t.history(period="1y", auto_adjust=False)
    if hist.empty or len(hist) < 2:
        raise ValueError(f"No usable price history for {ticker}")

    hist["sma20"] = hist["Close"].rolling(20).mean()
    hist["sma60"] = hist["Close"].rolling(60).mean()
    hist["sma120"] = hist["Close"].rolling(120).mean()
    hist["rsi14"] = _rsi(hist["Close"])
    hist["avg_volume20"] = hist["Volume"].rolling(20).mean()

    news_items: list[NewsItem] = []
    try:
        raw_news = t.news or []
    except Exception:
        raw_news = []
    for item in raw_news[:4]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        provider = content.get("provider")
        publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher")
        canon = content.get("canonicalUrl")
        link = canon.get("url") if isinstance(canon, dict) else item.get("link")
        if title:
            news_items.append(NewsItem(title_en=title, publisher=publisher or "Unknown", link=link or ""))

    return TickerData(ticker=ticker, history=hist, news=news_items)
