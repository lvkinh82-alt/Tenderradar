import { useColorScheme } from "react-native";

const light = {
  bg: "#f6f7fb",
  panel: "#ffffff",
  ink: "#1b1f2a",
  muted: "#6b7385",
  line: "#e3e6ee",
  accent: "#6d4aff",
  accentInk: "#ffffff",
  a: "#0f9d74",
  b: "#c2410c",
  danger: "#d92d20",
  chip: "#eef0f6",
};
const dark: typeof light = {
  bg: "#0f1218",
  panel: "#171b23",
  ink: "#e8ebf2",
  muted: "#9097a8",
  line: "#272d39",
  accent: "#8b7bff",
  accentInk: "#ffffff",
  a: "#34d399",
  b: "#fb923c",
  danger: "#f87171",
  chip: "#222835",
};
export type Theme = typeof light;
export const useTheme = (): Theme => (useColorScheme() === "dark" ? dark : light);
