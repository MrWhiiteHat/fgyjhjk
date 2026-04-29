export function formatPercentScore(value: number): string {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  return `${(clamped * 100).toFixed(2)}%`;
}

export function formatMs(value: number): string {
  const numeric = Number.isFinite(value) ? value : 0;
  return `${numeric.toFixed(2)} ms`;
}

export function toFriendlyError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Unexpected error. Please try again.";
}

export function estimateAverageConfidence(scores: number[]): number {
  if (scores.length === 0) {
    return 0;
  }
  const total = scores.reduce((acc, value) => acc + value, 0);
  return total / scores.length;
}
