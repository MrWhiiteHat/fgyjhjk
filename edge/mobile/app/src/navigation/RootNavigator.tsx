import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { RootStackParamList } from "@/navigation/routes";
import { HomeScreen } from "@/screens/HomeScreen";
import { ImageDetectScreen } from "@/screens/ImageDetectScreen";
import { VideoDetectScreen } from "@/screens/VideoDetectScreen";
import { CameraDetectScreen } from "@/screens/CameraDetectScreen";
import { HistoryScreen } from "@/screens/HistoryScreen";
import { ExplainScreen } from "@/screens/ExplainScreen";
import { SettingsScreen } from "@/screens/SettingsScreen";

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator(): React.JSX.Element {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Home">
        <Stack.Screen name="Home" component={HomeScreen} />
        <Stack.Screen name="ImageDetect" component={ImageDetectScreen} options={{ title: "Image Detection" }} />
        <Stack.Screen name="VideoDetect" component={VideoDetectScreen} options={{ title: "Video Detection" }} />
        <Stack.Screen name="CameraDetect" component={CameraDetectScreen} options={{ title: "Camera Detection" }} />
        <Stack.Screen name="History" component={HistoryScreen} options={{ title: "History" }} />
        <Stack.Screen name="Explain" component={ExplainScreen} options={{ title: "Explanation" }} />
        <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: "Settings" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
