import { backendPredictImage } from "@/services/backendProxyService";
import { ExtensionSettings, ScanResult } from "@/lib/types";

async function localInfer(_imageUrl: string): Promise<ScanResult> {
  // Local model runtime in extension is optional and environment-dependent.
  // If ONNX Runtime Web or WebNN path is integrated, this method can be wired.
  throw new Error("Local extension runtime unavailable");
}

export async function inferImage(
  imageUrl: string,
  settings: ExtensionSettings
): Promise<ScanResult> {
  if (settings.inferenceMode === "local") {
    return localInfer(imageUrl);
  }
  if (settings.inferenceMode === "backend") {
    return backendPredictImage(settings.backendBaseUrl, imageUrl);
  }

  try {
    return await localInfer(imageUrl);
  } catch {
    const backend = await backendPredictImage(settings.backendBaseUrl, imageUrl);
    return {
      ...backend,
      modelSource: "local_fallback_backend"
    };
  }
}
