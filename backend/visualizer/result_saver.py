"""
Модуль для сохранения результатов тестирования в различных форматах
"""
import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd


class ResultSaver:
    """Класс для сохранения результатов тестирования"""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Создаем поддиректории
        self.json_dir = os.path.join(output_dir, "json")
        self.csv_dir = os.path.join(output_dir, "csv")
        self.reports_dir = os.path.join(output_dir, "reports")
        self.charts_dir = os.path.join(output_dir, "charts")
        
        for dir_path in [self.json_dir, self.csv_dir, self.reports_dir, self.charts_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def generate_test_id(self) -> str:
        """Генерация уникального ID теста"""
        return datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def save_full_test_results(
        self,
        test_id: str,
        config: Dict[str, Any],
        results: List[Dict],
        system_metrics: Optional[Dict] = None,
        dbms_metrics: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Сохранение полных результатов теста во всех форматах
        
        Returns:
            Dict с путями ко всем созданным файлам
        """
        saved_files = {}
        
        # 1. Сохраняем полный JSON
        json_path = self.save_json(test_id, config, results, system_metrics, dbms_metrics)
        saved_files['json'] = json_path
        
        # 2. Сохраняем CSV с метриками
        csv_paths = self.save_csv(test_id, results)
        saved_files.update(csv_paths)
        
        # 3. Сохраняем детальный текстовый отчет
        report_path = self.save_detailed_report(test_id, config, results, system_metrics, dbms_metrics)
        saved_files['report'] = report_path
        
        # 4. Сохраняем markdown отчет
        md_path = self.save_markdown_report(test_id, config, results, system_metrics, dbms_metrics)
        saved_files['markdown'] = md_path
        
        # 5. Сохраняем конфигурацию теста отдельно
        config_path = self.save_config(test_id, config)
        saved_files['config'] = config_path
        
        return saved_files
    
    def save_json(
        self,
        test_id: str,
        config: Dict[str, Any],
        results: List[Dict],
        system_metrics: Optional[Dict] = None,
        dbms_metrics: Optional[Dict] = None
    ) -> str:
        """Сохранение результатов в JSON"""
        data = {
            'test_id': test_id,
            'timestamp': datetime.now().isoformat(),
            'config': config,
            'results': results,
            'system_metrics': system_metrics or {},
            'dbms_metrics': dbms_metrics or {},
            'summary': self._calculate_summary(results)
        }
        
        filepath = os.path.join(self.json_dir, f"test_{test_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        return filepath
    
    def save_csv(self, test_id: str, results: List[Dict]) -> Dict[str, str]:
        """Сохранение результатов в CSV"""
        saved_files = {}
        
        # CSV с основными метриками
        metrics_data = []
        for result in results:
            query_id = result.get('query_id', 'unknown')
            comparison = result.get('comparison', {})
            
            for db_type, stats in comparison.items():
                row = {
                    'test_id': test_id,
                    'timestamp': result.get('timestamp', ''),
                    'query_id': query_id,
                    'db_type': db_type,
                    'iterations': stats.get('iterations', 0),
                    'virtual_users': stats.get('virtual_users', 1),
                    'scenario': stats.get('scenario', ''),
                    'successful': stats.get('successful', 0),
                    'failed': stats.get('failed', 0),
                    'avg_time_ms': stats.get('avg_time_ms', 0),
                    'min_time_ms': stats.get('min_time_ms', 0),
                    'max_time_ms': stats.get('max_time_ms', 0),
                    'p50_time_ms': stats.get('p50_time_ms', 0),
                    'p95_time_ms': stats.get('p95_time_ms', 0),
                    'p99_time_ms': stats.get('p99_time_ms', 0),
                    'tps': stats.get('tps', 0),
                    'throughput': stats.get('throughput', 0),
                    'error_rate': stats.get('error_rate', 0),
                    'active_connections': stats.get('active_connections', 0),
                }
                metrics_data.append(row)
        
        if metrics_data:
            metrics_path = os.path.join(self.csv_dir, f"metrics_{test_id}.csv")
            df = pd.DataFrame(metrics_data)
            df.to_csv(metrics_path, index=False, encoding='utf-8')
            saved_files['csv_metrics'] = metrics_path
        
        # CSV для сравнительного анализа
        comparison_data = self._prepare_comparison_data(results)
        if comparison_data:
            comparison_path = os.path.join(self.csv_dir, f"comparison_{test_id}.csv")
            df = pd.DataFrame(comparison_data)
            df.to_csv(comparison_path, index=False, encoding='utf-8')
            saved_files['csv_comparison'] = comparison_path
        
        return saved_files
    
    def save_config(self, test_id: str, config: Dict[str, Any]) -> str:
        """Сохранение конфигурации теста"""
        filepath = os.path.join(self.json_dir, f"config_{test_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False, default=str)
        return filepath
    
    def save_detailed_report(
        self,
        test_id: str,
        config: Dict[str, Any],
        results: List[Dict],
        system_metrics: Optional[Dict] = None,
        dbms_metrics: Optional[Dict] = None
    ) -> str:
        """Сохранение детального текстового отчета"""
        filepath = os.path.join(self.reports_dir, f"report_{test_id}.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("           ДЕТАЛЬНЫЙ ОТЧЕТ О НАГРУЗОЧНОМ ТЕСТИРОВАНИИ\n")
            f.write("=" * 80 + "\n\n")
            
            # Информация о тесте
            f.write(f"ID теста: {test_id}\n")
            f.write(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            
            # Конфигурация
            f.write("-" * 80 + "\n")
            f.write("КОНФИГУРАЦИЯ ТЕСТА\n")
            f.write("-" * 80 + "\n")
            f.write(f"  СУБД: {', '.join(config.get('db_types', []))}\n")
            f.write(f"  Сценарий: {config.get('scenario', 'N/A')}\n")
            f.write(f"  Длительность: {config.get('duration', 'N/A')} сек\n")
            f.write(f"  Виртуальных пользователей: {config.get('virtual_users', 'N/A')}\n")
            f.write(f"  Итераций: {config.get('iterations', 'N/A')}\n")
            f.write(f"  Время прогрева: {config.get('warmup_time', 'N/A')} сек\n")
            f.write("\n")
            
            # Результаты по каждому запросу
            f.write("-" * 80 + "\n")
            f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ\n")
            f.write("-" * 80 + "\n")
            
            for result in results:
                query_id = result.get('query_id', 'unknown')
                comparison = result.get('comparison', {})
                
                f.write(f"\n{'='*40}\n")
                f.write(f"Запрос: {query_id}\n")
                f.write(f"{'='*40}\n")
                
                for db_type, stats in comparison.items():
                    f.write(f"\n  [{db_type.upper()}]\n")
                    
                    if stats.get('error'):
                        f.write(f"    ОШИБКА: {stats['error']}\n")
                        continue
                    
                    # Время отклика
                    f.write("    Время отклика:\n")
                    f.write(f"      Среднее (avg): {stats.get('avg_time_ms', 0):.3f} мс\n")
                    f.write(f"      Минимум (min): {stats.get('min_time_ms', 0):.3f} мс\n")
                    f.write(f"      Максимум (max): {stats.get('max_time_ms', 0):.3f} мс\n")
                    f.write(f"      Медиана (p50):  {stats.get('p50_time_ms', 0):.3f} мс\n")
                    f.write(f"      p95:            {stats.get('p95_time_ms', 0):.3f} мс\n")
                    f.write(f"      p99:            {stats.get('p99_time_ms', 0):.3f} мс\n")
                    
                    # Производительность
                    f.write("    Производительность:\n")
                    f.write(f"      TPS: {stats.get('tps', 0):.2f} транзакций/сек\n")
                    f.write(f"      Throughput: {stats.get('throughput', 0):.2f} req/sec\n")
                    
                    # Транзакции
                    f.write("    Транзакции:\n")
                    f.write(f"      Всего итераций: {stats.get('iterations', 0)}\n")
                    f.write(f"      Успешных: {stats.get('successful', 0)}\n")
                    f.write(f"      Неудачных: {stats.get('failed', 0)}\n")
                    f.write(f"      Error Rate: {stats.get('error_rate', 0):.2f}%\n")
                    
                    # Соединения
                    f.write("    Соединения:\n")
                    f.write(f"      Активных: {stats.get('active_connections', 0)}\n")
            
            # Системные метрики
            if system_metrics:
                f.write("\n" + "-" * 80 + "\n")
                f.write("СИСТЕМНЫЕ МЕТРИКИ\n")
                f.write("-" * 80 + "\n")
                for db_type, metrics in system_metrics.items():
                    f.write(f"\n  [{db_type.upper()}]\n")
                    f.write(f"    CPU: {metrics.get('cpu_usage', 0):.1f}%\n")
                    f.write(f"    RAM: {metrics.get('memory_usage_mb', 0):.1f} MB ({metrics.get('memory_usage_percent', 0):.1f}%)\n")
                    f.write(f"    Disk IOPS: {metrics.get('disk_iops', 0)}\n")
                    f.write(f"    Network In: {metrics.get('network_in_mbps', 0):.2f} MB/s\n")
                    f.write(f"    Network Out: {metrics.get('network_out_mbps', 0):.2f} MB/s\n")
            
            # Внутренние метрики СУБД
            if dbms_metrics:
                f.write("\n" + "-" * 80 + "\n")
                f.write("ВНУТРЕННИЕ МЕТРИКИ СУБД\n")
                f.write("-" * 80 + "\n")
                for db_type, metrics in dbms_metrics.items():
                    f.write(f"\n  [{db_type.upper()}]\n")
                    f.write(f"    Cache Hit Ratio: {metrics.get('cache_hit_ratio', 0):.1f}%\n")
                    f.write(f"    Buffer Pool Hit: {metrics.get('buffer_pool_hit_ratio', 0):.1f}%\n")
                    f.write(f"    Lock Waits: {metrics.get('lock_waits', 0)}\n")
                    f.write(f"    Deadlocks: {metrics.get('deadlocks', 0)}\n")
                    f.write(f"    Active Connections: {metrics.get('active_connections', 0)}\n")
                    f.write(f"    Total DB Size: {metrics.get('total_db_size_mb', 0):.2f} MB\n")
            
            # Сводка
            summary = self._calculate_summary(results)
            f.write("\n" + "-" * 80 + "\n")
            f.write("СВОДКА\n")
            f.write("-" * 80 + "\n")
            f.write(f"  Всего запросов протестировано: {summary.get('total_queries', 0)}\n")
            f.write(f"  Всего транзакций: {summary.get('total_transactions', 0)}\n")
            f.write(f"  Успешных: {summary.get('total_successful', 0)}\n")
            f.write(f"  Неудачных: {summary.get('total_failed', 0)}\n")
            f.write(f"  Общий Success Rate: {summary.get('success_rate', 0):.2f}%\n")
            
            if summary.get('fastest_db'):
                f.write(f"\n  Самая быстрая СУБД: {summary['fastest_db']}\n")
                f.write(f"  Среднее время: {summary.get('fastest_avg_time', 0):.3f} мс\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("                         КОНЕЦ ОТЧЕТА\n")
            f.write("=" * 80 + "\n")
        
        return filepath
    
    def save_markdown_report(
        self,
        test_id: str,
        config: Dict[str, Any],
        results: List[Dict],
        system_metrics: Optional[Dict] = None,
        dbms_metrics: Optional[Dict] = None
    ) -> str:
        """Сохранение отчета в формате Markdown"""
        filepath = os.path.join(self.reports_dir, f"report_{test_id}.md")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Отчет о нагрузочном тестировании\n\n")
            f.write(f"**ID теста:** `{test_id}`\n\n")
            f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Конфигурация
            f.write("## Конфигурация теста\n\n")
            f.write("| Параметр | Значение |\n")
            f.write("|----------|----------|\n")
            f.write(f"| СУБД | {', '.join(config.get('db_types', []))} |\n")
            f.write(f"| Сценарий | {config.get('scenario', 'N/A')} |\n")
            f.write(f"| Длительность | {config.get('duration', 'N/A')} сек |\n")
            f.write(f"| Виртуальные пользователи | {config.get('virtual_users', 'N/A')} |\n")
            f.write(f"| Итерации | {config.get('iterations', 'N/A')} |\n")
            f.write(f"| Время прогрева | {config.get('warmup_time', 'N/A')} сек |\n\n")
            
            # Сводная таблица результатов
            f.write("## Сводные результаты\n\n")
            f.write("| СУБД | Avg (мс) | p50 (мс) | p95 (мс) | p99 (мс) | TPS | Успешных | Ошибок |\n")
            f.write("|------|----------|----------|----------|----------|-----|----------|--------|\n")
            
            db_summary = {}
            for result in results:
                comparison = result.get('comparison', {})
                for db_type, stats in comparison.items():
                    if db_type not in db_summary:
                        db_summary[db_type] = {
                            'times': [], 'p50': [], 'p95': [], 'p99': [],
                            'tps': [], 'successful': 0, 'failed': 0
                        }
                    if stats.get('avg_time_ms'):
                        db_summary[db_type]['times'].append(stats['avg_time_ms'])
                        db_summary[db_type]['p50'].append(stats.get('p50_time_ms', 0))
                        db_summary[db_type]['p95'].append(stats.get('p95_time_ms', 0))
                        db_summary[db_type]['p99'].append(stats.get('p99_time_ms', 0))
                        db_summary[db_type]['tps'].append(stats.get('tps', 0))
                        db_summary[db_type]['successful'] += stats.get('successful', 0)
                        db_summary[db_type]['failed'] += stats.get('failed', 0)
            
            for db_type, data in db_summary.items():
                if data['times']:
                    avg = sum(data['times']) / len(data['times'])
                    p50 = sum(data['p50']) / len(data['p50'])
                    p95 = sum(data['p95']) / len(data['p95'])
                    p99 = sum(data['p99']) / len(data['p99'])
                    tps = sum(data['tps']) / len(data['tps'])
                    f.write(f"| {db_type} | {avg:.3f} | {p50:.3f} | {p95:.3f} | {p99:.3f} | {tps:.2f} | {data['successful']} | {data['failed']} |\n")
            
            f.write("\n")
            
            # Детальные результаты
            f.write("## Детальные результаты по запросам\n\n")
            for result in results:
                query_id = result.get('query_id', 'unknown')
                f.write(f"### {query_id}\n\n")
                
                comparison = result.get('comparison', {})
                for db_type, stats in comparison.items():
                    f.write(f"#### {db_type.upper()}\n\n")
                    
                    if stats.get('error'):
                        f.write(f"**Ошибка:** {stats['error']}\n\n")
                        continue
                    
                    f.write("| Метрика | Значение |\n")
                    f.write("|---------|----------|\n")
                    f.write(f"| Avg время | {stats.get('avg_time_ms', 0):.3f} мс |\n")
                    f.write(f"| Min время | {stats.get('min_time_ms', 0):.3f} мс |\n")
                    f.write(f"| Max время | {stats.get('max_time_ms', 0):.3f} мс |\n")
                    f.write(f"| p50 | {stats.get('p50_time_ms', 0):.3f} мс |\n")
                    f.write(f"| p95 | {stats.get('p95_time_ms', 0):.3f} мс |\n")
                    f.write(f"| p99 | {stats.get('p99_time_ms', 0):.3f} мс |\n")
                    f.write(f"| TPS | {stats.get('tps', 0):.2f} |\n")
                    f.write(f"| Успешных | {stats.get('successful', 0)} |\n")
                    f.write(f"| Неудачных | {stats.get('failed', 0)} |\n")
                    f.write(f"| Error Rate | {stats.get('error_rate', 0):.2f}% |\n\n")
            
            # Системные метрики
            if system_metrics:
                f.write("## Системные метрики\n\n")
                for db_type, metrics in system_metrics.items():
                    f.write(f"### {db_type.upper()}\n\n")
                    f.write("| Метрика | Значение |\n")
                    f.write("|---------|----------|\n")
                    f.write(f"| CPU | {metrics.get('cpu_usage', 0):.1f}% |\n")
                    f.write(f"| RAM | {metrics.get('memory_usage_mb', 0):.1f} MB |\n")
                    f.write(f"| RAM % | {metrics.get('memory_usage_percent', 0):.1f}% |\n")
                    f.write(f"| Disk IOPS | {metrics.get('disk_iops', 0)} |\n\n")
            
            # Внутренние метрики СУБД
            if dbms_metrics:
                f.write("## Внутренние метрики СУБД\n\n")
                for db_type, metrics in dbms_metrics.items():
                    f.write(f"### {db_type.upper()}\n\n")
                    f.write("| Метрика | Значение |\n")
                    f.write("|---------|----------|\n")
                    f.write(f"| Cache Hit Ratio | {metrics.get('cache_hit_ratio', 0):.1f}% |\n")
                    f.write(f"| Buffer Pool Hit | {metrics.get('buffer_pool_hit_ratio', 0):.1f}% |\n")
                    f.write(f"| Lock Waits | {metrics.get('lock_waits', 0)} |\n")
                    f.write(f"| Deadlocks | {metrics.get('deadlocks', 0)} |\n")
                    f.write(f"| Active Connections | {metrics.get('active_connections', 0)} |\n")
                    f.write(f"| Total DB Size | {metrics.get('total_db_size_mb', 0):.2f} MB |\n\n")
        
        return filepath
    
    def _calculate_summary(self, results: List[Dict]) -> Dict:
        """Вычисление сводных метрик"""
        total_queries = len(results)
        total_successful = 0
        total_failed = 0
        db_avg_times = {}
        
        for result in results:
            comparison = result.get('comparison', {})
            for db_type, stats in comparison.items():
                total_successful += stats.get('successful', 0)
                total_failed += stats.get('failed', 0)
                
                if stats.get('avg_time_ms'):
                    if db_type not in db_avg_times:
                        db_avg_times[db_type] = []
                    db_avg_times[db_type].append(stats['avg_time_ms'])
        
        total_transactions = total_successful + total_failed
        success_rate = (total_successful / total_transactions * 100) if total_transactions > 0 else 0
        
        # Определяем самую быструю СУБД
        fastest_db = None
        fastest_avg_time = float('inf')
        for db_type, times in db_avg_times.items():
            avg = sum(times) / len(times) if times else float('inf')
            if avg < fastest_avg_time:
                fastest_avg_time = avg
                fastest_db = db_type
        
        return {
            'total_queries': total_queries,
            'total_transactions': total_transactions,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'success_rate': success_rate,
            'fastest_db': fastest_db,
            'fastest_avg_time': fastest_avg_time if fastest_avg_time != float('inf') else 0,
            'db_avg_times': {k: sum(v)/len(v) for k, v in db_avg_times.items() if v}
        }
    
    def _prepare_comparison_data(self, results: List[Dict]) -> List[Dict]:
        """Подготовка данных для сравнительного анализа"""
        comparison_data = []
        
        # Собираем данные по СУБД
        db_metrics = {}
        for result in results:
            comparison = result.get('comparison', {})
            for db_type, stats in comparison.items():
                if db_type not in db_metrics:
                    db_metrics[db_type] = {
                        'times': [], 'p50': [], 'p95': [], 'p99': [],
                        'tps': [], 'successful': 0, 'failed': 0
                    }
                if stats.get('avg_time_ms'):
                    db_metrics[db_type]['times'].append(stats['avg_time_ms'])
                    db_metrics[db_type]['p50'].append(stats.get('p50_time_ms', 0))
                    db_metrics[db_type]['p95'].append(stats.get('p95_time_ms', 0))
                    db_metrics[db_type]['p99'].append(stats.get('p99_time_ms', 0))
                    db_metrics[db_type]['tps'].append(stats.get('tps', 0))
                    db_metrics[db_type]['successful'] += stats.get('successful', 0)
                    db_metrics[db_type]['failed'] += stats.get('failed', 0)
        
        # Формируем сравнительные данные
        for db_type, data in db_metrics.items():
            if data['times']:
                comparison_data.append({
                    'db_type': db_type,
                    'avg_time_ms': sum(data['times']) / len(data['times']),
                    'p50_time_ms': sum(data['p50']) / len(data['p50']),
                    'p95_time_ms': sum(data['p95']) / len(data['p95']),
                    'p99_time_ms': sum(data['p99']) / len(data['p99']),
                    'avg_tps': sum(data['tps']) / len(data['tps']),
                    'total_successful': data['successful'],
                    'total_failed': data['failed'],
                    'success_rate': (data['successful'] / (data['successful'] + data['failed']) * 100) 
                                    if (data['successful'] + data['failed']) > 0 else 0
                })
        
        return comparison_data
    
    def load_test_results(self, test_id: str) -> Optional[Dict]:
        """Загрузка результатов теста по ID"""
        filepath = os.path.join(self.json_dir, f"test_{test_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def list_all_tests(self) -> List[Dict]:
        """Получить список всех сохраненных тестов"""
        tests = []
        for filename in os.listdir(self.json_dir):
            if filename.startswith('test_') and filename.endswith('.json'):
                filepath = os.path.join(self.json_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        tests.append({
                            'test_id': data.get('test_id'),
                            'timestamp': data.get('timestamp'),
                            'config': data.get('config'),
                            'summary': data.get('summary')
                        })
                except Exception as e:
                    print(f"Ошибка чтения {filepath}: {e}")
        
        # Сортируем по времени (новые первыми)
        tests.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return tests
