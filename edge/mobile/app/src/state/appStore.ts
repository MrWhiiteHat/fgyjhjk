import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import { DEFAULT_SETTINGS } from "@/lib/constants";
import { AppSettings, ConnectivityState, ModelAvailability } from "@/lib/types";

interface AppStoreState {
  settings: AppSettings;
  model: ModelAvailability;
  connectivity: ConnectivityState;
  setSettings: (patch: Partial<AppSettings>) => void;
  setModel: (patch: Partial<ModelAvailability>) => void;
  setConnectivity: (patch: Partial<ConnectivityState>) => void;
}

const initialModel: ModelAvailability = {
  localModelPath: "src/assets/models/real_fake_mobile.tflite",
  modelVersion: "v1.0.0",
  available: false,
  runtime: "none"
};

const initialConnectivity: ConnectivityState = {
  isOnline: true,
  backendReachable: false
};

export const useAppStore = create<AppStoreState>()(
  persist(
    (set) => ({
      settings: DEFAULT_SETTINGS,
      model: initialModel,
      connectivity: initialConnectivity,
      setSettings: (patch) => set((state) => ({ settings: { ...state.settings, ...patch } })),
      setModel: (patch) => set((state) => ({ model: { ...state.model, ...patch } })),
      setConnectivity: (patch) => set((state) => ({ connectivity: { ...state.connectivity, ...patch } }))
    }),
    {
      name: "edge_mobile_app_store",
      storage: createJSONStorage(() => AsyncStorage)
    }
  )
);
