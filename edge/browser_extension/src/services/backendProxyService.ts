import { ScanResult } from "@/lib/types";

export async function backendPredictImage(
  backendBaseUrl: string,
  imageUrl: string,
  threshold = 0.5
): Promise<ScanResult> {
  const endpoint = `${backendBaseUrl}/api/v1/predict/image-url`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ image_url: imageUrl, threshold })
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: ${response.status}`);
  }

  const payload = (await response.json()) as Record<string, unknown>;
  const data = (payload.data || {}) as Record<string, any>;
  const prediction = (data.prediction || {}) as Record<string, any>;

  return {
    candidateId: imageUrl,
    src: imageUrl,
    predictedLabel: (prediction.predicted_label as "REAL" | "FAKE" | "UNKNOWN") || "UNKNOWN",
    predictedProbability: Number(prediction.predicted_probability || 0),
    modelSource: "backend"
  };
}
