import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";

import { RootStackParamList } from "@/navigation/routes";
import { useSync } from "@/hooks/useSync";
import { useAppStore } from "@/state/appStore";
import { theme } from "@/styles/theme";

export function HomeScreen({ navigation }: NativeStackScreenProps<RootStackParamList, "Home">): React.JSX.Element {
  const { isOnline, syncing, lastSyncSummary } = useSync();
  const connectivity = useAppStore((state) => state.connectivity);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Real vs Fake Detection</Text>
      <Text style={styles.subtitle}>Edge-ready inference with offline-safe sync.</Text>

      <View style={styles.statusCard}>
        <Text style={styles.statusText}>Online: {String(isOnline)}</Text>
        <Text style={styles.statusText}>Backend Reachable: {String(connectivity.backendReachable)}</Text>
        <Text style={styles.statusText}>Syncing: {String(syncing)}</Text>
        <Text style={styles.statusText}>
          Last Sync: {lastSyncSummary ? `synced=${lastSyncSummary.synced}, failed=${lastSyncSummary.failed}` : "none"}
        </Text>
      </View>

      <Pressable style={styles.button} onPress={() => navigation.navigate("ImageDetect")}>
        <Text style={styles.buttonText}>Image Detection</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => navigation.navigate("VideoDetect")}>
        <Text style={styles.buttonText}>Video Detection</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => navigation.navigate("CameraDetect")}>
        <Text style={styles.buttonText}>Camera Detection</Text>
      </Pressable>
      <Pressable style={styles.buttonSecondary} onPress={() => navigation.navigate("History")}>
        <Text style={styles.buttonSecondaryText}>History</Text>
      </Pressable>
      <Pressable style={styles.buttonSecondary} onPress={() => navigation.navigate("Settings")}>
        <Text style={styles.buttonSecondaryText}>Settings</Text>
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
    fontSize: 26,
    fontWeight: "800",
    color: theme.colors.ink
  },
  subtitle: {
    color: theme.colors.muted,
    marginBottom: theme.spacing.sm
  },
  statusCard: {
    backgroundColor: theme.colors.panel,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    gap: 4
  },
  statusText: {
    color: theme.colors.muted
  },
  button: {
    backgroundColor: theme.colors.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center"
  },
  buttonText: {
    color: "white",
    fontWeight: "800"
  },
  buttonSecondary: {
    borderWidth: 1,
    borderColor: theme.colors.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center"
  },
  buttonSecondaryText: {
    color: theme.colors.accent,
    fontWeight: "700"
  }
});
