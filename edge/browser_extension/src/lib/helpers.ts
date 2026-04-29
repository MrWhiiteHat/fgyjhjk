import { ScanResult, ScanSummary } from "@/lib/types";

export function randomId(prefix = "id"): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function summarizeResults(results: ScanResult[]): ScanSummary {
  const summary: ScanSummary = {
    scanned: results.length,
    fakeCount: 0,
    realCount: 0,
    unknownCount: 0
  };

  for (const result of results) {
    if (result.predictedLabel === "FAKE") {
      summary.fakeCount += 1;
    } else if (result.predictedLabel === "REAL") {
      summary.realCount += 1;
    } else {
      summary.unknownCount += 1;
    }
  }

  return summary;
}
