"""
Анализатор SQL запросов для определения write-операций и затронутых таблиц
"""
import re
from typing import List, Set


class QueryAnalyzer:
    """Класс для анализа SQL запросов"""
    
    # Паттерны для write-операций (в порядке приоритета)
    WRITE_PATTERNS = [
        r'\bUPDATE\b',
        r'\bINSERT\b',
        r'\bDELETE\b',
        r'\bTRUNCATE\b',
        r'\bREPLACE\b',
        r'\bMERGE\b',
        r'\bUPSERT\b',
        r'\bCOPY\s+INTO\b',
    ]
    
    # Паттерны для извлечения имён таблиц
    TABLE_PATTERNS = {
        'UPDATE': re.compile(r'UPDATE\s+(?:`?)(\w+)(?:`?)', re.IGNORECASE),
        'INSERT': re.compile(r'INSERT\s+INTO\s+(?:`?)(\w+)(?:`?)', re.IGNORECASE),
        'DELETE': re.compile(r'DELETE\s+FROM\s+(?:`?)(\w+)(?:`?)', re.IGNORECASE),
        'TRUNCATE': re.compile(r'TRUNCATE\s+(?:TABLE\s+)?(?:`?)(\w+)(?:`?)', re.IGNORECASE),
        'REPLACE': re.compile(r'REPLACE\s+INTO\s+(?:`?)(\w+)(?:`?)', re.IGNORECASE),
        'MERGE': re.compile(r'MERGE\s+INTO\s+(?:`?)(\w+)(?:`?)', re.IGNORECASE),
    }
    
    def __init__(self):
        self._write_regex = re.compile('|'.join(self.WRITE_PATTERNS), re.IGNORECASE)
    
    def has_write_operations(self, queries: List[str]) -> bool:
        """
        Быстрая проверка: есть ли write-операции в списке запросов
        
        Args:
            queries: Список SQL запросов
            
        Returns:
            True если есть хотя бы один write-запрос
        """
        for query in queries:
            if self._is_write_query(query):
                return True
        return False
    
    def _is_write_query(self, query: str) -> bool:
        """Проверить, является ли запрос write-операцией"""
        # Нормализуем запрос: убираем лишние пробелы, комментарии
        normalized = self._normalize_query(query)
        return bool(self._write_regex.search(normalized))
    
    def extract_affected_tables(self, queries: List[str]) -> Set[str]:
        """
        Извлечь имена затронутых таблиц из write-запросов
        
        Args:
            queries: Список SQL запросов
            
        Returns:
            Множество имён таблиц (в нижнем регистре)
        """
        tables = set()
        
        for query in queries:
            if not self._is_write_query(query):
                continue
                
            normalized = self._normalize_query(query)
            query_tables = self._extract_tables_from_query(normalized)
            tables.update(query_tables)
        
        return tables
    
    def _normalize_query(self, query: str) -> str:
        """
        Нормализовать SQL запрос для анализа
        
        - Убирает SQL комментарии (-- и /* */)
        - Убирает лишние пробелы
        - Сохраняет именованные параметры (:name)
        """
        # Убираем однострочные комментарии
        query = re.sub(r'--[^\n]*', '', query)
        # Убираем многострочные комментарии
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        # Убираем лишние пробелы
        query = ' '.join(query.split())
        return query.strip()
    
    def _extract_tables_from_query(self, query: str) -> Set[str]:
        """Извлечь имена таблиц из одного нормализованного запроса"""
        tables = set()
        
        for pattern in self.TABLE_PATTERNS.values():
            match = pattern.search(query)
            if match:
                table_name = match.group(1).lower()
                tables.add(table_name)
        
        return tables
