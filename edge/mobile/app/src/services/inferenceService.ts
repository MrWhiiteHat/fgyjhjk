import { backendPredict } from "@/lib/api";
import { DEFAULT_THRESHOLD, FRAME_STRIDE, MAX_FRAMES_PER_VIDEO } from "@/lib/constants";
import { DetectionRequest, InferenceMode, PredictionResult } from "@/lib/types";
import { nowIso } from "@/lib/helpers";
import { modelService } from "@/services/modelService";

class LocalRuntimeUnavailableError extends Error {}

async function runLocalInference(request: DetectionRequest): Promise<PredictionResult> {
  const isUsable = await modelService.isLocalRuntimeUsable();
  if (!isUsable) {
    throw new LocalRuntimeUnavailableError("Local runtime unavailable or model missing");
  }

  // Real local runtime integration depends on native runtime package wiring.
  // This method is intentionally strict: if native engine is not fully connected,
  // callers should route via backend fallback in auto mode.
  throw new LocalRuntimeUnavailableError("Native runtime bridge not wired in current build")
}

async function runBackendInference(request: DetectionRequest): Promise<PredictionResult> {
  return backendPredict(request);
}

export async function detect(request: DetectionRequest): Promise<PredictionResult> {
  const mode = request.inferenceMode || "auto";

  if (mode === "local") {
    return runLocalInference(request);
  }

  if (mode === "backend") {
    return runBackendInference(request);
  }

  try {
    return await runLocalInference(request);
  } catch (error) {
    if (error instanceof LocalRuntimeUnavailableError) {
      const backendResult = await runBackendInference({ ...request, inferenceMode: "backend" });
      return {
        ...backendResult,
        modelSource: "local_fallback_backend"
      };
    }
    throw error;
  }
}

export async function detectImage(uri: string, mode: InferenceMode, threshold = DEFAULT_THRESHOLD): Promise<PredictionResult> {
  return detect({
    uri,
    mediaType: "image",
    threshold,
    inferenceMode: mode
  });
}

export async function detectVideo(uri: string, mode: InferenceMode, threshold = DEFAULT_THRESHOLD): Promise<PredictionResult> {
  const result = await detect({
    uri,
    mediaType: "video",
    threshold,
    inferenceMode: mode
  });

  return {
    ...result,
    framesProcessed: result.framesProcessed ?? MAX_FRAMES_PER_VIDEO,
    fakeFrameRatio: result.fakeFrameRatio ?? result.probabilities.FAKE,
    aggregationStrategy: result.aggregationStrategy ?? "mean_probability"
  };
}

export async function detectCameraFrame(uri: string, mode: InferenceMode, threshold = DEFAULT_THRESHOLD): Promise<PredictionResult> {
  return detect({
    uri,
    mediaType: "camera_frame",
    threshold,
    inferenceMode: mode
  });
}
