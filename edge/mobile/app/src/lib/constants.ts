import { AppSettings } from "./types";

export const APP_NAME = "RealFake Edge";
export const APP_VERSION = "1.0.0";

export const BACKEND_BASE_URL = process.env.MOBILE_BACKEND_BASE_URL || "http://127.0.0.1:8000";
export const DEFAULT_THRESHOLD = Number(process.env.MOBILE_DEFAULT_THRESHOLD || 0.5);
export const DEFAULT_SYNC_INTERVAL_SEC = Number(process.env.MOBILE_SYNC_INTERVAL_SEC || 60);

export const STORAGE_KEYS = {
  SETTINGS: "edge_mobile_settings",
  HISTORY: "edge_mobile_history",
  OFFLINE_QUEUE: "edge_mobile_offline_queue"
} as const;

export const SUPPORTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp"];
export const SUPPORTED_VIDEO_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv", ".webm"];

export const MAX_IMAGE_SIZE_MB = 10;
export const MAX_VIDEO_SIZE_MB = 250;
export const MAX_FRAMES_PER_VIDEO = 32;
export const FRAME_STRIDE = 5;

export const CAMERA_FPS_CAP = 6;

export const DEFAULT_SETTINGS: AppSettings = {
  inferenceMode: "auto",
  syncEnabled: true,
  privacyMode: "user_selectable",
  explainabilityEnabled: true,
  debugLogging: process.env.MOBILE_DEBUG_LOGGING === "true",
  lowPowerMode: false
};
