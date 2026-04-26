"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getReport } from "@/lib/api";
import { HookState, ReportData } from "@/lib/types";
import { toFriendlyError } from "@/lib/helpers";

export function useReports() {
  const [state, setState] = useState<HookState<ReportData>>({
    status: "idle",
    loading: false,
    data: null,
    error: null
  });

  const controllerRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort("component unmounted");
    };
  }, []);

  const run = useCallback(async (reportId: string, reportFormat: "json" | "txt" | "csv") => {
    requestSeqRef.current += 1;
    const requestId = requestSeqRef.current;

    controllerRef.current?.abort("superseded request");
    const controller = new AbortController();
    controllerRef.current = controller;

    setState({ status: "loading", loading: true, data: null, error: null });

    try {
      const response = await getReport(reportId, reportFormat, controller.signal);
      if (!mountedRef.current || requestId !== requestSeqRef.current) {
        return null;
      }

      setState({ status: "success", loading: false, data: response, error: null });
      return response;
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSeqRef.current) {
        return null;
      }
      if (controller.signal.aborted) {
        setState({ status: "idle", loading: false, data: null, error: null });
        return null;
      }

      setState({ status: "error", loading: false, data: null, error: toFriendlyError(error) });
      return null;
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort("cancelled by user");
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
