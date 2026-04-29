import { MAX_IMAGE_UPLOAD_MB, MAX_VIDEO_UPLOAD_MB, SUPPORTED_IMAGE_MIME, SUPPORTED_VIDEO_MIME } from "./constants";

export type FileValidationResult = {
  valid: boolean;
  message: string;
};

function validateSize(file: File, maxMb: number): FileValidationResult {
  const maxBytes = maxMb * 1024 * 1024;
  if (file.size > maxBytes) {
    return {
      valid: false,
      message: `File is too large. Maximum supported size is ${maxMb} MB.`
    };
  }
  return { valid: true, message: "" };
}

export function validateImageFile(file: File | null): FileValidationResult {
  if (!file) {
    return { valid: false, message: "Please select an image file." };
  }

  if (!SUPPORTED_IMAGE_MIME.includes(file.type)) {
    return {
      valid: false,
      message: "Unsupported image type. Use JPEG, PNG, WEBP, or BMP."
    };
  }

  return validateSize(file, MAX_IMAGE_UPLOAD_MB);
}

export function validateVideoFile(file: File | null): FileValidationResult {
  if (!file) {
    return { valid: false, message: "Please select a video file." };
  }

  if (!SUPPORTED_VIDEO_MIME.includes(file.type) && !file.type.startsWith("video/")) {
    return {
      valid: false,
      message: "Unsupported video type. Use MP4, WEBM, MOV, AVI, or MKV."
    };
  }

  return validateSize(file, MAX_VIDEO_UPLOAD_MB);
}

export function validateThreshold(value: number): FileValidationResult {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    return {
      valid: false,
      message: "Threshold must be a number between 0 and 1."
    };
  }
  return { valid: true, message: "" };
}

export function validateReportId(reportId: string): FileValidationResult {
  if (!reportId.trim()) {
    return { valid: false, message: "Report ID is required." };
  }

  if (reportId.trim().length < 4) {
    return { valid: false, message: "Report ID is too short." };
  }

  return { valid: true, message: "" };
}
