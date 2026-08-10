"""
Менеджер конфигурации для SimpleWorkerNet
Синглтон для текущего процесса, использует имя текущего приложения
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union, Literal, List
from dataclasses import dataclass, field, asdict

from ..utils.app_name import get_app_name


# Типы для конфигурации
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


def _default_preload_types() -> List[str]:
    return ["node", "device", "splitter", "cross", "cwdm", "fiber"]


@dataclass
class WorkerNetConfig:
    """Конфигурация для текущего приложения.

    Настройки topology/attenuation — плоские поля здесь же
    (доступ через ConfigManager), без отдельных классов.
    """

    # Настройки кэша
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Настройки API
    default_timeout: int = 30
    max_retries: int = 3
    user_agent: str = "SimpleWorkerNet/1.0"

    # Настройки SmartData
    smartdata_max_depth: int = 100

    # --- Topology / DataCache ---
    # Таймаут HTTP для массовых get_all_* (сек). Абоненты грузятся долго.
    bulk_timeout: int = 120
    customer_list_timeout: int = 300
    # Фоновая предзагрузка get_all_* при DataCache(client) / NetworkTopology
    preload_on_init: bool = True
    preload_types: List[str] = field(default_factory=_default_preload_types)
    preload_customers: bool = False
    # Параллельные фоновые задачи (потоки; объекты API не сериализуются в процессы)
    preload_workers: int = 6

    # --- Attenuation ---
    # Каталог JSON: если None — ~/.config/simpleworkernet/
    attenuation_json_dir: Optional[str] = None
    # Шаблон имени файла; {host} → hostname клиента
    attenuation_json_filename: str = "attenuation_{host}.json"
    attenuation_default_wavelength: int = 1550
    attenuation_use_max_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerNetConfig":
        # неизвестные/устаревшие ключи игнорируются;
        # legacy вложенные topology/attenuation распаковываются в плоские поля
        valid_keys = set(cls.__annotations__.keys())
        filtered: Dict[str, Any] = {}

        # legacy: {"topology": {...}, "attenuation": {...}}
        topo = data.get("topology") if isinstance(data.get("topology"), dict) else {}
        att = data.get("attenuation") if isinstance(data.get("attenuation"), dict) else {}
        legacy_map = {
            "bulk_timeout": topo.get("bulk_timeout"),
            "customer_list_timeout": topo.get("customer_list_timeout"),
            "preload_on_init": topo.get("preload_on_init"),
            "preload_types": topo.get("preload_types"),
            "preload_customers": topo.get("preload_customers"),
            "preload_workers": topo.get("preload_workers"),
            "attenuation_json_dir": att.get("json_dir"),
            "attenuation_json_filename": att.get("json_filename"),
            "attenuation_default_wavelength": att.get("default_wavelength"),
            "attenuation_use_max_default": att.get("use_max_default"),
        }
        for k, v in legacy_map.items():
            if v is not None and k not in data:
                data = {**data, k: v}

        for k, v in data.items():
            if k not in valid_keys:
                continue
            if k == "cache" and isinstance(v, dict):
                filtered[k] = CacheConfig(**{
                    kk: vv for kk, vv in v.items()
                    if kk in CacheConfig.__annotations__
                })
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

    # --- API ---

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

    # --- Topology / DataCache (плоские свойства) ---

    @property
    def bulk_timeout(self) -> int:
        return self._config.bulk_timeout

    @bulk_timeout.setter
    def bulk_timeout(self, value: int):
        self._config.bulk_timeout = int(value)

    @property
    def customer_list_timeout(self) -> int:
        return self._config.customer_list_timeout

    @customer_list_timeout.setter
    def customer_list_timeout(self, value: int):
        self._config.customer_list_timeout = int(value)

    @property
    def preload_on_init(self) -> bool:
        return self._config.preload_on_init

    @preload_on_init.setter
    def preload_on_init(self, value: bool):
        self._config.preload_on_init = bool(value)

    @property
    def preload_types(self) -> List[str]:
        return list(self._config.preload_types)

    @preload_types.setter
    def preload_types(self, value: List[str]):
        self._config.preload_types = list(value)

    @property
    def preload_customers(self) -> bool:
        return self._config.preload_customers

    @preload_customers.setter
    def preload_customers(self, value: bool):
        self._config.preload_customers = bool(value)

    @property
    def preload_workers(self) -> int:
        return self._config.preload_workers

    @preload_workers.setter
    def preload_workers(self, value: int):
        self._config.preload_workers = int(value)

    # --- Attenuation (плоские свойства) ---

    @property
    def attenuation_json_dir(self) -> Optional[str]:
        return self._config.attenuation_json_dir

    @attenuation_json_dir.setter
    def attenuation_json_dir(self, value: Optional[str]):
        self._config.attenuation_json_dir = value

    @property
    def attenuation_json_filename(self) -> str:
        return self._config.attenuation_json_filename

    @attenuation_json_filename.setter
    def attenuation_json_filename(self, value: str):
        self._config.attenuation_json_filename = str(value)

    @property
    def attenuation_default_wavelength(self) -> int:
        return self._config.attenuation_default_wavelength

    @attenuation_default_wavelength.setter
    def attenuation_default_wavelength(self, value: int):
        self._config.attenuation_default_wavelength = int(value)

    @property
    def attenuation_use_max_default(self) -> bool:
        return self._config.attenuation_use_max_default

    @attenuation_use_max_default.setter
    def attenuation_use_max_default(self, value: bool):
        self._config.attenuation_use_max_default = bool(value)

    def attenuation_json_path(self, host: str = "default") -> Path:
        """Путь к attenuation_<host>.json (через config)."""
        if self._config.attenuation_json_dir:
            base = Path(self._config.attenuation_json_dir)
        else:
            if sys.platform == "win32":
                base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            elif sys.platform == "darwin":
                base = Path.home() / "Library" / "Application Support"
            else:
                base = Path.home() / ".config"
            base = base / "simpleworkernet"
        base.mkdir(parents=True, exist_ok=True)
        name = self._config.attenuation_json_filename.replace(
            "{host}", str(host or "default")
        )
        return base / name

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
        """Применяет изменения конфигурации к компонентам"""
        # Кэш – обновляем локальные копии
        if old.cache != new.cache:
            cache = self._get_cache()
            cache._apply_config()

    def _apply_all_changes(self):
        """Применяет все текущие настройки к компонентам"""
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
            "-" * 60,
            "TOPOLOGY / DATACACHE:",
            f"  bulk_timeout: {config_dict.get('bulk_timeout')}с",
            f"  customer_list_timeout: {config_dict.get('customer_list_timeout')}с",
            f"  preload_on_init: {config_dict.get('preload_on_init')}",
            f"  preload_types: {config_dict.get('preload_types')}",
            f"  preload_customers: {config_dict.get('preload_customers')}",
            f"  preload_workers: {config_dict.get('preload_workers')}",
            "-" * 60,
            "ATTENUATION:",
            f"  json_dir: {config_dict.get('attenuation_json_dir') or '(default XDG)'}",
            f"  json_filename: {config_dict.get('attenuation_json_filename')}",
            f"  default_wavelength: {config_dict.get('attenuation_default_wavelength')}",
            f"  use_max_default: {config_dict.get('attenuation_use_max_default')}",
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
