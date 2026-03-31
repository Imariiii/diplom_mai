# Copilot Instructions for Database Load Testing System

**Project:** Database Load Testing System with Automated Backup/Restore  
**Type:** Full-stack application (Python FastAPI + React Next.js)  
**Status:** Production-ready  
**Last Updated:** March 2026

---

## 🚀 Quick Start for AI Agents

### Project Context
This is a **dual-DBMS load testing framework** (PostgreSQL + MySQL) with an **automatic database rollback mechanism**. The system:
- Runs load tests and captures real-time metrics (RPS, latency, CPU)
- Automatically backs up affected tables before tests
- Restores original state after tests complete
- Provides REST API + WebSocket real-time updates + React dashboard

### Key Responsibility: Backup/Restore Architecture
The project's unique feature is the **DatabaseStateManager** orchestrator that:
1. Analyzes SQL queries to detect write operations
2. Creates selective backups of only affected tables (using SQL-based approach)
3. Verifies DB state before/after (fingerprinting with row counts and optional checksums)
4. Restores data with proper handling of foreign keys and sequences
5. Supports two strategies: SQL-based (default, universal) or Native dumps (pg_dump/mysqldump)

---

## 📋 Essential Commands

### Backend (Python/FastAPI)

```bash
# Full startup (venv + install + run)
./start_backend.sh
# Runs: http://localhost:8000
# Auto-creates venv, installs requirements.txt, runs main.py

# Manual startup
source venv/bin/activate
pip install -r requirements.txt
python3 backend/main.py

# Database initialization
python3 backend/scripts/init_history_db.py      # Create history DB schema
python3 backend/scripts/init_scenarios.py       # Load test scenarios

# Testing
python3 -m py_compile backend/**/*.py           # Syntax check
python3 backend/scripts/test_backup_restore.py  # Test backup/restore
```

### Frontend (React/Next.js)

```bash
cd frontend

# Install (choose one)
pnpm install      # Fast (uses pnpm-lock.yaml)
npm install       # Slower but more compatible

# Development
pnpm dev          # http://localhost:3000
npm run dev

# Production
pnpm build && pnpm start

# Linting
pnpm lint
```

### Database Setup (Docker)

```bash
# PostgreSQL (Pagila)
cd ../pagila/pagila && docker-compose up -d && ./init_pagila.sh

# MySQL (Sakila)
cd ../../sakila && docker-compose up -d

# Test History DB (PostgreSQL on port 5433)
docker-compose up -d history-db
```

### QUICKSTART (Full System)

```bash
# 1. Databases (in parallel terminals)
cd ../pagila/pagila && docker-compose up -d && ./init_pagila.sh
cd ../../sakila && docker-compose up -d
cd ../../code

# 2. Backend
./start_backend.sh  # Terminal 1

# 3. Frontend
cd frontend && pnpm dev  # Terminal 2
# Access: http://localhost:3000
```

---

## 🏗️ Architecture & Key Files

### Backend Structure

```
backend/
├── main.py                      # FastAPI entry point + 7 REST endpoints
├── config.py                    # Config management (RESTORE_CONFIG dict)
├── websocket_manager.py         # WebSocket for real-time metrics
├── database/
│   ├── connection.py            # DatabaseConnection (YAML-config + SQLAlchemy)
│   ├── models.py                # SQLAlchemy models (TestRun extended with restore fields)
│   ├── queries.py               # QueryManager (scenario management)
│   ├── query_analyzer.py        # QueryAnalyzer (SQL parsing, write-detection)
│   ├── repository.py            # TestRepository (test history persistence)
│   ├── state_manager.py         # DatabaseStateManager (orchestrator - 500+ lines)
│   ├── state_verifier.py        # StateVerifier (fingerprinting + verification)
│   └── backup_strategies/
│       ├── sql_strategy.py      # SqlBackupStrategy (CREATE TABLE AS SELECT)
│       └── native_strategy.py   # NativeDumpStrategy (pg_dump/mysqldump)
├── load_tester/
│   └── tester.py                # LoadTester (test execution with auto-restore hooks)
└── visualizer/
    ├── charts.py                # Chart generation (Matplotlib/Seaborn)
    └── result_saver.py          # Result persistence
```

### Frontend Structure

```
frontend/
├── app/
│   ├── page.tsx                 # Root (redirects to /home-page)
│   ├── layout.tsx               # Root layout + theme provider
│   └── globals.css              # Global styles
├── components/
│   ├── pages/
│   │   ├── home-page.tsx        # Connection status overview
│   │   ├── config-page.tsx      # Test configuration UI
│   │   ├── scenarios-page.tsx   # Manage load test scenarios
│   │   ├── dashboards-page.tsx  # Real-time metrics (RPS, latency, CPU)
│   │   ├── reports-page.tsx     # Saved test reports
│   │   └── history-page.tsx     # Test execution history
│   ├── ui/                      # 40+ Radix UI + Tailwind components
│   │   ├── button.tsx, card.tsx, dialog.tsx, etc.
│   ├── database-state-panel.tsx # DB state management UI
│   ├── header.tsx               # Top navigation
│   ├── sidebar.tsx              # Left sidebar menu
│   └── theme-provider.tsx       # Dark/Light mode provider
├── lib/
│   ├── api.ts                   # API client (fetch wrapper)
│   ├── types.ts                 # TypeScript types (DatabaseState, RestoreSettings, etc.)
│   ├── store.ts                 # Zustand state management
│   ├── chart-colors.ts          # Color palette for charts
│   └── utils.ts                 # Utility functions
├── hooks/
│   ├── use-test-websocket.ts    # WebSocket hook for real-time metrics
│   ├── use-mobile.ts            # Responsive design hook
│   └── use-toast.ts             # Toast notifications hook
├── package.json                 # Dependencies (Next.js, React, Zustand, Recharts)
└── next.config.mjs              # Next.js configuration
```

### Configuration Files

- **`backend/config/database_config.yaml`** — Multi-DBMS connection config (PostgreSQL + MySQL URLs)
- **`backend/config.py`** — RESTORE_CONFIG dict with 10 parameters (auto_restore, verify_after_restore, strategy selection, thresholds)
- **`env.example`** — Template for environment variables (backend and frontend)
- **`.github/copilot-instructions.md`** — This file

---

## 🔑 Key Architectural Decisions

### 1. Dual Backup Strategies

**SQL-Based (Default):**
- Creates shadow tables using `CREATE TABLE AS SELECT`
- Works universally (no external tools needed)
- Fast for most use cases
- Proper FK handling with `SET session_replication_role = 'replica'` (PG) / `SET FOREIGN_KEY_CHECKS = 0` (MySQL)

**Native Dump (Fallback):**
- Uses `pg_dump` (PostgreSQL) or `mysqldump` (MySQL)
- Better for very large databases (100M+ rows)
- Requires utilities in system PATH

**Selection:** Config-driven via `default_strategy` in RESTORE_CONFIG

### 2. Async/Await Architecture

- All I/O operations are async (FastAPI + SQLAlchemy async)
- Asyncio locks for managing concurrent test execution
- Per-DBMS locking (`_test_locks` dict in DatabaseStateManager)

### 3. Query Analysis for Smart Backup

- Only backs up tables affected by test queries
- Uses regex patterns to detect UPDATE/INSERT/DELETE/TRUNCATE operations
- Parses parameter markers (`:param_name`) without syntax errors
- Reduces backup time for large databases with minimal changes

### 4. State Verification

- Captures "fingerprint" (row count per table, optional checksums)
- Pre-test and post-test comparison
- Detects data corruption or incomplete restore
- Optional MD5 checksums for critical data (configurable threshold)

### 5. WebSocket Real-Time Updates

- Streaming test metrics to frontend during execution
- Events: test_started, test_metric, test_completed, backup_started, restore_completed
- Eliminates polling, reduces latency

---

## 🛠️ Code Patterns & Conventions

### Python (Backend)

**Async/Await Pattern:**
```python
async def prepare_for_test(
    self,
    engine: AsyncEngine,
    dbms_type: str,
    queries: List[str]
) -> PrepareResult:
    """
    Analyze queries and create backup.
    
    Args:
        engine: SQLAlchemy AsyncEngine
        dbms_type: 'postgresql' or 'mysql'
        queries: List of SQL query strings
        
    Returns:
        PrepareResult with backup_info and fingerprint
    """
    # Implementation with proper error handling
```

**Type Hints (Required):**
```python
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

@dataclass
class BackupInfo:
    backup_id: str
    strategy: str
    created_at: float
    affected_tables: List[str]
```

**Config Management:**
```python
from backend.config import get_restore_config, update_restore_config

config = get_restore_config()
if config['auto_restore']:
    # Enable automatic restore
    pass
```

### TypeScript/React (Frontend)

**Functional Components with Hooks:**
```typescript
import { useState, useEffect } from 'react';
import { useTestWebSocket } from '@/hooks/use-test-websocket';

export default function DashboardsPage() {
  const [metrics, setMetrics] = useState<Metrics[]>([]);
  const { metrics: wsMetrics } = useTestWebSocket();
  
  useEffect(() => {
    setMetrics(wsMetrics);
  }, [wsMetrics]);
  
  return <div>{/* UI */}</div>;
}
```

**State Management (Zustand):**
```typescript
import { create } from 'zustand';

interface TestStore {
  testRunId: string;
  setTestRunId: (id: string) => void;
}

export const useTestStore = create<TestStore>((set) => ({
  testRunId: '',
  setTestRunId: (id) => set({ testRunId: id }),
}));
```

**API Calls:**
```typescript
import { getDatabaseState, createBackup } from '@/lib/api';

const state = await getDatabaseState('postgresql');
const backup = await createBackup('mysql', ['film', 'customer']);
```

---

## ⚠️ Common Pitfalls & Solutions

### 1. Write Operations Corrupt Database

**Problem:** Test queries with UPDATE/DELETE change database state permanently.  
**Solution:** DatabaseStateManager automatically detects write operations and creates backup before test.  
**Check:** Look at `QueryAnalyzer.has_write_operations()` and `DatabaseStateManager.prepare_for_test()`.

### 2. WebSocket Connection Fails

**Problem:** Frontend can't connect to backend WebSocket.  
**Solution:** Verify `.env.local` has correct backend URL:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 3. Virtual Environment Issues

**Problem:** `python3: command not found` or module import errors.  
**Solution:** Always run `./start_backend.sh` or manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. History Database Not Initialized

**Problem:** Test results not saved, "table doesn't exist" errors.  
**Solution:** Run initialization:
```bash
python3 backend/scripts/init_history_db.py
python3 backend/scripts/init_scenarios.py
```

### 5. Foreign Key Constraint Violations During Restore

**Problem:** Restore fails with FK constraint error.  
**Solution:** Already handled in `SqlBackupStrategy.restore_backup()`:
- PostgreSQL: Uses `SET session_replication_role = 'replica'`
- MySQL: Uses `SET FOREIGN_KEY_CHECKS = 0`
- Topological sort ensures correct TRUNCATE/INSERT order

### 6. Backup Tables Not Cleaned Up

**Problem:** `_loadtest_backup_*` shadow tables accumulate.  
**Solution:** Manual cleanup:
- POST `/api/database/{dbms_type}/cleanup` endpoint
- Or use `DatabaseStateManager.cleanup_all_backups()`

---

## 📊 API Endpoints

### Database State Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/database/{dbms_type}/state` | Get current DB state with tables + backup status |
| POST | `/api/database/{dbms_type}/backup` | Create backup on-demand |
| POST | `/api/database/{dbms_type}/restore` | Restore from backup_id |
| POST | `/api/database/{dbms_type}/cleanup` | Remove all backup tables |
| GET | `/api/database/{dbms_type}/estimate` | Estimate backup size + time |

### Settings Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/settings/restore` | Get restore config |
| PUT | `/api/settings/restore` | Update restore settings |

### Test Execution (Main Endpoints)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/test/run_scenario_test` | Run single scenario test |
| POST | `/api/test/run_comparison_test` | Compare two scenarios |
| POST | `/api/test/run_full_test_suite` | Run all scenarios |
| WS | `/ws/{test_id}` | WebSocket for real-time metrics |

---

## 🧪 Testing & Validation

### Syntax Validation

```bash
# Check all Python files for syntax errors
python3 -m py_compile backend/**/*.py

# Or specific modules
python3 -m py_compile backend/database/state_manager.py
```

### Import Validation

```bash
# Test imports resolve correctly
python3 -c "from backend.database.state_manager import DatabaseStateManager; print('✅ OK')"
python3 -c "from backend.database.query_analyzer import QueryAnalyzer; print('✅ OK')"
```

### Functional Testing

```bash
# Test backup/restore end-to-end
python3 backend/scripts/test_backup_restore.py

# Test with actual load
pnpm dev  # Frontend
./start_backend.sh  # Backend
# Then run tests from UI at http://localhost:3000
```

---

## 📝 Development Workflow

### Adding a New Feature

1. **Backend:**
   - Create async functions with type hints
   - Add to appropriate module (state_manager, query_analyzer, etc.)
   - Update REST endpoint in main.py if needed
   - Test with sql_strategy and native_strategy

2. **Frontend:**
   - Create React component with TypeScript types
   - Add to pages/ or components/ with proper structure
   - Use hooks (useState, useEffect, custom hooks)
   - Update types.ts if new API contract

3. **Database:**
   - Update models.py if schema changes
   - Run migration scripts in backend/scripts/
   - Test with both PostgreSQL and MySQL

### Debugging Tips

**Backend:**
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check async lock contention
print(f"Test lock status: {self._test_locks[dbms_type]}")

# Validate backup creation
backup_info = await self.state_manager.prepare_for_test(...)
print(f"Backup created: {backup_info.backup_id}")
```

**Frontend:**
```typescript
// Open browser console (F12)
// Check WebSocket connection
// Network tab shows ws:// connections
// Check Zustand store state in localStorage

// React DevTools Extension helpful
// Check component re-renders and hooks
```

---

## 🔍 Code Search & Navigation

### Finding Key Concepts

- **"Backup logic"** → `backend/database/state_manager.py` + `backup_strategies/`
- **"Write detection"** → `backend/database/query_analyzer.py` → `has_write_operations()`
- **"Verify restore"** → `backend/database/state_verifier.py` → `verify()`
- **"Real-time metrics"** → `backend/websocket_manager.py` + `frontend/hooks/use-test-websocket.ts`
- **"Test execution"** → `backend/load_tester/tester.py` → `run_scenario_test()`
- **"API endpoints"** → `backend/main.py` → search for `@app.get`, `@app.post`

---

## 📦 Dependencies (Critical Only)

### Backend
- **fastapi** — Web framework
- **sqlalchemy** (async) — ORM
- **psycopg2** — PostgreSQL driver
- **pymysql** — MySQL driver
- **uvicorn** — ASGI server

### Frontend
- **next.js** — React framework
- **react** & **react-dom** — UI
- **typescript** — Type safety
- **zustand** — State management
- **recharts** — Charts
- **radix-ui** — Component library

---

## 🎯 Success Criteria

A change is complete when:

1. ✅ All Python files compile: `python3 -m py_compile` returns 0
2. ✅ Imports resolve: `from module import Class` works
3. ✅ Backend starts: `./start_backend.sh` runs without errors
4. ✅ Frontend builds: `pnpm build` completes successfully
5. ✅ API tests pass: Run test from http://localhost:3000
6. ✅ Backup/restore works: Manual test creates and restores backup

---

## 🔗 Related Resources

- **Full codebase analysis:** See [CODEBASE_ANALYSIS.md](../CODEBASE_ANALYSIS.md)
- **Implementation summary:** See [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- **QUICKSTART guide:** See [QUICKSTART.md](../QUICKSTART.md)
- **Database config:** `backend/config/database_config.yaml`

---

## 💡 For AI Agents: Quick Decisions

**When implementing a feature:**
- Default to async/await (FastAPI async driver)
- Use type hints (Python dataclasses, TypeScript interfaces)
- Handle both PostgreSQL and MySQL paths (check dbms_type parameter)
- Test with `python3 -m py_compile` first
- WebSocket updates go through `websocket_manager.py`

**When debugging:**
- Check imports first: `from module import X`
- Check async locking in state_manager: `_test_locks[dbms_type]`
- Check connection pool: `DatabaseConnection.engines`
- Check WebSocket client count: `websocket_manager.active_connections`

**When uncertain:**
- Refer to existing patterns in state_manager.py (500+ lines, fully implemented)
- Check query_analyzer.py for SQL parsing patterns
- Review state_verifier.py for fingerprint verification logic
- Study load_tester.py for async test execution patterns

---

**Last Reviewed:** March 16, 2026  
**Maintainer:** Database Load Testing Team  
**Questions?** Check CODEBASE_ANALYSIS.md for detailed explanations
