import {
  MAX_IMAGE_SIZE_MB,
  MAX_VIDEO_SIZE_MB,
  SUPPORTED_IMAGE_EXTENSIONS,
  SUPPORTED_VIDEO_EXTENSIONS
} from "./constants";

export interface MediaValidationInput {
  uri: string;
  fileName?: string;
  sizeBytes?: number;
  mediaType: "image" | "video";
}

export interface ValidationResult {
  ok: boolean;
  error?: string;
}

function extensionFromName(nameOrUri: string): string {
  const match = nameOrUri.toLowerCase().match(/\.[a-z0-9]+$/);
  return match ? match[0] : "";
}

export function validateMediaInput(input: MediaValidationInput): ValidationResult {
  const ext = extensionFromName(input.fileName || input.uri);

  if (input.mediaType === "image") {
    if (!SUPPORTED_IMAGE_EXTENSIONS.includes(ext)) {
      return { ok: false, error: `Unsupported image type: ${ext}` };
    }
    if (typeof input.sizeBytes === "number" && input.sizeBytes > MAX_IMAGE_SIZE_MB * 1024 * 1024) {
      return { ok: false, error: `Image exceeds ${MAX_IMAGE_SIZE_MB} MB limit` };
    }
  }

  if (input.mediaType === "video") {
    if (!SUPPORTED_VIDEO_EXTENSIONS.includes(ext)) {
      return { ok: false, error: `Unsupported video type: ${ext}` };
    }
    if (typeof input.sizeBytes === "number" && input.sizeBytes > MAX_VIDEO_SIZE_MB * 1024 * 1024) {
      return { ok: false, error: `Video exceeds ${MAX_VIDEO_SIZE_MB} MB limit` };
    }
  }

  return { ok: true };
}

export function validateThreshold(value: number): ValidationResult {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    return { ok: false, error: "Threshold must be between 0 and 1" };
  }
  return { ok: true };
}
