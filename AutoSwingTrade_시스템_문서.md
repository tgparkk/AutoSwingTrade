# AutoSwingTrade 시스템 문서

## 📋 개요
AutoSwingTrade는 한국투자증권(KIS) API를 활용한 실전 주식 자동매매 시스템입니다. 실시간 시장 데이터를 분석하여 자동으로 매매 결정을 내리고, 포지션과 리스크를 체계적으로 관리합니다.

## 🏗️ 시스템 아키텍처

### 1. 핵심 폴더 구조
```
AutoSwingTrade/
├── core/           # 핵심 시스템 컴포넌트
│   ├── enums.py    # 시스템 열거형 정의
│   ├── models.py   # 데이터 모델 정의
│   └── trading_bot.py  # 메인 트레이딩 봇
└── trading/        # 매매 관련 컴포넌트
    ├── order_manager.py    # 주문 관리
    └── position_manager.py # 포지션 관리
```

## 🔧 Core 모듈 상세

### 1. **enums.py** - 시스템 열거형
시스템 전반에서 사용하는 모든 상태 및 타입을 중앙집중식으로 관리합니다.

#### 주요 열거형:
- **TradingStatus**: 매매 상태 (정지, 실행중, 일시정지, 오류)
- **MarketStatus**: 장 상태 (장마감, 장중, 장전, 장후)
- **SignalType**: 매매 신호 (매수, 매도, 보유)
- **OrderType**: 주문 타입 (시장가, 지정가, 손절, 익절)
- **PositionStatus**: 포지션 상태 (활성, 종료, 부분체결)
- **TradingMode**: 매매 모드 (보수적, 중간, 공격적)
- **RiskLevel**: 리스크 수준 (낮음, 보통, 높음, 매우높음)
- **MessageType**: 메시지 타입 (정보, 경고, 오류, 성공, 거래)
- **CommandType**: 명령 타입 (시작, 정지, 일시정지, 재개, 상태 등)

### 2. **models.py** - 데이터 모델
실전 매매에 필요한 모든 데이터 구조를 정의합니다.

#### 핵심 데이터 모델:

##### 📊 **TradingConfig** - 매매 설정
```python
- max_position_count: 최대 보유 종목 수 (기본 10개)
- max_position_ratio: 종목당 최대 투자 비율 (기본 10%)
- stop_loss_ratio: 손절 비율 (기본 -5%)
- take_profit_ratio: 익절 비율 (기본 10%)
- min_trade_amount: 최소 거래 금액 (기본 10만원)
- max_trade_amount: 최대 거래 금액 (기본 100만원)
- trading_start_time: 매매 시작 시간 (기본 09:00)
- trading_end_time: 매매 종료 시간 (기본 15:20)
- check_interval: 체크 간격 (기본 30초)
- max_daily_loss: 일일 최대 손실률 (기본 3%)
- max_daily_trades: 일일 최대 거래 횟수 (기본 50회)
```

##### 📈 **Position** - 포지션 정보
```python
- stock_code: 종목 코드
- stock_name: 종목명
- quantity: 보유 수량
- avg_price: 평균 매수가
- current_price: 현재가
- profit_loss: 손익 금액
- profit_loss_rate: 손익률
- entry_time: 진입 시간
- last_update: 최종 업데이트 시간
- stop_loss_price: 손절가
- take_profit_price: 익절가
- entry_reason: 진입 사유
```

##### 📶 **TradingSignal** - 매매 신호
```python
- stock_code: 종목 코드
- stock_name: 종목명
- signal_type: 신호 타입 (매수/매도/보유)
- price: 신호 가격
- quantity: 신호 수량
- reason: 신호 사유
- confidence: 신호 신뢰도 (0.0 ~ 1.0)
- timestamp: 신호 생성 시간
- order_type: 주문 타입
- priority: 우선순위
```

##### 📋 **TradeRecord** - 거래 기록
```python
- timestamp: 거래 시간
- trade_type: 거래 타입 (BUY/SELL)
- stock_code: 종목 코드
- stock_name: 종목명
- quantity: 거래 수량
- price: 거래 가격
- amount: 거래 금액
- reason: 거래 사유
- order_id: 주문 ID
- success: 성공 여부
- commission: 수수료
- profit_loss: 손익 (매도 시)
```

#### 고급 데이터 모델:
- **AccountSnapshot**: 계좌 스냅샷
- **MarketData**: 시장 데이터
- **TechnicalIndicator**: 기술적 지표
- **RiskMetrics**: 리스크 지표
- **StrategyConfig**: 전략 설정
- **BacktestResult**: 백테스트 결과
- **AlertConfig**: 알림 설정
- **SystemStatus**: 시스템 상태

### 3. **trading_bot.py** - 메인 트레이딩 봇
시스템의 핵심 엔진으로, 매매 전략을 실행하고 전체 시스템을 제어합니다.

#### 핵심 기능:

##### 🚀 **초기화 및 제어**
- `initialize()`: 시스템 초기화 (API 연결, 계좌 정보 로드)
- `start()`: 매매 봇 시작
- `stop()`: 매매 봇 정지
- `pause()`: 일시정지
- `resume()`: 재개

##### 🔄 **매매 루프**
- `_trading_loop()`: 메인 매매 루프
  - 명령 처리
  - 장 상태 확인
  - 계좌 정보 업데이트
  - 포지션 업데이트
  - 매매 전략 실행
  - 리스크 관리
  - 통계 업데이트

##### 📊 **상태 관리**
- `get_status()`: 현재 상태 반환
- `get_positions()`: 포지션 정보 반환
- `_update_market_status()`: 장 상태 업데이트
- `_is_trading_time()`: 매매 시간 확인

##### 🎯 **매매 전략**
- `_execute_trading_strategy()`: 매매 전략 실행
- `_generate_trading_signals()`: 매매 신호 생성
- `_execute_buy_order()`: 매수 주문 실행
- `_execute_sell_order()`: 매도 주문 실행
- `_manage_risk()`: 리스크 관리

## 🔄 Trading 모듈 상세

### 1. **order_manager.py** - 주문 관리
실제 매매 주문을 실행하고 관리하는 핵심 컴포넌트입니다.

#### 주요 기능:

##### 📈 **매수 주문 관리**
- `execute_buy_order()`: 매수 주문 실행
  - 사전 검증 (계좌 잔고, 포지션 수, 중복 확인)
  - 수량 조정 (가용 금액, 포트폴리오 비율 고려)
  - 주문 실행 및 결과 처리

##### 📉 **매도 주문 관리**
- `execute_sell_order()`: 매도 주문 실행
  - 보유 포지션 검증
  - 수량 확인 및 조정
  - 주문 실행 및 손익 계산


##### 📊 **주문 검증 및 통계**
- `_validate_buy_order()`: 매수 주문 검증
- `_validate_sell_order()`: 매도 주문 검증
- `_adjust_buy_quantity()`: 매수 수량 조정
- `get_order_stats()`: 주문 통계 반환

#### 주문 통계 추적:
- 총 주문 수
- 성공/실패 주문 수
- 매수/매도 주문 수
- 성공률 계산
- 최근 주문 시간

### 2. **position_manager.py** - 포지션 관리
보유 포지션을 체계적으로 관리하고 분석하는 컴포넌트입니다.

#### 주요 기능:

##### 📋 **포지션 로드 및 업데이트**
- `load_existing_positions()`: 기존 포지션 로드
  - 계좌 정보에서 포지션 데이터 추출
  - Position 객체 생성
  - 포지션 통계 업데이트

- `update_positions()`: 포지션 정보 업데이트
  - 현재가 조회
  - 손익 계산
  - 손익률 계산
  - 최종 업데이트 시간 갱신

##### 📊 **포지션 분석**
- `analyze_positions()`: 포지션 종합 분석
  - 총 포지션 수 및 가치 계산
  - 수익/손실 포지션 분류
  - 최대 포지션 및 수익/손실 포지션 식별
  - 포지션별 비중 계산
  - 리스크 분석 수행

##### ⚠️ **리스크 관리**
- `get_positions_requiring_attention()`: 주의 포지션 식별
  - 손절 조건 달성 포지션
  - 익절 조건 달성 포지션
  - 알림 및 경고 메시지 생성

- `_analyze_risk()`: 리스크 분석
  - 집중도 리스크 계산 (허핀달 지수)
  - 최대 포지션 비중 확인
  - 한도 초과 포지션 수 계산
  - 총 노출도 계산

##### 🔄 **거래 후 포지션 업데이트**
- `update_position_after_trade()`: 거래 후 포지션 업데이트
  - 매수 시 포지션 추가 및 평균가 계산
  - 매도 시 포지션 감소 및 상태 업데이트

#### 포지션 통계 추적:
- 총 포지션 수
- 수익/손실 포지션 수
- 총 포지션 가치
- 총 손익 금액
- 최종 업데이트 시간

## 🔗 시스템 연계 구조

### 1. **메시지 큐 시스템**
- 텔레그램 봇과 트레이딩 봇 간 비동기 통신
- 명령 큐를 통한 실시간 제어
- 알림 메시지 큐를 통한 상태 전송

### 2. **API 연동**
- KIS API Manager와 연동
- 실시간 계좌 정보 조회
- 현재가 조회
- 주문 실행

### 3. **데이터 흐름**
```
TradingBot (메인 루프)
    ↓
OrderManager (주문 실행)
    ↓
PositionManager (포지션 관리)
    ↓
API Manager (KIS API 호출)
```

## 🛡️ 리스크 관리 체계

### 1. **포지션 리스크**
- 종목당 최대 투자 비율 제한
- 최대 보유 종목 수 제한
- 집중도 리스크 모니터링

### 2. **손익 리스크**
- 자동 손절/익절 시스템
- 일일 최대 손실률 제한
- 실시간 손익 모니터링

### 3. **시스템 리스크**
- 주문 검증 시스템
- 예외 처리 및 로깅
- 장애 복구 메커니즘

## 📈 주요 특징

### 1. **실전 최적화**
- 실제 거래 환경에 맞춘 설계
- 수수료 및 세금 고려
- 시장 상황별 대응 로직

### 2. **안정성 중심**
- 철저한 입력 검증
- 예외 상황 처리
- 상태 복구 메커니즘

### 3. **확장성**
- 모듈화된 구조
- 전략 추가 용이
- 다양한 지표 지원

### 4. **모니터링**
- 실시간 상태 추적
- 상세한 로깅
- 통계 및 분석 기능

## 🎯 향후 확장 가능성

### 1. **전략 모듈**
- 기술적 분석 전략
- 기본적 분석 전략
- 머신러닝 기반 전략

### 2. **백테스팅**
- 과거 데이터 기반 검증
- 성과 분석 도구
- 최적화 기능

### 3. **고급 리스크 관리**
- VaR 계산
- 포트폴리오 최적화
- 동적 헤징

이 시스템은 실전 주식 자동매매를 위한 견고한 기반을 제공하며, 안정성과 수익성을 동시에 추구하는 전문적인 매매 도구입니다. 