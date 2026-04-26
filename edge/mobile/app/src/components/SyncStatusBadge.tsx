import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { SyncStatus } from "@/lib/types";
import { theme } from "@/styles/theme";

interface SyncStatusBadgeProps {
  status: SyncStatus;
}

const STATUS_COLORS: Record<SyncStatus, string> = {
  pending: theme.colors.warning,
  syncing: theme.colors.accent,
  synced: theme.colors.success,
  failed: theme.colors.danger,
  conflict: theme.colors.danger
};

export function SyncStatusBadge({ status }: SyncStatusBadgeProps): React.JSX.Element {
  return (
    <View style={[styles.badge, { borderColor: STATUS_COLORS[status] }]} accessibilityLabel={`sync-status-${status}`}>
      <Text style={[styles.label, { color: STATUS_COLORS[status] }]}>{status.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 3,
    alignSelf: "flex-start"
  },
  label: {
    fontSize: 12,
    fontWeight: "700"
  }
});
