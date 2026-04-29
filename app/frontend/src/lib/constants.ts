export const API_BASE_URL = "https://mrwhite44-realfake-backend.hf.space/api/v1";

export const DEFAULT_REQUEST_TIMEOUT_MS = 180_000;

export const MAX_IMAGE_UPLOAD_MB = 10;
export const MAX_VIDEO_UPLOAD_MB = 250;

export const SUPPORTED_IMAGE_MIME = ["image/jpeg", "image/png", "image/webp", "image/bmp"];
export const SUPPORTED_VIDEO_MIME = ["video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/x-matroska"];

export const IMAGE_ACCEPT_ATTR = "image/jpeg,image/png,image/webp,image/bmp";
export const VIDEO_ACCEPT_ATTR = "video/mp4,video/webm,video/quicktime,video/x-msvideo,video/x-matroska,video/*";

export const VIDEO_AGGREGATION_STRATEGIES = [
	"mean_probability",
	"max_probability",
	"fake_frame_ratio",
	"majority_vote",
	"sliding_window_mean",
	"sliding_window_max",
] as const;
