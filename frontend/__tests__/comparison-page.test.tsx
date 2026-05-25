// @vitest-environment node
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

describe("ComparisonPage", () => {
  it("не показывает раздел ресурсов хоста и СУБД", async () => {
    const pagePath = fileURLToPath(
      new URL("../components/pages/comparison-page.tsx", import.meta.url)
    )
    const pageSource = readFileSync(pagePath, "utf8")

    expect(pageSource).not.toContain("ResourceMetricsPanel")
  })
})
