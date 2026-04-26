import { collectImageCandidates } from "@/content/domScanner";
import { inferImage } from "@/services/extensionInferenceService";
import { ExtensionSettings, ScanResult } from "@/lib/types";

export async function scanCurrentPage(settings: ExtensionSettings): Promise<ScanResult[]> {
  const candidates = collectImageCandidates(settings.scanLimit);
  const results: ScanResult[] = [];

  for (const candidate of candidates) {
    try {
      const result = await inferImage(candidate.src, settings);
      results.push({ ...result, candidateId: candidate.id, src: candidate.src });
    } catch (error) {
      results.push({
        candidateId: candidate.id,
        src: candidate.src,
        predictedLabel: "UNKNOWN",
        predictedProbability: 0,
        modelSource: "backend",
        error: error instanceof Error ? error.message : "scan error"
      });
    }
  }

  return results;
}
