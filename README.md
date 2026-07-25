# finance-yoo — 매일 아침 관심종목 매수 신호 브리핑

미국 주식 관심종목의 가격/거래량을 매일 분석해서, 아래 규칙에 따른 매수 신호나
현재 진행 중인 분할매수 구간을 이메일로 보내는 GitHub Actions 자동화입니다.

## 매수 규칙 (사용자 정의)

1. 20일 이동평균선 터치 → 가용 현금의 10% 매수
2. 60일 이동평균선 터치 → 남은 현금의 50%를 5거래일에 걸쳐 분할매수
3. 120일 이동평균선 터치 → 남은 현금의 50%를 5거래일에 걸쳐 분할매수
4. (3번이 최소 1회 발생한 이후) 120일선 아래 + RSI(14) ≤ 30 → 남은 현금 100%를
   최대 40거래일에 걸쳐 분할매수
5. 손절가는 항상 "전일 종가 대비 -10%"로 매일 새로 계산

"터치"는 그날의 고가~저가 범위 안에 해당 이동평균선이 들어오는 경우로 판단합니다.
1번은 매번 새로 닿을 때마다(과거에 이미 닿았어도) 다시 알림이 오고, 2~4번은 며칠에
걸친 분할매수 구간이라 "오늘이 몇 일차인지"를 `state/signals.json`에 저장해뒀다가
다음 실행 때 이어서 판단합니다 (그래서 GitHub Actions가 실행될 때마다 이 파일을
자동으로 커밋합니다 — 직접 수정하지 마세요).

## 관심종목 관리

`config/watchlist.txt`에 티커를 한 줄에 하나씩 적으면 됩니다. 그때그때 바뀌면
GitHub에서 이 파일만 수정(웹/모바일에서도 가능)하면 다음 날 아침부터 바로 반영돼요.

```
# 예시
AAPL
NVDA
```

## 설정이 필요한 것

GitHub 저장소 Settings → Secrets and variables → Actions 에 아래 4개를 등록하세요.

| Secret 이름 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | 영문 뉴스 제목 번역에만 사용 (분석/코멘트 생성 아님). [console.anthropic.com](https://console.anthropic.com)에서 발급, 비용은 매우 적음 |
| `MAIL_FROM_ADDRESS` | 발신용 Gmail 주소 |
| `MAIL_FROM_APP_PASSWORD` | 위 Gmail 계정의 **앱 비밀번호** (일반 로그인 비밀번호 아님 — Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호) |
| `MAIL_TO` | 받는 사람 이메일 |

Gmail이 아닌 다른 SMTP를 쓰려면 `SMTP_HOST`/`SMTP_PORT` 시크릿을 추가하면 됩니다
(기본값은 Gmail 465 포트).

## 로컬 테스트

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python main.py --dry-run   # out.html 생성, 이메일 발송 안 함, state/signals.json은 갱신됨
```

메일 발송까지 테스트하려면 `MAIL_FROM_ADDRESS`/`MAIL_FROM_APP_PASSWORD`/`MAIL_TO`도
export한 뒤 `--dry-run` 없이 실행하세요.

GitHub Actions에서 스케줄을 기다리지 않고 바로 테스트하려면 저장소의
**Actions → Daily Watchlist Briefing → Run workflow**로 수동 실행할 수 있습니다.
이때 `dry_run` 체크박스를 켜면 메일을 보내지 않고 `out.html`을 아티팩트로 만들어주므로,
`MAIL_FROM_ADDRESS`/`MAIL_FROM_APP_PASSWORD`/`MAIL_TO` 시크릿 없이 `ANTHROPIC_API_KEY`만
있어도(그마저 없어도 뉴스가 영문으로 나올 뿐 동작은 함) 실행 결과를 미리 확인할 수
있습니다. 실행이 끝나면 해당 워크플로우 run 페이지 하단의 Artifacts에서
`briefing-preview`를 내려받아 `out.html`을 브라우저로 열어보세요.

## 알아두면 좋은 점

- 미국 주식 전용입니다 (국내 종목/증권사 연동 없음).
- "현금의 10%/50%/100%"는 실제 계좌 잔고를 연동하지 않으므로 금액이 아니라 비율
  안내로만 나갑니다. 실제 매수는 본인이 브로커 앱에서 직접 실행하는 걸 전제로 합니다.
- 뉴스는 `yfinance`가 제공하는 영문 헤드라인을 Claude로 번역만 한 것이라, 개수/품질이
  종목마다 다를 수 있습니다.
- `state/signals.json`은 자동 관리 파일입니다. 규칙이나 분할매수 진행 상황을
  리셋하고 싶으면 이 파일 내용을 `{}`로 되돌리면 됩니다.
