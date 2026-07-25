#!/usr/bin/env python3
"""Entry point: check the watchlist against the buy/stop-loss rules and email the result.

Usage:
    python main.py            # fetch, evaluate, update state, and send the email
    python main.py --dry-run  # same, but write out.html instead of sending / doesn't require mail secrets
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent / "src"))

from finance_yoo.data import fetch_ticker_data
from finance_yoo.mailer import send_html_email
from finance_yoo.render import render_email
from finance_yoo.signals import evaluate, load_state, save_state
from finance_yoo.translate import translate_headlines

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.txt"


def _load_watchlist() -> list[str]:
    tickers = []
    for line in WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(line.upper())
    return tickers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Write out.html instead of sending email")
    args = parser.parse_args()

    tickers = _load_watchlist()
    if not tickers:
        print("config/watchlist.txt에 티커가 없습니다.")
        return

    client = Anthropic()
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
        news_kr[ticker] = translate_headlines([n.title_en for n in data.news], client=client)

    save_state(state)

    if not tickers_data:
        print("가져올 수 있는 종목 데이터가 없어 종료합니다.")
        return

    html = render_email(tickers_data=tickers_data, statuses=statuses, news_kr=news_kr)

    if args.dry_run:
        out_path = Path("out.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote {out_path.resolve()}")
        return

    today_str = dt.datetime.now().strftime("%Y-%m-%d")
    send_html_email(f"[매수 신호 체크] {today_str} 관심종목 브리핑", html)
    print("Sent briefing email.")


if __name__ == "__main__":
    main()
