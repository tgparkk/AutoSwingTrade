"""
로깅 시스템
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict


def setup_logger(name: str, level: str = "DEBUG") -> logging.Logger:
    """로거 설정"""
    
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 이미 핸들러가 있으면 중복 방지
    if logger.handlers:
        return logger
    
    # 루트 로거로 전파하지 않음 (중복 로그 방지)
    logger.propagate = False
    
    # 포매터 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"trading_{today}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


class TradingLogger:
    """거래 전용 로거"""
    
    def __init__(self):
        self.logger = setup_logger("TRADING")
        self.trade_logger = setup_logger("TRADE")
        
        # 거래 로그 전용 파일 핸들러 추가
        trade_dir = Path("logs/trades")
        trade_dir.mkdir(exist_ok=True)
        
        today = datetime.now().strftime("%Y%m%d")
        trade_file = trade_dir / f"trades_{today}.log"
        
        trade_handler = logging.FileHandler(trade_file, encoding='utf-8')
        trade_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        trade_handler.setFormatter(trade_formatter)
        self.trade_logger.addHandler(trade_handler)
    
    def log_order(self, order_info: dict):
        """주문 로깅"""
        self.trade_logger.info(f"ORDER: {order_info}")
    
    def log_fill(self, fill_info: dict):
        """체결 로깅"""
        self.trade_logger.info(f"FILL: {fill_info}")
    
    def log_position_open(self, position_info: dict):
        """포지션 오픈 로깅"""
        self.trade_logger.info(f"POSITION_OPEN: {position_info}")
    
    def log_position_close(self, position_info: dict):
        """포지션 클로즈 로깅"""
        self.trade_logger.info(f"POSITION_CLOSE: {position_info}")
    
    def log_error(self, error: str, context: Optional[Dict] = None):
        """에러 로깅"""
        self.logger.error(f"ERROR: {error}")
        if context:
            self.logger.error(f"CONTEXT: {context}")
    
    def log_system_event(self, event: str):
        """시스템 이벤트 로깅"""
        self.logger.info(f"SYSTEM: {event}")


def setup_logging(level: str = "INFO"):
    """전역 로깅 설정"""
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 포매터 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"system_{today}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """로거 인스턴스 반환"""
    logger = logging.getLogger(name)
    
    # 이미 설정된 로거면 그대로 반환
    if logger.handlers:
        return logger
    
    # 새로운 로거 설정
    return setup_logger(name)


# 전역 로거 인스턴스
trading_logger = TradingLogger() 