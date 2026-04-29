export type InferenceMode = "local" | "backend" | "auto";
export type MediaType = "image" | "video" | "camera_frame";
export type SyncStatus = "pending" | "syncing" | "synced" | "failed" | "conflict";

export interface ProbabilityMap {
  REAL: number;
  FAKE: number;
}

export interface PredictionResult {
  predictedLabel: "REAL" | "FAKE" | "UNKNOWN";
  predictedProbability: number;
  probabilities: ProbabilityMap;
  threshold: number;
  modelSource: "local" | "backend" | "local_fallback_backend";
  inferenceTimeMs: number;
  mediaType: MediaType;
  framesProcessed?: number;
  fakeFrameRatio?: number;
  aggregationStrategy?: string;
}

export interface ExplainabilityResult {
  type: "local_lightweight" | "backend" | "unavailable";
  overlayUri?: string;
  note: string;
  metadata?: Record<string, unknown>;
}

export interface DetectionHistoryEntry {
  id: string;
  createdAt: string;
  mediaUri: string;
  mediaType: MediaType;
  mediaSha256: string;
  prediction: PredictionResult;
  explainability?: ExplainabilityResult;
  syncStatus: SyncStatus;
  syncError?: string;
}

export interface QueueItem {
  eventId: string;
  createdAt: string;
  entryId: string;
  payload: DetectionHistoryEntry;
  attempts: number;
  status: SyncStatus;
  lastError?: string;
}

export interface AppSettings {
  inferenceMode: InferenceMode;
  syncEnabled: boolean;
  privacyMode: "strict_local" | "user_selectable";
  explainabilityEnabled: boolean;
  debugLogging: boolean;
  lowPowerMode: boolean;
}

export interface ModelAvailability {
  localModelPath: string;
  modelVersion: string;
  available: boolean;
  runtime: "tflite" | "onnx" | "none";
}

export interface ConnectivityState {
  isOnline: boolean;
  backendReachable: boolean;
}

export interface DetectionRequest {
  uri: string;
  mediaType: MediaType;
  threshold?: number;
  inferenceMode?: InferenceMode;
  requestExplainability?: boolean;
}
