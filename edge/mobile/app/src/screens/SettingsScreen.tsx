import React from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { formatFileSize } from "@/lib/helpers";
import { InferenceMode } from "@/lib/types";
import { storageService } from "@/services/storageService";
import { useAppStore } from "@/state/appStore";
import { useHistoryStore } from "@/state/historyStore";
import { theme } from "@/styles/theme";

const modes: InferenceMode[] = ["local", "backend", "auto"];

export function SettingsScreen(): React.JSX.Element {
  const settings = useAppStore((state) => state.settings);
  const model = useAppStore((state) => state.model);
  const setSettings = useAppStore((state) => state.setSettings);
  const clearEntries = useHistoryStore((state) => state.clearEntries);
  const [storageUsage, setStorageUsage] = React.useState<string>("calculating...");

  React.useEffect(() => {
    const load = async () => {
      const bytes = await storageService.estimateStorageUsageBytes();
      setStorageUsage(formatFileSize(bytes));
    };
    void load();
  }, [settings]);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Settings</Text>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Inference Preference</Text>
        <View style={styles.modeRow}>
          {modes.map((mode) => (
            <Pressable
              key={mode}
              style={[styles.modeButton, settings.inferenceMode === mode && styles.modeButtonActive]}
              onPress={() => setSettings({ inferenceMode: mode })}
            >
              <Text style={[styles.modeText, settings.inferenceMode === mode && styles.modeTextActive]}>{mode.toUpperCase()}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Sync Enabled</Text>
          <Switch value={settings.syncEnabled} onValueChange={(value) => setSettings({ syncEnabled: value })} />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Privacy Mode (Strict Local)</Text>
          <Switch
            value={settings.privacyMode === "strict_local"}
            onValueChange={(value) => setSettings({ privacyMode: value ? "strict_local" : "user_selectable" })}
          />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Debug Logging</Text>
          <Switch value={settings.debugLogging} onValueChange={(value) => setSettings({ debugLogging: value })} />
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Model Version: {model.modelVersion}</Text>
        <Text style={styles.label}>Local Model Available: {String(model.available)}</Text>
        <Text style={styles.label}>Runtime: {model.runtime}</Text>
        <Text style={styles.label}>Storage Usage (estimate): {storageUsage}</Text>
      </View>

      <Pressable
        style={styles.clearButton}
        onPress={() => {
          clearEntries();
          void storageService.clearHistory();
        }}
      >
        <Text style={styles.clearText}>Clear Local History</Text>
      </Pressable>
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
  card: {
    backgroundColor: theme.colors.panel,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    gap: theme.spacing.sm
  },
  sectionTitle: {
    color: theme.colors.ink,
    fontWeight: "700"
  },
  modeRow: {
    flexDirection: "row",
    gap: theme.spacing.xs,
    flexWrap: "wrap"
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
  modeText: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  modeTextActive: {
    color: theme.colors.accent
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  label: {
    color: theme.colors.muted
  },
  clearButton: {
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.danger,
    padding: theme.spacing.md,
    alignItems: "center"
  },
  clearText: {
    color: theme.colors.danger,
    fontWeight: "800"
  }
});
