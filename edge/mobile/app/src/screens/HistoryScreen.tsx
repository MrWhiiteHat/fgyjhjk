import React, { useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";

import { ResultCard } from "@/components/ResultCard";
import { SyncStatusBadge } from "@/components/SyncStatusBadge";
import { RootStackParamList } from "@/navigation/routes";
import { useHistoryStore } from "@/state/historyStore";
import { syncService } from "@/services/syncService";
import { theme } from "@/styles/theme";

const filters = ["all", "image", "video", "camera_frame", "REAL", "FAKE"] as const;

type FilterValue = (typeof filters)[number];

export function HistoryScreen({ navigation }: NativeStackScreenProps<RootStackParamList, "History">): React.JSX.Element {
  const entries = useHistoryStore((state) => state.entries);
  const removeEntry = useHistoryStore((state) => state.removeEntry);
  const updateSyncStatus = useHistoryStore((state) => state.updateSyncStatus);
  const [filter, setFilter] = useState<FilterValue>("all");

  const filtered = useMemo(() => {
    if (filter === "all") {
      return entries;
    }
    if (filter === "REAL" || filter === "FAKE") {
      return entries.filter((item) => item.prediction.predictedLabel === filter);
    }
    return entries.filter((item) => item.mediaType === filter);
  }, [entries, filter]);

  const retrySync = async (entryId: string) => {
    const summary = await syncService.syncPending();
    if (summary.failed === 0) {
      updateSyncStatus(entryId, "synced");
    } else {
      updateSyncStatus(entryId, "failed", "sync failed");
    }
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View style={styles.filterRow}>
            {filters.map((item) => (
              <Pressable
                key={item}
                style={[styles.filterButton, filter === item && styles.filterButtonActive]}
                onPress={() => setFilter(item)}
              >
                <Text style={[styles.filterText, filter === item && styles.filterTextActive]}>{item}</Text>
              </Pressable>
            ))}
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.itemCard}>
            <Text style={styles.timestamp}>{new Date(item.createdAt).toLocaleString()}</Text>
            <SyncStatusBadge status={item.syncStatus} />
            <ResultCard result={item.prediction} />
            <View style={styles.actions}>
              <Pressable style={styles.actionButton} onPress={() => navigation.navigate("Explain", { entryId: item.id })}>
                <Text style={styles.actionText}>Open Explain</Text>
              </Pressable>
              <Pressable style={styles.actionButton} onPress={() => retrySync(item.id)}>
                <Text style={styles.actionText}>Retry Sync</Text>
              </Pressable>
              <Pressable style={styles.actionDanger} onPress={() => removeEntry(item.id)}>
                <Text style={styles.actionDangerText}>Delete</Text>
              </Pressable>
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: theme.spacing.md
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm
  },
  filterButton: {
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 6
  },
  filterButtonActive: {
    borderColor: theme.colors.accent,
    backgroundColor: "#e5f2f8"
  },
  filterText: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  filterTextActive: {
    color: theme.colors.accent
  },
  itemCard: {
    backgroundColor: theme.colors.panel,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    gap: theme.spacing.xs
  },
  timestamp: {
    color: theme.colors.muted,
    fontSize: 12
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs
  },
  actionButton: {
    borderColor: theme.colors.accent,
    borderWidth: 1,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 6
  },
  actionText: {
    color: theme.colors.accent,
    fontWeight: "700",
    fontSize: 12
  },
  actionDanger: {
    borderColor: theme.colors.danger,
    borderWidth: 1,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 6
  },
  actionDangerText: {
    color: theme.colors.danger,
    fontWeight: "700",
    fontSize: 12
  }
});
