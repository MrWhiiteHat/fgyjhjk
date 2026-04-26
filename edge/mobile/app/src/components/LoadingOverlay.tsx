import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { theme } from "@/styles/theme";

interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
}

export function LoadingOverlay({ visible, message = "Processing..." }: LoadingOverlayProps): React.JSX.Element | null {
  if (!visible) {
    return null;
  }

  return (
    <View style={styles.overlay} accessibilityLabel="loading-overlay">
      <View style={styles.card}>
        <ActivityIndicator size="large" color={theme.colors.accent} />
        <Text style={styles.text}>{message}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(11, 28, 40, 0.28)",
    zIndex: 10
  },
  card: {
    backgroundColor: theme.colors.panel,
    padding: theme.spacing.lg,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    alignItems: "center"
  },
  text: {
    marginTop: theme.spacing.sm,
    color: theme.colors.ink
  }
});
