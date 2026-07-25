"""Turn raw quote/news data into a short Korean strategy write-up via the Claude API."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from anthropic import Anthropic

from .data import Quote

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_SYSTEM_PROMPT = """\
당신은 개인 투자자를 위한 간결한 전략 브리핑 작성자입니다.
주어진 시세/컨센서스/뉴스 데이터만 근거로 사용하고, 데이터에 없는 애널리스트 의견이나
목표가, 기관명을 지어내지 마세요. 뉴스가 부족하면 "최신 뉴스 부족"이라고 솔직히 쓰세요.
반드시 아래 JSON 스키마로만 응답하세요 (설명 문장 없이 JSON만):
{
  "bull_case": "강세 근거 1~2문장, 가능하면 (출처)로 뉴스 발행사 표기",
  "bear_case": "약세/리스크 근거 1~2문장, 가능하면 (출처) 표기",
  "action": "현재가/목표가/매수선 위치를 반영한 구체적 대응 한두 문장",
  "checkpoints": ["앞으로 지켜볼 이벤트나 지표 1~2개"]
}
"""


@dataclass
class StockBriefing:
    bull_case: str
    bear_case: str
    action: str
    checkpoints: list[str]


def _fallback(quote: Quote) -> StockBriefing:
    return StockBriefing(
        bull_case="데이터 부족으로 자동 생성 실패",
        bear_case="데이터 부족으로 자동 생성 실패",
        action="수동으로 확인이 필요합니다.",
        checkpoints=[],
    )


def generate_stock_briefing(
    quote: Quote,
    *,
    quantity: float,
    avg_price: float,
    buy_line_multiplier: float,
    take_profit_growth_drop_pct: float,
    client: Anthropic | None = None,
) -> StockBriefing:
    client = client or Anthropic()

    news_lines = "\n".join(f"- {n.title} ({n.publisher})" for n in quote.news) or "(뉴스 없음)"
    buy_line = (
        f"{quote.target_mean * buy_line_multiplier:,.0f}" if quote.target_mean else "N/A"
    )
    payload = f"""
종목: {quote.name} ({quote.ticker})
현재가: {quote.price} {quote.currency or ''}
전일 대비: {f'{quote.change_pct:.2f}%' if quote.change_pct is not None else 'N/A'}
컨센서스 목표가: {quote.target_mean or 'N/A'} (출처: {quote.target_source or 'N/A'})
매수선(목표가 x {buy_line_multiplier}): {buy_line}
보유 수량: {quantity}, 평균 매입가: {avg_price}
익절 신호 기준: 성장률 {take_profit_growth_drop_pct}%p 둔화 또는 목표가 도달
최근 뉴스:
{news_lines}
"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        data = json.loads(text)
        return StockBriefing(
            bull_case=data.get("bull_case", ""),
            bear_case=data.get("bear_case", ""),
            action=data.get("action", ""),
            checkpoints=data.get("checkpoints", []),
        )
    except Exception:
        return _fallback(quote)
