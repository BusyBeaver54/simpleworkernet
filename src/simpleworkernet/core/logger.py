# simpleworkernet/core/logger.py
"""
Модуль логирования для SimpleWorkerNet.

Только консольный вывод. Клиентский код включает логи через
config_manager.console_output / log.set_console_output(True)
или напрямую через объект log.
"""
import logging
import sys
from typing import Optional, Dict, Any, Union

from .constants import DEBUG, INFO, WARNING, ERROR, CRITICAL, LOGGER_NAME
from ..utils.app_name import get_app_name


class WorkerNetLogger:
    """
    Логгер для WorkerNet.
    Синглтон для текущего процесса, использует имя текущего приложения.
    Пишет только в консоль (stdout); файловое логирование не поддерживается.
    Клиентский код может вызывать log.debug/info/... и включать вывод
    через set_console_output / configure.
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

        logger_name = f"{LOGGER_NAME}.{self.app_name}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(DEBUG)
        # Не пробрасываем в root: клиент сам решает, куда слать свои логи
        self._logger.propagate = False

        self._console_handler: Optional[logging.Handler] = None
        self._suppress_output = False

        self._console_level = INFO
        self._console_output = False

        self._initialized = True

    def configure(self, **kwargs):
        """
        Настраивает консольное логирование.

        Args:
            console_level: Уровень для консоли (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: Включить вывод в консоль

        Устаревшие ключи (log_to_file, file_level, max_log_files, log_dir)
        игнорируются для обратной совместимости.
        """
        console_level = kwargs.get('console_level', 'INFO')
        console_output = kwargs.get('console_output', False)

        self._console_output = console_output
        self._console_level = self._str_to_level(console_level)

        self._clear_handlers()

        if console_output and not self._suppress_output:
            self._setup_console_handler()

    def _str_to_level(self, level: Union[str, int]) -> int:
        if isinstance(level, int):
            return level
        level_map = {
            'DEBUG': DEBUG,
            'INFO': INFO,
            'WARNING': WARNING,
            'ERROR': ERROR,
            'CRITICAL': CRITICAL,
        }
        return level_map.get(str(level).upper(), INFO)

    def _clear_handlers(self):
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        self._console_handler = None

    def _setup_console_handler(self):
        formatter = logging.Formatter(
            f'%(asctime)s.%(msecs)03d - [{self.display_name}] - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S',
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self._console_level)
        handler.setFormatter(formatter)

        self._logger.addHandler(handler)
        self._console_handler = handler

    def set_console_output(self, enabled: bool):
        """Включает/отключает консольный вывод (из клиентского кода)."""
        if enabled == (self._console_handler is not None):
            self._console_output = enabled
            return

        if enabled:
            if not self._suppress_output:
                self._setup_console_handler()
                self._console_output = True
                self._logger.log(
                    self._console_level,
                    f"Консольный вывод активирован: (уровень: {logging.getLevelName(self._console_level)})",
                )
        else:
            if self._console_handler:
                self._logger.removeHandler(self._console_handler)
                self._console_handler = None
                self._console_output = False

    def set_console_level(self, level: Union[str, int]):
        """Изменяет уровень логирования для консоли."""
        new_level = self._str_to_level(level)
        if new_level == self._console_level:
            return

        self._console_level = new_level
        if self._console_handler:
            self._console_handler.setLevel(new_level)
            self._logger.log(
                new_level,
                f"Уровень консоли изменён на {logging.getLevelName(new_level)}",
            )

    def suppress_output(self, suppress: bool = True):
        """
        Подавляет или восстанавливает вывод в консоль.
        При подавлении — удаляет консольный обработчик.
        При восстановлении — создаёт заново, если console_output=True.
        """
        if self._suppress_output == suppress:
            return

        self._suppress_output = suppress

        if suppress:
            if self._console_handler:
                self._logger.removeHandler(self._console_handler)
                self._console_handler = None
        else:
            if self._console_output:
                self._setup_console_handler()

    @property
    def underlying_logger(self) -> logging.Logger:
        """Стандартный logging.Logger — для интеграции с клиентским кодом."""
        return self._logger

    # ==================== Специализированные методы логирования ====================

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

    # ==================== Основные методы логирования ====================

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


# Глобальный экземпляр — используйте из клиентского кода:
#   from simpleworkernet import log
#   log.set_console_output(True)
#   log.info("...")
log = WorkerNetLogger()
