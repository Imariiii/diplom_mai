/**
 * Unit-тесты для Zustand store (useAppStore).
 * Проверяют навигацию, управление comparison selection,
 * конфигурацию тестов и realtime data.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "@/lib/store";

describe("useAppStore", () => {
  beforeEach(() => {
    // Сбрасываем store перед каждым тестом
    const { setState } = useAppStore;
    setState({
      currentPage: "home",
      sidebarOpen: false,
      comparisonTestIds: [],
      comparisonBaselineId: null,
      realtimeData: {},
      connectionNames: {},
      connectionDbTypes: {},
      testHistory: [],
      currentTest: null,
    });
  });

  // =============================================
  // Navigation
  // =============================================

  describe("navigation", () => {
    it("default page is home", () => {
      expect(useAppStore.getState().currentPage).toBe("home");
    });

    it("setCurrentPage changes page", () => {
      useAppStore.getState().setCurrentPage("comparison");
      expect(useAppStore.getState().currentPage).toBe("comparison");
    });

    it("setSidebarOpen toggles sidebar", () => {
      useAppStore.getState().setSidebarOpen(true);
      expect(useAppStore.getState().sidebarOpen).toBe(true);
    });
  });

  // =============================================
  // Comparison selection
  // =============================================

  describe("comparison selection", () => {
    it("setComparisonSelection sets ids and default baseline", () => {
      useAppStore.getState().setComparisonSelection(["id1", "id2"]);
      const state = useAppStore.getState();
      expect(state.comparisonTestIds).toEqual(["id1", "id2"]);
      expect(state.comparisonBaselineId).toBe("id1");
    });

    it("setComparisonSelection with explicit baseline", () => {
      useAppStore.getState().setComparisonSelection(["id1", "id2"], "id2");
      expect(useAppStore.getState().comparisonBaselineId).toBe("id2");
    });

    it("clearComparisonSelection resets", () => {
      useAppStore.getState().setComparisonSelection(["id1", "id2"]);
      useAppStore.getState().clearComparisonSelection();
      const state = useAppStore.getState();
      expect(state.comparisonTestIds).toEqual([]);
      expect(state.comparisonBaselineId).toBeNull();
    });
  });

  // =============================================
  // Test config
  // =============================================

  describe("test config", () => {
    it("setTestConfig merges partial config", () => {
      useAppStore.getState().setTestConfig({ virtualUsers: 20 });
      expect(useAppStore.getState().testConfig.virtualUsers).toBe(20);
      // Other fields remain
      expect(useAppStore.getState().testConfig.iterations).toBe(100);
    });

    it("default scenario is mixed_light", () => {
      expect(useAppStore.getState().testConfig.scenario).toBe("mixed_light");
    });
  });

  // =============================================
  // Realtime data
  // =============================================

  describe("realtime data", () => {
    it("addRealtimeData adds a point", () => {
      const point = {
        timestamp: Date.now(),
        avgResponseTime: 10,
        tps: 100,
        successCount: 50,
        failCount: 0,
      };
      useAppStore.getState().addRealtimeData("db1", point as any);
      expect(useAppStore.getState().realtimeData["db1"]).toHaveLength(1);
    });

    it("clearRealtimeData empties all", () => {
      useAppStore.getState().addRealtimeData("db1", { timestamp: 1 } as any);
      useAppStore.getState().clearRealtimeData();
      expect(useAppStore.getState().realtimeData).toEqual({});
    });

    it("caps at 100 points per db", () => {
      for (let i = 0; i < 110; i++) {
        useAppStore.getState().addRealtimeData("db1", { timestamp: i } as any);
      }
      expect(useAppStore.getState().realtimeData["db1"].length).toBeLessThanOrEqual(100);
    });
  });

  // =============================================
  // Connection management
  // =============================================

  describe("connection management", () => {
    it("setConnectionNames merges", () => {
      useAppStore.getState().setConnectionNames({ c1: "MySQL" });
      useAppStore.getState().setConnectionNames({ c2: "PG" });
      const names = useAppStore.getState().connectionNames;
      expect(names.c1).toBe("MySQL");
      expect(names.c2).toBe("PG");
    });

    it("updateConnectionDbType updates single key", () => {
      useAppStore.getState().updateConnectionDbType("c1", "postgresql");
      expect(useAppStore.getState().connectionDbTypes.c1).toBe("postgresql");
    });
  });
});
