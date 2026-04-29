import { MAX_SCAN_LIMIT, MIN_IMAGE_DIMENSION } from "@/lib/constants";
import { ExtensionSettings, ImageCandidate } from "@/lib/types";

export function validateSettings(settings: ExtensionSettings): string[] {
  const errors: string[] = [];
  if (!settings.backendBaseUrl.startsWith("http://") && !settings.backendBaseUrl.startsWith("https://")) {
    errors.push("backendBaseUrl must be http/https");
  }
  if (settings.scanLimit < 1 || settings.scanLimit > MAX_SCAN_LIMIT) {
    errors.push(`scanLimit must be between 1 and ${MAX_SCAN_LIMIT}`);
  }
  return errors;
}

export function isSupportedImageUrl(src: string): boolean {
  const normalized = src.toLowerCase();
  if (normalized.startsWith("data:")) {
    return false;
  }
  return /(\.jpg|\.jpeg|\.png|\.webp|\.gif)(\?|$)/.test(normalized) || normalized.startsWith("http");
}

export function shouldScanCandidate(candidate: ImageCandidate): boolean {
  if (!isSupportedImageUrl(candidate.src)) {
    return false;
  }
  return candidate.width >= MIN_IMAGE_DIMENSION && candidate.height >= MIN_IMAGE_DIMENSION;
}
