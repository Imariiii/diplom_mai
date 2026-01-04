"use client"

import { Database, Cpu, BarChart3, Zap, ArrowRight } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/lib/store"

const features = [
  {
    icon: Database,
    title: "Множество СУБД",
    description: "Поддержка PostgreSQL, MySQL, MariaDB, SQLite и MS SQL Server",
  },
  {
    icon: Cpu,
    title: "Распределённое тестирование",
    description: "Масштабируемая архитектура на основе Celery и RabbitMQ",
  },
  {
    icon: BarChart3,
    title: "Real-time мониторинг",
    description: "Интерактивные дашборды с обновлением в реальном времени",
  },
  {
    icon: Zap,
    title: "Детальный анализ",
    description: "Сравнительные отчёты с метриками производительности",
  },
]

const steps = [
  { step: 1, title: "Выберите СУБД", description: "Укажите базы данных для тестирования" },
  { step: 2, title: "Настройте параметры", description: "Задайте нагрузку, длительность и тип запросов" },
  { step: 3, title: "Запустите тест", description: "Система распределит задачи по воркерам" },
  { step: 4, title: "Анализируйте результаты", description: "Изучите метрики и сравните СУБД" },
]

export function HomePage() {
  const { setCurrentPage } = useAppStore()

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <div className="text-center space-y-4 py-8">
        <h1 className="text-4xl font-bold text-balance">
          Добро пожаловать в <span className="text-primary">TestBDBench</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto text-pretty">
          Система для сравнительного нагрузочного тестирования и визуального анализа производительности реляционных баз
          данных
        </p>
        <Button size="lg" className="mt-4" onClick={() => setCurrentPage("config")}>
          Начать тестирование
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {features.map((feature) => (
          <Card key={feature.title} className="bg-card border-border">
            <CardHeader>
              <feature.icon className="h-8 w-8 text-primary mb-2" />
              <CardTitle className="text-lg">{feature.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-muted-foreground">{feature.description}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Как это работает</CardTitle>
          <CardDescription>Простой процесс тестирования в 4 шага</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map((item) => (
              <div key={item.step} className="flex flex-col items-center text-center space-y-2">
                <div className="w-12 h-12 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold text-lg">
                  {item.step}
                </div>
                <h3 className="font-semibold">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Архитектура системы</CardTitle>
          <CardDescription>Распределённая обработка задач на основе микросервисной архитектуры</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-secondary/50 border border-border">
              <h4 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary" />
                Frontend
              </h4>
              <p className="text-sm text-muted-foreground">
                React/TypeScript веб-интерфейс для настройки тестов и визуализации результатов
              </p>
            </div>
            <div className="p-4 rounded-lg bg-secondary/50 border border-border">
              <h4 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-chart-2" />
                Backend
              </h4>
              <p className="text-sm text-muted-foreground">
                FastAPI сервер для обработки запросов и управления очередью задач через RabbitMQ
              </p>
            </div>
            <div className="p-4 rounded-lg bg-secondary/50 border border-border">
              <h4 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-chart-3" />
                Workers
              </h4>
              <p className="text-sm text-muted-foreground">
                Celery воркеры выполняют нагрузочные тесты и собирают метрики в реальном времени
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
