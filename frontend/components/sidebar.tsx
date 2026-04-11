"use client"

import { X, Home, Settings, BarChart3, FileText, History, Database, Plug } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/lib/store"
import { cn } from "@/lib/utils"

const navItems = [
  { id: "home", label: "Начальная страница", icon: Home },
  { id: "connections", label: "Подключения к СУБД", icon: Plug },
  { id: "config", label: "Конфигурация и запуск", icon: Settings },
  { id: "scenarios", label: "Сценарии тестирования", icon: Database },
  { id: "dashboards", label: "Дашборды", icon: BarChart3 },
  { id: "reports", label: "Отчёты", icon: FileText },
  { id: "history", label: "История тестов", icon: History },
  { id: "comparison", label: "Сравнение тестов", icon: BarChart3 },
] as const

export function Sidebar() {
  const { sidebarOpen, setSidebarOpen, currentPage, setCurrentPage } = useAppStore()

  return (
    <>
      {sidebarOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40" onClick={() => setSidebarOpen(false)} />
      )}

      <aside
        className={cn(
          "fixed top-0 left-0 h-full w-72 bg-sidebar border-r border-sidebar-border z-50 transform transition-transform duration-200 ease-in-out",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
          <span className="font-semibold text-sidebar-foreground">Навигация</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            className="text-sidebar-foreground hover:bg-sidebar-accent"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="p-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setCurrentPage(item.id)
                setSidebarOpen(false)
              }}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors",
                currentPage === item.id
                  ? "bg-sidebar-accent text-sidebar-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50",
              )}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
    </>
  )
}
