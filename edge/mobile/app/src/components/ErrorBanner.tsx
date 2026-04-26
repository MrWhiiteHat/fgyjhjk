import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { theme } from "@/styles/theme";

interface ErrorBannerProps {
  message?: string;
}

export function ErrorBanner({ message }: ErrorBannerProps): React.JSX.Element | null {
  if (!message) {
    return null;
  }

  return (
    <View style={styles.container} accessibilityLabel="error-banner">
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#ffe7ea",
    borderColor: "#f2bac3",
    borderWidth: 1,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.sm
  },
  text: {
    color: theme.colors.danger,
    fontWeight: "600"
  }
});
