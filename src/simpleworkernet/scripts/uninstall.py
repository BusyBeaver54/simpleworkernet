# simpleworkernet/scripts/uninstall.py
"""
Скрипт для полной очистки SimpleWorkerNet
"""
import os
# Устанавливаем переменную окружения до любых импортов simpleworkernet
os.environ['SIMPLEWORKERNET_CLEANUP'] = '1'

import sys
import shutil
import time
import stat
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Set, Any, Literal
import argparse

# Импорты внутри функций, чтобы избежать лишней инициализации
# (но переменная окружения уже установлена, поэтому __init__ не будет создавать кэш)


# Тип для режима очистки
CleanupMode = Literal['all', 'logs', 'cache', 'config']


def get_simpleworkernet_root_dirs() -> Dict[str, Path]:
    """Возвращает корневые директории SimpleWorkerNet для разных ОС."""
    dirs = {}
    
    if sys.platform == 'win32':
        app_data = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        local_app_data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        dirs['config_root'] = app_data / 'simpleworkernet'
        dirs['cache_root'] = local_app_data / 'simpleworkernet'
        dirs['logs_root'] = app_data / 'simpleworkernet'
    elif sys.platform == 'darwin':
        dirs['config_root'] = Path.home() / 'Library' / 'Application Support' / 'simpleworkernet'
        dirs['cache_root'] = Path.home() / 'Library' / 'Caches' / 'simpleworkernet'
        dirs['logs_root'] = Path.home() / 'Library' / 'Logs' / 'simpleworkernet'
    else:
        dirs['config_root'] = Path.home() / '.config' / 'simpleworkernet'
        dirs['cache_root'] = Path.home() / '.cache' / 'simpleworkernet'
        dirs['logs_root'] = Path.home() / '.local' / 'share' / 'simpleworkernet' / 'logs'
    
    return dirs


def disable_cache_in_config(config_path: Path) -> bool:
    """Отключает кэширование в конфигурационном файле."""
    if not config_path.exists():
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if config.get('cache_enabled', True):
            config['cache_enabled'] = False
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
    except Exception:
        pass
    return False


def disable_cache_for_all_apps() -> List[str]:
    """Отключает кэширование во всех найденных конфигурациях приложений."""
    roots = get_simpleworkernet_root_dirs()
    modified_apps = []
    
    if not roots['config_root'].exists():
        return modified_apps
    
    try:
        for app_dir in roots['config_root'].iterdir():
            if app_dir.is_dir():
                config_file = app_dir / 'config.json'
                if disable_cache_in_config(config_file):
                    modified_apps.append(app_dir.name)
    except Exception:
        pass
    
    return modified_apps


def find_cache_files(cache_root: Path) -> List[Path]:
    """Рекурсивно находит все файлы кэша (*.pkl) в директории."""
    if not cache_root.exists():
        return []
    
    cache_files = []
    try:
        for root, dirs, files in os.walk(str(cache_root)):
            for file in files:
                if file.endswith('.pkl'):
                    cache_files.append(Path(root) / file)
    except Exception:
        pass
    
    return cache_files


def list_applications() -> List[str]:
    """Возвращает список всех установленных приложений."""
    roots = get_simpleworkernet_root_dirs()
    apps: Set[str] = set()
    
    # Сканируем директории конфигурации
    if roots['config_root'].exists():
        try:
            for item in roots['config_root'].iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    apps.add(item.name)
        except Exception:
            pass
    
    # Сканируем директории кэша
    if roots['cache_root'].exists():
        try:
            for item in roots['cache_root'].iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    apps.add(item.name)
        except Exception:
            pass
    
    # Сканируем директории логов
    if roots['logs_root'].exists():
        try:
            for item in roots['logs_root'].iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    if item.name != 'logs':
                        apps.add(item.name)
        except Exception:
            pass
    
    return sorted(list(apps))


def get_app_info(app_name: str) -> Dict[str, Any]:
    """Возвращает информацию о приложении."""
    roots = get_simpleworkernet_root_dirs()
    
    app_config_dir = roots['config_root'] / app_name
    app_cache_dir = roots['cache_root'] / app_name
    app_logs_dir = roots['logs_root'] / app_name / 'logs'
    
    info = {
        'name': app_name,
        'has_config': False,
        'has_cache': False,
        'has_logs': False,
        'config_size': 0.0,
        'cache_size': 0.0,
        'logs_size': 0.0,
        'config_path': app_config_dir,
        'cache_path': app_cache_dir,
        'logs_path': app_logs_dir,
        'cache_files': [],
        'cache_enabled': True
    }
    
    if app_config_dir.exists():
        try:
            info['has_config'] = True
            config_files = list(app_config_dir.rglob('*'))
            info['config_size'] = sum(f.stat().st_size for f in config_files if f.is_file()) / 1024
            config_file = app_config_dir / 'config.json'
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    info['cache_enabled'] = config.get('cache_enabled', True)
        except Exception:
            pass
    
    if app_cache_dir.exists():
        try:
            info['has_cache'] = True
            cache_files = find_cache_files(app_cache_dir)
            info['cache_files'] = cache_files
            info['cache_size'] = sum(f.stat().st_size for f in cache_files) / 1024
        except Exception:
            pass
    
    if app_logs_dir.exists():
        try:
            info['has_logs'] = True
            log_files = list(app_logs_dir.rglob('*.log'))
            info['logs_size'] = sum(f.stat().st_size for f in log_files if f.is_file()) / 1024
        except Exception:
            pass
    
    return info


def remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def force_remove_path(path: Path, max_attempts: int = 5, delay: float = 1.0) -> Tuple[bool, str]:
    """Принудительно удаляет файл или директорию с проверкой результата."""
    if not path.exists():
        return True, ""
    
    if path.is_file():
        if sys.platform == 'win32':
            try:
                os.chmod(path, stat.S_IWRITE)
            except:
                pass
        for attempt in range(max_attempts):
            try:
                path.unlink()
                if not path.exists():
                    return True, ""
                time.sleep(delay)
            except Exception as e:
                if attempt == max_attempts - 1:
                    return False, str(e)
                time.sleep(delay)
        return False, "Файл существует после всех попыток удаления"
    
    if path.is_dir():
        for attempt in range(max_attempts):
            try:
                shutil.rmtree(path, onerror=remove_readonly)
                if not path.exists():
                    return True, ""
                time.sleep(delay)
            except Exception as e:
                if attempt == max_attempts - 1:
                    try:
                        for item in path.rglob('*'):
                            if item.is_file():
                                try:
                                    os.chmod(item, stat.S_IWRITE)
                                    item.unlink()
                                except:
                                    pass
                        if path.exists():
                            path.rmdir()
                        if not path.exists():
                            return True, ""
                    except Exception as e2:
                        return False, f"rmtree failed: {e}, manual cleanup failed: {e2}"
                time.sleep(delay)
        return False, "Директория существует после всех попыток удаления"
    
    return True, ""


def cleanup(
    dry_run: bool = False,
    mode: CleanupMode = 'all',
    app_name: Optional[str] = None,
    disable_cache_first: bool = True
) -> Tuple[bool, List[str]]:
    """
    Очищает следы SimpleWorkerNet.
    
    Args:
        dry_run: Если True, только показывает, что будет удалено
        mode: Режим очистки ('all', 'logs', 'cache', 'config')
        app_name: Имя приложения (если None, удаляет все приложения)
        disable_cache_first: Отключить кэширование перед удалением
    
    Returns:
        Кортеж (успех, список сообщений)
    """
    roots = get_simpleworkernet_root_dirs()
    messages = []
    success = True
    paths_to_verify = []
    
    # Шаг 1: Отключаем кэширование в конфигурации
    if not dry_run and disable_cache_first and mode in ('all', 'cache'):
        if app_name:
            config_file = roots['config_root'] / app_name / 'config.json'
            if disable_cache_in_config(config_file):
                messages.append(f"  • Кэширование отключено в конфигурации {app_name}")
        else:
            modified = disable_cache_for_all_apps()
            if modified:
                messages.append(f"  • Кэширование отключено в конфигурациях: {', '.join(modified)}")
    
    if app_name:
        messages.append(f"\nПриложение: {app_name}")
        app_config = roots['config_root'] / app_name
        app_cache = roots['cache_root'] / app_name
        app_logs = roots['logs_root'] / app_name / 'logs'
        
        # Удаление конфигурации
        if mode in ('all', 'config'):
            if app_config.exists():
                config_size = sum(f.stat().st_size for f in app_config.rglob('*') if f.is_file()) / 1024
                if dry_run:
                    messages.append(f"  • Конфигурация будет удалена: {app_config} ({config_size:.1f} KB)")
                else:
                    ok, error = force_remove_path(app_config)
                    if ok:
                        messages.append(f"  • Конфигурация удалена: {app_config}")
                    else:
                        messages.append(f"  • ОШИБКА: не удалось удалить конфигурацию {app_config}: {error}")
                        success = False
                        paths_to_verify.append(app_config)
            else:
                messages.append(f"  • Конфигурация не найдена")
        
        # Удаление кэша
        if mode in ('all', 'cache'):
            if app_cache.exists():
                cache_files = find_cache_files(app_cache)
                cache_size = sum(f.stat().st_size for f in cache_files) / 1024
                if dry_run:
                    messages.append(f"  • Кэш будет удален: {app_cache} ({cache_size:.1f} KB)")
                    for cf in cache_files[:5]:
                        try:
                            rel_path = cf.relative_to(app_cache)
                            messages.append(f"      - {rel_path}")
                        except:
                            messages.append(f"      - {cf.name}")
                    if len(cache_files) > 5:
                        messages.append(f"      ... и еще {len(cache_files) - 5} файлов")
                else:
                    all_files_deleted = True
                    for cf in cache_files:
                        ok, error = force_remove_path(cf)
                        if not ok:
                            messages.append(f"      • ОШИБКА: не удалось удалить {cf.name}: {error}")
                            all_files_deleted = False
                            paths_to_verify.append(cf)
                    if all_files_deleted:
                        ok, error = force_remove_path(app_cache)
                        if ok:
                            messages.append(f"  • Кэш удален: {app_cache}")
                        else:
                            messages.append(f"  • Файлы кэша удалены, но директория {app_cache} не удалена: {error}")
                            paths_to_verify.append(app_cache)
                    else:
                        messages.append(f"  • ОШИБКА: не все файлы кэша удалены")
                        success = False
            else:
                messages.append(f"  • Кэш не найден")
        
        # Удаление логов
        if mode in ('all', 'logs'):
            if app_logs.exists():
                log_files = list(app_logs.rglob('*.log'))
                log_size = sum(f.stat().st_size for f in log_files) / 1024
                if dry_run:
                    messages.append(f"  • Логи будут удалены: {app_logs} ({log_size:.1f} KB)")
                    for lf in log_files[:5]:
                        try:
                            rel_path = lf.relative_to(app_logs)
                            messages.append(f"      - {rel_path}")
                        except:
                            messages.append(f"      - {lf.name}")
                    if len(log_files) > 5:
                        messages.append(f"      ... и еще {len(log_files) - 5} файлов")
                else:
                    ok, error = force_remove_path(app_logs)
                    if ok:
                        messages.append(f"  • Логи удалены: {app_logs}")
                    else:
                        messages.append(f"  • ОШИБКА: не удалось удалить логи {app_logs}: {error}")
                        success = False
                        paths_to_verify.append(app_logs)
            else:
                messages.append(f"  • Логи не найдены")
    
    else:
        messages.append("\nПОЛНАЯ ОЧИСТКА SIMPLEWORKERNET")
        
        # Удаление всей конфигурации
        if mode in ('all', 'config') and roots['config_root'].exists():
            config_size = sum(f.stat().st_size for f in roots['config_root'].rglob('*') if f.is_file()) / 1024
            if dry_run:
                messages.append(f"  • Вся конфигурация будет удалена: {roots['config_root']} ({config_size:.1f} KB)")
            else:
                ok, error = force_remove_path(roots['config_root'])
                if ok:
                    messages.append(f"  • Вся конфигурация удалена: {roots['config_root']}")
                else:
                    messages.append(f"  • ОШИБКА: не удалось удалить конфигурацию {roots['config_root']}: {error}")
                    success = False
                    paths_to_verify.append(roots['config_root'])
        
        # Удаление всего кэша
        if mode in ('all', 'cache') and roots['cache_root'].exists():
            cache_files = find_cache_files(roots['cache_root'])
            cache_size = sum(f.stat().st_size for f in cache_files) / 1024
            if dry_run:
                messages.append(f"  • Весь кэш будет удален: {roots['cache_root']} ({cache_size:.1f} KB)")
                for cf in cache_files[:5]:
                    try:
                        rel_path = cf.relative_to(roots['cache_root'])
                        messages.append(f"      - {rel_path}")
                    except:
                        messages.append(f"      - {cf.name}")
                if len(cache_files) > 5:
                    messages.append(f"      ... и еще {len(cache_files) - 5} файлов")
            else:
                app_dirs = []
                try:
                    app_dirs = [d for d in roots['cache_root'].iterdir() if d.is_dir()]
                except:
                    pass
                
                all_apps_deleted = True
                for app_dir in app_dirs:
                    ok, error = force_remove_path(app_dir)
                    if ok:
                        messages.append(f"  • Удален кэш приложения: {app_dir.name}")
                    else:
                        messages.append(f"  • ОШИБКА: не удалось удалить кэш приложения {app_dir.name}: {error}")
                        all_apps_deleted = False
                        paths_to_verify.append(app_dir)
                
                if all_apps_deleted and roots['cache_root'].exists():
                    ok, error = force_remove_path(roots['cache_root'])
                    if ok:
                        messages.append(f"  • Корневая директория кэша удалена: {roots['cache_root']}")
                    else:
                        messages.append(f"  • ОШИБКА: не удалось удалить корневую директорию кэша {roots['cache_root']}: {error}")
                        success = False
                        paths_to_verify.append(roots['cache_root'])
                elif not all_apps_deleted:
                    success = False
        
        # Удаление всех логов
        if mode in ('all', 'logs') and roots['logs_root'].exists():
            log_files = list(roots['logs_root'].rglob('*.log'))
            log_size = sum(f.stat().st_size for f in log_files) / 1024
            if dry_run:
                messages.append(f"  • Все логи будут удалены: {roots['logs_root']} ({log_size:.1f} KB)")
                for lf in log_files[:5]:
                    try:
                        rel_path = lf.relative_to(roots['logs_root'])
                        messages.append(f"      - {rel_path}")
                    except:
                        messages.append(f"      - {lf.name}")
                if len(log_files) > 5:
                    messages.append(f"      ... и еще {len(log_files) - 5} файлов")
            else:
                ok, error = force_remove_path(roots['logs_root'])
                if ok:
                    messages.append(f"  • Все логи удалены: {roots['logs_root']}")
                else:
                    messages.append(f"  • ОШИБКА: не удалось удалить логи {roots['logs_root']}: {error}")
                    success = False
                    paths_to_verify.append(roots['logs_root'])
    
    # Финальная проверка
    if not dry_run and paths_to_verify:
        still_exist = [p for p in paths_to_verify if p.exists()]
        if still_exist:
            messages.append("\n  ВНИМАНИЕ! Следующие пути все еще существуют:")
            for p in still_exist:
                messages.append(f"    • {p}")
            success = False
    
    return success, messages


def cleanup_with_confirmation(
    force: bool = False,
    mode: CleanupMode = 'all',
    app_name: Optional[str] = None,
    list_apps: bool = False
) -> bool:
    """Очистка с запросом подтверждения."""

    os.environ.pop('SIMPLEWORKERNET_CLEANUP', None)

    if list_apps:
        print("\n" + "=" * 60)
        print("УСТАНОВЛЕННЫЕ ПРИЛОЖЕНИЯ SIMPLEWORKERNET")
        print("=" * 60)
        
        apps = list_applications()
        if not apps:
            print("\nПриложения не найдены.")
            return True
        
        total_config = total_cache = total_logs = 0
        for app in sorted(apps):
            info = get_app_info(app)
            print(f"\n  {app}:")
            if info['has_config']:
                status = " (кэш ВКЛ)" if info['cache_enabled'] else " (кэш ВЫКЛ)"
                print(f"    • Конфигурация: {info['config_size']:.1f} KB{status}")
                total_config += info['config_size']
            if info['has_cache']:
                print(f"    • Кэш: {info['cache_size']:.1f} KB ({len(info['cache_files'])} файлов)")
                total_cache += info['cache_size']
            if info['has_logs']:
                log_count = len(list(info['logs_path'].glob('*.log'))) if info['logs_path'].exists() else 0
                print(f"    • Логи: {info['logs_size']:.1f} KB ({log_count} файлов)")
                total_logs += info['logs_size']
        
        print("\n" + "-" * 60)
        print(f"ВСЕГО: Конфигурация: {total_config:.1f} KB, Кэш: {total_cache:.1f} KB, Логи: {total_logs:.1f} KB")
        print(f"Общий размер: {total_config + total_cache + total_logs:.1f} KB")
        print("=" * 60)
        return True
    
    mode_desc = {'all': 'ВСЕХ приложений (ПОЛНАЯ ОЧИСТКА)', 'logs': 'логов', 'cache': 'кэша', 'config': 'конфигурации'}
    action = f"для приложения '{app_name}'" if app_name else f"для {mode_desc[mode]}"
    print("=" * 60)
    print(f"ОЧИСТКА SIMPLEWORKERNET {action}")
    print("=" * 60)
    
    success, messages = cleanup(dry_run=True, mode=mode, app_name=app_name)
    print("\nБудет удалено:\n")
    for msg in messages:
        print(f"  {msg}")
    
    if not force:
        print()
        resp = input("\nВы уверены, что хотите удалить эти данные? (y/N): ").strip().lower()
        if resp not in ('y', 'yes', 'д', 'да'):
            print("\nОчистка отменена")
            return False
    
    print("\nВыполнение очистки...")
    success, messages = cleanup(dry_run=False, mode=mode, app_name=app_name, disable_cache_first=True)
    
    print("\n" + "=" * 60)
    for msg in messages:
        print(f"  {msg}")
    print("=" * 60)
    
    # Финальная проверка
    if success:
        time.sleep(2)
        roots = get_simpleworkernet_root_dirs()
        new_files = []
        if app_name:
            if (roots['cache_root'] / app_name).exists():
                new_files.extend(find_cache_files(roots['cache_root'] / app_name))
        else:
            if roots['cache_root'].exists():
                new_files.extend(find_cache_files(roots['cache_root']))
        
        if new_files:
            print(f"\n⚠️  ВНИМАНИЕ: Обнаружены новые файлы кэша ({len(new_files)} шт.)")
            print("   Возможно, какой-то процесс создал их заново. Рекомендуется закрыть все программы,")
            print("   использующие SimpleWorkerNet, и повторить очистку.")
            success = False
        else:
            print("\n✅ Очистка успешно завершена")
    else:
        print("\n❌ Очистка завершена с ошибками")
        print("\nВозможные причины: файлы используются другим процессом, недостаточно прав, антивирус.")
        print("\nРекомендации: закройте программы, запустите от имени администратора или удалите вручную:")
        roots = get_simpleworkernet_root_dirs()
        if app_name:
            for p in [roots['config_root'] / app_name, roots['cache_root'] / app_name, roots['logs_root'] / app_name / 'logs']:
                if p.exists():
                    print(f"    rmdir /s /q \"{p}\"")
        else:
            for p in [roots['config_root'], roots['cache_root'], roots['logs_root']]:
                if p.exists():
                    print(f"    rmdir /s /q \"{p}\"")
    
    return success


def main():
    parser = argparse.ArgumentParser(description="SimpleWorkerNet cleanup tool")
    parser.add_argument('--force', '-f', action='store_true', help='принудительная очистка без подтверждения')
    parser.add_argument('--logs-only', action='store_true', help='очистить только логи')
    parser.add_argument('--cache-only', action='store_true', help='очистить только кэш')
    parser.add_argument('--config-only', action='store_true', help='очистить только конфигурацию')
    parser.add_argument('--dry-run', action='store_true', help='показать, что будет удалено, без удаления')
    parser.add_argument('--list', '-l', action='store_true', help='показать список установленных приложений')
    parser.add_argument('--app', '-a', type=str, help='имя приложения для очистки')
    
    args = parser.parse_args()
    
    if args.list:
        return 0 if cleanup_with_confirmation(list_apps=True) else 1
    
    mode: CleanupMode
    if args.logs_only:
        mode = 'logs'
    elif args.cache_only:
        mode = 'cache'
    elif args.config_only:
        mode = 'config'
    else:
        mode = 'all'
    
    return 0 if cleanup_with_confirmation(force=args.force, mode=mode, app_name=args.app) else 1


if __name__ == "__main__":
    sys.exit(main())