# simpleworkernet/core/logger.py
"""
Тонкая обёртка над стандартным logging.

Библиотека только пишет сообщения; управление handlers/уровнями —
задача клиентского кода (logging.basicConfig / getLogger).
"""
import logging
from typing import Optional, Dict, Any

from .constants import DEBUG, LOGGER_NAME
from ..utils.app_name import get_app_name


class WorkerNetLogger:
    """
    Фасад над logging.Logger.
    Без configure / handlers / уровней — клиент настраивает logging сам.
    """

    _instance: Optional['WorkerNetLogger'] = None

    def __new__(cls) -> 'WorkerNetLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.app_name = get_app_name(with_hash=True)
        self.display_name = get_app_name(with_hash=False)

        # Имя в иерархии logging: workernet.<app>
        # propagate=True — сообщения уходят в root, если клиент его настроил
        self._logger = logging.getLogger(f"{LOGGER_NAME}.{self.app_name}")
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

        self._initialized = True

    @property
    def underlying_logger(self) -> logging.Logger:
        return self._logger

    # ==================== Специализированные методы ====================

    def log_api_call(self, category: str, action: str, params: dict = None):
        if self._logger.isEnabledFor(DEBUG):
            params_str = f"Параметры: {params}" if params else ""
            self.debug(f"API вызов: {category}.{action}; {params_str}")

    def log_api_response(self, category: str, action: str, status_code: int, size: int = None):
        if self._logger.isEnabledFor(DEBUG):
            size_str = f"({size} байт)" if size else ""
            self.debug(f"API ответ: HTTP {status_code}; данных принято {size_str}")

    def log_cache_operation(self, operation: str, details: dict = None):
        if details:
            details_str = " ".join(f"{k}={v}" for k, v in details.items())
            self.info(f"Кэш {operation}: {details_str}")
        else:
            self.info(f"Кэш {operation}")

    def log_smartdata_operation(self, operation: str, details: dict = None):
        if details:
            details_str = " ".join(f"{k}={v}" for k, v in details.items())
            self.debug(f"SmartData.{operation}: {details_str}")
        else:
            self.debug(f"SmartData.{operation}")

    def log_cache_stats(self, stats: Dict[str, Any]):
        self.info(f"Статистика кэша: попаданий={stats.get('hits', 0)}")

    # ==================== Основные методы ====================

    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._logger.exception(message, *args, **kwargs)


log = WorkerNetLogger()
