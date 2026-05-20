"use client"

import { Menu, Database } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { useAppStore } from "@/lib/store"

export function Header() {
  const { setSidebarOpen } = useAppStore()

  return (
    <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setSidebarOpen(true)}
        className="text-muted-foreground hover:text-foreground"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex items-center gap-2">
        <Database className="h-5 w-5 text-primary" />
        <span className="font-semibold text-lg">TestBDBench</span>
        <ThemeToggle />
      </div>
    </header>
  )
}
