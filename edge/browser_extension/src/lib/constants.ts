import { ExtensionSettings } from "@/lib/types";

export const EXTENSION_APP_NAME = "RealFake Face Detector";
export const DEFAULT_SETTINGS: ExtensionSettings = {
  inferenceMode: "auto",
  backendBaseUrl: "http://127.0.0.1:8000",
  scanLimit: 40,
  autoScanEnabled: false,
  overlayEnabled: true,
  privacyMode: "extension_minimum_retention"
};

export const MIN_IMAGE_DIMENSION = 64;
export const MAX_SCAN_LIMIT = 100;
export const STORAGE_KEY_SETTINGS = "edge_extension_settings";
export const STORAGE_KEY_LAST_RESULTS = "edge_extension_last_results";
