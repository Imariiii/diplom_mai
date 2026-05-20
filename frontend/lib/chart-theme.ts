"use client"

import { useCallback, useEffect, useState } from "react"
import { useTheme } from "next-themes"

export type ChartThemeToken =
  | "--border"
  | "--foreground"
  | "--muted-foreground"
  | "--card"
  | "--card-foreground"

/** Читает значение CSS-переменной темы (oklch/hsl) с documentElement. */
export function getThemeColor(token: ChartThemeToken): string {
  if (typeof document === "undefined") {
    return ""
  }
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim()
}

export interface ChartThemeColors {
  border: string
  foreground: string
  mutedForeground: string
  card: string
  cardForeground: string
}

function resolveChartThemeColors(): ChartThemeColors {
  return {
    border: getThemeColor("--border"),
    foreground: getThemeColor("--foreground"),
    mutedForeground: getThemeColor("--muted-foreground"),
    card: getThemeColor("--card"),
    cardForeground: getThemeColor("--card-foreground"),
  }
}

/** Реактивные цвета графиков при смене light/dark. */
export function useChartTheme(): ChartThemeColors {
  const { resolvedTheme } = useTheme()
  const [colors, setColors] = useState<ChartThemeColors>(resolveChartThemeColors)

  const refresh = useCallback(() => {
    setColors(resolveChartThemeColors())
  }, [])

  useEffect(() => {
    refresh()
  }, [resolvedTheme, refresh])

  return colors
}
