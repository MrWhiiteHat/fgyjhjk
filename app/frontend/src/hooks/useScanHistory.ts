"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PredictionResult } from "@/lib/types";

type HistoryItem = {
  id: string;
  mode: "image" | "video";
  filename: string;
  timestamp: string;
  result: PredictionResult;
};

const STORAGE_KEY = "realfake.scan.history.v1";

export function useScanHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  // Use a ref to keep addItem stable across renders while still
  // accessing the latest items without stale closures.
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as HistoryItem[];
      if (Array.isArray(parsed)) {
        setItems(parsed.slice(0, 25));
      }
    } catch {
      setItems([]);
    }
  }, []);

  const persist = useCallback((next: HistoryItem[]) => {
    setItems(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Best-effort persistence.
    }
  }, []);

  // addItem is now stable — it reads current items from the ref
  // rather than closing over the `items` state value.
  const addItem = useCallback(
    (mode: "image" | "video", filename: string, result: PredictionResult) => {
      const current = itemsRef.current;
      const next: HistoryItem[] = [
        {
          id: `${Date.now()}-${Math.floor(Math.random() * 10000)}`,
          mode,
          filename,
          timestamp: new Date().toISOString(),
          result,
        },
        ...current,
      ].slice(0, 25);
      persist(next);
    },
    [persist]
  );

  const clear = useCallback(() => {
    persist([]);
  }, [persist]);

  const analytics = useMemo(() => {
    if (items.length === 0) {
      return {
        totalScans: 0,
        fakeRate: 0,
        avgConfidence: 0,
      };
    }

    const fakeCount = items.filter((item) => item.result.risk_score >= item.result.threshold_used).length;
    const avgConfidence =
      items.reduce((acc, item) => acc + Number(item.result.confidence_score || 0), 0) / Math.max(items.length, 1);

    return {
      totalScans: items.length,
      fakeRate: fakeCount / Math.max(items.length, 1),
      avgConfidence,
    };
  }, [items]);

  return {
    items,
    analytics,
    addItem,
    clear,
  };
}

export type { HistoryItem };
