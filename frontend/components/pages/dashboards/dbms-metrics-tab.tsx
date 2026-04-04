"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"

interface DbmsMetrics {
  cacheHitRatio?: number
  bufferPoolHitRatio?: number
  lockWaits?: number
  deadlocks?: number
  totalDBSizeMB?: number
  tableSizesMB?: Record<string, number>
}

interface TestResult {
  databaseId: string
  dbmsMetrics?: DbmsMetrics
}

interface RealtimeDataPoint {
  cacheHitRatio?: number
  bufferPoolHitRatio?: number
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

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {databases.map((dbId) => {
          const result = getResultForDb(dbId)
          const dbmsMetrics = result?.dbmsMetrics
          const dbType = getDbType ? getDbType(dbId) : dbId
          const displayName = getDbDisplayName ? getDbDisplayName(dbId) : (DB_NAMES[dbType] || dbType)

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
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">Cache Hit Ratio</div>
                    <div className="text-2xl font-mono text-foreground">
                      {dbmsMetrics?.cacheHitRatio?.toFixed(1) || getRealtimeDbmsMetric(dbId, "cacheHitRatio")}%
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">Buffer Pool Hit</div>
                    <div className="text-2xl font-mono text-foreground">
                      {dbmsMetrics?.bufferPoolHitRatio?.toFixed(1) || getRealtimeDbmsMetric(dbId, "bufferPoolHitRatio")}%
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">Ожидание блокировок</div>
                    <div className="text-2xl font-mono text-foreground">
                      {dbmsMetrics?.lockWaits ?? getRealtimeDbmsMetric(dbId, "lockWaits", "0")}
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground">Дедлоки</div>
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
