import { backendHealthCheck } from "@/lib/api";
import { QueueItem } from "@/lib/types";
import { randomId, nowIso } from "@/lib/helpers";
import { storageService } from "@/services/storageService";

async function postSyncEvent(item: QueueItem): Promise<boolean> {
  const reachable = await backendHealthCheck();
  if (!reachable) {
    return false;
  }

  const endpoint = `${process.env.MOBILE_BACKEND_BASE_URL || "http://127.0.0.1:8000"}/api/v1/sync/events`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(item.payload)
  });

  return response.ok;
}

export const syncService = {
  async enqueue(entryId: string, payload: QueueItem["payload"]): Promise<QueueItem> {
    const queue = await storageService.getQueue();

    const existing = queue.find(
      (item) => item.payload.mediaSha256 === payload.mediaSha256 && item.payload.prediction.threshold === payload.prediction.threshold
    );
    if (existing) {
      return existing;
    }

    const item: QueueItem = {
      eventId: randomId("sync_event"),
      createdAt: nowIso(),
      entryId,
      payload,
      attempts: 0,
      status: "pending"
    };

    await storageService.setQueue([item, ...queue]);
    return item;
  },

  async listQueue(): Promise<QueueItem[]> {
    return storageService.getQueue();
  },

  async syncPending(maxAttempts = 5): Promise<{ synced: number; failed: number }> {
    const queue = await storageService.getQueue();
    let synced = 0;
    let failed = 0;

    const nextQueue: QueueItem[] = [];

    for (const item of queue) {
      if (item.status === "synced") {
        continue;
      }
      if (item.attempts >= maxAttempts) {
        nextQueue.push({ ...item, status: "conflict", lastError: "max attempts exceeded" });
        continue;
      }

      const ok = await postSyncEvent(item);
      if (ok) {
        synced += 1;
      } else {
        failed += 1;
        nextQueue.push({
          ...item,
          attempts: item.attempts + 1,
          status: "failed",
          lastError: "sync failed",
        });
      }
    }

    await storageService.setQueue(nextQueue);
    return { synced, failed };
  }
};
