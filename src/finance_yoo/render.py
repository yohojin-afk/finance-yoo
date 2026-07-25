"""Render the day's data + generated briefings into a single HTML email body."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .briefing import StockBriefing
from .data import Quote

_WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass
class HoldingRow:
    quote: Quote
    briefing: StockBriefing
    quantity: float
    avg_price: float
    status: str  # "보유" | "매수 후보"


def _fmt_money(v: float | None, currency: str | None = None) -> str:
    if v is None:
        return "N/A"
    suffix = "원" if currency in (None, "KRW") else f" {currency}"
    return f"{v:,.0f}{suffix}"


def _change_color(change_pct: float | None, is_kr: bool) -> str:
    if change_pct is None:
        return "#666"
    up_color, down_color = ("#d64545", "#2f6fed") if is_kr else ("#1a9e5c", "#d64545")
    return up_color if change_pct >= 0 else down_color


def _stock_card(row: HoldingRow) -> str:
    q = row.quote
    is_kr = q.ticker.upper().endswith((".KS", ".KQ"))
    arrow = "▲" if (q.change_pct or 0) >= 0 else "▼"
    color = _change_color(q.change_pct, is_kr)
    change_txt = f"{arrow} {abs(q.change_pct):.2f}%" if q.change_pct is not None else "N/A"

    target_txt = _fmt_money(q.target_mean, q.currency) if q.target_mean else "컨센서스 없음"
    buy_line_txt = (
        _fmt_money(q.target_mean * 0.7, q.currency) if q.target_mean else "N/A"
    )
    valuation = _fmt_money(row.quantity * q.price, q.currency) if row.quantity and q.price else None

    checkpoints_html = "".join(f"<li>{c}</li>" for c in row.briefing.checkpoints) or "<li>특이사항 없음</li>"

    return f"""
    <div style="background:#fff;border:1px solid #eee;border-radius:12px;padding:20px 24px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <div style="font-size:18px;font-weight:700;color:#111;">{q.name}</div>
          <div style="font-size:13px;color:#888;margin-top:2px;">{q.ticker} · {row.quantity:g}주</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:18px;font-weight:700;color:#111;">{_fmt_money(q.price, q.currency)}</div>
          <div style="font-size:13px;color:{color};font-weight:600;">{change_txt}</div>
          {f'<div style="font-size:12px;color:#999;">평가액 {valuation}</div>' if valuation else ''}
        </div>
      </div>
      <div style="display:flex;gap:24px;margin-top:14px;">
        <div>
          <div style="font-size:11px;color:#999;">목표가(컨센서스)</div>
          <div style="font-size:14px;font-weight:600;color:#333;">{target_txt}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#999;">×0.7 매수선</div>
          <div style="font-size:14px;font-weight:600;color:#333;">{buy_line_txt}</div>
        </div>
        <div style="margin-left:auto;">
          <span style="background:#f3e8ff;color:#7c3aed;font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;">{row.status}</span>
        </div>
      </div>
      <div style="margin-top:14px;font-size:13px;line-height:1.6;color:#333;">
        <div><b style="color:#d64545;">[강세론]</b> {row.briefing.bull_case}</div>
        <div style="margin-top:4px;"><b style="color:#2f6fed;">[약세론]</b> {row.briefing.bear_case}</div>
      </div>
      <div style="margin-top:12px;background:#faf8ff;border-left:3px solid #7c3aed;padding:10px 14px;font-size:13px;color:#222;border-radius:0 6px 6px 0;">
        <b>▶ 대응</b> {row.briefing.action}
      </div>
      <div style="margin-top:10px;font-size:12px;color:#888;">
        <b>체크</b> <ul style="margin:4px 0 0 18px;padding:0;">{checkpoints_html}</ul>
      </div>
    </div>
    """


def render_email(
    *,
    investor_name: str,
    strategy_tagline: str,
    domestic_rows: list[HoldingRow],
    overseas_rows: list[HoldingRow],
) -> str:
    today = dt.datetime.now()
    date_str = f"{today.year}년 {today.month}월 {today.day}일 ({_WEEKDAYS_KR[today.weekday()]}요일)"

    domestic_total = sum((r.quantity * r.quote.price) for r in domestic_rows if r.quantity and r.quote.price)
    overseas_total = sum((r.quantity * r.quote.price) for r in overseas_rows if r.quantity and r.quote.price)

    cards_html = "".join(_stock_card(r) for r in (domestic_rows + overseas_rows))

    return f"""\
<div style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:680px;margin:0 auto;background:#f6f6f8;">
  <div style="background:linear-gradient(135deg,#7c3aed,#a855f7);padding:28px 28px 24px;color:#fff;border-radius:12px 12px 0 0;">
    <div style="font-size:12px;letter-spacing:2px;opacity:.85;">DAILY STRATEGY BRIEFING</div>
    <div style="font-size:24px;font-weight:800;margin-top:6px;">{investor_name}님 전략 브리핑</div>
    <div style="font-size:13px;opacity:.9;margin-top:4px;">{date_str}</div>
    <div style="font-size:12px;opacity:.85;margin-top:10px;">{strategy_tagline}</div>
    <div style="display:flex;gap:12px;margin-top:16px;">
      <div style="background:rgba(255,255,255,.15);border-radius:10px;padding:10px 16px;">
        <div style="font-size:11px;opacity:.85;">국내 평가액</div>
        <div style="font-size:16px;font-weight:700;">{_fmt_money(domestic_total) if domestic_total else '—'}</div>
      </div>
      <div style="background:rgba(255,255,255,.15);border-radius:10px;padding:10px 16px;">
        <div style="font-size:11px;opacity:.85;">해외 평가액</div>
        <div style="font-size:16px;font-weight:700;">{_fmt_money(overseas_total, 'USD') if overseas_total else '—'}</div>
      </div>
    </div>
  </div>
  <div style="padding:24px 16px;">
    <div style="font-size:14px;font-weight:700;color:#333;margin:4px 4px 12px;">📦 보유주 — 대응 전략</div>
    {cards_html}
  </div>
</div>
"""
