"""Evaluate the user's staged buy-the-dip rules + daily trailing stop-loss.

Rules (as specified by the user):
  1. Price touches the 20-day SMA           -> buy 10% of cash (fires every fresh touch)
  2. Price touches the 60-day SMA           -> buy 50% of remaining cash, split over 5 trading days
  3. Price touches the 120-day SMA          -> buy 50% of remaining cash, split over 5 trading days
  4. After #3 has happened at least once, whenever price is below the 120-day SMA
     and RSI(14) <= 30                      -> buy 100% of remaining cash, split over up to 40 trading days
  5. Stop-loss is always "-10% from the previous close", recomputed every day

Multi-day tranches (#2-#4) need to remember which day of the window we're on, so the
state is persisted to state/signals.json and committed back to the repo by the
GitHub Actions workflow after each run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .data import TickerData

STATE_PATH = Path(__file__).resolve().parent.parent.parent / "state" / "signals.json"


def _valid(x) -> bool:
    return x == x  # NaN-safe check (NaN != NaN)


def _touched(low: float, high: float, ma: float) -> bool:
    return _valid(ma) and low <= ma <= high


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _blank_ticker_state() -> dict:
    return {
        "stage2": {"active": False, "days_done": 0},
        "stage3": {"active": False, "days_done": 0},
        "stage4": {"active": False, "days_done": 0},
        "stage3_completed_before": False,
    }


@dataclass
class StageAlert:
    stage: str
    headline: str
    detail: str


@dataclass
class TickerStatus:
    alerts: list[StageAlert] = field(default_factory=list)
    stop_loss_price: float | None = None
    stop_loss_triggered: bool = False


def evaluate(ticker: str, data: TickerData, state: dict) -> TickerStatus:
    hist = data.history
    last, prev = hist.iloc[-1], hist.iloc[-2]
    ts = state.setdefault(ticker, _blank_ticker_state())
    last_date = str(last.name.date()) if hasattr(last.name, "date") else str(last.name)

    if ts.get("last_processed_date") == last_date:
        # Same trading day already advanced the tranche counters (e.g. the workflow
        # was re-run manually for testing) -- replay the cached result instead of
        # incrementing days_done a second time for one real trading day.
        cached = ts.get("last_status", {})
        status = TickerStatus(
            alerts=[StageAlert(**a) for a in cached.get("alerts", [])],
            stop_loss_price=cached.get("stop_loss_price"),
            stop_loss_triggered=cached.get("stop_loss_triggered", False),
        )
        return status

    status = TickerStatus()

    # Stage 1: fresh touch of the 20-day SMA -> 10% of cash. Stateless: fires every
    # time a *new* touch happens (today touching, yesterday not), so it can recur
    # across independent dips without spamming every day price lingers near the line.
    if _touched(last.Low, last.High, last.sma20) and not _touched(prev.Low, prev.High, prev.sma20):
        status.alerts.append(StageAlert(
            "stage1", "20일선 터치 — 가용 현금의 10% 매수",
            f"종가 ${last.Close:,.2f}, 20일선 ${last.sma20:,.2f} 부근 도달."
        ))

    # Stage 2: fresh touch of the 60-day SMA opens a 5-trading-day window.
    if not ts["stage2"]["active"] and _touched(last.Low, last.High, last.sma60) and not _touched(prev.Low, prev.High, prev.sma60):
        ts["stage2"] = {"active": True, "days_done": 0}
    if ts["stage2"]["active"]:
        ts["stage2"]["days_done"] += 1
        d = ts["stage2"]["days_done"]
        status.alerts.append(StageAlert(
            "stage2", f"60일선 매수 구간 {d}/5일차 — 남은 현금의 50% 분할매수",
            f"종가 ${last.Close:,.2f}, 60일선 ${last.sma60:,.2f}. 5거래일 분할매수 계획의 {d}일차."
        ))
        if d >= 5:
            ts["stage2"] = {"active": False, "days_done": 0}

    # Stage 3: fresh touch of the 120-day SMA opens a 5-trading-day window.
    if not ts["stage3"]["active"] and _touched(last.Low, last.High, last.sma120) and not _touched(prev.Low, prev.High, prev.sma120):
        ts["stage3"] = {"active": True, "days_done": 0}
    if ts["stage3"]["active"]:
        ts["stage3"]["days_done"] += 1
        d = ts["stage3"]["days_done"]
        status.alerts.append(StageAlert(
            "stage3", f"120일선 매수 구간 {d}/5일차 — 남은 현금의 50% 분할매수",
            f"종가 ${last.Close:,.2f}, 120일선 ${last.sma120:,.2f}. 5거래일 분할매수 계획의 {d}일차."
        ))
        if d >= 5:
            ts["stage3"] = {"active": False, "days_done": 0}
            ts["stage3_completed_before"] = True

    # Stage 4: only eligible once stage 3 has completed at least once. Fresh entry
    # into (below 120-SMA AND RSI<=30) opens an up-to-40-trading-day window.
    below_120 = _valid(last.sma120) and last.Close < last.sma120
    rsi_oversold = _valid(last.rsi14) and last.rsi14 <= 30
    prev_below_120 = _valid(prev.sma120) and prev.Close < prev.sma120
    prev_rsi_oversold = _valid(prev.rsi14) and prev.rsi14 <= 30

    if (
        ts["stage3_completed_before"]
        and not ts["stage4"]["active"]
        and below_120 and rsi_oversold
        and not (prev_below_120 and prev_rsi_oversold)
    ):
        ts["stage4"] = {"active": True, "days_done": 0}
    if ts["stage4"]["active"]:
        ts["stage4"]["days_done"] += 1
        d = ts["stage4"]["days_done"]
        status.alerts.append(StageAlert(
            "stage4", f"120선 아래 RSI 과매도 매수 구간 {d}/40일차 — 남은 현금 100% 분할매수",
            f"종가 ${last.Close:,.2f}, RSI14 {last.rsi14:.1f}. 최대 40거래일 분할매수 계획의 {d}일차."
        ))
        if d >= 40:
            ts["stage4"] = {"active": False, "days_done": 0}

    # Stop-loss: recomputed every day as 10% below the *previous* close.
    status.stop_loss_price = prev.Close * 0.9 if _valid(prev.Close) else None
    if _valid(prev.Close) and prev.Close and (last.Close / prev.Close - 1) <= -0.10:
        status.stop_loss_triggered = True
        status.alerts.insert(0, StageAlert(
            "stop_loss", "손절 신호 — 전일 대비 -10% 이상 하락",
            f"전일 종가 ${prev.Close:,.2f} → 오늘 종가 ${last.Close:,.2f} ({(last.Close/prev.Close-1)*100:.1f}%)."
        ))

    ts["last_processed_date"] = last_date
    ts["last_status"] = {
        "alerts": [vars(a) for a in status.alerts],
        "stop_loss_price": status.stop_loss_price,
        "stop_loss_triggered": status.stop_loss_triggered,
    }
    return status
