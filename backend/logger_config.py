import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

def setup_logger():
    # 创建logger对象
    logger = logging.getLogger('paper_checker')
    logger.setLevel(logging.DEBUG)

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 文件处理器（按日期切割）
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'paper_checker.log')
    
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# 创建全局logger实例
logger = setup_logger()