# simpleworkernet/cli.py
#!/usr/bin/env python
"""
Интерфейс командной строки для SimpleWorkerNet
"""
import sys
import argparse
from pathlib import Path

from . import __version__
from .scripts.uninstall import (
    cleanup_with_confirmation,
    cleanup,
    list_applications,
    get_app_info,
    find_cache_files
)


def main():
    """Точка входа для команды cleanup-simpleworkernet"""
    parser = argparse.ArgumentParser(
        description="Cleanup SimpleWorkerNet - инструмент очистки данных",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Очистка всех данных всех приложений
  cleanup-simpleworkernet
  
  # Очистка конкретного приложения
  cleanup-simpleworkernet --app myapp_abc123
  
  # Просмотр установленных приложений с деталями
  cleanup-simpleworkernet --list
  
  # Просмотр детальной информации о конкретном приложении
  cleanup-simpleworkernet --info --app myapp_abc123
  
  # Очистка только логов для приложения
  cleanup-simpleworkernet --app myapp_abc123 --logs-only
  
  # Очистка только кэша с просмотром файлов
  cleanup-simpleworkernet --app myapp_abc123 --cache-only --verbose
  
  # Принудительная очистка без подтверждения
  cleanup-simpleworkernet --force
  
  # Просмотр того, что будет удалено (без удаления)
  cleanup-simpleworkernet --dry-run
  
  # Показать версию
  cleanup-simpleworkernet --version
        """
    )
    
    parser.add_argument('--version', '-v', action='store_true',
                       help='показать версию')
    parser.add_argument('--force', '-f', action='store_true',
                       help='принудительная очистка без подтверждения')
    parser.add_argument('--logs-only', action='store_true',
                       help='очистить только логи')
    parser.add_argument('--cache-only', action='store_true',
                       help='очистить только кэш')
    parser.add_argument('--config-only', action='store_true',
                       help='очистить только конфигурацию')
    parser.add_argument('--dry-run', action='store_true',
                       help='показать, что будет удалено, без удаления')
    parser.add_argument('--list', '-l', action='store_true',
                       help='показать список установленных приложений')
    parser.add_argument('--info', '-i', action='store_true',
                       help='показать детальную информацию о приложении')
    parser.add_argument('--verbose', action='store_true',
                       help='подробный вывод (показывать все файлы)')
    parser.add_argument('--app', '-a', type=str,
                       help='имя приложения для очистки')
    
    args = parser.parse_args()
    
    if args.version:
        print(f"SimpleWorkerNet версия {__version__}")
        return 0
    
    # Режим просмотра информации о конкретном приложении
    if args.info:
        if not args.app:
            print("Ошибка: для --info требуется указать --app")
            return 1
        
        info = get_app_info(args.app)
        print("\n" + "=" * 60)
        print(f"ИНФОРМАЦИЯ О ПРИЛОЖЕНИИ: {args.app}")
        print("=" * 60)
        print(f"\nКонфигурация:")
        print(f"  Путь: {info['config_path']}")
        print(f"  Существует: {'Да' if info['has_config'] else 'Нет'}")
        if info['has_config']:
            print(f"  Размер: {info['config_size']:.1f} KB")
            if args.verbose:
                config_files = list(info['config_path'].rglob('*'))
                if config_files:
                    print(f"  Файлы:")
                    for f in sorted(config_files)[:10]:
                        rel = f.relative_to(info['config_path'])
                        size = f.stat().st_size / 1024 if f.is_file() else 0
                        print(f"    - {rel} ({size:.1f} KB)")
        
        print(f"\nКэш:")
        print(f"  Путь: {info['cache_path']}")
        print(f"  Существует: {'Да' if info['has_cache'] else 'Нет'}")
        if info['has_cache']:
            print(f"  Файлов: {len(info['cache_files'])}")
            print(f"  Размер: {info['cache_size']:.1f} KB")
            if args.verbose and info['cache_files']:
                print(f"  Файлы:")
                for cf in sorted(info['cache_files'])[:20]:
                    rel = cf.relative_to(info['cache_path'])
                    size = cf.stat().st_size / 1024
                    print(f"    - {rel} ({size:.1f} KB)")
        
        print(f"\nЛоги:")
        print(f"  Путь: {info['logs_path']}")
        print(f"  Существует: {'Да' if info['has_logs'] else 'Нет'}")
        if info['has_logs']:
            log_files = list(info['logs_path'].glob('*.log'))
            print(f"  Файлов: {len(log_files)}")
            print(f"  Размер: {info['logs_size']:.1f} KB")
            if args.verbose and log_files:
                print(f"  Файлы:")
                for lf in sorted(log_files)[:20]:
                    size = lf.stat().st_size / 1024
                    print(f"    - {lf.name} ({size:.1f} KB)")
        
        print("\n" + "=" * 60)
        return 0
    
    # Режим просмотра всех приложений
    if args.list:
        apps = list_applications()
        if not apps:
            print("\nПриложения не найдены.")
            return 0
        
        print("\n" + "=" * 60)
        print("УСТАНОВЛЕННЫЕ ПРИЛОЖЕНИЯ:")
        print("=" * 60)
        
        total_config = 0
        total_cache = 0
        total_logs = 0
        
        for app in sorted(apps):
            info = get_app_info(app)
            print(f"\n  {app}:")
            if info['has_config']:
                print(f"    • Конфигурация: {info['config_size']:.1f} KB")
                total_config += info['config_size']
            if info['has_cache']:
                print(f"    • Кэш: {info['cache_size']:.1f} KB ({len(info['cache_files'])} файлов)")
                total_cache += info['cache_size']
            if info['has_logs']:
                log_count = len(list(info['logs_path'].glob('*.log'))) if info['logs_path'].exists() else 0
                print(f"    • Логи: {info['logs_size']:.1f} KB ({log_count} файлов)")
                total_logs += info['logs_size']
        
        print("\n" + "-" * 60)
        print(f"ВСЕГО:")
        print(f"  Конфигурация: {total_config:.1f} KB")
        print(f"  Кэш: {total_cache:.1f} KB")
        print(f"  Логи: {total_logs:.1f} KB")
        print(f"  Общий размер: {total_config + total_cache + total_logs:.1f} KB")
        print("=" * 60)
        return 0
    
    # Определяем режим очистки
    if args.logs_only:
        mode = 'logs'
    elif args.cache_only:
        mode = 'cache'
    elif args.config_only:
        mode = 'config'
    else:
        mode = 'all'
    
    # Режим просмотра (dry run)
    if args.dry_run:
        action = f"для приложения '{args.app}'" if args.app else "для ВСЕХ приложений"
        print(f"\nРЕЖИМ ПРОСМОТРА - ничего не будет удалено {action}\n")
        
        success, messages = cleanup(
            dry_run=True, 
            mode=mode, 
            app_name=args.app
        )
        
        for msg in messages:
            print(f"  {msg}")
        
        # Если verbose, показываем детали
        if args.verbose and args.app:
            info = get_app_info(args.app)
            if mode in ('all', 'cache') and info['cache_files']:
                print(f"\n  Детали файлов кэша (первые 10):")
                for cf in sorted(info['cache_files'])[:10]:
                    rel = cf.relative_to(info['cache_path'])
                    size = cf.stat().st_size / 1024
                    print(f"    - {rel} ({size:.1f} KB)")
            
            if mode in ('all', 'logs') and info['logs_path'].exists():
                log_files = list(info['logs_path'].glob('*.log'))
                if log_files:
                    print(f"\n  Детали файлов логов (первые 10):")
                    for lf in sorted(log_files)[:10]:
                        size = lf.stat().st_size / 1024
                        print(f"    - {lf.name} ({size:.1f} KB)")
        
        return 0
    
    # Режим очистки
    success = cleanup_with_confirmation(
        force=args.force, 
        mode=mode, 
        app_name=args.app
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
