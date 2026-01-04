"""
Backend API для системы нагрузочного тестирования
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_tester.tester import LoadTester
from visualizer.charts import ResultVisualizer
from database.connection import DatabaseConnection
from database.queries import QueryManager

app = FastAPI(title="Database Load Testing API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модели данных
class TestRequest(BaseModel):
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10


class TestResult(BaseModel):
    query_id: str
    comparison: Dict
    timestamp: str


# Инициализация компонентов
tester = LoadTester()
visualizer = ResultVisualizer()
db_connection = DatabaseConnection()
query_manager = QueryManager()


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "Database Load Testing API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    mysql_status = db_connection.test_connection("mysql")
    postgres_status = db_connection.test_connection("postgresql")
    
    return {
        "status": "ok",
        "mysql": "connected" if mysql_status else "disconnected",
        "postgresql": "connected" if postgres_status else "disconnected"
    }


@app.get("/queries")
async def get_queries():
    """Получить список всех доступных запросов"""
    return query_manager.get_all_queries()


@app.get("/queries/{query_id}")
async def get_query(query_id: str):
    """Получить конкретный запрос"""
    try:
        return query_manager.get_query(query_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/test/single", response_model=TestResult)
async def run_single_test(request: TestRequest):
    """Запуск теста для одного запроса"""
    try:
        if request.query_id is None:
            queries = query_manager.get_all_queries()
            if not queries:
                raise HTTPException(status_code=400, detail="Нет доступных запросов")
            request.query_id = queries[0]['id']
        
        result = await tester.run_comparison_test(
            request.query_id,
            request.db_types,
            request.iterations
        )
        
        return TestResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/full")
async def run_full_test(request: TestRequest):
    """Запуск полного набора тестов"""
    try:
        results = await tester.run_full_test_suite(
            request.db_types,
            request.iterations
        )
        
        # Создание визуализаций
        comparison_chart = visualizer.create_comparison_chart(results)
        statistics_chart = visualizer.create_statistics_chart(results)
        report = visualizer.create_summary_report(results)
        
        return {
            "results": results,
            "charts": {
                "comparison": comparison_chart,
                "statistics": statistics_chart,
                "report": report
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/charts")
async def get_charts():
    """Получить список созданных графиков"""
    charts_dir = visualizer.output_dir
    charts = []
    
    if os.path.exists(charts_dir):
        for filename in os.listdir(charts_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                charts.append({
                    "filename": filename,
                    "path": os.path.join(charts_dir, filename)
                })
    
    return {"charts": charts}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

