# finance-yoo — 매일 아침 포트폴리오 전략 브리핑

매일 07:00(KST)에 보유 종목의 시세 · 컨센서스 목표가 · 최근 뉴스를 모아 Claude API로
강세론/약세론/대응 전략을 요약한 뒤, 이메일로 발송하는 GitHub Actions 자동화입니다.

## 동작 방식

1. `config/portfolio.yaml`에 적어둔 보유 종목을 읽습니다.
2. 종목별로 `yfinance`에서 현재가/등락률/뉴스를 가져오고, 국내(`.KS`/`.KQ`) 종목은
   네이버 금융에서 컨센서스 목표가를 스크레이핑합니다 (해외는 Yahoo Finance 애널리스트
   목표가 필드 사용).
3. 수집한 데이터를 Claude API에 보내 강세론/약세론/대응/체크포인트를 한국어로 생성합니다.
   **뉴스가 부족하면 모델이 그대로 "뉴스 부족"이라고 쓰도록 프롬프트를 제한**해서, 없는
   애널리스트 리포트를 지어내지 않게 했습니다.
4. 결과를 HTML 이메일로 렌더링해서 발송합니다.
5. GitHub Actions가 매일 22:00 UTC(=07:00 KST)에 자동 실행합니다.

## 설정이 필요한 것 (직접 채워주셔야 해요)

### 1. `config/portfolio.yaml`
보유 종목/수량/평균 매입가, 이름, 전략 문구를 실제 값으로 수정해주세요.
- 국내 종목 코드는 `005930.KS`처럼 뒤에 `.KS`(코스피) 또는 `.KQ`(코스닥)를 붙여야 합니다.
- 토스/키움 계좌를 프로그램으로 직접 조회하는 공식 API가 없어서(토스는 공식 API 자체가
  없고, 키움 REST API는 별도 인증서 발급이 필요해 복잡합니다) 수량/매입가는 지금은
  수동으로 채우는 구조입니다. 나중에 키움 REST 연동을 원하시면 알려주세요.

### 2. GitHub 저장소 Secrets (Settings → Secrets and variables → Actions)
| Secret 이름 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키. [console.anthropic.com](https://console.anthropic.com)에서 발급. 매일 실행 시 종목당 소량의 API 비용이 발생합니다. |
| `MAIL_FROM_ADDRESS` | 발신용 Gmail 주소 (예: 본인 gmail) |
| `MAIL_FROM_APP_PASSWORD` | 위 Gmail 계정의 **앱 비밀번호** (일반 로그인 비밀번호 아님 — Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호에서 발급) |
| `MAIL_TO` | 받는 사람 이메일 — `yohojin@kbiohealth.kr` |

Gmail 대신 다른 SMTP(회사 메일 등)를 쓰고 싶으면 `SMTP_HOST`/`SMTP_PORT` 시크릿을
추가로 넣으면 됩니다 (기본값은 Gmail의 465 포트).

## 로컬 테스트

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python main.py --dry-run   # out.html 생성, 이메일 발송 안 함
```

메일 발송까지 테스트하려면 `MAIL_FROM_ADDRESS`/`MAIL_FROM_APP_PASSWORD`/`MAIL_TO`도
export한 뒤 `--dry-run` 없이 실행하세요.

GitHub Actions에서 스케줄을 기다리지 않고 바로 테스트하려면 저장소의
**Actions → Daily Strategy Briefing → Run workflow**로 수동 실행할 수 있습니다.

## 알아두면 좋은 한계

- **국내 종목 컨센서스 목표가**는 네이버 금융 페이지를 스크레이핑하는 방식이라 네이버가
  페이지 구조를 바꾸면 깨질 수 있습니다(그 경우 해당 종목은 "컨센서스 없음"으로만
  표시되고 전체 실행이 죽지는 않습니다).
- **뉴스 품질**: `yfinance` 뉴스는 대부분 영문/해외 소스 위주라, 스크린샷에서 보신
  "KB증권/맥쿼리 리포트" 수준의 국내 증권사 코멘트까지는 자동으로 못 가져옵니다. 더
  정교한 국내 리서치 반영을 원하시면 별도 뉴스 API 연동이 필요합니다.
- 토스/키움 보유 잔고 자동 동기화는 없고, `portfolio.yaml`을 직접 갱신해야 합니다.
