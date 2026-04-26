import React from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { Video, ResizeMode } from "expo-av";

import { MediaType } from "@/lib/types";
import { theme } from "@/styles/theme";

interface MediaPreviewProps {
  uri?: string;
  mediaType: MediaType;
}

export function MediaPreview({ uri, mediaType }: MediaPreviewProps): React.JSX.Element {
  if (!uri) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No media selected</Text>
      </View>
    );
  }

  if (mediaType === "video") {
    return (
      <Video
        source={{ uri }}
        style={styles.preview}
        useNativeControls
        resizeMode={ResizeMode.CONTAIN}
      />
    );
  }

  return <Image source={{ uri }} style={styles.preview} resizeMode="contain" accessibilityLabel="media-preview" />;
}

const styles = StyleSheet.create({
  preview: {
    width: "100%",
    height: 240,
    borderRadius: theme.radius.md,
    backgroundColor: "#dbe8ef"
  },
  empty: {
    width: "100%",
    height: 240,
    borderRadius: theme.radius.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#eef4f8"
  },
  emptyText: {
    color: theme.colors.muted
  }
});
