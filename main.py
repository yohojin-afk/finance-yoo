#!/usr/bin/env python3
"""Entry point: build today's strategy briefing and email it.

Usage:
    python main.py            # fetch, generate, and send the email
    python main.py --dry-run  # fetch + generate, write HTML to out.html instead of sending
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent / "src"))

from finance_yoo.briefing import generate_stock_briefing
from finance_yoo.data import fetch_quote
from finance_yoo.mailer import send_html_email
from finance_yoo.render import HoldingRow, render_email

CONFIG_PATH = Path(__file__).parent / "config" / "portfolio.yaml"


def _build_rows(entries, status, buy_line_multiplier, take_profit_growth_drop_pct, client):
    rows = []
    for entry in entries:
        quote = fetch_quote(entry["ticker"], entry["name"])
        briefing = generate_stock_briefing(
            quote,
            quantity=entry.get("quantity", 0),
            avg_price=entry.get("avg_price", 0),
            buy_line_multiplier=buy_line_multiplier,
            take_profit_growth_drop_pct=take_profit_growth_drop_pct,
            client=client,
        )
        rows.append(
            HoldingRow(
                quote=quote,
                briefing=briefing,
                quantity=entry.get("quantity", 0),
                avg_price=entry.get("avg_price", 0),
                status=status,
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Write out.html instead of sending email")
    args = parser.parse_args()

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    buy_line_multiplier = config.get("buy_line_multiplier", 0.7)
    take_profit_growth_drop_pct = config.get("take_profit_growth_drop_pct", 20)

    client = Anthropic()

    domestic_rows = _build_rows(
        config["holdings"].get("domestic", []), "보유", buy_line_multiplier, take_profit_growth_drop_pct, client
    )
    overseas_rows = _build_rows(
        config["holdings"].get("overseas", []), "보유", buy_line_multiplier, take_profit_growth_drop_pct, client
    )
    watchlist_rows = _build_rows(
        config.get("watchlist", []), "매수 후보", buy_line_multiplier, take_profit_growth_drop_pct, client
    )

    html = render_email(
        investor_name=config.get("investor_name", "투자자"),
        strategy_tagline=config.get("strategy_tagline", ""),
        domestic_rows=domestic_rows + [r for r in watchlist_rows if r.quote.ticker.upper().endswith((".KS", ".KQ"))],
        overseas_rows=[r for r in overseas_rows + watchlist_rows if not r.quote.ticker.upper().endswith((".KS", ".KQ"))],
    )

    if args.dry_run:
        out_path = Path("out.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote {out_path.resolve()}")
        return

    today_str = dt.datetime.now().strftime("%Y-%m-%d")
    subject = f"[전략 브리핑] {today_str} {config.get('investor_name', '')}님 포트폴리오"
    send_html_email(subject, html)
    print("Sent briefing email.")


if __name__ == "__main__":
    main()
