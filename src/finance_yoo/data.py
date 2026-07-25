"""Price / analyst-consensus / news data collection for one ticker."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests
import yfinance as yf
from bs4 import BeautifulSoup

_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; finance-yoo-briefing/1.0)"}


@dataclass
class NewsItem:
    title: str
    publisher: str
    link: str


@dataclass
class Quote:
    ticker: str
    name: str
    price: float | None
    prev_close: float | None
    change_pct: float | None
    currency: str | None
    target_low: float | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_source: str | None = None  # e.g. "Naver 컨센서스" / "Yahoo Finance 애널리스트"
    news: list[NewsItem] = field(default_factory=list)


def _is_kr_ticker(ticker: str) -> bool:
    return ticker.upper().endswith((".KS", ".KQ"))


def _kr_code(ticker: str) -> str:
    return ticker.split(".")[0]


def fetch_kr_consensus_target(code: str) -> tuple[float | None, float | None, float | None]:
    """Best-effort scrape of Naver Finance's analyst consensus target price for a KRX code.

    Naver's markup changes occasionally; this returns (low, mean, high) all None on
    any failure so the rest of the pipeline degrades gracefully instead of crashing.
    """
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        resp = requests.get(url, headers=_NAVER_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        target_el = soup.select_one("#_representative_market_1, .tab_con1 table.gray tbody")
        mean_price = None
        table = soup.find("table", {"summary": re.compile("목표주가")})
        if table is None:
            for t in soup.find_all("table"):
                if "목표주가" in t.get_text():
                    table = t
                    break
        if table is not None:
            m = re.search(r"목표주가[^\d]*([\d,]+)", table.get_text())
            if m:
                mean_price = float(m.group(1).replace(",", ""))
        if mean_price is None:
            return None, None, None
        return None, mean_price, None
    except Exception:
        return None, None, None


def fetch_quote(ticker: str, display_name: str) -> Quote:
    t = yf.Ticker(ticker)
    fast = {}
    try:
        fast = t.fast_info or {}
    except Exception:
        fast = {}

    price = fast.get("last_price")
    prev_close = fast.get("previous_close")
    currency = fast.get("currency")

    info = {}
    if price is None or prev_close is None:
        try:
            info = t.info or {}
        except Exception:
            info = {}
        price = price or info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = prev_close or info.get("previousClose")
        currency = currency or info.get("currency")

    change_pct = None
    if price is not None and prev_close:
        change_pct = (price - prev_close) / prev_close * 100

    quote = Quote(
        ticker=ticker,
        name=display_name,
        price=price,
        prev_close=prev_close,
        change_pct=change_pct,
        currency=currency,
    )

    if _is_kr_ticker(ticker):
        low, mean, high = fetch_kr_consensus_target(_kr_code(ticker))
        if mean is not None:
            quote.target_low, quote.target_mean, quote.target_high = low, mean, high
            quote.target_source = "Naver 컨센서스(스크레이핑, 참고용)"
    else:
        try:
            info = info or t.info or {}
            mean = info.get("targetMeanPrice")
            low = info.get("targetLowPrice")
            high = info.get("targetHighPrice")
            if mean:
                quote.target_low, quote.target_mean, quote.target_high = low, mean, high
                quote.target_source = "Yahoo Finance 애널리스트 컨센서스"
        except Exception:
            pass

    try:
        raw_news = t.news or []
    except Exception:
        raw_news = []
    for item in raw_news[:5]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        publisher = (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher")
        link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link")
        if title:
            quote.news.append(NewsItem(title=title, publisher=publisher or "출처 미상", link=link or ""))

    return quote
