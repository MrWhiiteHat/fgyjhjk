import { backendExplain } from "@/lib/api";
import { ExplainabilityResult } from "@/lib/types";

export const explainabilityService = {
  async resolveExplainability(
    params: {
      requestId?: string;
      localOverlayUri?: string;
      localSupported: boolean;
      privacyMode: "strict_local" | "user_selectable";
    }
  ): Promise<ExplainabilityResult> {
    if (params.localSupported && params.localOverlayUri) {
      return {
        type: "local_lightweight",
        overlayUri: params.localOverlayUri,
        note: "Heuristic on-device explanation"
      };
    }

    if (params.privacyMode === "strict_local") {
      return {
        type: "unavailable",
        note: "Privacy mode blocks backend explainability"
      };
    }

    if (!params.requestId) {
      return {
        type: "unavailable",
        note: "No backend request id available for explainability"
      };
    }

    return backendExplain(params.requestId);
  }
};
