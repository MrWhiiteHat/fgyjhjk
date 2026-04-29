export type InferenceMode = "local" | "backend" | "auto";

export interface ExtensionSettings {
  inferenceMode: InferenceMode;
  backendBaseUrl: string;
  scanLimit: number;
  autoScanEnabled: boolean;
  overlayEnabled: boolean;
  privacyMode: "strict_local" | "extension_minimum_retention";
}

export interface ImageCandidate {
  id: string;
  src: string;
  width: number;
  height: number;
}

export interface ScanResult {
  candidateId: string;
  src: string;
  predictedLabel: "REAL" | "FAKE" | "UNKNOWN";
  predictedProbability: number;
  modelSource: "local" | "backend" | "local_fallback_backend";
  error?: string;
}

export interface ScanSummary {
  scanned: number;
  fakeCount: number;
  realCount: number;
  unknownCount: number;
}

export interface RuntimeMessage {
  action: "SCAN_PAGE" | "GET_SETTINGS" | "SET_SETTINGS" | "SCAN_RESULTS" | "GET_LAST_RESULTS";
  payload?: unknown;
}
