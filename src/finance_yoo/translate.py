"""Translate English headlines to Korean via Claude — translation only, no commentary."""
from __future__ import annotations

import json
import os

from anthropic import Anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_SYSTEM_PROMPT = (
    "입력된 영문 뉴스 제목들을 자연스러운 한국어로 번역만 하세요. "
    "설명, 의견, 분석을 추가하지 마세요. 입력과 동일한 개수/순서의 JSON 문자열 배열로만 응답하세요."
)


def translate_headlines(titles: list[str], client: Anthropic | None = None) -> list[str]:
    if not titles:
        return []
    client = client or Anthropic()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(titles, ensure_ascii=False)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        translated = json.loads(text)
        if isinstance(translated, list) and len(translated) == len(titles):
            return translated
    except Exception:
        pass
    return titles
