"use client"

import { Database, Cpu, BarChart3, Zap, ArrowRight } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/lib/store"

const features = [
  {
    icon: Database,
    title: "Несколько СУБД",
    description: "Поддержка PostgreSQL, MySQL и MariaDB с примерами баз данных Sakila и Pagila",
  },
  {
    icon: Cpu,
    title: "Нагрузочное тестирование",
    description: "Сравнительный анализ производительности различных СУБД",
  },
  {
    icon: BarChart3,
    title: "Визуальный анализ",
    description: "Интерактивные графики и отчёты с результатами тестирования",
  },
  {
    icon: Zap,
    title: "Детальный анализ",
    description: "Сравнительные отчёты с метриками производительности",
  },
]

const steps = [
  {
    step: 1,
    title: "Добавьте подключения",
    description: "В разделе «Подключения к СУБД» создайте логическую базу данных и добавьте подключения к нужным СУБД",
  },
  {
    step: 2,
    title: "Настройте профиль и сценарии",
    description: "Через меню «Профиль и сценарии» назначьте схемный профиль и сгенерируйте наборы сценариев тестирования",
  },
  {
    step: 3,
    title: "Настройте параметры теста",
    description: "На странице «Конфигурация» выберите базу данных, тип теста, число виртуальных пользователей и итераций",
  },
  {
    step: 4,
    title: "Запустите и следите",
    description: "Запустите тест и наблюдайте за метриками в реальном времени на дашбордах",
  },
  {
    step: 5,
    title: "Сравните результаты",
    description: "В разделах «История» и «Сравнение» проанализируйте и сопоставьте производительность СУБД",
  },
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
          <CardDescription>Процесс тестирования в 5 шагов</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
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
    </div>
  )
}
