# AutoSwingTrade 자동매매 시스템

한국투자증권(KIS) API를 활용한 실전 주식 자동매매 시스템입니다.

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 필요한 패키지 설치
pip install -r requirements.txt
```

### 2. 설정 파일 생성

```bash
# 설정 파일 템플릿 복사
cp config/key.ini.template config/key.ini
```

### 3. API 키 설정

`config/key.ini` 파일을 편집하여 다음 정보를 입력하세요:

```ini
[KIS]
KIS_BASE_URL="https://openapi.koreainvestment.com:9443"
KIS_APP_KEY="YOUR_KIS_APP_KEY_HERE"
KIS_APP_SECRET="YOUR_KIS_APP_SECRET_HERE"
KIS_ACCOUNT_NO="YOUR_ACCOUNT_NUMBER_HERE"
KIS_HTS_ID="YOUR_HTS_ID_HERE"

[TELEGRAM]
enabled=true
token=YOUR_TELEGRAM_BOT_TOKEN_HERE
chat_id=YOUR_TELEGRAM_CHAT_ID_HERE
```

### 4. 시스템 실행

```bash
# 메인 시스템 실행
python main.py
```

## 📋 필수 설정

### KIS API 설정

1. [KIS Developers](https://apiportal.koreainvestment.com/) 접속
2. 앱 등록 후 APP KEY와 APP SECRET 발급
3. 계좌번호와 HTS ID 확인

### 텔레그램 봇 설정 (선택사항)

1. [@BotFather](https://t.me/BotFather)에서 봇 생성
2. 봇 토큰 발급
3. 본인의 채팅 ID 확인 ([@userinfobot](https://t.me/userinfobot) 사용)

## 🤖 텔레그램 명령어

- `/start` - 봇 시작 및 도움말
- `/help` - 도움말 보기
- `/status` - 매매 봇 상태 확인
- `/stop` - 매매 봇 정지
- `/pause` - 매매 봇 일시정지
- `/resume` - 매매 봇 재개
- `/screening` - 수동 스크리닝 실행
- `/candidates` - 매수후보 종목 조회
- `/stats` - 텔레그램 봇 통계

## 📊 주요 기능

### 자동매매 기능
- 캔들패턴 기반 매수후보 종목 스크리닝
- 자동 매수/매도 주문 실행
- 손절/익절 자동 관리
- 포지션 리스크 관리

### 모니터링 기능
- 실시간 계좌 상태 모니터링
- 매매 신호 및 주문 알림
- 시스템 상태 알림
- 상세한 로깅 시스템

### 원격 제어
- 텔레그램을 통한 원격 제어
- 실시간 상태 확인
- 매매 봇 제어 (시작/정지/일시정지)

## 🛡️ 리스크 관리

### 자동 리스크 관리
- 종목당 최대 투자 비율 제한 (기본 10%)
- 최대 보유 종목 수 제한 (기본 10개)
- 일일 최대 손실률 제한 (기본 3%)
- 자동 손절/익절 시스템

### 안전 장치
- 주문 전 잔고 확인
- 시장 시간 외 매매 금지
- 예외 상황 자동 처리
- 상세한 거래 로그 기록

## 📁 프로젝트 구조

```
AutoSwingTrade/
├── main.py                 # 메인 실행 파일
├── telegram_bot.py         # 텔레그램 봇
├── requirements.txt        # 필요 패키지
├── README.md              # 사용 설명서
├── core/                  # 핵심 시스템
│   ├── trading_bot.py     # 매매 봇
│   ├── enums.py          # 열거형 정의
│   └── models.py         # 데이터 모델
├── api/                   # KIS API 연동
│   ├── kis_api_manager.py # API 매니저
│   ├── kis_auth.py       # 인증 관리
│   ├── kis_market_api.py # 시장 데이터 API
│   ├── kis_order_api.py  # 주문 API
│   └── kis_account_api.py # 계좌 API
├── trading/               # 매매 관련
│   ├── order_manager.py   # 주문 관리
│   ├── position_manager.py # 포지션 관리
│   └── candidate_screener.py # 종목 스크리닝
├── config/                # 설정 파일
│   ├── settings.py       # 설정 관리
│   ├── key.ini           # API 키 설정
│   └── key.ini.template  # 설정 템플릿
└── utils/                 # 유틸리티
    ├── logger.py         # 로깅 시스템
    └── korean_time.py    # 한국 시간 유틸리티
```

## ⚠️ 주의사항

1. **실전 매매 시스템**: 실제 자금이 투입되므로 신중하게 사용하세요.
2. **API 제한**: KIS API의 일일 호출 제한을 확인하세요.
3. **네트워크 안정성**: 안정적인 네트워크 환경에서 실행하세요.
4. **백업**: 중요한 설정과 로그는 정기적으로 백업하세요.
5. **테스트**: 소액으로 충분히 테스트한 후 본격 운용하세요.

## 🔧 문제 해결

### 일반적인 오류

1. **API 인증 오류**
   - `config/key.ini` 파일의 API 키 확인
   - KIS API 서비스 상태 확인

2. **텔레그램 봇 오류**
   - 봇 토큰과 채팅 ID 확인
   - 네트워크 연결 상태 확인

3. **매매 오류**
   - 계좌 잔고 확인
   - 시장 시간 확인
   - 주문 가능 종목 확인

### 로그 확인

```bash
# 로그 디렉토리 확인
ls logs/

# 최신 로그 확인
tail -f logs/trading_$(date +%Y%m%d).log
```

## 📞 지원

문제가 발생하거나 개선 사항이 있으면 GitHub Issues를 통해 문의해주세요.

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.

---

**⚠️ 투자 주의사항**: 이 시스템은 투자 참고용으로만 사용하세요. 모든 투자 결정과 그에 따른 손익은 사용자 본인의 책임입니다. 