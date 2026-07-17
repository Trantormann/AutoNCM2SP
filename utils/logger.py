"""
日志管理模块
提供统一的日志输出，同时写入文件和终端
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = 'autoncm', log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    配置并返回日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径，默认为 logs/autoncm.log
        level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 终端输出 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出 handler
    if log_file is None:
        base_dir = Path(__file__).parent.parent
        log_dir = base_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / 'autoncm.log')
    
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (IOError, OSError) as e:
        # 文件日志不可用时仅终端输出
        logger.warning(f'无法创建日志文件 {log_file}: {e}')
    
    return logger


# 全局日志实例
_logger = None


def get_logger() -> logging.Logger:
    """获取全局日志实例（单例模式）"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
