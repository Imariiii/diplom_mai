import { afterEach, describe, expect, it, vi } from "vitest"
import { getThemeColor } from "@/lib/chart-theme"

describe("getThemeColor", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns trimmed CSS variable value from documentElement", () => {
    vi.stubGlobal("document", {
      documentElement: {},
    })
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      getPropertyValue: (name: string) => {
        if (name === "--border") return " oklch(0.9 0.01 260) "
        if (name === "--foreground") return "oklch(0.2 0.02 260)"
        return ""
      },
    } as CSSStyleDeclaration)

    expect(getThemeColor("--border")).toBe("oklch(0.9 0.01 260)")
    expect(getThemeColor("--foreground")).toBe("oklch(0.2 0.02 260)")
  })

  it("returns empty string when document is undefined", () => {
    const originalDocument = globalThis.document
    // @ts-expect-error — simulate SSR
    delete globalThis.document

    expect(getThemeColor("--border")).toBe("")

    globalThis.document = originalDocument
  })
})
