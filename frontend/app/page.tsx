"use client"

import { Header } from "@/components/header"
import { Sidebar } from "@/components/sidebar"
import { HomePage } from "@/components/pages/home-page"
import { ConnectionsPage } from "@/components/pages/connections-page"
import { ConfigPage } from "@/components/pages/config-page"
import { DatabaseStatePage } from "@/components/pages/database-state-page"
import { ScenariosPage } from "@/components/pages/scenarios-page"
import { DashboardsPage } from "@/components/pages/dashboards-page"
import { ReportsPage } from "@/components/pages/reports-page"
import { HistoryPage } from "@/components/pages/history-page"
import { ComparisonPage } from "@/components/pages/comparison-page"
import { useAppStore } from "@/lib/store"

export default function Page() {
  const { currentPage } = useAppStore()

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar />
      <main className="min-h-[calc(100vh-3.5rem)]">
        {currentPage === "home" && <HomePage />}
        {currentPage === "connections" && <ConnectionsPage />}
        {currentPage === "config" && <ConfigPage />}
        {currentPage === "scenarios" && <ScenariosPage />}
        {currentPage === "dashboards" && <DashboardsPage />}
        {currentPage === "reports" && <ReportsPage />}
        {currentPage === "history" && <HistoryPage />}
        {currentPage === "comparison" && <ComparisonPage />}
        {currentPage === "database-state" && <DatabaseStatePage />}
      </main>
    </div>
  )
}
