export type ErrorDetail = {
  error_code: string;
  message: string;
  details?: Record<string, unknown> | null;
};

export type ApiSuccessResponse<TData> = {
  success: true;
  request_id: string;
  timestamp: string;
  message: string;
  data: TData;
  errors: ErrorDetail[];
};

export type ApiErrorResponse = {
  success: false;
  request_id: string;
  timestamp: string;
  error_code: string;
  message: string;
  details?: Record<string, unknown> | null;
  data?: unknown;
  errors: ErrorDetail[];
};

export type PredictionResult = {
  predicted_label: string;
  predicted_probability: number;
  predicted_logit: number;
  threshold_used: number;
  inference_time_ms: number;
  model_name: string;
  artifact_path: string;
  confidence_score: number;
  authenticity_score: number;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | string;
  uncertain_prediction: boolean;
  uncertainty_margin: number;
  final_decision: string;
  explanation_available: boolean;
  report_id?: string | null;
};

export type HealthData = {
  app_status: string;
  model_loaded: boolean;
  artifact_path: string;
  device: string;
  uptime_seconds: number;
  version: string;
};

export type ReadyData = {
  ready: boolean;
  app_status: string;
  model_loaded: boolean;
  artifact_path: string;
  artifact_exists: boolean;
  last_load_error: string;
  version: string;
};

export type ImagePredictionData = {
  prediction: PredictionResult;
  timing?: Record<string, number>;
  cache_hit?: boolean;
  metadata_summary?: Record<string, unknown>;
  explainability?: Record<string, unknown> | null;
  report?: {
    report_id: string;
    metadata: Record<string, unknown>;
    files: Record<string, string>;
  } | null;
};

export type VideoPredictionData = {
  result: PredictionResult;
  num_frames_processed: number;
  fake_frame_ratio: number;
  aggregation_strategy: string;
  aggregated_probability: number;
  aggregated_label: string;
  frame_report_path: string;
  cache_hit?: boolean;
  metadata_summary?: Record<string, unknown>;
};

export type ExplainabilityData = {
  explanation_type: string;
  target_layer: string;
  heatmap_path: string;
  overlay_path: string;
  generated_at: string;
};

export type ReportData = {
  report_id: string;
  metadata: Record<string, unknown>;
  files: Record<string, string>;
};

export type ModelInfoData = {
  model_name: string;
  artifact_path: string;
  threshold: number;
  loaded_at: string;
  device: string;
  explainability_enabled: boolean;
  model_type: string;
};

export type RequestStatus = "idle" | "loading" | "success" | "error";

export type HookState<TData> = {
  status: RequestStatus;
  loading: boolean;
  data: ApiSuccessResponse<TData> | null;
  error: string | null;
};
