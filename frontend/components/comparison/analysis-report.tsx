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
  ComparisonType,
} from "@/lib/api"
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

const SECTION_CONFIG: Record<
  string,
  {
    configKey: keyof AnalysisReportConfig
    icon: React.ElementType
    accent: "primary" | "success" | "warning" | "neutral"
  }
> = {
  "Основной вердикт": {
    configKey: "include_verdict",
    icon: Target,
    accent: "primary",
  },
  "Выявленные паттерны": {
    configKey: "include_patterns",
    icon: Search,
    accent: "neutral",
  },
  "Рекомендации": {
    configKey: "include_recommendations",
    icon: Lightbulb,
    accent: "success",
  },
  "Возможные причины различий": {
    configKey: "include_hypotheses",
    icon: Sparkles,
    accent: "warning",
  },
}

const ACCENT_STYLES = {
  primary: {
    icon: "bg-primary/10 text-primary",
    stripe: "bg-primary",
  },
  success: {
    icon: "bg-success/10 text-success",
    stripe: "bg-success",
  },
  warning: {
    icon: "bg-warning/10 text-warning",
    stripe: "bg-warning",
  },
  neutral: {
    icon: "bg-muted text-muted-foreground",
    stripe: "bg-muted-foreground/40",
  },
} as const

export function AnalysisReport({
  report,
  config,
  comparisonType,
}: AnalysisReportProps) {
  if (!report) return null

  const filteredSections = config
    ? report.sections.filter((section) => {
        const cfg = SECTION_CONFIG[section.title]
        if (!cfg) return true
        return config[cfg.configKey]
      })
    : report.sections

  return (
    <section className="space-y-4">
      {/* Verdict card */}
      {report.verdict && (
        <div className="relative overflow-hidden rounded-xl border border-border bg-card p-5 md:p-6">
          <div className="absolute left-0 top-0 h-full w-1 bg-primary" />
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold tracking-tight">
                  Аналитический отчёт
                </h2>
                {comparisonType && (
                  <Badge variant="secondary" className="text-[11px]">
                    {COMPARISON_TYPE_LABELS[comparisonType]}
                  </Badge>
                )}
              </div>
              <p className="mt-2 text-pretty text-base leading-relaxed">
                {report.verdict}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Sections grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {filteredSections
          .filter((section) => section.title !== "Основной вердикт")
          .map((section) => {
            const cfg = SECTION_CONFIG[section.title]
            const Icon = cfg?.icon ?? FileText
            const accent = ACCENT_STYLES[cfg?.accent ?? "neutral"]

            return (
              <div
                key={section.title}
                className="relative overflow-hidden rounded-xl border border-border bg-card p-4 md:p-5"
              >
                <div className={`absolute left-0 top-0 h-full w-1 ${accent.stripe}`} />
                <div className="flex items-start gap-3">
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${accent.icon}`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{section.title}</h3>
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {section.items.length}
                      </Badge>
                    </div>
                    {section.items.length > 0 ? (
                      <ul className="mt-2.5 space-y-2">
                        {section.items.map((item, idx) => (
                          <li
                            key={idx}
                            className="flex items-start gap-2 text-sm leading-relaxed text-foreground/80"
                          >
                            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">
                        Нет данных для этой секции
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
      </div>

      {/* Verdict section items (if verdict in filteredSections and has items) */}
      {filteredSections.find((s) => s.title === "Основной вердикт") && (
        <VerdictItemsCard
          section={filteredSections.find((s) => s.title === "Основной вердикт")!}
        />
      )}
    </section>
  )
}

function VerdictItemsCard({
  section,
}: {
  section: AnalysisReportType["sections"][number]
}) {
  if (section.items.length === 0) return null
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Target className="h-3.5 w-3.5" />
        </div>
        <h3 className="text-sm font-semibold">Ключевые выводы</h3>
      </div>
      <ol className="space-y-2">
        {section.items.map((item, idx) => (
          <li key={idx} className="flex items-start gap-3 text-sm leading-relaxed">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border bg-muted/30 font-mono text-[10px] text-muted-foreground tabular-nums">
              {idx + 1}
            </span>
            <span className="text-foreground/85">{item}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
