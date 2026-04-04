"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Database, CheckCircle, XCircle, BarChart3 } from "lucide-react"
import { DB_NAMES, getDbColor, CHART_COLORS } from "@/lib/chart-colors"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"

interface TransactionMetrics {
  totalTransactions?: number
  successfulTransactions?: number
  failedTransactions?: number
  rollbacks?: number
}

interface TestResult {
  databaseId: string
  transactionMetrics?: TransactionMetrics
}

interface TransactionMetricsTabProps {
  databases: string[]
  results: TestResult[] | undefined
}

export function TransactionMetricsTab({ databases, results }: TransactionMetricsTabProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {databases.map((dbId) => {
          const result = results?.find(r => r.databaseId === dbId)
          const txMetrics = result?.transactionMetrics
          const total = txMetrics?.totalTransactions || 0
          const successful = txMetrics?.successfulTransactions || 0
          const failed = txMetrics?.failedTransactions || 0
          const successRate = total > 0 ? ((successful / total) * 100).toFixed(1) : "0"

          return (
            <Card key={dbId} className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Database className="h-5 w-5" style={{ color: getDbColor(dbId) }} />
                  {DB_NAMES[dbId]}
                </CardTitle>
                <CardDescription>Статистика транзакций</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Всего транзакций</span>
                  <span className="font-mono text-lg text-foreground">{total}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    Успешные
                  </span>
                  <span className="font-mono text-lg text-green-500">{successful}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <XCircle className="h-4 w-4 text-red-500" />
                    Неудачные
                  </span>
                  <span className="font-mono text-lg text-red-500">{failed}</span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-border">
                  <span className="text-muted-foreground">Успешность</span>
                  <span className="font-mono text-lg text-foreground">{successRate}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Откаты</span>
                  <span className="font-mono text-lg text-foreground">{txMetrics?.rollbacks || 0}</span>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {results && results.length > 0 && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <BarChart3 className="h-5 w-5 text-primary" />
              Сравнение транзакций
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={results.map(r => ({
                    name: DB_NAMES[r.databaseId] || r.databaseId,
                    successful: r.transactionMetrics?.successfulTransactions || 0,
                    failed: r.transactionMetrics?.failedTransactions || 0,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="name"
                    stroke={CHART_COLORS.axis}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  <YAxis
                    stroke={CHART_COLORS.axis}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      color: CHART_COLORS.text,
                    }}
                    labelStyle={{ color: CHART_COLORS.text }}
                  />
                  <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                  <Bar dataKey="successful" name="Успешные" fill={CHART_COLORS.success} />
                  <Bar dataKey="failed" name="Неудачные" fill={CHART_COLORS.error} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
