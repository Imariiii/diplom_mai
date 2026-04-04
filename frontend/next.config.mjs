import { existsSync } from "node:fs"
import { resolve } from "node:path"

const rootEnvPath = resolve(process.cwd(), "..", ".env")

if (typeof process.loadEnvFile === "function" && existsSync(rootEnvPath)) {
  process.loadEnvFile(rootEnvPath)
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
  },
}

export default nextConfig
