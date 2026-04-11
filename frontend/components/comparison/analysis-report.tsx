"use client"

import { FileText } from "lucide-react"

import type { AnalysisReport as AnalysisReportType, AnalysisReportConfig, ComparisonType } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { useState } from "react"

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

const SECTION_VISIBILITY: Record<string, keyof AnalysisReportConfig> = {
  "Основной вердикт": "include_verdict",
  "Выявленные паттерны": "include_patterns",
  "Рекомендации": "include_recommendations",
  "Возможные причины различий": "include_hypotheses",
}

export function AnalysisReport({ report, config, comparisonType }: AnalysisReportProps) {
  const [isOpen, setIsOpen] = useState(true)

  if (!report) {
    return null
  }

  const filteredSections = config
    ? report.sections.filter((section) => {
        const configKey = SECTION_VISIBILITY[section.title]
        if (!configKey) return true
        return config[configKey]
      })
    : report.sections

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="bg-card border-border">
        <CardHeader>
          <CollapsibleTrigger asChild>
            <button className="flex items-center gap-2 hover:opacity-80 transition-opacity text-left">
              <FileText className="h-5 w-5 text-primary shrink-0" />
              <CardTitle>Аналитический отчёт</CardTitle>
            </button>
          </CollapsibleTrigger>
          <div className="flex flex-wrap gap-2 mt-1">
            {comparisonType && (
              <Badge variant="secondary">{COMPARISON_TYPE_LABELS[comparisonType]}</Badge>
            )}
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="space-y-6">
            {filteredSections.map((section) => (
              <div key={section.title} className="space-y-2">
                <h3 className="font-medium">{section.title}</h3>
                {section.items.length > 0 ? (
                  <ul className="space-y-1.5 text-sm text-muted-foreground">
                    {section.items.map((item, idx) => (
                      <li key={idx} className="leading-relaxed">• {item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">Нет данных для этой секции</p>
                )}
              </div>
            ))}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
