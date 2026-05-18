"use client"

/**
 * Единый блок параметров нагрузки: виртуальные пользователи, итерации, прогрев.
 *
 * Паттерн 2025: slider + редактируемое числовое поле рядом.
 * Ползунок — быстрая визуальная коррекция в типичном диапазоне.
 * Поле — целочисленный ввод без верхней границы (кроме правил валидации).
 * Валидация при фиксации (blur / Enter): только неотрицательные целые, без текста и дробей;
 * для параметров с min ≥ 1 ноль недопустим. Во время ввода допускаются только цифры.
 */

import { useCallback, useId, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { SlidersHorizontal } from "lucide-react"

// Типичные пресеты для быстрого выбора
const VU_PRESETS = [10, 50, 100, 200, 500]
const ITER_PRESETS = [100, 500, 1000, 2000]
const WARMUP_PRESETS = [0, 5, 10, 30]

interface LoadParamsCardProps {
  virtualUsers: number
  iterations: number
  warmupTime: number
  onVirtualUsersChange: (v: number) => void
  onIterationsChange: (v: number) => void
  onWarmupTimeChange: (v: number) => void
}

// ─── Один ряд параметра ────────────────────────────────────────────────────

interface ParamRowProps {
  label: string
  hint: string
  value: number
  unit?: string
  /** Визуальный диапазон ползунка (не ограничивает ввод) */
  sliderMax: number
  min: number
  step: number
  presets: number[]
  onChange: (v: number) => void
}

function ParamRow({ label, hint, value, unit, sliderMax, min, step, presets, onChange }: ParamRowProps) {
  const inputId = useId()
  /** Строка во время редактирования; только цифры или пусто */
  const [rawInput, setRawInput] = useState<string | null>(null)

  const displayValue = rawInput !== null ? rawInput : String(value)

  /** true, если строка — целое ≥ min (для min=0 допускается 0) */
  const isValidInteger = useCallback(
    (trimmed: string): boolean => {
      if (trimmed === "" || !/^\d+$/.test(trimmed)) return false
      const n = parseInt(trimmed, 10)
      return Number.isFinite(n) && n >= min
    },
    [min],
  )

  const commit = useCallback(
    (raw: string) => {
      const t = raw.trim()
      setRawInput(null)
      if (t === "") return
      if (!isValidInteger(t)) return
      const n = parseInt(t, 10)
      onChange(n)
    },
    [isValidInteger, onChange],
  )

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const digits = e.target.value.replace(/\D/g, "")
    setRawInput(digits)
  }

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => commit(e.target.value)

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      commit((e.target as HTMLInputElement).value)
      ;(e.target as HTMLInputElement).blur()
    }
    if (e.key === "ArrowUp") {
      e.preventDefault()
      const next = value + step
      if (next >= min) onChange(next)
    }
    if (e.key === "ArrowDown") {
      e.preventDefault()
      onChange(Math.max(min, value - step))
    }
  }

  // Ползунок показывает значение в пределах sliderMax; если value > sliderMax — большой прогресс
  const sliderValue = Math.min(value, sliderMax)

  return (
    <div className="space-y-2.5">
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <label htmlFor={inputId} className="cursor-pointer text-sm font-medium leading-none">
            {label}
          </label>
          <p className="mt-0.5 text-xs text-muted-foreground text-pretty">{hint}</p>
        </div>

        {/* Числовое поле: произвольный ввод, клампинг на blur */}
        <div className="flex shrink-0 items-center gap-1.5">
          <input
            id={inputId}
            inputMode="numeric"
            aria-label={label}
            value={displayValue}
            onChange={handleChange}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            className="h-9 w-24 rounded-md border border-input bg-background px-3 py-1 text-right font-mono text-sm tabular-nums shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
          />
          {unit && (
            <span className="min-w-[2rem] text-sm text-muted-foreground">{unit}</span>
          )}
        </div>
      </div>

      {/* Ползунок — визуальный scrubber в «типичном» диапазоне */}
      <Slider
        value={[sliderValue]}
        min={min}
        max={sliderMax}
        step={step}
        onValueChange={([v]) => onChange(v)}
        aria-label={label}
        className="w-full"
      />

      {/* Метки диапазона */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{min}{unit}</span>
        <span className="text-[10px] opacity-60">типичный диапазон до {sliderMax}{unit}</span>
        <span>{sliderMax}{unit}</span>
      </div>

      {/* Пресеты — быстрый выбор */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={`Быстрый выбор: ${label}`}>
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            className={`rounded-md border px-2.5 py-0.5 text-xs font-mono transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              value === p
                ? "border-primary bg-primary/10 font-semibold text-primary"
                : "border-border bg-background text-muted-foreground hover:border-muted-foreground hover:text-foreground"
            }`}
          >
            {p}{unit}
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Основной компонент ────────────────────────────────────────────────────

export function LoadParamsCard({
  virtualUsers,
  iterations,
  warmupTime,
  onVirtualUsersChange,
  onIterationsChange,
  onWarmupTimeChange,
}: LoadParamsCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <SlidersHorizontal className="h-5 w-5 text-primary" />
          Параметры нагрузки
        </CardTitle>
        <CardDescription className="text-pretty">
          Только целые числа: без дробей, букв и отрицательных значений. Для пользователей и итераций минимум 1; время прогрева может быть 0.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-7 pt-4">
        <ParamRow
          label="Виртуальные пользователи"
          hint="Число параллельных соединений к базе данных"
          value={virtualUsers}
          sliderMax={200}
          min={1}
          step={1}
          presets={VU_PRESETS}
          onChange={onVirtualUsersChange}
        />

        <div className="h-px bg-border" aria-hidden />

        <ParamRow
          label="Итерации"
          hint="Количество выполнений запроса на одного пользователя"
          value={iterations}
          sliderMax={1000}
          min={1}
          step={1}
          presets={ITER_PRESETS}
          onChange={onIterationsChange}
        />

        <div className="h-px bg-border" aria-hidden />

        <ParamRow
          label="Время прогрева"
          hint="Нагрузка тем же SQL и числом VU перед измерением: пул соединений, планы, buffer pool. Не входит в итоговые метрики."
          value={warmupTime}
          unit=" сек"
          sliderMax={300}
          min={0}
          step={1}
          presets={WARMUP_PRESETS}
          onChange={onWarmupTimeChange}
        />
      </CardContent>
    </Card>
  )
}
