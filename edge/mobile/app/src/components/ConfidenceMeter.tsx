import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { formatProbability } from "@/lib/helpers";
import { theme } from "@/styles/theme";

interface ConfidenceMeterProps {
  value: number;
  label?: string;
}

export function ConfidenceMeter({ value, label = "Confidence" }: ConfidenceMeterProps): React.JSX.Element {
  const normalized = Math.max(0, Math.min(1, value));

  return (
    <View style={styles.container} accessibilityLabel="confidence-meter">
      <Text style={styles.label}>{label}</Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${normalized * 100}%` }]} />
      </View>
      <Text style={styles.value}>{formatProbability(normalized)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: theme.spacing.xs
  },
  label: {
    color: theme.colors.muted,
    fontSize: 12
  },
  track: {
    height: 10,
    borderRadius: 999,
    backgroundColor: "#dce8ef",
    overflow: "hidden"
  },
  fill: {
    height: "100%",
    backgroundColor: theme.colors.accent
  },
  value: {
    color: theme.colors.ink,
    fontWeight: "700"
  }
});
