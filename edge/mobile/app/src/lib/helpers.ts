import * as Crypto from "expo-crypto";

export function formatProbability(value: number): string {
  return `${(Math.max(0, Math.min(1, value)) * 100).toFixed(2)}%`;
}

export function formatDurationMs(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return "0 ms";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} s`;
  }
  return `${value.toFixed(1)} ms`;
}

export function formatFileSize(bytes: number): string {
  if (bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(2)} ${units[idx]}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function randomId(prefix = "id"): string {
  const randomPart = Math.random().toString(36).slice(2, 10);
  return `${prefix}_${Date.now()}_${randomPart}`;
}

export async function sha256FromText(value: string): Promise<string> {
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, value);
}

export function safeNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}
