# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: comparison-flow.spec.ts >> Comparison flow >> navigate to history page
- Location: e2e/comparison-flow.spec.ts:12:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('text=История')
    - locator resolved to <span>История тестов</span>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - element is outside of the viewport
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - element is outside of the viewport
    - retrying click action
      - waiting 100ms
    54 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - element is outside of the viewport
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - banner [ref=e3]:
      - button [ref=e4]:
        - img
      - generic [ref=e5]:
        - img [ref=e6]
        - generic [ref=e10]: TestBDBench
    - complementary [ref=e11]:
      - generic [ref=e12]:
        - generic [ref=e13]: Навигация
        - button [ref=e14]:
          - img
      - navigation [ref=e15]:
        - button "Начальная страница" [ref=e16]:
          - img [ref=e17]
          - generic [ref=e20]: Начальная страница
        - button "Подключения к СУБД" [ref=e21]:
          - img [ref=e22]
          - generic [ref=e24]: Подключения к СУБД
        - button "Конфигурация и запуск" [ref=e25]:
          - img [ref=e26]
          - generic [ref=e29]: Конфигурация и запуск
        - button "Сценарии тестирования" [ref=e30]:
          - img [ref=e31]
          - generic [ref=e35]: Сценарии тестирования
        - button "Дашборды" [ref=e36]:
          - img [ref=e37]
          - generic [ref=e39]: Дашборды
        - button "Отчёты" [ref=e40]:
          - img [ref=e41]
          - generic [ref=e44]: Отчёты
        - button "История тестов" [ref=e45]:
          - img [ref=e46]
          - generic [ref=e50]: История тестов
        - button "Сравнение тестов" [ref=e51]:
          - img [ref=e52]
          - generic [ref=e54]: Сравнение тестов
        - button "Состояние БД" [ref=e55]:
          - img [ref=e56]
          - generic [ref=e58]: Состояние БД
    - main [ref=e59]:
      - generic [ref=e60]:
        - generic [ref=e61]:
          - heading "Добро пожаловать в TestBDBench" [level=1] [ref=e62]
          - paragraph [ref=e63]: Система для сравнительного нагрузочного тестирования и визуального анализа производительности реляционных баз данных
          - generic [ref=e64]:
            - generic [ref=e65]:
              - img [ref=e66]
              - generic [ref=e69]: "Backend API: Подключено"
            - generic [ref=e70]:
              - img [ref=e71]
              - generic [ref=e74]: "БД истории: Подключено"
          - button "Начать тестирование" [ref=e75]:
            - text: Начать тестирование
            - img
        - generic [ref=e76]:
          - generic [ref=e77]:
            - generic [ref=e78]:
              - img [ref=e79]
              - generic [ref=e83]: Множество СУБД
            - generic [ref=e85]: Поддержка PostgreSQL, MySQL и MariaDB с примерами баз данных Sakila и Pagila
          - generic [ref=e86]:
            - generic [ref=e87]:
              - img [ref=e88]
              - generic [ref=e91]: Нагрузочное тестирование
            - generic [ref=e93]: Сравнительный анализ производительности различных СУБД
          - generic [ref=e94]:
            - generic [ref=e95]:
              - img [ref=e96]
              - generic [ref=e98]: Визуальный анализ
            - generic [ref=e100]: Интерактивные графики и отчеты с результатами тестирования
          - generic [ref=e101]:
            - generic [ref=e102]:
              - img [ref=e103]
              - generic [ref=e105]: Детальный анализ
            - generic [ref=e107]: Сравнительные отчёты с метриками производительности
        - generic [ref=e108]:
          - generic [ref=e109]:
            - generic [ref=e110]: Как это работает
            - generic [ref=e111]: Простой процесс тестирования в 4 шага
          - generic [ref=e113]:
            - generic [ref=e114]:
              - generic [ref=e115]: "1"
              - heading "Выберите СУБД" [level=3] [ref=e116]
              - paragraph [ref=e117]: Укажите базы данных для тестирования
            - generic [ref=e118]:
              - generic [ref=e119]: "2"
              - heading "Настройте параметры" [level=3] [ref=e120]
              - paragraph [ref=e121]: Задайте количество итераций и выберите запросы
            - generic [ref=e122]:
              - generic [ref=e123]: "3"
              - heading "Запустите тест" [level=3] [ref=e124]
              - paragraph [ref=e125]: Система выполнит нагрузочное тестирование
            - generic [ref=e126]:
              - generic [ref=e127]: "4"
              - heading "Анализируйте результаты" [level=3] [ref=e128]
              - paragraph [ref=e129]: Изучите метрики и сравните СУБД
        - generic [ref=e130]:
          - generic [ref=e131]:
            - generic [ref=e132]: Архитектура системы
            - generic [ref=e133]: Веб-интерфейс для настройки тестов и визуализации результатов
          - generic [ref=e135]:
            - generic [ref=e136]:
              - heading "Frontend" [level=4] [ref=e137]: Frontend
              - paragraph [ref=e139]: Next.js/React/TypeScript веб-интерфейс для настройки тестов и визуализации результатов
            - generic [ref=e140]:
              - heading "Backend" [level=4] [ref=e141]: Backend
              - paragraph [ref=e143]: FastAPI сервер для обработки запросов и выполнения нагрузочного тестирования
  - region "Notifications alt+T"
  - button "Open Next.js Dev Tools" [ref=e149] [cursor=pointer]:
    - img [ref=e150]
  - alert [ref=e153]
```

# Test source

```ts
  1  | /**
  2  |  * E2E-тест: "золотой" сценарий сравнения тестов.
  3  |  *
  4  |  * Предполагает запущенный frontend (localhost:3000) и backend (localhost:8000)
  5  |  * с хотя бы 2 завершёнными тестами в истории.
  6  |  *
  7  |  * Запуск: npx playwright test
  8  |  */
  9  | import { test, expect } from "@playwright/test";
  10 | 
  11 | test.describe("Comparison flow", () => {
  12 |   test("navigate to history page", async ({ page }) => {
  13 |     await page.goto("/");
  14 |     await page.waitForLoadState("networkidle");
  15 | 
  16 |     // SPA navigation through sidebar
  17 |     const historyLink = page.locator("text=История");
  18 |     if (await historyLink.isVisible()) {
> 19 |       await historyLink.click();
     |                         ^ Error: locator.click: Test timeout of 30000ms exceeded.
  20 |       await expect(page.locator("text=История тестов").or(page.locator("text=История"))).toBeVisible();
  21 |     }
  22 |   });
  23 | 
  24 |   test("home page loads and shows status", async ({ page }) => {
  25 |     await page.goto("/");
  26 |     await page.waitForLoadState("networkidle");
  27 | 
  28 |     // Main heading or logo should be visible
  29 |     await expect(page.locator("body")).toBeVisible();
  30 |     // API status indicator should appear
  31 |     const statusText = page.locator("text=API").or(page.locator("text=Статус"));
  32 |     await expect(statusText.first()).toBeVisible({ timeout: 10000 });
  33 |   });
  34 | });
  35 | 
```