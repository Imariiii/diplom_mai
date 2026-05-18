"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { getCacheHitDisplay, type CacheHitDisplayInput } from "@/lib/dbms-cache-metrics"

interface DbmsMetrics extends CacheHitDisplayInput {
  lockWaits?: number
  lockWaitsMode?: "current" | "delta" | "sampled_max"
  deadlocks?: number
  deadlocksMode?: "current" | "delta" | "sampled_max"
  totalDBSizeMB?: number
  tableSizesMB?: Record<string, number>
}

interface TestResult {
  databaseId: string
  dbmsMetrics?: DbmsMetrics
}

interface RealtimeDataPoint extends CacheHitDisplayInput {
  lockWaits?: number
  deadlocks?: number
}

interface DbmsMetricsTabProps {
  databases: string[]
  realtimeData: Record<string, RealtimeDataPoint[]>
  getResultForDb: (dbId: string) => TestResult | undefined
  getDbType?: (dbKey: string) => string
  getDbDisplayName?: (dbKey: string) => string
}

export function DbmsMetricsTab({ databases, realtimeData, getResultForDb, getDbType, getDbDisplayName }: DbmsMetricsTabProps) {
  const getRealtimeDbmsMetric = (dbId: string, metric: string, defaultValue: string = "—") => {
    const points = realtimeData[dbId]
    if (!points || points.length === 0) return defaultValue
    const value = points[points.length - 1][metric as keyof RealtimeDataPoint]
    return typeof value === "number" ? value.toFixed(1) : defaultValue
  }

  const resolveCacheDisplay = (dbId: string, dbmsMetrics?: DbmsMetrics) => {
    if (dbmsMetrics?.cacheHitRatioStatus || dbmsMetrics?.cacheHitRatio !== undefined) {
      return getCacheHitDisplay(dbmsMetrics)
    }
    const points = realtimeData[dbId]
    if (points && points.length > 0) {
      return getCacheHitDisplay(points[points.length - 1])
    }
    return getCacheHitDisplay({})
  }

  const getLockWaitsLabel = (mode?: DbmsMetrics["lockWaitsMode"]) => {
    if (mode === "delta") return "Ожидания блокировок за прогон"
    if (mode === "sampled_max") return "Пик ожиданий блокировок"
    return "Текущие ожидания блокировок"
  }

  const getDeadlocksLabel = (mode?: DbmsMetrics["deadlocksMode"]) => {
    if (mode === "delta") return "Дедлоки за прогон"
    return "Дедлоки"
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {databases.map((dbId) => {
          const result = getResultForDb(dbId)
          const dbmsMetrics = result?.dbmsMetrics
          const dbType = getDbType ? getDbType(dbId) : dbId
          const displayName = getDbDisplayName ? getDbDisplayName(dbId) : (DB_NAMES[dbType] || dbType)
          const cacheDisplay = resolveCacheDisplay(dbId, dbmsMetrics)

          return (
            <Card key={dbId} className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Database className="h-5 w-5" style={{ color: getDbColor(dbType) }} />
                  {displayName} — Внутренние метрики
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-muted rounded-lg col-span-2" title={cacheDisplay.title}>
                    <div className="text-sm text-muted-foreground">Доля попаданий в кэш за прогон</div>
                    <div className="text-2xl font-mono text-foreground">{cacheDisplay.valueText}</div>
                    <div className="text-xs text-muted-foreground mt-1">{cacheDisplay.subtitle}</div>
                    {cacheDisplay.details ? (
                      <div className="text-xs text-muted-foreground mt-2 whitespace-pre-line border-t border-border pt-2">
                        {cacheDisplay.details}
                      </div>
                    ) : null}
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">{getLockWaitsLabel(dbmsMetrics?.lockWaitsMode)}</div>
                    <div className="text-2xl font-mono text-foreground">
                      {dbmsMetrics?.lockWaits ?? getRealtimeDbmsMetric(dbId, "lockWaits", "0")}
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">{getDeadlocksLabel(dbmsMetrics?.deadlocksMode)}</div>
                    <div className="text-2xl font-mono text-foreground">
                      {dbmsMetrics?.deadlocks ?? getRealtimeDbmsMetric(dbId, "deadlocks", "0")}
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-border">
                  <div className="text-sm text-muted-foreground mb-2">Размер БД</div>
                  <div className="text-xl font-mono text-foreground">
                    {dbmsMetrics?.totalDBSizeMB?.toFixed(2) || "—"} MB
                  </div>
                </div>

                {dbmsMetrics?.tableSizesMB && Object.keys(dbmsMetrics.tableSizesMB).length > 0 && (
                  <div className="pt-4 border-t border-border">
                    <div className="text-sm text-muted-foreground mb-2">Размеры таблиц (топ-5)</div>
                    <div className="space-y-1">
                      {Object.entries(dbmsMetrics.tableSizesMB)
                        .slice(0, 5)
                        .map(([table, size]) => (
                          <div key={table} className="flex justify-between text-sm">
                            <span className="text-muted-foreground truncate mr-2">{table}</span>
                            <span className="font-mono text-foreground">{size.toFixed(2)} MB</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}