"use client"

import { FileText } from "lucide-react"

import type { AnalysisReport as AnalysisReportType, AnalysisReportConfig, ComparisonType } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface AnalysisReportProps {
  report?: AnalysisReportType | null
  config?: AnalysisReportConfig
  comparisonType?: ComparisonType
}

const COMPARISON_TYPE_LABELS: Record<ComparisonType, string> = {
  cross_database: "Сравнение СУБД",
  scalability: "Анализ масштабируемости",
  mixed: "Смешанное сравнение",
  temporal: "Временное сравнение",
}

export function AnalysisReport({ report, config, comparisonType }: AnalysisReportProps) {
  if (!report) {
    return null
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          Аналитический отчёт
        </CardTitle>
        <CardDescription>{report.verdict}</CardDescription>
        <div className="flex flex-wrap gap-2">
          {comparisonType && <Badge variant="secondary">{COMPARISON_TYPE_LABELS[comparisonType]}</Badge>}
          {config && (
            <>
              <Badge variant={config.include_verdict ? "default" : "outline"}>Вердикт</Badge>
              <Badge variant={config.include_patterns ? "default" : "outline"}>Паттерны</Badge>
              <Badge variant={config.include_recommendations ? "default" : "outline"}>Рекомендации</Badge>
              <Badge variant={config.include_hypotheses ? "default" : "outline"}>Гипотезы</Badge>
            </>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {report.sections.map((section) => (
          <div key={section.title} className="space-y-2">
            <h3 className="font-medium">{section.title}</h3>
            {section.items.length > 0 ? (
              <ul className="space-y-1 text-sm text-muted-foreground">
                {section.items.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Нет данных для этой секции</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
