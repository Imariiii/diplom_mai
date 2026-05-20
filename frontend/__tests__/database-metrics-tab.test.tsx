import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DatabaseMetricsTab } from "@/components/pages/dashboards/database-metrics-tab"

describe("DatabaseMetricsTab", () => {
  it("shows transaction window units for transaction workload", () => {
    render(
      <DatabaseMetricsTab
        databases={["db1"]}
        chartData={[]}
        getResultForDb={() => undefined}
        getLatestMetric={() => "0.00"}
        getDbDisplayName={() => "Pagila"}
        getDbType={() => "postgresql"}
        virtualUsers={10}
        isTestFinished={false}
        showCharts={false}
        workloadMode="transaction"
        primaryRateUnit="tps"
      />,
    )

    expect(screen.getByText("Транзакций в окне")).toBeTruthy()
    expect(screen.queryByText("Запросов в окне")).toBeNull()
  })
})
