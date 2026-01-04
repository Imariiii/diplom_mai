"""
Модуль для создания графиков и визуализации результатов тестирования
"""
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import List, Dict
import os
from datetime import datetime


class ResultVisualizer:
    """Класс для визуализации результатов тестирования"""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        sns.set_style("darkgrid")
        plt.rcParams['figure.figsize'] = (12, 6)
        plt.rcParams['font.size'] = 10
        plt.rcParams['figure.facecolor'] = '#1e1e1e'  # Темный фон
        plt.rcParams['axes.facecolor'] = '#2d2d2d'  # Темный фон для осей
        plt.rcParams['text.color'] = 'white'  # Белый текст
        plt.rcParams['axes.labelcolor'] = 'white'  # Белые подписи осей
        plt.rcParams['xtick.color'] = 'white'  # Белые метки по X
        plt.rcParams['ytick.color'] = 'white'  # Белые метки по Y
        plt.rcParams['axes.edgecolor'] = 'white'  # Белые границы осей
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.color'] = '#404040'  # Серые линии сетки
    
    def create_comparison_chart(self, results: List[Dict], filename: str = None) -> str:
        """Создание графика сравнения производительности"""
        if filename is None:
            filename = f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        # Подготовка данных
        data = []
        for result in results:
            query_id = result['query_id']
            comparison = result.get('comparison', {})
            
            for db_type, stats in comparison.items():
                if 'avg_time_ms' in stats:
                    data.append({
                        'query_id': query_id,
                        'db_type': db_type,
                        'avg_time_ms': stats['avg_time_ms'],
                        'min_time_ms': stats.get('min_time_ms', 0),
                        'max_time_ms': stats.get('max_time_ms', 0)
                    })
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Создание графика
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Группировка по query_id и db_type
        pivot_df = df.pivot(index='query_id', columns='db_type', values='avg_time_ms')
        
        pivot_df.plot(kind='bar', ax=ax, width=0.8)
        
        ax.set_xlabel('Запрос', fontsize=12, color='white')
        ax.set_ylabel('Среднее время выполнения (мс)', fontsize=12, color='white')
        ax.set_title('Сравнение производительности БД', fontsize=14, fontweight='bold', color='white')
        legend = ax.legend(title='СУБД', title_fontsize=11, facecolor='#2d2d2d', edgecolor='white')
        legend.get_title().set_color('white')
        for text in legend.get_texts():
            text.set_color('white')
        ax.grid(axis='y', alpha=0.3, color='#404040')
        plt.xticks(rotation=45, ha='right', color='white')
        plt.tight_layout()
        
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def create_statistics_chart(self, results: List[Dict], filename: str = None) -> str:
        """Создание графика статистики"""
        if filename is None:
            filename = f"statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        # Подготовка данных
        stats_data = []
        for result in results:
            comparison = result.get('comparison', {})
            for db_type, stats in comparison.items():
                if 'avg_time_ms' in stats:
                    stats_data.append({
                        'db_type': db_type,
                        'avg': stats['avg_time_ms'],
                        'min': stats.get('min_time_ms', 0),
                        'max': stats.get('max_time_ms', 0)
                    })
        
        if not stats_data:
            return None
        
        df = pd.DataFrame(stats_data)
        
        # Группировка по db_type
        grouped = df.groupby('db_type').agg({
            'avg': 'mean',
            'min': 'mean',
            'max': 'mean'
        }).reset_index()
        
        # Создание графика
        fig, ax = plt.subplots(figsize=(10, 6))
        
        x = range(len(grouped))
        width = 0.25
        
        ax.bar([i - width for i in x], grouped['min'], width, label='Мин', alpha=0.8)
        ax.bar(x, grouped['avg'], width, label='Среднее', alpha=0.8)
        ax.bar([i + width for i in x], grouped['max'], width, label='Макс', alpha=0.8)
        
        ax.set_xlabel('СУБД', fontsize=12, color='white')
        ax.set_ylabel('Время выполнения (мс)', fontsize=12, color='white')
        ax.set_title('Статистика производительности', fontsize=14, fontweight='bold', color='white')
        ax.set_xticks(x)
        ax.set_xticklabels(grouped['db_type'], color='white')
        legend = ax.legend(facecolor='#2d2d2d', edgecolor='white')
        for text in legend.get_texts():
            text.set_color('white')
        ax.grid(axis='y', alpha=0.3, color='#404040')
        plt.tight_layout()
        
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def create_summary_report(self, results: List[Dict], filename: str = None) -> str:
        """Создание текстового отчета"""
        if filename is None:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("ОТЧЕТ О РЕЗУЛЬТАТАХ НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for result in results:
                query_id = result['query_id']
                comparison = result.get('comparison', {})
                
                f.write(f"\nЗапрос: {query_id}\n")
                f.write("-" * 60 + "\n")
                
                for db_type, stats in comparison.items():
                    f.write(f"\n{db_type.upper()}:\n")
                    if 'avg_time_ms' in stats:
                        f.write(f"  Среднее время: {stats['avg_time_ms']:.2f} мс\n")
                        f.write(f"  Мин. время: {stats.get('min_time_ms', 0):.2f} мс\n")
                        f.write(f"  Макс. время: {stats.get('max_time_ms', 0):.2f} мс\n")
                        f.write(f"  Успешных запросов: {stats.get('successful', 0)}\n")
                        f.write(f"  Неудачных запросов: {stats.get('failed', 0)}\n")
                    else:
                        f.write(f"  Ошибка: {stats.get('error', 'Неизвестная ошибка')}\n")
        
        return filepath

