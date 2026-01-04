#!/usr/bin/env python3
"""
Скрипт для быстрого запуска тестирования из командной строки
"""
import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from load_tester.tester import LoadTester
from visualizer.charts import ResultVisualizer


async def main():
    """Основная функция для запуска тестирования"""
    print("=" * 60)
    print("Система нагрузочного тестирования БД")
    print("=" * 60)
    print()
    
    # Инициализация
    tester = LoadTester()
    visualizer = ResultVisualizer()
    
    try:
        # Проверка подключений
        print("Проверка подключений к БД...")
        mysql_ok = tester.db_connection.test_connection("mysql")
        postgres_ok = tester.db_connection.test_connection("postgresql")
        
        print(f"MySQL: {'✓' if mysql_ok else '✗'}")
        print(f"PostgreSQL: {'✓' if postgres_ok else '✗'}")
        print()
        
        if not mysql_ok and not postgres_ok:
            print("Ошибка: Нет подключений к БД. Проверьте конфигурацию.")
            return
        
        # Запуск тестирования
        print("Запуск полного набора тестов...")
        print("Это может занять некоторое время...")
        print()
        
        db_types = []
        if mysql_ok:
            db_types.append("mysql")
        if postgres_ok:
            db_types.append("postgresql")
        
        results = await tester.run_full_test_suite(
            db_types=db_types,
            iterations=10
        )
        
        print()
        print("=" * 60)
        print("Результаты тестирования:")
        print("=" * 60)
        
        for result in results:
            print(f"\nЗапрос: {result['query_id']}")
            comparison = result.get('comparison', {})
            
            for db_type, stats in comparison.items():
                print(f"\n  {db_type.upper()}:")
                if 'avg_time_ms' in stats:
                    print(f"    Среднее время: {stats['avg_time_ms']:.2f} мс")
                    print(f"    Мин. время: {stats.get('min_time_ms', 0):.2f} мс")
                    print(f"    Макс. время: {stats.get('max_time_ms', 0):.2f} мс")
                    print(f"    Успешных: {stats.get('successful', 0)}")
                    print(f"    Ошибок: {stats.get('failed', 0)}")
                else:
                    print(f"    Ошибка: {stats.get('error', 'Неизвестная ошибка')}")
        
        # Создание визуализаций
        print()
        print("Создание графиков и отчетов...")
        
        comparison_chart = visualizer.create_comparison_chart(results)
        statistics_chart = visualizer.create_statistics_chart(results)
        report = visualizer.create_summary_report(results)
        
        print(f"✓ График сравнения: {comparison_chart}")
        print(f"✓ График статистики: {statistics_chart}")
        print(f"✓ Текстовый отчет: {report}")
        
        print()
        print("=" * 60)
        print("Тестирование завершено!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем.")
    except Exception as e:
        print(f"\n\nОшибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.close()


if __name__ == "__main__":
    asyncio.run(main())

