import { useCallback, useRef, useState } from "react";

import { detectCameraFrame } from "@/services/inferenceService";
import { InferenceMode, PredictionResult } from "@/lib/types";

interface CameraDetectionState {
  loading: boolean;
  error: string;
  result: PredictionResult | null;
}

export function useCameraDetection() {
  const [state, setState] = useState<CameraDetectionState>({
    loading: false,
    error: "",
    result: null
  });
  const activeRequest = useRef(0);

  const runDetection = useCallback(async (uri: string, mode: InferenceMode, threshold: number) => {
    const token = Date.now();
    activeRequest.current = token;
    setState((prev) => ({ ...prev, loading: true, error: "" }));

    try {
      const result = await detectCameraFrame(uri, mode, threshold);
      if (activeRequest.current !== token) {
        return null;
      }
      setState({ loading: false, error: "", result });
      return result;
    } catch (error) {
      if (activeRequest.current !== token) {
        return null;
      }
      setState({ loading: false, error: error instanceof Error ? error.message : "Camera detection failed", result: null });
      return null;
    }
  }, []);

  return {
    ...state,
    runDetection,
    cancel: () => {
      activeRequest.current = -1;
      setState((prev) => ({ ...prev, loading: false }));
    }
  };
}
