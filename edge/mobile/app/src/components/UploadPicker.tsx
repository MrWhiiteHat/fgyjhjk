import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { theme } from "@/styles/theme";

interface UploadPickerProps {
  onPickImage?: () => void;
  onPickVideo?: () => void;
}

export function UploadPicker({ onPickImage, onPickVideo }: UploadPickerProps): React.JSX.Element {
  return (
    <View style={styles.row}>
      {onPickImage ? (
        <Pressable style={styles.button} onPress={onPickImage} accessibilityLabel="pick-image-button">
          <Text style={styles.buttonText}>Choose Image</Text>
        </Pressable>
      ) : null}
      {onPickVideo ? (
        <Pressable style={styles.button} onPress={onPickVideo} accessibilityLabel="pick-video-button">
          <Text style={styles.buttonText}>Choose Video</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: theme.spacing.sm,
    flexWrap: "wrap"
  },
  button: {
    backgroundColor: theme.colors.accent,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.radius.sm
  },
  buttonText: {
    color: "white",
    fontWeight: "700"
  }
});
