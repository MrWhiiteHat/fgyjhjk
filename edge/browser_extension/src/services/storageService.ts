import { DEFAULT_SETTINGS, STORAGE_KEY_LAST_RESULTS, STORAGE_KEY_SETTINGS } from "@/lib/constants";
import { ExtensionSettings, ScanResult } from "@/lib/types";

export async function getSettings(): Promise<ExtensionSettings> {
  const data = await chrome.storage.local.get(STORAGE_KEY_SETTINGS);
  return (data[STORAGE_KEY_SETTINGS] as ExtensionSettings) || DEFAULT_SETTINGS;
}

export async function saveSettings(settings: ExtensionSettings): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY_SETTINGS]: settings });
}

export async function getLastResults(): Promise<ScanResult[]> {
  const data = await chrome.storage.local.get(STORAGE_KEY_LAST_RESULTS);
  return (data[STORAGE_KEY_LAST_RESULTS] as ScanResult[]) || [];
}

export async function saveLastResults(results: ScanResult[]): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY_LAST_RESULTS]: results });
}
