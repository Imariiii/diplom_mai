"""
Анализатор SQL запросов для определения write-операций и затронутых таблиц
"""
import re
from typing import List, Set, Dict


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
    
    def classify_queries(self, queries: List[str]) -> Dict[str, Set[str]]:
        """
        Классифицировать запросы по типам операций для каждой таблицы
        
        Args:
            queries: Список SQL запросов
            
        Returns:
            Словарь {table_name: {operation_types}}
            Например: {"film": {"UPDATE"}, "customer": {"UPDATE", "DELETE"}}
        """
        classification: Dict[str, Set[str]] = {}
        
        for query in queries:
            normalized = self._normalize_query(query)
            
            for op_type, pattern in self.TABLE_PATTERNS.items():
                if op_type in normalized.upper():
                    match = pattern.search(normalized)
                    if match:
                        table_name = match.group(1).lower()
                        if table_name not in classification:
                            classification[table_name] = set()
                        classification[table_name].add(op_type.upper())
        
        return classification
    
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
    
    def analyze_scenario(self, queries: List[str]) -> Dict:
        """
        Полный анализ сценария
        
        Args:
            queries: Список SQL запросов сценария
            
        Returns:
            Словарь с результатами анализа:
            {
                "has_write_operations": bool,
                "affected_tables": [str],
                "table_operations": {table: [operations]},
                "total_queries": int,
                "write_queries": int
            }
        """
        has_write = self.has_write_operations(queries)
        affected_tables = self.extract_affected_tables(queries)
        table_ops = self.classify_queries(queries)
        
        write_count = sum(1 for q in queries if self._is_write_query(q))
        
        return {
            "has_write_operations": has_write,
            "affected_tables": sorted(list(affected_tables)),
            "table_operations": {k: sorted(list(v)) for k, v in table_ops.items()},
            "total_queries": len(queries),
            "write_queries": write_count
        }
