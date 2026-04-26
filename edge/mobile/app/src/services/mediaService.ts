import * as Camera from "expo-camera";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";

import { MediaType } from "@/lib/types";
import { validateMediaInput } from "@/lib/validators";

export interface PickedMedia {
  uri: string;
  fileName?: string;
  sizeBytes?: number;
  mediaType: MediaType;
}

export const mediaService = {
  async pickImage(): Promise<PickedMedia | null> {
    const response = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 1
    });

    if (response.canceled || response.assets.length === 0) {
      return null;
    }

    const asset = response.assets[0];
    const validation = validateMediaInput({
      uri: asset.uri,
      fileName: asset.fileName,
      sizeBytes: asset.fileSize,
      mediaType: "image"
    });
    if (!validation.ok) {
      throw new Error(validation.error);
    }

    return {
      uri: asset.uri,
      fileName: asset.fileName,
      sizeBytes: asset.fileSize,
      mediaType: "image"
    };
  },

  async pickVideo(): Promise<PickedMedia | null> {
    const response = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
      quality: 1
    });

    if (response.canceled || response.assets.length === 0) {
      return null;
    }

    const asset = response.assets[0];
    const validation = validateMediaInput({
      uri: asset.uri,
      fileName: asset.fileName,
      sizeBytes: asset.fileSize,
      mediaType: "video"
    });
    if (!validation.ok) {
      throw new Error(validation.error);
    }

    return {
      uri: asset.uri,
      fileName: asset.fileName,
      sizeBytes: asset.fileSize,
      mediaType: "video"
    };
  },

  async requestCameraPermission(): Promise<boolean> {
    const permission = await Camera.Camera.requestCameraPermissionsAsync();
    return permission.granted;
  },

  async getFileInfo(uri: string): Promise<{ sizeBytes: number; exists: boolean }> {
    const info = await FileSystem.getInfoAsync(uri);
    return {
      sizeBytes: "size" in info && typeof info.size === "number" ? info.size : 0,
      exists: Boolean(info.exists)
    };
  }
};
