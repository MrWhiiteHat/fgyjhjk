import { useCallback, useRef, useState } from "react";

import { detectVideo } from "@/services/inferenceService";
import { InferenceMode, PredictionResult } from "@/lib/types";

interface VideoDetectionState {
  loading: boolean;
  error: string;
  result: PredictionResult | null;
}

export function useVideoDetection() {
  const [state, setState] = useState<VideoDetectionState>({
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
      const result = await detectVideo(uri, mode, threshold);
      if (activeRequest.current !== token) {
        return null;
      }
      setState({ loading: false, error: "", result });
      return result;
    } catch (error) {
      if (activeRequest.current !== token) {
        return null;
      }
      setState({ loading: false, error: error instanceof Error ? error.message : "Video detection failed", result: null });
      return null;
    }
  }, []);

  const cancel = useCallback(() => {
    activeRequest.current = -1;
    setState((prev) => ({ ...prev, loading: false }));
  }, []);

  return { ...state, runDetection, cancel };
}
