import { BACKEND_BASE_URL, DEFAULT_THRESHOLD } from "./constants";
import { DetectionRequest, ExplainabilityResult, PredictionResult } from "./types";

interface BackendPredictResponse {
  success: boolean;
  data?: {
    prediction?: {
      predicted_label: string;
      predicted_probability: number;
      probabilities?: {
        REAL?: number;
        FAKE?: number;
      };
      threshold?: number;
    };
    timing?: {
      total_ms?: number;
    };
    explainability?: {
      overlay_path?: string;
      method?: string;
      note?: string;
    };
  };
}

function mapBackendPrediction(
  response: BackendPredictResponse,
  mediaType: DetectionRequest["mediaType"]
): PredictionResult {
  const prediction = response.data?.prediction;
  const probs = prediction?.probabilities || {};

  return {
    predictedLabel: (prediction?.predicted_label as "REAL" | "FAKE" | "UNKNOWN") || "UNKNOWN",
    predictedProbability: Number(prediction?.predicted_probability || 0),
    probabilities: {
      REAL: Number(probs.REAL || 0),
      FAKE: Number(probs.FAKE || 0)
    },
    threshold: Number(prediction?.threshold ?? DEFAULT_THRESHOLD),
    modelSource: "backend",
    inferenceTimeMs: Number(response.data?.timing?.total_ms || 0),
    mediaType
  };
}

export async function backendPredict(request: DetectionRequest): Promise<PredictionResult> {
  const endpoint = request.mediaType === "video" ? "/api/v1/predict/video" : "/api/v1/predict/image";
  const url = `${BACKEND_BASE_URL}${endpoint}`;

  const form = new FormData();
  form.append("threshold", String(request.threshold ?? DEFAULT_THRESHOLD));
  form.append("explain", String(Boolean(request.requestExplainability)));

  const fileName = request.uri.split("/").pop() || "media.bin";
  const fileType = request.mediaType === "video" ? "video/mp4" : "image/jpeg";
  form.append("file", {
    uri: request.uri,
    name: fileName,
    type: fileType
  } as unknown as Blob);

  const response = await fetch(url, {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    throw new Error(`Backend inference failed: ${response.status}`);
  }

  const payload = (await response.json()) as BackendPredictResponse;
  if (!payload.success) {
    throw new Error("Backend inference response was unsuccessful");
  }

  return mapBackendPrediction(payload, request.mediaType);
}

export async function backendExplain(requestId: string): Promise<ExplainabilityResult> {
  const url = `${BACKEND_BASE_URL}/api/v1/explain/${encodeURIComponent(requestId)}`;
  const response = await fetch(url, { method: "GET" });
  if (!response.ok) {
    return {
      type: "unavailable",
      note: `Backend explainability unavailable (${response.status})`
    };
  }

  const payload = (await response.json()) as Record<string, unknown>;
  const data = payload.data as Record<string, unknown> | undefined;
  return {
    type: "backend",
    overlayUri: (data?.overlay_path as string) || undefined,
    note: (data?.note as string) || "Backend explanation retrieved",
    metadata: data || {}
  };
}

export async function backendHealthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/v1/health`, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}
