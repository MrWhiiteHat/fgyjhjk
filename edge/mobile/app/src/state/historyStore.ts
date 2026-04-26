import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import { DetectionHistoryEntry, SyncStatus } from "@/lib/types";

interface HistoryStoreState {
  entries: DetectionHistoryEntry[];
  addEntry: (entry: DetectionHistoryEntry) => void;
  removeEntry: (id: string) => void;
  clearEntries: () => void;
  updateSyncStatus: (id: string, status: SyncStatus, error?: string) => void;
  getEntryById: (id: string) => DetectionHistoryEntry | undefined;
}

export const useHistoryStore = create<HistoryStoreState>()(
  persist(
    (set, get) => ({
      entries: [],
      addEntry: (entry) => set((state) => ({ entries: [entry, ...state.entries] })),
      removeEntry: (id) => set((state) => ({ entries: state.entries.filter((item) => item.id !== id) })),
      clearEntries: () => set({ entries: [] }),
      updateSyncStatus: (id, status, error) =>
        set((state) => ({
          entries: state.entries.map((item) =>
            item.id === id
              ? {
                  ...item,
                  syncStatus: status,
                  syncError: error
                }
              : item
          )
        })),
      getEntryById: (id) => get().entries.find((item) => item.id === id)
    }),
    {
      name: "edge_mobile_history_store",
      storage: createJSONStorage(() => AsyncStorage)
    }
  )
);
