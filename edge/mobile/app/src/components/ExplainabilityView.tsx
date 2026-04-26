import React from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { ExplainabilityResult } from "@/lib/types";
import { theme } from "@/styles/theme";

interface ExplainabilityViewProps {
  data?: ExplainabilityResult;
}

export function ExplainabilityView({ data }: ExplainabilityViewProps): React.JSX.Element {
  if (!data) {
    return (
      <View style={styles.card}>
        <Text style={styles.note}>No explainability artifact available.</Text>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Explanation Type: {data.type}</Text>
      {data.overlayUri ? <Image source={{ uri: data.overlayUri }} style={styles.image} resizeMode="contain" /> : null}
      <Text style={styles.note}>{data.note}</Text>
      {data.metadata ? <Text style={styles.meta}>Metadata available</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.panel,
    borderRadius: theme.radius.md,
    borderColor: theme.colors.border,
    borderWidth: 1,
    padding: theme.spacing.md,
    gap: theme.spacing.xs
  },
  title: {
    color: theme.colors.ink,
    fontWeight: "700"
  },
  image: {
    width: "100%",
    height: 220,
    borderRadius: theme.radius.sm,
    backgroundColor: "#eef4f8"
  },
  note: {
    color: theme.colors.muted
  },
  meta: {
    color: theme.colors.muted,
    fontSize: 12
  }
});
