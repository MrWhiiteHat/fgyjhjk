import { useCallback, useEffect, useState } from "react";
import * as Network from "expo-network";

import { DEFAULT_SYNC_INTERVAL_SEC } from "@/lib/constants";
import { syncService } from "@/services/syncService";

export function useSync(intervalSec = DEFAULT_SYNC_INTERVAL_SEC) {
  const [isOnline, setIsOnline] = useState(true);
  const [lastSyncSummary, setLastSyncSummary] = useState<{ synced: number; failed: number } | null>(null);
  const [syncing, setSyncing] = useState(false);

  const syncNow = useCallback(async () => {
    setSyncing(true);
    try {
      const summary = await syncService.syncPending();
      setLastSyncSummary(summary);
      return summary;
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    const tick = async () => {
      const state = await Network.getNetworkStateAsync();
      const online = Boolean(state.isConnected && state.isInternetReachable);
      setIsOnline(online);
      if (online) {
        await syncNow();
      }
    };

    void tick();
    const timer = setInterval(() => {
      void tick();
    }, Math.max(10, intervalSec) * 1000);

    return () => clearInterval(timer);
  }, [intervalSec, syncNow]);

  return {
    isOnline,
    syncing,
    lastSyncSummary,
    syncNow
  };
}
