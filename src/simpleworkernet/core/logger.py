"""
Тонкая обёртка над стандартным logging.

Библиотека только пишет сообщения; уровень и handlers настраивает
клиентский код (logging.basicConfig / getLogger).

Имя логгера для %(name)s:
    workernet.<имя_файла_без_.py>.<имя_клиентского_скрипта_без_хеша>

Уровень логгера библиотеки — NOTSET: фильтрация идёт по root / parent,
поэтому logging.basicConfig(level=INFO) скрывает debug из библиотеки.
"""
from __future__ import annotations

import inspect
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import LOGGER_NAME
from ..utils.app_name import get_app_name


def _script_display_name() -> str:
    """Имя клиентского скрипта без хеша пути."""
    return get_app_name(with_hash=False)


def _caller_module_stem() -> str:
    """Имя .py файла (stem), из которого пишется лог — снаружи simpleworkernet.core.logger."""
    try:
        stack = inspect.stack()
        for frame_info in stack[2:]:
            filename = frame_info.filename or ""
            # пропускаем сам logger и logging
            norm = filename.replace("\\", "/")
            if "/logging/" in norm or norm.endswith("logging/__init__.py"):
                continue
            if norm.endswith("core/logger.py") or norm.endswith("core\\logger.py"):
                continue
            stem = Path(filename).stem
            if stem and stem not in ("logger", "__init__"):
                return stem
            if stem:
                return stem
    except Exception:
        pass
    return "unknown"


def _logger_name_for_caller() -> str:
    """workernet.<file>.<script>."""
    return f"{LOGGER_NAME}.{_caller_module_stem()}.{_script_display_name()}"


class WorkerNetLogger:
    """
    Фасад над logging.Logger.

    На каждый вызов debug/info/… выбирается logger с именем
    workernet.<модуль>.<скрипт>, уровень NOTSET → наследует root.
    """

    _instance: Optional["WorkerNetLogger"] = None

    def __new__(cls) -> "WorkerNetLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.app_name = get_app_name(with_hash=True)
        self.display_name = get_app_name(with_hash=False)

        # Корневой logger библиотеки — без принудительного DEBUG
        self._root = logging.getLogger(LOGGER_NAME)
        self._root.setLevel(logging.NOTSET)
        self._root.propagate = True

        self._initialized = True

    def _get(self) -> logging.Logger:
        name = _logger_name_for_caller()
        lg = logging.getLogger(name)
        # NOTSET → эффективный уровень от parent/root (клиентский INFO скрывает DEBUG)
        if lg.level != logging.NOTSET:
            lg.setLevel(logging.NOTSET)
        lg.propagate = True
        return lg

    @property
    def underlying_logger(self) -> logging.Logger:
        return self._get()

    # ==================== Специализированные методы ====================

    def log_api_call(self, category: str, action: str, params: dict = None):
        lg = self._get()
        if lg.isEnabledFor(logging.DEBUG):
            params_str = f"Параметры: {params}" if params else ""
            lg.debug("API вызов: %s.%s; %s", category, action, params_str)

    def log_api_response(
        self, category: str, action: str, status_code: int, size: int = None
    ):
        lg = self._get()
        if lg.isEnabledFor(logging.DEBUG):
            size_str = f"({size} байт)" if size else ""
            lg.debug(
                "API ответ: HTTP %s; данных принято %s", status_code, size_str
            )

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
        self._get().debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._get().info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._get().warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._get().error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._get().critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._get().exception(message, *args, **kwargs)


log = WorkerNetLogger()
