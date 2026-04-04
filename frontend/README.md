# TestBDBench Frontend

Next.js frontend приложение для системы нагрузочного тестирования баз данных.

## Технологии

- **Next.js 16** - React фреймворк
- **TypeScript** - Типизация
- **Tailwind CSS** - Стилизация
- **shadcn/ui** - UI компоненты
- **Recharts** - Графики и визуализация
- **Zustand** - Управление состоянием

## Установка

1. Установите зависимости:
```bash
pnpm install
# или
npm install
```

2. Настройте переменные окружения:
```bash
cp ../env.example ../.env
```

Отредактируйте корневой `.env` и укажите URL backend API:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Запустите dev сервер:
```bash
pnpm dev
# или
npm run dev
```

Приложение будет доступно на http://localhost:3000

## Сборка для production

```bash
pnpm build
pnpm start
```

## Структура

- `app/` - Next.js App Router страницы
- `components/` - React компоненты
  - `pages/` - Страницы приложения
  - `ui/` - UI компоненты (shadcn/ui)
- `lib/` - Утилиты и API клиент
  - `api.ts` - API клиент для работы с backend
  - `store.ts` - Zustand store для состояния
  - `types.ts` - TypeScript типы

## API интеграция

Frontend использует REST API backend для:
- Проверки статуса подключений к БД (`/health`)
- Получения списка запросов (`/queries`)
- Запуска тестирования (`/test/single`, `/test/full`)
- Получения результатов и графиков

## Особенности

- ✅ Проверка статуса подключений к БД в реальном времени
- ✅ Выбор запросов из конфигурации
- ✅ Настройка параметров тестирования
- ✅ Визуализация результатов в реальном времени
- ✅ Детальные отчеты с графиками
- ✅ Сравнение производительности СУБД
