import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { formatDurationMs } from "@/lib/helpers";
import { PredictionResult } from "@/lib/types";
import { theme } from "@/styles/theme";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";

interface ResultCardProps {
  result: PredictionResult;
}

export function ResultCard({ result }: ResultCardProps): React.JSX.Element {
  return (
    <View style={styles.card} accessibilityLabel="result-card">
      <Text style={styles.heading}>Prediction: {result.predictedLabel}</Text>
      <ConfidenceMeter value={result.predictedProbability} />
      <Text style={styles.meta}>Inference Time: {formatDurationMs(result.inferenceTimeMs)}</Text>
      <Text style={styles.meta}>Threshold: {result.threshold.toFixed(2)}</Text>
      <Text style={styles.meta}>Source: {result.modelSource}</Text>
      {typeof result.framesProcessed === "number" ? <Text style={styles.meta}>Frames: {result.framesProcessed}</Text> : null}
      {typeof result.fakeFrameRatio === "number" ? (
        <Text style={styles.meta}>Fake Frame Ratio: {(result.fakeFrameRatio * 100).toFixed(2)}%</Text>
      ) : null}
      {result.aggregationStrategy ? <Text style={styles.meta}>Aggregation: {result.aggregationStrategy}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.panel,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    gap: theme.spacing.xs
  },
  heading: {
    color: theme.colors.ink,
    fontWeight: "800",
    fontSize: 16
  },
  meta: {
    color: theme.colors.muted,
    fontSize: 12
  }
});
