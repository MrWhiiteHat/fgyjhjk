import { getSettings, saveLastResults } from "@/services/storageService";
import { scanCurrentPage } from "@/services/pageScanService";
import { RuntimeMessage, ScanResult } from "@/lib/types";

function attachOverlay(result: ScanResult): void {
  const images = Array.from(document.querySelectorAll("img"));
  const target = images.find((img) => (img.currentSrc || img.src) === result.src);
  if (!target) {
    return;
  }

  const marker = document.createElement("span");
  marker.className = "edge-overlay-badge";
  marker.textContent = `${result.predictedLabel} ${(result.predictedProbability * 100).toFixed(1)}%`;
  marker.setAttribute("data-edge-overlay", "true");

  const parent = target.parentElement;
  if (!parent) {
    return;
  }
  parent.style.position = "relative";
  marker.style.position = "absolute";
  marker.style.top = "6px";
  marker.style.left = "6px";
  parent.appendChild(marker);
}

function clearOverlays(): void {
  document.querySelectorAll("[data-edge-overlay='true']").forEach((node) => node.remove());
}

async function runScan(): Promise<ScanResult[]> {
  const settings = await getSettings();
  const results = await scanCurrentPage(settings);

  clearOverlays();
  if (settings.overlayEnabled) {
    for (const item of results) {
      attachOverlay(item);
    }
  }

  await saveLastResults(results);
  return results;
}

chrome.runtime.onMessage.addListener((message: RuntimeMessage, _sender, sendResponse) => {
  if (message.action === "SCAN_PAGE") {
    void runScan()
      .then((results) => sendResponse({ ok: true, results }))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : "scan failed" }));
    return true;
  }

  return false;
});

void getSettings().then((settings) => {
  if (settings.autoScanEnabled) {
    void runScan();
  }
});
