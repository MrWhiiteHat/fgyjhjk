import React, { useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { CameraView } from "expo-camera";

import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { ResultCard } from "@/components/ResultCard";
import { useCameraDetection } from "@/hooks/useCameraDetection";
import { DEFAULT_THRESHOLD } from "@/lib/constants";
import { InferenceMode } from "@/lib/types";
import { mediaService } from "@/services/mediaService";
import { theme } from "@/styles/theme";

const modes: InferenceMode[] = ["local", "backend", "auto"];

export function CameraDetectScreen(): React.JSX.Element {
  const cameraRef = useRef<CameraView | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [mode, setMode] = useState<InferenceMode>("auto");
  const [note, setNote] = useState("Live mode is experimental and FPS-capped for battery safety.");

  const { loading, error, result, runDetection } = useCameraDetection();

  const requestPermission = async () => {
    const granted = await mediaService.requestCameraPermission();
    setPermissionGranted(granted);
    if (!granted) {
      setNote("Camera permission denied.");
    }
  };

  const captureAndDetect = async () => {
    if (!cameraRef.current) {
      return;
    }
    const photo = await cameraRef.current.takePictureAsync({ quality: 1, skipProcessing: false });
    if (!photo?.uri) {
      return;
    }
    await runDetection(photo.uri, mode, DEFAULT_THRESHOLD);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Camera Detection</Text>
      <Text style={styles.caption}>{note}</Text>

      {!permissionGranted ? (
        <Pressable style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Camera Permission</Text>
        </Pressable>
      ) : (
        <View style={styles.cameraWrap}>
          <CameraView ref={cameraRef} style={styles.camera} facing="front" />
        </View>
      )}

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

      <Pressable style={styles.button} onPress={captureAndDetect}>
        <Text style={styles.buttonText}>Capture Frame and Detect</Text>
      </Pressable>

      <ErrorBanner message={error} />
      {result ? <ResultCard result={result} /> : null}
      <LoadingOverlay visible={loading} message="Analyzing camera frame" />
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
  caption: {
    color: theme.colors.muted
  },
  cameraWrap: {
    borderRadius: theme.radius.md,
    overflow: "hidden"
  },
  camera: {
    width: "100%",
    height: 280
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
  button: {
    backgroundColor: theme.colors.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center"
  },
  buttonText: {
    color: "white",
    fontWeight: "800"
  }
});
