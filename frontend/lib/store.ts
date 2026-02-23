"use client"

import { create } from "zustand"
import type { TestConfig, TestRun, TimeSeriesPoint } from "./types"

interface AppState {
  currentPage: "home" | "config" | "dashboards" | "reports" | "history"
  setCurrentPage: (page: "home" | "config" | "dashboards" | "reports" | "history") => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void

  testConfig: TestConfig
  setTestConfig: (config: Partial<TestConfig>) => void

  currentTest: TestRun | null
  setCurrentTest: (test: TestRun | null) => void

  testHistory: TestRun[]
  addTestToHistory: (test: TestRun) => void

  realtimeData: Record<string, TimeSeriesPoint[]>
  addRealtimeData: (databaseId: string, point: TimeSeriesPoint) => void
  clearRealtimeData: () => void
}

export const useAppStore = create<AppState>((set) => ({
  currentPage: "home",
  setCurrentPage: (page) => set({ currentPage: page }),
  sidebarOpen: false,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  testConfig: {
    databases: [],
    testMode: "scenario",       // По умолчанию: режим со сценарием
    scenario: "mixed_light",     // По умолчанию: 80% SELECT, 20% UPDATE (как TPC-C)
    selectedQueryId: "",         // Выбранный запрос из списка
    customSql: "",               // Пользовательский SQL
    virtualUsers: 10,            // 10 виртуальных пользователей
    iterations: 100,             // 100 итераций на пользователя
    warmupTime: 5,               // 5 секунд прогрева
    queryTypes: ["mixed"],
    dataSize: "medium",
  },
  setTestConfig: (config) => set((state) => ({ testConfig: { ...state.testConfig, ...config } })),

  currentTest: null,
  setCurrentTest: (test) => set({ currentTest: test }),

  testHistory: [],
  addTestToHistory: (test) => set((state) => ({ testHistory: [...state.testHistory, test] })),

  realtimeData: {},
  addRealtimeData: (databaseId, point) =>
    set((state) => ({
      realtimeData: {
        ...state.realtimeData,
        [databaseId]: [...(state.realtimeData[databaseId] || []), point].slice(-100),
      },
    })),
  clearRealtimeData: () => set({ realtimeData: {} }),
}))
