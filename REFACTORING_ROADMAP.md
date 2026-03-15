# 🔧 Roadmap рефакторинга кодовой базы

**Дата:** 16 марта 2026  
**Статус проекта:** Production-ready (логика верна, организация требует улучшений)  
**Общая оценка:** B+ → A- с рефакторингом  

---

## 📊 Итоговая оценка

### Что хорошо:
✅ **Архитектура логична** - чёткое разделение concerns (backend/frontend/database)  
✅ **Нет циклических зависимостей** - граф импортов чист  
✅ **Async/await везде** - правильное использование асинхронности  
✅ **DatabaseStateManager** - хорошо спроектированный оркестратор  
✅ **Бизнес-логика верна** - backup/restore механизм работает корректно  

### Что требует рефакторинга:
🔴 **main.py: 1328 строк** (36 функций + 19 Pydantic моделей в одном файле)  
🔴 **Большие компоненты Frontend** (dashboards: 1071 строк, scenarios: 923 строк)  
🟠 **repository.py: 726 строк** (смешаны TestRepository + ScenarioRepository)  
🟠 **sql_strategy.py: 443 строк** (backup + restore + helpers в одном классе)  
🟠 **config-page.tsx: 641 строк** (многовато для одного компонента)  

---

## 🎯 Фазы рефакторинга

### ФАЗА 1: КРИТИЧЕСКОЕ (10-12 часов) - **ВЫПОЛНИТЬ СЕЙЧАС**

#### 1️⃣ Разделить `backend/main.py` на модульную структуру

**Текущее состояние:**
```python
# backend/main.py (1328 строк)
@app.post("/api/test/run_scenario_test")
async def run_scenario_test(...): ...  # 50 строк

@app.get("/api/database/{dbms_type}/state")
async def get_database_state(...): ...  # 40 строк

class TestRequest(BaseModel): ...       # Pydantic модель
class AsyncTestRequest(BaseModel): ...  # Ещё одна модель
# ... 17 других моделей
```

**Целевое состояние:**
```
backend/
├── main.py (200-300 строк - только инициализация)
├── api/
│   ├── routes/
│   │   ├── test_routes.py        # Endpoints тестирования
│   │   ├── scenario_routes.py    # Endpoints сценариев
│   │   ├── database_state_routes.py  # Endpoints состояния БД
│   │   └── __init__.py
│   └── schemas/
│       ├── test_schemas.py       # TestRequest, AsyncTestRequest, etc.
│       ├── scenario_schemas.py   # ScenarioCreate, ScenarioUpdate, etc.
│       ├── backup_schemas.py     # BackupRequest, RestoreRequest, etc.
│       ├── settings_schemas.py   # RestoreSettings, etc.
│       └── __init__.py
```

**Новый main.py (упрощённый):**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import test_routes, scenario_routes, database_state_routes
from websocket_manager import WebSocketManager

app = FastAPI(title="Database Load Testing System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(test_routes.router)
app.include_router(scenario_routes.router)
app.include_router(database_state_routes.router)

# WebSocket and health
ws_manager = WebSocketManager()

@app.websocket("/ws/{test_id}")
async def websocket_endpoint(websocket: WebSocket, test_id: str):
    await ws_manager.connect(websocket, test_id)
    ...

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Выгода:** main.py с 1328 до 150 строк, каждый route-файл < 200 строк

---

#### 2️⃣ Разделить большие Frontend компоненты

**Текущее состояние:**
```
frontend/components/pages/
├── dashboards-page.tsx (1071 строк в одном файле)
├── scenarios-page.tsx (923 строк)
└── config-page.tsx (641 строк)
```

**Целевое состояние:**

**A. dashboards-page структура:**
```
frontend/components/pages/dashboard-page/
├── dashboards-page.tsx (400-500 строк) - основной компонент
├── metrics-section.tsx (300 строк) - таблица метрик
├── live-chart.tsx (250 строк) - RPS/latency графики
├── performance-stats.tsx (200 строк) - статистика
└── index.ts - экспорт
```

**B. scenarios-page структура:**
```
frontend/components/pages/scenarios-page/
├── scenarios-page.tsx (400-500 строк) - основной компонент
├── scenario-list.tsx (250 строк) - список сценариев
├── scenario-editor.tsx (300 строк) - редактор запросов
├── query-params.tsx (200 строк) - параметры запросов
└── index.ts - экспорт
```

**C. config-page структура:**
```
frontend/components/pages/config-page/
├── config-page.tsx (350 строк) - основной компонент
├── restore-settings.tsx (200 строк) - настройки восстановления
├── database-selector.tsx (150 строк) - выбор БД
└── index.ts - экспорт
```

**Пример разделения dashboards-page:**

```typescript
// ДО: dashboards-page.tsx (1071 строк)
export default function DashboardsPage() {
  const [metrics, setMetrics] = useState(...);
  const [stats, setStats] = useState(...);
  const [charts, setCharts] = useState(...);
  
  // 200+ строк логики для метрик
  // 200+ строк логики для статистики
  // 200+ строк логики для графиков
  // 200+ строк JSX для таблиц метрик
  // 200+ строк JSX для графиков
  
  return (
    <div>
      {/* ВСЕ В ОДНОМ */}
    </div>
  );
}

// ПОСЛЕ: разбиение на компоненты
// dashboards-page.tsx (450 строк) - орхестратор
export default function DashboardsPage() {
  const { metrics, stats } = useTestWebSocket();
  
  return (
    <div className="grid grid-cols-3 gap-4">
      <MetricsSection data={metrics} />
      <PerformanceStats data={stats} />
      <LiveChart data={metrics} />
    </div>
  );
}

// metrics-section.tsx (250 строк) - таблица метрик
export function MetricsSection({ data }: Props) {
  return (
    <Card>
      <Table>
        {/* Таблица метрик */}
      </Table>
    </Card>
  );
}

// live-chart.tsx (250 строк) - графики
export function LiveChart({ data }: Props) {
  return (
    <Card>
      <LineChart data={data} />
    </Card>
  );
}

// performance-stats.tsx (200 строк) - статистика
export function PerformanceStats({ data }: Props) {
  return <StatsSummary data={data} />;
}
```

**Выгода:** Каждый компонент становится < 500 строк, легче тестировать, переиспользовать

---

### ФАЗА 2: ВАЖНАЯ (8-10 часов) - Следующий спринт

#### 3️⃣ Разделить `backend/database/repository.py` (726 строк)

**Текущая структура:**
```python
# repository.py (726 строк)
class TestRepository:
    # 350 строк логики тестов
    async def get_test_run(self, test_id: str) -> TestRun: ...
    async def save_test_run(self, test: TestRun) -> str: ...
    async def get_test_history(self, ...) -> List[TestRun]: ...

class ScenarioRepository:
    # 350 строк логики сценариев
    async def get_scenarios(self) -> List[Scenario]: ...
    async def create_scenario(self, scenario: Scenario) -> str: ...
    async def update_scenario(self, id: str, scenario: Scenario) -> None: ...
```

**Целевая структура:**
```
backend/database/repository/
├── __init__.py (экспорт)
├── base.py (BaseRepository - common logic)
├── test_repository.py (350 строк - только TestRepository)
├── scenario_repository.py (350 строк - только ScenarioRepository)
└── models.py (если нужны специфичные модели)
```

---

#### 4️⃣ Разделить `backend/database/backup_strategies/sql_strategy.py` (443 строк)

**Текущая структура:**
```python
# sql_strategy.py (443 строк)
class SqlBackupStrategy:
    async def create_backup(self, engine, tables):
        # Создание backup таблиц
        ...
    
    async def restore_backup(self, engine, backup_info):
        # Восстановление + FK обработка + sequence восстановление
        ...
    
    async def _get_fk_relationships(self):  # helper
    async def _restore_sequences(self):    # helper
    async def _topological_sort(self):     # helper
```

**Целевая структура:**
```
backend/database/backup_strategies/sql_strategy/
├── __init__.py
├── core.py (SqlBackupStrategy класс - интерфейс)
├── backup.py (логика создания backup)
├── restore.py (логика восстановления)
└── helpers.py (FK, sequences, topological_sort)
```

---

#### 5️⃣ Реорганизовать `frontend/lib/api.ts` (432 строки)

**Текущая структура - МОНОЛИТ:**
```typescript
// frontend/lib/api.ts (432 строк)
export async function getDatabaseState(...) { ... }
export async function createBackup(...) { ... }
export async function restoreBackup(...) { ... }
export async function createScenario(...) { ... }
export async function getScenarios(...) { ... }
export async function updateScenario(...) { ... }
export async function runTest(...) { ... }
export async function getTestHistory(...) { ... }
export async function getRestoreSettings(...) { ... }
export async function updateRestoreSettings(...) { ... }
// ... и ещё 10+ функций
```

**Целевая структура:**
```
frontend/lib/api/
├── index.ts (главный экспорт)
├── test.ts (test endpoints)
│   ├── runTest()
│   ├── runComparison()
│   └── getTestHistory()
├── scenario.ts (scenario endpoints)
│   ├── getScenarios()
│   ├── createScenario()
│   └── updateScenario()
├── database.ts (database state endpoints)
│   ├── getDatabaseState()
│   ├── createBackup()
│   └── restoreBackup()
└── settings.ts (settings endpoints)
    ├── getRestoreSettings()
    └── updateRestoreSettings()
```

**Импорт становится ясным:**
```typescript
// Было
import { getDatabaseState, createBackup, createScenario, runTest } from '@/lib/api';

// Стало
import { getDatabaseState, createBackup } from '@/lib/api/database';
import { getScenarios, createScenario } from '@/lib/api/scenario';
import { runTest } from '@/lib/api/test';
```

---

### ФАЗА 3: ЖЕЛАТЕЛЬНАЯ (5-7 часов) - Третий спринт

#### 6️⃣ Централизовать конфигурацию

Использовать Pydantic BaseSettings вместо нескольких источников:
```python
# backend/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    postgresql_url: str
    mysql_url: str
    history_db_url: str
    
    # Restore settings
    auto_restore: bool = True
    verify_after_restore: bool = True
    default_strategy: str = "sql"
    operation_timeout: int = 300
    
    # Paths
    snapshots_dir: str = "./snapshots"
    logs_dir: str = "./logs"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Использование везде
from core.config import settings

if settings.auto_restore:
    # ...
```

---

#### 7️⃣ Организовать скрипты

```
backend/scripts/
├── __init__.py
├── init/
│   ├── __init__.py
│   ├── history_db.py      # init_history_db.py → переместить сюда
│   ├── scenarios.py       # init_scenarios.py → переместить сюда
│   └── databases.py       # Новый: инициализация тестовых БД
└── migration/
    ├── __init__.py
    ├── add_restore_columns.py
    └── timestamps.py
```

---

## 📈 Ожидаемые улучшения

### После Фазы 1 (10-12 часов):

| Метрика | Улучшение |
|---------|-----------|
| **Читаемость кода** | +300% (файлы < 500 строк) |
| **Maintainability** | +250% (изменения изолированы) |
| **Testability** | +200% (модули меньше) |
| **Time to Onboard** | -50% (легче ориентироваться) |
| **IDE Navigation** | Much easier (Ctrl+Click работает лучше) |

### После Фаз 1+2 (18-22 часа):

- **Легкость добавления новых endpoint-ов** (+400%)
- **Скорость поиска багов** (-30% времени)
- **Переиспользуемость компонентов** (+200%)

---

## ✅ Что НУЖНО оставить (правильный дизайн)

| Файл | Строк | Статус |
|------|-------|--------|
| `state_manager.py` | 487 | ✅ Хорошо (оркестратор, правильный размер) |
| `query_analyzer.py` | 163 | ✅ Отлично (single responsibility) |
| `state_verifier.py` | 252 | ✅ Отлично (focused domain) |
| `models.py` | 180+ | ✅ Правильно (все SQLAlchemy в одном месте) |
| `websocket_manager.py` | 310 | ✅ Удовлетворительно |
| `history-page.tsx` | 432 | ✅ Нормально для страницы |
| `reports-page.tsx` | 380 | ✅ Нормально |

---

## 🚀 Процесс рефакторинга

### Шаг за шагом для Фазы 1:

#### 1. Подготовка
```bash
# Создать новые директории
mkdir -p backend/api/{routes,schemas}
mkdir -p backend/database/repository

# Убедиться что нет незакоммиченных изменений
git status
```

#### 2. Создание новых модулей
```bash
# Создать пустые файлы
touch backend/api/__init__.py
touch backend/api/routes/{__init__,test_routes,scenario_routes,database_state_routes}.py
touch backend/api/schemas/{__init__,test_schemas,scenario_schemas,backup_schemas,settings_schemas}.py
```

#### 3. Копирование кода
- Скопировать Pydantic модели из main.py в соответствующие файлы в schemas/
- Скопировать endpoint функции из main.py в соответствующие файлы в routes/

#### 4. Тестирование
```bash
# Проверить что всё компилируется
python3 -m py_compile backend/**/*.py

# Запустить тесты
python3 backend/scripts/test_backup_restore.py

# Запустить сервер
./start_backend.sh
```

#### 5. Проверка frontend
```bash
cd frontend
npm run dev  # или pnpm dev
# Протестировать API запросы
```

---

## 📋 Чек-лист для успеха

### Fase 1 Checklist:

- [ ] Создана структура `api/routes/` и `api/schemas/`
- [ ] Pydantic модели перемещены в schema-файлы
- [ ] Endpoints перемещены в route-файлы
- [ ] `main.py` содержит < 300 строк
- [ ] Все импорты обновлены
- [ ] `python3 -m py_compile` passes
- [ ] Backend запускается: `./start_backend.sh`
- [ ] Frontend подключается: `pnpm dev`
- [ ] API endpoints работают
- [ ] WebSocket тест успешен
- [ ] История тестов сохраняется

### После каждого изменения:

```bash
# Проверка синтаксиса
python3 -m py_compile backend/**/*.py

# Проверка импортов
python3 -c "from api.routes import test_routes; print('✅ OK')"

# Запуск backend
./start_backend.sh &

# Проверка endpoint-ов (в другом терминале)
curl http://localhost:8000/health
```

---

## ⏱️ Оценка времени

| Фаза | Задача | Время |
|------|--------|-------|
| **1** | Разделить main.py | 6-8 ч |
| **1** | Разделить Frontend компоненты | 4-6 ч |
| **2** | Разделить repository.py | 3-4 ч |
| **2** | Разделить sql_strategy.py | 3-4 ч |
| **2** | Реорганизовать api.ts | 2-3 ч |
| **3** | Централизовать конфиг | 3-4 ч |
| **3** | Организовать скрипты | 2-3 ч |
| **❓** | Тестирование & QA | 4-6 ч |
| **❓** | Документирование | 2-3 ч |
| | **TOTAL** | **~32-42 часа** |

---

## 🎯 Критерии завершения

Рефакторинг считается **успешным** когда:

1. ✅ Все файлы < 500 строк (кроме legacy)
2. ✅ Каждый модуль имеет одну ответственность
3. ✅ `python3 -m py_compile` не выдаёт ошибок
4. ✅ Все тесты проходят
5. ✅ Frontend + Backend общаются корректно
6. ✅ Backup/restore работает
7. ✅ WebSocket real-time обновления работают
8. ✅ IDE быстро ориентируется (fast Go to Definition)
9. ✅ Новые разработчики быстрее ориентируются в коде
10. ✅ Нет циклических зависимостей

---

## 📚 Дополнительные ресурсы

- **Детальный анализ:** [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)
- **Инструкции для разработчиков:** [.github/copilot-instructions.md](.github/copilot-instructions.md)
- **Быстрый старт:** [QUICKSTART.md](QUICKSTART.md)

---

## 💡 Next Steps

### Вариант 1: Начать сейчас
1. Прочитать полный анализ в [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)
2. Выбрать Фазу 1 как проект на эту неделю
3. Следить за чек-листом выше
4. Запросить help от Copilot для каждого шага

### Вариант 2: Отложить
Проект **полностью функционален** сейчас. Рефакторинг - это **инвестиция в качество**, не критическая необходимость. Используйте существующее состояние как-есть, если сроки сжаты.

### Вариант 3: Постепенный подход
- Фаза 1 (main.py) - неделя 1
- Фаза 1 (Frontend) - неделя 2
- Фаза 2 - неделя 3-4
- Фаза 3 - когда есть время

---

**Адрес для вопросов:** Используйте встроенный Copilot с `.github/copilot-instructions.md` для ассистанции при рефакторинге.

**Дата обновления:** 16 марта 2026
