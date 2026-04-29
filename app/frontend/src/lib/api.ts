import { API_BASE_URL } from "./constants";
import {
  ApiErrorResponse,
  ApiSuccessResponse,
  ExplainabilityData,
  HealthData,
  ImagePredictionData,
  ModelInfoData,
  ReadyData,
  ReportData,
  VideoPredictionData,
} from "./types";
import { DEFAULT_REQUEST_TIMEOUT_MS } from "./constants";

export class ApiClientError extends Error {
  status: number;
  payload?: ApiErrorResponse | Record<string, unknown>;

  constructor(message: string, status: number, payload?: ApiErrorResponse | Record<string, unknown>) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

type RequestOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
};

function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): AbortSignal {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => {
    timeoutController.abort("Request timed out");
  }, timeoutMs);

  if (signal) {
    if (signal.aborted) {
      clearTimeout(timer);
      timeoutController.abort(signal.reason);
    } else {
      signal.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          timeoutController.abort(signal.reason);
        },
        { once: true }
      );
    }
  }

  timeoutController.signal.addEventListener(
    "abort",
    () => {
      clearTimeout(timer);
    },
    { once: true }
  );

  return timeoutController.signal;
}

function mapAbortToClientError(signal: AbortSignal): ApiClientError {
  const reason = String(signal.reason ?? "").toLowerCase();
  if (reason.includes("timed out")) {
    return new ApiClientError(
      "Request timed out. The first prediction can take up to 2 minutes while the model warms up.",
      408
    );
  }

  if (reason.includes("cancel") || reason.includes("superseded") || reason.includes("unmounted")) {
    return new ApiClientError("Request cancelled.", 499);
  }

  return new ApiClientError("Request was aborted.", 499);
}

async function requestJson<T>(path: string, init?: RequestInit, options?: RequestOptions): Promise<T> {
  const requestSignal = withTimeout(options?.signal, options?.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS);
  let response: Response;
  
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: requestSignal,
    });
  } catch (error) {
    if (requestSignal.aborted) {
      throw mapAbortToClientError(requestSignal);
    }
    throw error;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  const payload = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    if (isJson && payload && typeof payload === "object") {
      const maybeError = payload as Partial<ApiErrorResponse>;
      const detail = Array.isArray(maybeError.errors) && maybeError.errors.length > 0 ? maybeError.errors[0].message : "";
      const message = String(maybeError.message || detail || `Request failed with status ${response.status}`);
      throw new ApiClientError(message, response.status, payload as ApiErrorResponse);
    }
    throw new ApiClientError(typeof payload === "string" ? payload : `Request failed with status ${response.status}`, response.status);
  }

  if (!isValidSuccessEnvelope(payload)) {
    throw new ApiClientError("Invalid API response schema received from server.", 502, {
      payload: payload as unknown as Record<string, unknown>,
    });
  }

  return payload as T;
}

function isValidSuccessEnvelope(payload: unknown): payload is ApiSuccessResponse<unknown> {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  return (
    candidate.success === true &&
    typeof candidate.request_id === "string" &&
    typeof candidate.timestamp === "string" &&
    typeof candidate.message === "string" &&
    "data" in candidate &&
    Array.isArray(candidate.errors)
  );
}

function appendIfDefined(formData: FormData, key: string, value: string | number | boolean | undefined) {
  if (value === undefined) {
    return;
  }
  formData.append(key, String(value));
}

export function getHealth(): Promise<ApiSuccessResponse<HealthData>> {
  return requestJson<ApiSuccessResponse<HealthData>>("/health", { method: "GET" });
}

export function getReady(): Promise<ApiSuccessResponse<ReadyData>> {
  return requestJson<ApiSuccessResponse<ReadyData>>("/ready", { method: "GET" });
}

export function getModelInfo(): Promise<ApiSuccessResponse<ModelInfoData>> {
  return requestJson<ApiSuccessResponse<ModelInfoData>>("/admin/model-info", { method: "GET" });
}

export function predictImage(options: {
  file: File;
  threshold?: number;
  explain: boolean;
  generateReport: boolean;
  signal?: AbortSignal;
}): Promise<ApiSuccessResponse<ImagePredictionData>> {
  const formData = new FormData();
  formData.append("file", options.file);
  appendIfDefined(formData, "threshold", options.threshold);
  formData.append("explain", String(options.explain));
  formData.append("generate_report", String(options.generateReport));

  return requestJson<ApiSuccessResponse<ImagePredictionData>>(
    "/predict/image",
    {
      method: "POST",
      body: formData,
    },
    { signal: options.signal }
  );
}

export function predictVideo(options: {
  file: File;
  threshold?: number;
  frameStride: number;
  maxFrames: number;
  aggregationStrategy: string;
  generateReport: boolean;
  signal?: AbortSignal;
}): Promise<ApiSuccessResponse<VideoPredictionData>> {
  const formData = new FormData();
  formData.append("file", options.file);
  appendIfDefined(formData, "threshold", options.threshold);
  appendIfDefined(formData, "frame_stride", options.frameStride);
  appendIfDefined(formData, "max_frames", options.maxFrames);
  appendIfDefined(formData, "aggregation_strategy", options.aggregationStrategy);
  appendIfDefined(formData, "generate_report", options.generateReport);

  return requestJson<ApiSuccessResponse<VideoPredictionData>>(
    "/predict/video",
    {
      method: "POST",
      body: formData,
    },
    { signal: options.signal }
  );
}

export function explainImage(options: {
  file: File;
  explanationType: "gradcam" | "saliency" | "both";
  targetLayer?: string;
  signal?: AbortSignal;
}): Promise<ApiSuccessResponse<ExplainabilityData>> {
  const formData = new FormData();
  formData.append("file", options.file);
  formData.append("explanation_type", options.explanationType);
  if (options.targetLayer) {
    formData.append("target_layer", options.targetLayer);
  }

  return requestJson<ApiSuccessResponse<ExplainabilityData>>(
    "/explain/image",
    {
      method: "POST",
      body: formData,
    },
    { signal: options.signal }
  );
}

export function getReport(
  reportId: string,
  reportFormat: "json" | "txt" | "csv",
  signal?: AbortSignal
): Promise<ApiSuccessResponse<ReportData>> {
  return requestJson<ApiSuccessResponse<ReportData>>(
    `/reports/${encodeURIComponent(reportId)}?format=${reportFormat}`,
    {
      method: "GET",
    },
    { signal }
  );
}

export function generateReport(options: {
  requestMetadata?: Record<string, unknown>;
  fileMetadata?: Record<string, unknown>;
  predictionResults: Record<string, unknown>;
  explanationOutputs?: Record<string, unknown>;
  modelMetadata?: Record<string, unknown>;
  signal?: AbortSignal;
}): Promise<ApiSuccessResponse<ReportData>> {
  return requestJson<ApiSuccessResponse<ReportData>>(
    "/report/generate",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        request_metadata: options.requestMetadata ?? {},
        file_metadata: options.fileMetadata ?? {},
        prediction_results: options.predictionResults,
        explanation_outputs: options.explanationOutputs ?? null,
        model_metadata: options.modelMetadata ?? null,
      }),
    },
    { signal: options.signal }
  );
}
