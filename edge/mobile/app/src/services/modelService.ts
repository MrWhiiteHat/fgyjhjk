import * as FileSystem from "expo-file-system";

import { ModelAvailability } from "@/lib/types";

const DEFAULT_MODEL_PATH = "src/assets/models/real_fake_mobile.tflite";
const DEFAULT_MODEL_VERSION = "v1.0.0";

function detectNativeRuntime(): ModelAvailability["runtime"] {
  try {
    // Optional runtime package check.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    require("react-native-fast-tflite");
    return "tflite";
  } catch {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      require("onnxruntime-react-native");
      return "onnx";
    } catch {
      return "none";
    }
  }
}

export const modelService = {
  async getLocalModelAvailability(localModelPath = DEFAULT_MODEL_PATH): Promise<ModelAvailability> {
    const runtime = detectNativeRuntime();
    const info = await FileSystem.getInfoAsync(localModelPath);

    return {
      localModelPath,
      modelVersion: DEFAULT_MODEL_VERSION,
      available: Boolean(info.exists) && runtime !== "none",
      runtime
    };
  },

  async isLocalRuntimeUsable(localModelPath = DEFAULT_MODEL_PATH): Promise<boolean> {
    const availability = await this.getLocalModelAvailability(localModelPath);
    return availability.available;
  }
};
