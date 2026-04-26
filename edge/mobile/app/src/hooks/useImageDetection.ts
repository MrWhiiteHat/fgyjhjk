import { useCallback, useRef, useState } from "react";

import { detectImage } from "@/services/inferenceService";
import { ExplainabilityResult, InferenceMode, PredictionResult } from "@/lib/types";

interface ImageDetectionState {
  loading: boolean;
  error: string;
  result: PredictionResult | null;
  requestId: string;
}

export function useImageDetection() {
  const [state, setState] = useState<ImageDetectionState>({
    loading: false,
    error: "",
    result: null,
    requestId: ""
  });
  const activeRequest = useRef(0);

  const runDetection = useCallback(async (uri: string, mode: InferenceMode, threshold: number) => {
    const requestId = Date.now();
    activeRequest.current = requestId;
    setState((prev) => ({ ...prev, loading: true, error: "" }));

    try {
      const result = await detectImage(uri, mode, threshold);
      if (activeRequest.current !== requestId) {
        return null;
      }
      setState({ loading: false, error: "", result, requestId: String(requestId) });
      return result;
    } catch (error) {
      if (activeRequest.current !== requestId) {
        return null;
      }
      setState({ loading: false, error: error instanceof Error ? error.message : "Image detection failed", result: null, requestId: String(requestId) });
      return null;
    }
  }, []);

  const cancel = useCallback(() => {
    activeRequest.current = -1;
    setState((prev) => ({ ...prev, loading: false }));
  }, []);

  return {
    ...state,
    runDetection,
    cancel
  };
}
