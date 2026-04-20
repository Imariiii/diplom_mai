"use client"

import { create } from "zustand"
import type { TestConfig, TestRun, TimeSeriesPoint } from "./types"

interface AppState {
  currentPage: "home" | "connections" | "config" | "scenarios" | "dashboards" | "history" | "comparison" | "database-state"
  setCurrentPage: (page: "home" | "connections" | "config" | "scenarios" | "dashboards" | "history" | "comparison" | "database-state") => void
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

  connectionNames: Record<string, string>
  setConnectionNames: (names: Record<string, string>) => void

  connectionDbTypes: Record<string, string>
  setConnectionDbTypes: (types: Record<string, string>) => void
  updateConnectionDbType: (key: string, dbType: string) => void

  comparisonTestIds: string[]
  comparisonBaselineId: string | null
  analysisMode: "per_test" | "series"
  setComparisonSelection: (testIds: string[], baselineId?: string | null, mode?: "per_test" | "series") => void
  clearComparisonSelection: () => void
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
    bundleId: undefined,
    useIndexes: false,
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

  connectionNames: {},
  setConnectionNames: (names) => set((state) => ({ connectionNames: { ...state.connectionNames, ...names } })),

  connectionDbTypes: {},
  setConnectionDbTypes: (types) => set((state) => ({ connectionDbTypes: { ...state.connectionDbTypes, ...types } })),
  updateConnectionDbType: (key, dbType) => set((state) => ({
    connectionDbTypes: { ...state.connectionDbTypes, [key]: dbType }
  })),

  comparisonTestIds: [],
  comparisonBaselineId: null,
  analysisMode: "per_test",
  setComparisonSelection: (testIds, baselineId = null, mode = "per_test") => set({
    comparisonTestIds: testIds,
    comparisonBaselineId: baselineId ?? testIds[0] ?? null,
    analysisMode: mode,
  }),
  clearComparisonSelection: () => set({
    comparisonTestIds: [],
    comparisonBaselineId: null,
    analysisMode: "per_test",
  }),
}))
