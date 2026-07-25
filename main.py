#!/usr/bin/env python3
"""Entry point: check the watchlist against the buy/stop-loss rules and build the dashboard page.

Usage:
    python main.py            # fetch, evaluate, update state, write public/index.html
    python main.py --dry-run  # same, but write out.html locally without touching public/ or state
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent / "src"))

from finance_yoo.data import fetch_ticker_data
from finance_yoo.render import render_email, render_page
from finance_yoo.signals import evaluate, load_state, save_state
from finance_yoo.translate import translate_headlines

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.txt"
PUBLIC_DIR = Path(__file__).parent / "public"


def _load_watchlist() -> list[str]:
    tickers = []
    for line in WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(line.upper())
    return tickers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Write out.html instead of public/index.html")
    args = parser.parse_args()

    tickers = _load_watchlist()
    if not tickers:
        print("config/watchlist.txt에 티커가 없습니다.")
        return

    try:
        client = Anthropic()
    except Exception:
        print("ANTHROPIC_API_KEY가 없어 뉴스는 영문 원문으로 표시합니다.")
        client = None
    state = load_state()

    tickers_data, statuses, news_kr = {}, {}, {}
    for ticker in tickers:
        try:
            data = fetch_ticker_data(ticker)
        except Exception as e:
            print(f"{ticker} 데이터 조회 실패, 건너뜁니다: {e}")
            continue
        tickers_data[ticker] = data
        statuses[ticker] = evaluate(ticker, data, state)
        news_kr[ticker] = (
            translate_headlines([n.title_en for n in data.news], client=client)
            if client
            else [n.title_en for n in data.news]
        )

    if not tickers_data:
        print("가져올 수 있는 종목 데이터가 없어 종료합니다.")
        return

    page_html = render_page(render_email(tickers_data=tickers_data, statuses=statuses, news_kr=news_kr))

    if args.dry_run:
        out_path = Path("out.html")
        out_path.write_text(page_html, encoding="utf-8")
        print(f"Wrote {out_path.resolve()} (state not saved in --dry-run)")
        return

    save_state(state)
    PUBLIC_DIR.mkdir(exist_ok=True)
    (PUBLIC_DIR / "index.html").write_text(page_html, encoding="utf-8")
    print(f"Wrote {PUBLIC_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
