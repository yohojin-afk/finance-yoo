"""Render the day's watchlist status + alerts into an HTML email body."""
from __future__ import annotations

import datetime as dt

from .data import TickerData
from .signals import TickerStatus
from .trades import Position
from .watchlist_manager_ui import WATCHLIST_MANAGER_HTML

_WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _dist(price: float, ma: float) -> str:
    if ma != ma:  # NaN
        return "N/A"
    return _pct((price / ma - 1) * 100)


def _position_html(ticker: str, position: Position | None, current_price: float) -> str:
    if position is None:
        return ""
    pl_pct = (current_price / position.avg_price - 1) * 100
    pl_color = "#1a9e5c" if pl_pct >= 0 else "#d64545"
    pl_sign = "+" if pl_pct >= 0 else ""
    return (
        '<div style="margin-top:8px;font-size:12px;color:#666;">'
        f"평단가 ${position.avg_price:,.2f} · 보유 {position.quantity:g}주 · "
        f'평가손익 <span style="color:{pl_color};font-weight:600;">{pl_sign}{pl_pct:.2f}%</span>'
        "</div>"
    )


def _trade_form_html(ticker: str) -> str:
    return f"""
      <div style="margin-top:10px;padding-top:10px;border-top:1px dashed #eee;display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
        <input type="date" id="trade-date-{ticker}" class="fy-trade-date" style="padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px;">
        <input type="number" id="trade-price-{ticker}" placeholder="가격" step="0.01" style="width:80px;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px;">
        <input type="number" id="trade-qty-{ticker}" placeholder="수량" step="any" style="width:70px;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px;">
        <button onclick="fyAddTrade('{ticker}')" style="padding:6px 12px;border:none;border-radius:6px;background:#7c3aed;color:#fff;font-size:12px;cursor:pointer;">매수 기록</button>
        <button onclick="fySellTrade('{ticker}')" style="padding:6px 12px;border:none;border-radius:6px;background:#d64545;color:#fff;font-size:12px;cursor:pointer;">매도 기록</button>
        <button onclick="fyResetPosition('{ticker}')" style="padding:6px 12px;border:1px solid #ddd;border-radius:6px;background:#fff;color:#888;font-size:12px;cursor:pointer;">보유 초기화</button>
      </div>
      <div id="trade-status-{ticker}" style="margin-top:4px;font-size:11px;color:#888;"></div>
    """


def _ticker_card(ticker: str, data: TickerData, status: TickerStatus, news_kr: list[str], position: Position | None) -> str:
    last, prev = data.history.iloc[-1], data.history.iloc[-2]
    change_pct = (last.Close / prev.Close - 1) * 100 if prev.Close else 0
    color = "#1a9e5c" if change_pct >= 0 else "#d64545"
    arrow = "▲" if change_pct >= 0 else "▼"
    vol_ratio = (last.Volume / last.avg_volume20) if last.avg_volume20 == last.avg_volume20 and last.avg_volume20 else None
    rsi_txt = f"{last.rsi14:.1f}" if last.rsi14 == last.rsi14 else "N/A"
    stop_loss_txt = f"${status.stop_loss_price:,.2f}" if status.stop_loss_price else "N/A"
    position_html = _position_html(ticker, position, last.Close)
    trade_form_html = _trade_form_html(ticker)

    alerts_html = "".join(
        f'<div style="margin-top:8px;background:#faf8ff;border-left:3px solid #7c3aed;'
        f'padding:10px 14px;border-radius:0 6px 6px 0;font-size:13px;">'
        f'<b>▶ {a.headline}</b><div style="margin-top:2px;color:#333;">{a.detail}</div></div>'
        for a in status.alerts
    ) or '<div style="margin-top:8px;font-size:13px;color:#888;">오늘은 새로 발동된 매수/손절 신호가 없습니다 (관망).</div>'

    news_html = "".join(f"<li>{n}</li>" for n in news_kr) or "<li>최근 뉴스 없음</li>"

    return f"""
    <div style="background:#fff;border:1px solid #eee;border-radius:12px;padding:20px 24px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div style="font-size:18px;font-weight:700;color:#111;">{ticker}</div>
        <div style="text-align:right;">
          <div style="font-size:18px;font-weight:700;color:#111;">${last.Close:,.2f}</div>
          <div style="font-size:13px;color:{color};font-weight:600;">{arrow} {abs(change_pct):.2f}%</div>
        </div>
      </div>
      <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;">
        <div><div style="font-size:11px;color:#999;">20일선 대비</div><div style="font-size:13px;font-weight:600;">{_dist(last.Close, last.sma20)}</div></div>
        <div><div style="font-size:11px;color:#999;">60일선 대비</div><div style="font-size:13px;font-weight:600;">{_dist(last.Close, last.sma60)}</div></div>
        <div><div style="font-size:11px;color:#999;">120일선 대비</div><div style="font-size:13px;font-weight:600;">{_dist(last.Close, last.sma120)}</div></div>
        <div><div style="font-size:11px;color:#999;">RSI14</div><div style="font-size:13px;font-weight:600;">{rsi_txt}</div></div>
        <div><div style="font-size:11px;color:#999;">거래량(20일 평균 대비)</div><div style="font-size:13px;font-weight:600;">{f'{vol_ratio:.2f}배' if vol_ratio else 'N/A'}</div></div>
      </div>
      {alerts_html}
      <div style="margin-top:10px;font-size:12px;color:#888;">오늘 기준 손절가(전일 종가 대비 -10%): {stop_loss_txt}</div>
      {position_html}
      <div style="margin-top:10px;font-size:12px;color:#666;"><b>뉴스</b><ul style="margin:4px 0 0 18px;padding:0;">{news_html}</ul></div>
      {trade_form_html}
    </div>
    """


def render_email(
    *,
    tickers_data: dict[str, TickerData],
    statuses: dict[str, TickerStatus],
    news_kr: dict[str, list[str]],
    positions: dict[str, Position | None] | None = None,
) -> str:
    positions = positions or {}
    now_kst = dt.datetime.utcnow() + dt.timedelta(hours=9)
    date_str = f"{now_kst.year}년 {now_kst.month}월 {now_kst.day}일 ({_WEEKDAYS_KR[now_kst.weekday()]}요일)"
    time_str = now_kst.strftime("%H:%M")
    cards_html = "".join(
        _ticker_card(ticker, tickers_data[ticker], statuses[ticker], news_kr.get(ticker, []), positions.get(ticker))
        for ticker in tickers_data
    )
    return f"""\
<div style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:680px;margin:0 auto;background:#f6f6f8;">
  <div style="background:linear-gradient(135deg,#7c3aed,#a855f7);padding:28px 28px 24px;color:#fff;border-radius:12px 12px 0 0;">
    <div style="font-size:12px;letter-spacing:2px;opacity:.85;">DAILY WATCHLIST BRIEFING</div>
    <div style="font-size:24px;font-weight:800;margin-top:6px;">오늘의 매수 신호 체크</div>
    <div style="font-size:13px;opacity:.9;margin-top:4px;">{date_str} · {time_str} 기준(KST)</div>
    <div style="display:flex;align-items:center;gap:8px;margin-top:12px;flex-wrap:wrap;">
      <button onclick="fyHardRefresh()" style="padding:6px 12px;border:none;border-radius:6px;background:rgba(255,255,255,.25);color:#fff;font-size:12px;cursor:pointer;">🔄 캐시 무시 새로고침</button>
      <button onclick="fyRebuildNow()" style="padding:6px 12px;border:none;border-radius:6px;background:rgba(255,255,255,.25);color:#fff;font-size:12px;cursor:pointer;">⟳ 지금 다시 빌드</button>
      <span id="refresh-status" style="font-size:11px;opacity:.85;"></span>
    </div>
  </div>
  <div style="padding:24px 16px;">
    {cards_html}
  </div>
</div>
"""


_PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
<meta http-equiv="Pragma" content="no-cache" />
<meta http-equiv="Expires" content="0" />
<title>오늘의 매수 신호 체크</title>
</head>
<body style="margin:0;background:#f6f6f8;">
__CONTENT__
__WATCHLIST_MANAGER__
</body>
</html>
"""


def render_page(content_html: str) -> str:
    """Wrap the rendered content + the watchlist-manager widget as a standalone page."""
    return (
        _PAGE_TEMPLATE
        .replace("__CONTENT__", content_html)
        .replace("__WATCHLIST_MANAGER__", WATCHLIST_MANAGER_HTML)
    )
