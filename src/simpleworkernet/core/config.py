# simpleworkernet/core/config.py
"""
Менеджер конфигурации для SimpleWorkerNet
Синглтон для текущего процесса, использует имя текущего приложения
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union, Literal
from dataclasses import dataclass, field, asdict

from ..utils.app_name import get_app_name
from .constants import DEBUG, INFO, WARNING, ERROR, CRITICAL


# Типы для конфигурации
LogLevel = Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
CacheEvictStrategy = Literal['lru', 'lfu', 'fifo']


def get_app_config_dir(app_name: str) -> Path:
    """Возвращает директорию конфигурации для приложения"""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.config'
    return base / 'simpleworkernet' / app_name


def get_app_cache_dir(app_name: str) -> Path:
    """Возвращает директорию кэша для приложения"""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Caches'
    else:
        base = Path.home() / '.cache'
    return base / 'simpleworkernet' / app_name


def get_app_logs_dir(app_name: str) -> Path:
    """Возвращает директорию логов для приложения (legacy, для cleanup старых файлов)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Logs'
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'simpleworkernet' / app_name / 'logs'


@dataclass
class CacheConfig:
    """Конфигурация кэша для SmartDataCache"""
    enabled: bool = True
    max_size: int = 200000
    evict_strategy: CacheEvictStrategy = 'lru'
    evict_threshold: float = 0.95                 # порог заполнения
    evict_percent: float = 0.25                   # доля удаляемых записей
    auto_save: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'max_size': self.max_size,
            'evict_strategy': self.evict_strategy,
            'evict_threshold': self.evict_threshold,
            'evict_percent': self.evict_percent,
            'auto_save': self.auto_save,
        }


@dataclass
class WorkerNetConfig:
    """Конфигурация для текущего приложения"""

    # Общие настройки (логирование только в консоль)
    console_level: LogLevel = 'INFO'      # Уровень для консоли
    console_output: bool = False          # Включить вывод в stdout (из клиентского кода)

    # Настройки кэша
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Настройки API
    default_timeout: int = 30
    max_retries: int = 3
    user_agent: str = "SimpleWorkerNet/1.0"

    # Настройки SmartData
    smartdata_max_depth: int = 100

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Преобразуем вложенный cache в словарь для удобства
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerNetConfig':
        # Рекурсивно создаём объекты; неизвестные/устаревшие ключи (file_level и т.п.) игнорируются
        valid_keys = cls.__annotations__.keys()
        filtered = {}
        for k, v in data.items():
            if k not in valid_keys:
                continue
            if k == 'cache' and isinstance(v, dict):
                filtered[k] = CacheConfig(**v)
            else:
                filtered[k] = v
        return cls(**filtered)


class ConfigManager:
    """
    Менеджер конфигурации - синглтон для текущего процесса.
    Изменения настроек применяются immediately к текущей сессии.
    Сохранение в файл происходит только при вызове save().
    """

    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Определяем имя текущего приложения
        self.app_name = get_app_name(with_hash=True)
        self.display_name = get_app_name(with_hash=False)

        # Пути для текущего приложения
        self.config_dir = get_app_config_dir(self.app_name)
        self.config_file = self.config_dir / 'config.json'
        self.cache_dir = get_app_cache_dir(self.app_name)
        self.logs_dir = get_app_logs_dir(self.app_name)

        # Создаём директории если нужно (логи больше не пишем — logs_dir только для cleanup legacy)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Загружаем конфигурацию из файла
        self._config = self._load()

        # Ленивые ссылки на компоненты
        self._logger = None
        self._cache = None

        self._initialized = True

    def _get_logger(self):
        """Ленивый импорт логгера"""
        if self._logger is None:
            from .logger import log
            self._logger = log
        return self._logger

    def _get_cache(self):
        """Ленивый импорт кэша"""
        if self._cache is None:
            from .cache import cache
            self._cache = cache
        return self._cache

    def _load(self) -> WorkerNetConfig:
        """Загружает конфигурацию из файла"""
        config_data = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e:
                print(f"Предупреждение: не удалось загрузить конфигурацию: {e}")
        return WorkerNetConfig.from_dict(config_data)

    def _save(self):
        """Сохраняет конфигурацию в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger = self._get_logger()
            logger.error(f"Ошибка сохранения конфигурации: {e}")

    # ==================== Свойства для прямого доступа к настройкам ====================

    @property
    def console_level(self) -> str:
        return self._config.console_level

    @console_level.setter
    def console_level(self, value: str):
        self._config.console_level = value
        logger = self._get_logger()
        logger.set_console_level(value)
        logger.info(f"Уровень логирования в консоли изменён на {value}")

    @property
    def console_output(self) -> bool:
        return self._config.console_output

    @console_output.setter
    def console_output(self, value: bool):
        self._config.console_output = value
        logger = self._get_logger()
        logger.configure(**self.get_log_config())
        status = "включён" if value else "отключён"
        logger.info(f"Вывод в консоль: {status}")

    # --- Свойства кэша ---

    @property
    def cache_enabled(self) -> bool:
        return self._config.cache.enabled

    @cache_enabled.setter
    def cache_enabled(self, value: bool):
        self._config.cache.enabled = value
        cache = self._get_cache()
        cache._apply_config()  # применить изменения к локальным атрибутам кэша
        if value:
            cache.enable()
        else:
            cache.disable()

    @property
    def cache_max_size(self) -> int:
        return self._config.cache.max_size

    @cache_max_size.setter
    def cache_max_size(self, value: int):
        self._config.cache.max_size = value
        cache = self._get_cache()
        cache._apply_config()
        self._get_logger().info(f"Максимальный размер кэша изменён на {value}")

    @property
    def cache_auto_save(self) -> bool:
        return self._config.cache.auto_save

    @cache_auto_save.setter
    def cache_auto_save(self, value: bool):
        self._config.cache.auto_save = value
        cache = self._get_cache()
        cache._apply_config()
        self._get_logger().info(f"Автосохранение кэша: {'включено' if value else 'отключено'}")

    @property
    def cache_evict_strategy(self) -> str:
        return self._config.cache.evict_strategy

    @cache_evict_strategy.setter
    def cache_evict_strategy(self, value: str):
        if self._config.cache.evict_strategy != value:
            self._config.cache.evict_strategy = value
            self._get_logger().info(f"Стратегия очистки кэша изменена на {value}")

    @property
    def cache_evict_threshold(self) -> float:
        return self._config.cache.evict_threshold

    @cache_evict_threshold.setter
    def cache_evict_threshold(self, value: float):
        self._config.cache.evict_threshold = value
        cache = self._get_cache()
        cache._apply_config()
        self._get_logger().info(f"Порог очистки кэша изменён на {value}")

    @property
    def cache_evict_percent(self) -> float:
        return self._config.cache.evict_percent

    @cache_evict_percent.setter
    def cache_evict_percent(self, value: float):
        self._config.cache.evict_percent = value
        cache = self._get_cache()
        cache._apply_config()
        self._get_logger().info(f"Процент удаляемых записей кэша изменён на {value}")

    # --- Остальные свойства ---

    @property
    def default_timeout(self) -> int:
        return self._config.default_timeout

    @default_timeout.setter
    def default_timeout(self, value: int):
        self._config.default_timeout = value
        self._get_logger().info(f"Таймаут клиента изменён на {value}")

    @property
    def max_retries(self) -> int:
        return self._config.max_retries

    @max_retries.setter
    def max_retries(self, value: int):
        self._config.max_retries = value
        self._get_logger().info(f"Максимальное количество повторов изменено на {value}")

    @property
    def user_agent(self) -> str:
        return self._config.user_agent

    @user_agent.setter
    def user_agent(self, value: str):
        self._config.user_agent = value
        self._get_logger().info(f"User-Agent изменён на {value}")

    @property
    def smartdata_max_depth(self) -> int:
        return self._config.smartdata_max_depth

    @smartdata_max_depth.setter
    def smartdata_max_depth(self, value: int):
        self._config.smartdata_max_depth = value
        self._get_logger().info(f"Максимальная глубина SmartData изменена на {value}")

    # ==================== Основные методы ====================

    def get(self) -> WorkerNetConfig:
        """Возвращает текущую конфигурацию"""
        return self._config

    def save(self) -> bool:
        """Сохраняет текущую конфигурацию в файл"""
        try:
            self._save()
            self._get_logger().info(f"Конфигурация сохранена в {self.config_file}")
            return True
        except Exception as e:
            self._get_logger().error(f"Ошибка сохранения конфигурации: {e}")
            return False

    def reset(self, save: bool = False) -> 'ConfigManager':
        """Сбрасывает конфигурацию на значения по умолчанию."""
        self._config = WorkerNetConfig()
        self._apply_all_changes()
        if save:
            self.save()
        else:
            self._get_logger().info("Конфигурация сброшена на значения по умолчанию (не сохранено)")
        return self

    def _apply_changes(self, old: WorkerNetConfig, new: WorkerNetConfig):
        """Применяет изменения конфигурации к компонентам (здесь только кэш и логирование)"""
        # Логирование
        if (old.console_level != new.console_level or
            old.console_output != new.console_output):
            logger = self._get_logger()
            logger.configure(**self.get_log_config())

        # Кэш – обновляем локальные копии
        if old.cache != new.cache:
            cache = self._get_cache()
            cache._apply_config()

    def _apply_all_changes(self):
        """Применяет все текущие настройки к компонентам"""
        logger = self._get_logger()
        logger.configure(**self.get_log_config())

        cache = self._get_cache()
        cache._apply_config()
        self._get_logger().debug("Все настройки применены к компонентам")

    # ==================== Методы для компонентов ====================

    def get_cache_config(self) -> Dict[str, Any]:
        """Возвращает настройки для кэша в виде словаря"""
        cfg = self._config.cache
        return {
            'enabled': cfg.enabled,
            'max_size': cfg.max_size,
            'evict_threshold': cfg.evict_threshold,
            'evict_percent': cfg.evict_percent,
            'auto_save': cfg.auto_save,
            'cache_dir': str(self.cache_dir),
            'evict_strategy': cfg.evict_strategy,
        }

    def get_log_config(self) -> Dict[str, Any]:
        return {
            'console_level': self._config.console_level,
            'console_output': self._config.console_output,
            'app_name': self.app_name,
            'display_name': self.display_name,
        }

    def get_client_config(self) -> Dict[str, Any]:
        return {
            'timeout': self._config.default_timeout,
            'max_retries': self._config.max_retries,
            'user_agent': self._config.user_agent,
        }

    def get_smartdata_config(self) -> Dict[str, Any]:
        return {
            'max_depth': self._config.smartdata_max_depth,
        }

    def show_config(self, return_string: bool = False) -> Optional[str]:
        """Показывает текущую конфигурацию."""
        config_dict = self._config.to_dict()
        # Распаковываем вложенный кэш
        cache_cfg = config_dict.get('cache', {})
        lines = [
            "=" * 60,
            f"КОНФИГУРАЦИЯ SIMPLEWORKERNET - {self.display_name}",
            "=" * 60,
            f"Приложение: {self.app_name}",
            f"Файл конфигурации: {self.config_file}",
            f"Директория кэша: {self.cache_dir}",
            f"Директория логов (legacy): {self.logs_dir}",
            "-" * 60,
            "ЛОГИРОВАНИЕ (только консоль):",
            f"  Уровень консоль: {config_dict.get('console_level', 'INFO')}",
            f"  В консоль: {config_dict.get('console_output', False)}",
            "-" * 60,
            "КЭШ:",
            f"  Включён: {cache_cfg.get('enabled', False)}",
            f"  Макс. размер: {cache_cfg.get('max_size', 50000)}",
            f"  Стратегия: {cache_cfg.get('evict_strategy', 'lru')}",
            f"  Порог очистки: {cache_cfg.get('evict_threshold', 0.9)}",
            f"  Процент удаления: {cache_cfg.get('evict_percent', 0.2)}",
            f"  Автосохранение: {cache_cfg.get('auto_save', True)}",
            "-" * 60,
            "API КЛИЕНТ:",
            f"  Таймаут: {config_dict['default_timeout']}с",
            f"  Повторы: {config_dict['max_retries']}",
            f"  User-Agent: {config_dict['user_agent']}",
            "-" * 60,
            "SMARTDATA:",
            f"  Макс. глубина: {config_dict['smartdata_max_depth']}",
            "=" * 60,
        ]
        result = "\n".join(lines)
        if return_string:
            return result
        logger = self._get_logger()
        for line in lines:
            logger.info(line)
        return None

    def update(self, save: bool = False, **kwargs) -> 'ConfigManager':
        """Массовое обновление настроек."""
        old_config = WorkerNetConfig.from_dict(self._config.to_dict())
        changed = False

        for key, value in kwargs.items():
            if key == 'cache':
                # Если передают словарь для кэша
                if isinstance(value, dict):
                    for ck, cv in value.items():
                        if hasattr(self._config.cache, ck):
                            old_val = getattr(self._config.cache, ck)
                            if old_val != cv:
                                setattr(self._config.cache, ck, cv)
                                changed = True
            elif hasattr(self._config, key):
                old_value = getattr(self._config, key)
                if old_value != value:
                    setattr(self._config, key, value)
                    changed = True

        if changed:
            self._apply_changes(old_config, self._config)

        if save:
            self.save()

        return self


config_manager = ConfigManager()
