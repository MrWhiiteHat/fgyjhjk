import React from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";

import { ExplainabilityView } from "@/components/ExplainabilityView";
import { RootStackParamList } from "@/navigation/routes";
import { useHistoryStore } from "@/state/historyStore";
import { theme } from "@/styles/theme";

export function ExplainScreen({ route }: NativeStackScreenProps<RootStackParamList, "Explain">): React.JSX.Element {
  const entry = useHistoryStore((state) => state.getEntryById(route.params.entryId));

  if (!entry) {
    return (
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Explanation</Text>
        <Text style={styles.message}>History entry not found.</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Explanation</Text>
      <Text style={styles.message}>Prediction label: {entry.prediction.predictedLabel}</Text>
      <Text style={styles.limitNote}>
        On-device explanation may be heuristic. Use backend explanation for deeper attribution where available.
      </Text>
      <ExplainabilityView data={entry.explainability} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing.md,
    gap: theme.spacing.sm
  },
  title: {
    fontSize: 22,
    fontWeight: "800",
    color: theme.colors.ink
  },
  message: {
    color: theme.colors.muted
  },
  limitNote: {
    color: theme.colors.warning,
    fontSize: 12
  }
});
