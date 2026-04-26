"use client";

import { useCallback, useRef, useState } from "react";

import { predictVideo } from "@/lib/api";
import { HookState, VideoPredictionData } from "@/lib/types";
import { toFriendlyError } from "@/lib/helpers";

export function usePredictVideo() {
  const [state, setState] = useState<HookState<VideoPredictionData>>({
    status: "idle",
    loading: false,
    data: null,
    error: null
  });

  const controllerRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  const run = useCallback(
    async (options: {
      file: File;
      threshold?: number;
      frameStride: number;
      maxFrames: number;
      aggregationStrategy: string;
      generateReport: boolean;
    }) => {
      requestSeqRef.current += 1;
      const requestId = requestSeqRef.current;

      controllerRef.current?.abort("superseded request");
      const controller = new AbortController();
      controllerRef.current = controller;

      setState({ status: "loading", loading: true, data: null, error: null });

      try {
        const response = await predictVideo({ ...options, signal: controller.signal });
        if (requestId !== requestSeqRef.current) {
          return null;
        }

        setState({ status: "success", loading: false, data: response, error: null });
        return response;
      } catch (error) {
        if (requestId !== requestSeqRef.current) {
          return null;
        }
        if (controller.signal.aborted) {
          setState({ status: "idle", loading: false, data: null, error: null });
          return null;
        }

        const friendlyError = toFriendlyError(error);
        setState({ status: "error", loading: false, data: null, error: friendlyError });
        return null;
      }
    },
    []
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort("cancelled by user");
    setState((prev) => {
      if (prev.loading) {
        return { status: "idle", loading: false, data: null, error: null };
      }
      return prev;
    });
  }, []);

  const reset = useCallback(() => {
    setState({ status: "idle", loading: false, data: null, error: null });
  }, []);

  return {
    ...state,
    run,
    cancel,
    reset
  };
}
