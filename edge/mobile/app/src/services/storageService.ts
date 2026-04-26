import AsyncStorage from "@react-native-async-storage/async-storage";

import { STORAGE_KEYS } from "@/lib/constants";
import { AppSettings, DetectionHistoryEntry, QueueItem } from "@/lib/types";

async function readJson<T>(key: string, fallback: T): Promise<T> {
  const raw = await AsyncStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function writeJson<T>(key: string, value: T): Promise<void> {
  await AsyncStorage.setItem(key, JSON.stringify(value));
}

export const storageService = {
  async getSettings(): Promise<AppSettings | null> {
    return readJson<AppSettings | null>(STORAGE_KEYS.SETTINGS, null);
  },

  async setSettings(settings: AppSettings): Promise<void> {
    await writeJson(STORAGE_KEYS.SETTINGS, settings);
  },

  async getHistory(): Promise<DetectionHistoryEntry[]> {
    return readJson<DetectionHistoryEntry[]>(STORAGE_KEYS.HISTORY, []);
  },

  async setHistory(entries: DetectionHistoryEntry[]): Promise<void> {
    await writeJson(STORAGE_KEYS.HISTORY, entries);
  },

  async getQueue(): Promise<QueueItem[]> {
    return readJson<QueueItem[]>(STORAGE_KEYS.OFFLINE_QUEUE, []);
  },

  async setQueue(queue: QueueItem[]): Promise<void> {
    await writeJson(STORAGE_KEYS.OFFLINE_QUEUE, queue);
  },

  async clearHistory(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEYS.HISTORY);
  },

  async clearQueue(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEYS.OFFLINE_QUEUE);
  },

  async estimateStorageUsageBytes(): Promise<number> {
    const [settings, history, queue] = await Promise.all([
      AsyncStorage.getItem(STORAGE_KEYS.SETTINGS),
      AsyncStorage.getItem(STORAGE_KEYS.HISTORY),
      AsyncStorage.getItem(STORAGE_KEYS.OFFLINE_QUEUE)
    ]);

    return [settings, history, queue]
      .filter((item): item is string => Boolean(item))
      .reduce((total, value) => total + value.length, 0);
  }
};
