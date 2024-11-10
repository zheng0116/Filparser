import logging


def setup_logger(logger_name="main", level=logging.INFO):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger
