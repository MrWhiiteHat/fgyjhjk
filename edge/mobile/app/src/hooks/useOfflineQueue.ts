import { useCallback, useEffect, useState } from "react";

import { QueueItem } from "@/lib/types";
import { syncService } from "@/services/syncService";

export function useOfflineQueue() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    const next = await syncService.listQueue();
    setQueue(next);
  }, []);

  const enqueue = useCallback(async (entryId: string, payload: QueueItem["payload"]) => {
    setLoading(true);
    try {
      const item = await syncService.enqueue(entryId, payload);
      await refresh();
      return item;
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    queue,
    loading,
    enqueue,
    refresh
  };
}
