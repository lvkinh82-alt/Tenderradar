import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AppProvider } from "../lib/store";
import { useTheme } from "../lib/theme";

function Nav() {
  const c = useTheme();
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: c.panel },
        headerTintColor: c.ink,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: c.bg },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Muối Từ" }} />
      <Stack.Screen name="settings" options={{ title: "設定", presentation: "modal" }} />
      <Stack.Screen name="caption" options={{ headerShown: false, presentation: "fullScreenModal", animation: "fade" }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="auto" />
        <Nav />
      </AppProvider>
    </SafeAreaProvider>
  );
}
