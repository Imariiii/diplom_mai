import { describe, expect, it } from "vitest"
import {
  buildDefaultTestRunName,
  formatTestRunNameForSummary,
  isWhitespaceOnlyTestDisplayName,
  normalizeTestDisplayName,
  resolveTestRunName,
} from "./test-run-name"

describe("test-run-name", () => {
  it("normalizeTestDisplayName trims and drops empty", () => {
    expect(normalizeTestDisplayName("  hello  ")).toBe("hello")
    expect(normalizeTestDisplayName("   ")).toBeUndefined()
    expect(normalizeTestDisplayName("")).toBeUndefined()
  })

  it("buildDefaultTestRunName matches backend format", () => {
    expect(buildDefaultTestRunName(new Date(2026, 4, 21, 14, 30))).toBe("Тест 21.05.2026 14:30")
  })

  it("resolveTestRunName uses custom or default", () => {
    expect(resolveTestRunName("  My run ")).toBe("My run")
    expect(resolveTestRunName("")).toMatch(/^Тест \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$/)
  })

  it("formatTestRunNameForSummary marks auto names", () => {
    expect(formatTestRunNameForSummary("Custom")).toBe("Custom")
    expect(formatTestRunNameForSummary("")).toMatch(/^\(авто\) Тест /)
  })

  it("isWhitespaceOnlyTestDisplayName detects spaces-only", () => {
    expect(isWhitespaceOnlyTestDisplayName("   ")).toBe(true)
    expect(isWhitespaceOnlyTestDisplayName("")).toBe(false)
    expect(isWhitespaceOnlyTestDisplayName(undefined)).toBe(false)
  })
})
