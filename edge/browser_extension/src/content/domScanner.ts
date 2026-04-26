import { ImageCandidate } from "@/lib/types";
import { randomId } from "@/lib/helpers";
import { shouldScanCandidate } from "@/lib/validators";

const scannedCache = new Set<string>();

function imageVisibilityOk(img: HTMLImageElement): boolean {
  const style = window.getComputedStyle(img);
  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
    return false;
  }
  if (img.clientWidth <= 0 || img.clientHeight <= 0) {
    return false;
  }
  return true;
}

export function collectImageCandidates(scanLimit: number): ImageCandidate[] {
  const images = Array.from(document.querySelectorAll("img"));
  const candidates: ImageCandidate[] = [];

  for (const img of images) {
    if (candidates.length >= scanLimit) {
      break;
    }
    const src = img.currentSrc || img.src;
    if (!src || scannedCache.has(src)) {
      continue;
    }
    if (!imageVisibilityOk(img)) {
      continue;
    }

    const candidate: ImageCandidate = {
      id: randomId("img"),
      src,
      width: img.naturalWidth || img.clientWidth,
      height: img.naturalHeight || img.clientHeight
    };

    if (!shouldScanCandidate(candidate)) {
      continue;
    }

    scannedCache.add(src);
    candidates.push(candidate);
  }

  return candidates;
}

export function resetScanCache(): void {
  scannedCache.clear();
}
