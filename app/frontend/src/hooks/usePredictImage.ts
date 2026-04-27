"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { predictImage } from "@/lib/api";
import { HookState, ImagePredictionData } from "@/lib/types";
import { toFriendlyError } from "@/lib/helpers";

export function usePredictImage() {
  const [state, setState] = useState<HookState<ImagePredictionData>>({
    status: "idle",
    loading: false,
    data: null,
    error: null
  });

  const controllerRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort("component unmounted");
    };
  }, []);

  const run = useCallback(
    async (options: { file: File; threshold?: number; explain: boolean; generateReport: boolean }) => {
      requestSeqRef.current += 1;
      const requestId = requestSeqRef.current;

      controllerRef.current?.abort("superseded request");
      const controller = new AbortController();
      controllerRef.current = controller;

      setState({ status: "loading", loading: true, data: null, error: null });

      try {
        const response = await predictImage({ ...options, signal: controller.signal });
        // Only guard against superseded requests — not unmount,
        // because React Strict Mode double-mounts in dev and would
        // permanently set mountedRef to false.
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
    // Immediately reset loading state so the UI is responsive.
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
