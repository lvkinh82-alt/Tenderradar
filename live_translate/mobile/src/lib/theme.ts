import { useColorScheme } from "react-native";

const light = {
  bg: "#f6f7fb",
  panel: "#ffffff",
  ink: "#1b1f2a",
  muted: "#6b7385",
  line: "#e3e6ee",
  accent: "#047857",
  accentInk: "#ffffff",
  a: "#2563eb",
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
  accent: "#34d399",
  accentInk: "#052e24",
  a: "#60a5fa",
  b: "#fb923c",
  danger: "#f87171",
  chip: "#222835",
};
export type Theme = typeof light;
export const useTheme = (): Theme => (useColorScheme() === "dark" ? dark : light);
