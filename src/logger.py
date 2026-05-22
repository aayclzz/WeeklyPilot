"""
日志管理模块
基于 loguru 实现，每次运行创建独立的日志文件夹
"""

import sys
from datetime import datetime
from pathlib import Path
from loguru import logger
from src.config import config


class LogManager:
    """日志管理器"""
    
    def __init__(self):
        self.run_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_dir = config.LOGS_DIR / self.run_time
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logger()
    
    def _setup_logger(self):
        """配置日志器"""
        # 移除默认处理器
        logger.remove()
        
        # 控制台输出
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level=config.LOG_LEVEL,
            colorize=True
        )
        
        # 文件输出
        log_file = self.log_dir / "weekly.log"
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            encoding="utf-8"
        )
        
        logger.info(f"日志目录：{self.log_dir}")
    
    def get_run_time(self) -> str:
        """获取本次运行时间戳"""
        return self.run_time
    
    def get_log_dir(self) -> Path:
        """获取日志目录"""
        return self.log_dir


# 全局日志管理器
log_manager = LogManager()

# 导出logger供其他模块使用
__all__ = ['logger', 'log_manager']
