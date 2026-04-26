import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { MediaPreview } from "@/components/MediaPreview";
import { ResultCard } from "@/components/ResultCard";
import { UploadPicker } from "@/components/UploadPicker";
import { useImageDetection } from "@/hooks/useImageDetection";
import { DEFAULT_THRESHOLD } from "@/lib/constants";
import { InferenceMode } from "@/lib/types";
import { nowIso, randomId, sha256FromText } from "@/lib/helpers";
import { mediaService } from "@/services/mediaService";
import { useHistoryStore } from "@/state/historyStore";
import { useAppStore } from "@/state/appStore";
import { useOfflineQueue } from "@/hooks/useOfflineQueue";
import { theme } from "@/styles/theme";

const modes: InferenceMode[] = ["local", "backend", "auto"];

export function ImageDetectScreen(): React.JSX.Element {
  const [uri, setUri] = useState("");
  const [mode, setMode] = useState<InferenceMode>("auto");
  const [threshold] = useState(DEFAULT_THRESHOLD);

  const { loading, error, result, runDetection } = useImageDetection();
  const addEntry = useHistoryStore((state) => state.addEntry);
  const settings = useAppStore((state) => state.settings);
  const { enqueue } = useOfflineQueue();

  const handlePick = async () => {
    const picked = await mediaService.pickImage();
    if (picked) {
      setUri(picked.uri);
    }
  };

  const run = async () => {
    if (!uri) {
      return;
    }
    const prediction = await runDetection(uri, mode, threshold);
    if (!prediction) {
      return;
    }

    const id = randomId("history");
    const mediaSha256 = await sha256FromText(uri);
    const entry = {
      id,
      createdAt: nowIso(),
      mediaUri: uri,
      mediaType: "image" as const,
      mediaSha256,
      prediction,
      syncStatus: settings.syncEnabled ? "pending" as const : "synced" as const
    };

    addEntry(entry);

    if (settings.syncEnabled && settings.privacyMode !== "strict_local") {
      await enqueue(id, entry);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Image Detection</Text>
      <UploadPicker onPickImage={handlePick} />
      <MediaPreview uri={uri} mediaType="image" />

      <View style={styles.modeRow}>
        {modes.map((item) => (
          <Pressable
            key={item}
            style={[styles.modeButton, mode === item && styles.modeButtonActive]}
            onPress={() => setMode(item)}
          >
            <Text style={[styles.modeLabel, mode === item && styles.modeLabelActive]}>{item.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.detectButton} onPress={run}>
        <Text style={styles.detectText}>Run Detection</Text>
      </Pressable>

      <ErrorBanner message={error} />
      {result ? <ResultCard result={result} /> : null}
      <LoadingOverlay visible={loading} message="Running image inference" />
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
  modeRow: {
    flexDirection: "row",
    gap: theme.spacing.xs
  },
  modeButton: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 8
  },
  modeButtonActive: {
    borderColor: theme.colors.accent,
    backgroundColor: "#e5f2f8"
  },
  modeLabel: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  modeLabelActive: {
    color: theme.colors.accent
  },
  detectButton: {
    backgroundColor: theme.colors.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center"
  },
  detectText: {
    color: "white",
    fontWeight: "800"
  }
});
