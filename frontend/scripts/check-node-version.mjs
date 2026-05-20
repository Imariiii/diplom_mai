#!/usr/bin/env node
/**
 * Проверка версии Node.js перед запуском Vitest/Playwright.
 * Согласовано с engines в package.json и .nvmrc в корне репозитория.
 */
const [major, minor, patch] = process.versions.node.split(".").map(Number);
const min = { major: 20, minor: 19, patch: 0 };
const maxExclusive = { major: 21, minor: 0, patch: 0 };

function compare(a, b) {
  if (a.major !== b.major) return a.major - b.major;
  if (a.minor !== b.minor) return a.minor - b.minor;
  return a.patch - b.patch;
}

const current = { major, minor, patch };

if (compare(current, min) < 0 || compare(current, maxExclusive) >= 0) {
  console.error(
    `[frontend] Требуется Node ${min.major}.${min.minor}.${min.patch} <= v < ${maxExclusive.major}.0.0, сейчас ${process.versions.node}.`,
  );
  console.error("[frontend] В корне репозитория: nvm use  (см. .nvmrc)");
  process.exit(1);
}
