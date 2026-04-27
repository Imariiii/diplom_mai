"use client"

import { useState } from "react"
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileText,
  Lightbulb,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react"

import type {
  AnalysisReport as AnalysisReportType,
  AnalysisMode,
  DbFinding,
  DbFindingStatus,
  DbMetricChipTone,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

interface AnalysisReportProps {
  report?: AnalysisReportType | null
  analysisMode?: AnalysisMode
}

const MODE_LABELS: Record<string, string> = {
  per_test: "Внутритестовый анализ",
  series: "Серийный анализ",
}

const STATUS_CONFIG: Record<
  DbFindingStatus,
  {
    icon: React.ReactNode
    border: string
    bg: string
    text: string
    badgeLabel: string
  }
> = {
  good: {
    icon: <CheckCircle2 className="h-4 w-4" />,
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/10",
    text: "text-emerald-600 dark:text-emerald-400",
    badgeLabel: "Стабильна",
  },
  warning: {
    icon: <AlertTriangle className="h-4 w-4" />,
    border: "border-amber-500/40",
    bg: "bg-amber-500/10",
    text: "text-amber-600 dark:text-amber-400",
    badgeLabel: "Внимание",
  },
  critical: {
    icon: <AlertCircle className="h-4 w-4" />,
    border: "border-destructive/40",
    bg: "bg-destructive/10",
    text: "text-destructive",
    badgeLabel: "Критично",
  },
}

const CHIP_TONE: Record<DbMetricChipTone, string> = {
  neutral: "",
  positive: "border-emerald-500/30 text-emerald-600 dark:text-emerald-400",
  negative: "border-destructive/30 text-destructive",
}

const SECTION_ICONS: Record<string, React.ReactNode> = {
  "Надёжность вывода": <ShieldCheck className="h-3.5 w-3.5" />,
  "Что делать дальше": <Lightbulb className="h-3.5 w-3.5" />,
}

export function AnalysisReport({ report, analysisMode }: AnalysisReportProps) {
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
  const summary = report.sections.find((s) => s.title === "Итог")
  const reliability = report.sections.find((s) => s.title === "Надёжность вывода")
  const actions = report.sections.find((s) => s.title === "Что делать дальше")
  const important = report.sections.find((s) => s.title === "Что важно")
  const hasFindings = report.per_db_findings && report.per_db_findings.length > 0

  if (!hasFindings) {
    return <LegacyReport report={report} modeLabel={modeLabel} />
  }

  return (
    <div className="space-y-4">
      {/* Header */}
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

      {/* Hero: Итог */}
      {summary && (
        <section className="relative overflow-hidden rounded-xl border border-primary/30 bg-card">
          <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-primary via-primary to-primary/40" />
          <div className="space-y-3 p-5 md:p-6">
            <Badge variant="outline" className="gap-1.5 border-primary/30 bg-primary/5 text-primary">
              <Sparkles className="h-3 w-3" />
              Ключевой вывод
            </Badge>
            <h3 className="text-pretty text-lg font-semibold leading-snug tracking-tight md:text-xl">
              {summary.items[0] || report.verdict}
            </h3>
            {summary.items.length > 1 && (
              <p className="text-sm text-muted-foreground">
                {summary.items.slice(1, 3).join(" ")}
              </p>
            )}
          </div>
        </section>
      )}

      {/* Per-DB scorecards grid */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {report.per_db_findings.map((finding) => (
          <DbScorecard key={finding.db_key} finding={finding} />
        ))}
      </div>

      {/* Compact footer: Надёжность + Действия */}
      {(reliability || actions) && (
        <div className="grid gap-3 md:grid-cols-2">
          {reliability && (
            <CompactSection
              icon={SECTION_ICONS["Надёжность вывода"]}
              title="Надёжность вывода"
              items={reliability.items}
            />
          )}
          {actions && (
            <CompactSection
              icon={SECTION_ICONS["Что делать дальше"]}
              title="Что делать дальше"
              items={actions.items}
            />
          )}
        </div>
      )}

      {/* Progressive disclosure: Что важно */}
      {important && important.items.length > 0 && (
        <ExpandableObservations items={important.items} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Per-DB Scorecard
// ---------------------------------------------------------------------------

function DbScorecard({ finding }: { finding: DbFinding }) {
  const cfg = STATUS_CONFIG[finding.status]

  return (
    <section className={cn("rounded-xl border bg-card", cfg.border)}>
      <div className="space-y-3 p-4">
        {/* Header: name + status badge */}
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-semibold tracking-tight">
            {finding.db_label}
          </h4>
          <Badge
            variant="outline"
            className={cn("shrink-0 gap-1 text-[10px]", cfg.bg, cfg.text, cfg.border)}
          >
            {cfg.icon}
            {cfg.badgeLabel}
          </Badge>
        </div>

        {/* Status reason */}
        <p className="text-xs text-muted-foreground">{finding.status_reason}</p>

        {/* Metric chips */}
        {finding.chips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {finding.chips.map((chip, idx) => (
              <Badge
                key={idx}
                variant="secondary"
                className={cn(
                  "text-[11px] font-normal",
                  CHIP_TONE[chip.tone],
                )}
              >
                {chip.label}: {chip.value}
              </Badge>
            ))}
          </div>
        )}

        {/* Highlights */}
        {finding.highlights.length > 0 && (
          <ul className="space-y-1.5 text-[13px] text-muted-foreground">
            {finding.highlights.map((item, idx) => (
              <li key={idx} className="flex gap-2 leading-relaxed">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Compact footer section
// ---------------------------------------------------------------------------

function CompactSection({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode
  title: string
  items: string[]
}) {
  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
          {icon}
        </div>
        <h4 className="text-xs font-semibold tracking-tight">{title}</h4>
      </div>
      <ul className="space-y-2 p-4 text-[13px] text-muted-foreground">
        {items.map((item, idx) => (
          <li key={idx} className="flex gap-2 leading-relaxed">
            <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Expandable observations (progressive disclosure)
// ---------------------------------------------------------------------------

function ExpandableObservations({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex w-full items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5",
            "text-sm text-muted-foreground transition-colors hover:bg-muted/50",
          )}
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span>
            {open ? "Скрыть" : "Показать"} полный список наблюдений ({items.length})
          </span>
          <ChevronDown
            className={cn(
              "ml-auto h-4 w-4 transition-transform",
              open && "rotate-180",
            )}
          />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="mt-2 space-y-2 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {items.map((item, idx) => (
            <li key={idx} className="flex gap-2.5 leading-relaxed">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

// ---------------------------------------------------------------------------
// Legacy fallback (when per_db_findings is missing / old API)
// ---------------------------------------------------------------------------

function LegacyReport({
  report,
  modeLabel,
}: {
  report: AnalysisReportType
  modeLabel: string
}) {
  const summary = report.sections.find((s) => s.title === "Итог")
  const otherSections = report.sections.filter((s) => s.title !== "Итог")

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

      {summary && (
        <section className="relative overflow-hidden rounded-xl border border-primary/30 bg-card">
          <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-primary via-primary to-primary/40" />
          <div className="space-y-3 p-5 md:p-6">
            <Badge variant="outline" className="gap-1.5 border-primary/30 bg-primary/5 text-primary">
              <Sparkles className="h-3 w-3" />
              Ключевой вывод
            </Badge>
            <h3 className="text-pretty text-lg font-semibold leading-snug tracking-tight md:text-xl">
              {summary.items[0] || report.verdict}
            </h3>
            {summary.items.length > 1 && (
              <div className="grid gap-2 md:grid-cols-2">
                {summary.items.slice(1).map((item, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-border bg-muted/25 px-3 py-2 text-sm text-muted-foreground"
                  >
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {otherSections.map((section) => (
          <LegacySectionCard key={section.title} section={section} />
        ))}
      </div>
    </div>
  )
}

function LegacySectionCard({
  section,
}: {
  section: AnalysisReportType["sections"][number]
}) {
  const LEGACY_ICONS: Record<string, React.ReactNode> = {
    "Что важно": <Search className="h-4 w-4" />,
    "Надёжность вывода": <ShieldCheck className="h-4 w-4" />,
    "Что делать дальше": <Lightbulb className="h-4 w-4" />,
  }
  const icon = LEGACY_ICONS[section.title] || <FileText className="h-4 w-4" />

  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex items-start gap-2.5 border-b border-border/60 p-4">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          {icon}
        </div>
        <h3 className="text-sm font-semibold tracking-tight">{section.title}</h3>
      </div>
      <div className="p-4">
        <ul className="space-y-3 text-sm text-muted-foreground">
          {section.items.map((item, idx) => (
            <li key={idx} className="flex gap-2.5 leading-relaxed">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
