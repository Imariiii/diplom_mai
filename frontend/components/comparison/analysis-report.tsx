"use client"

import {
  CheckCircle2,
  FileText,
  Lightbulb,
  Search,
  Sparkles,
  Target,
} from "lucide-react"

import type {
  AnalysisReport as AnalysisReportType,
  AnalysisReportConfig,
  AnalysisMode,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"

interface AnalysisReportProps {
  report?: AnalysisReportType | null
  config?: AnalysisReportConfig
  analysisMode?: AnalysisMode
}

const MODE_LABELS: Record<string, string> = {
  per_test: "Внутритестовый анализ",
  series: "Серийный анализ",
}

const SECTION_ICONS: Record<string, React.ReactNode> = {
  "Краткое резюме": <Sparkles className="h-4 w-4" />,
  "Основной вердикт": <Target className="h-4 w-4" />,
  "Влияние параметров конфигурации": <CheckCircle2 className="h-4 w-4" />,
  "Выявленные паттерны": <Search className="h-4 w-4" />,
  "Практическая значимость различий": <CheckCircle2 className="h-4 w-4" />,
  "Рекомендации": <Lightbulb className="h-4 w-4" />,
  "Возможные причины различий": <Search className="h-4 w-4" />,
  "Заключение": <FileText className="h-4 w-4" />,
}

export function AnalysisReport({ report, config, analysisMode }: AnalysisReportProps) {
  if (!report) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center">
        <FileText className="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p className="mt-3 text-sm text-muted-foreground">
          Аналитический отчёт не сгенерирован
        </p>
      </div>
    )
  }

  const modeLabel = analysisMode ? MODE_LABELS[analysisMode] : ""

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <FileText className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Аналитический отчёт</h2>
          {modeLabel && (
            <p className="text-xs text-muted-foreground">{modeLabel}</p>
          )}
        </div>
      </div>

      {report.sections.map((section, idx) => {
        const icon = SECTION_ICONS[section.title] || <FileText className="h-4 w-4" />
        const isVerdict = section.title === "Основной вердикт"

        return (
          <div
            key={idx}
            className={`rounded-xl border bg-card p-5 ${
              isVerdict ? "border-primary/30 bg-primary/5" : "border-border"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-3">
              <div className={`flex h-7 w-7 items-center justify-center rounded-md ${
                isVerdict ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"
              }`}>
                {icon}
              </div>
              <h3 className="font-medium text-sm">{section.title}</h3>
              {isVerdict && (
                <Badge variant="secondary" className="text-[10px]">
                  Ключевой вывод
                </Badge>
              )}
            </div>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {section.items.map((item, i) => (
                <li key={i} className="leading-relaxed pl-9">
                  {isVerdict ? (
                    <span className="font-medium text-foreground">{item}</span>
                  ) : (
                    <span>— {item}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
