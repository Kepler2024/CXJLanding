"""统一日志配置：带时间日期前缀，按天自动轮转。"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

_CONFIGURED = False


def setup_logging() -> logging.Logger:
    """配置根日志器。

    - 在每条日志前添加时间日期（asctime）。
    - 使用 TimedRotatingFileHandler 按天自动轮转，保留 14 天，轮转文件名带日期后缀。
    - 同时输出到控制台，方便 `docker logs` 查看。
    """
    global _CONFIGURED
    logger = logging.getLogger()
    if _CONFIGURED:
        return logger

    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 时间日期 + 级别 + 模块 + 消息
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.setLevel(logging.INFO)

    # 文件处理器：每天午夜轮转，旧文件后缀为 .YYYY-MM-DD
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # 控制台处理器
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 降低第三方库噪声
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True
    logger.info("日志系统已初始化，日志目录: %s", os.path.abspath(log_dir))
    return logger
