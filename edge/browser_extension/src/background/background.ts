import { RuntimeMessage } from "@/lib/types";
import { getSettings, getLastResults, saveSettings } from "@/services/storageService";

chrome.runtime.onInstalled.addListener(() => {
  void getSettings();
});

chrome.runtime.onMessage.addListener((message: RuntimeMessage, sender, sendResponse) => {
  if (message.action === "GET_SETTINGS") {
    void getSettings().then((settings) => sendResponse({ ok: true, settings }));
    return true;
  }

  if (message.action === "SET_SETTINGS") {
    void saveSettings(message.payload as any)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.action === "GET_LAST_RESULTS") {
    void getLastResults().then((results) => sendResponse({ ok: true, results }));
    return true;
  }

  if (message.action === "SCAN_PAGE") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      if (!tabId) {
        sendResponse({ ok: false, error: "No active tab" });
        return;
      }

      chrome.tabs.sendMessage(tabId, message, (response) => {
        sendResponse(response || { ok: false, error: "No response from content script" });
      });
    });
    return true;
  }

  return false;
});
