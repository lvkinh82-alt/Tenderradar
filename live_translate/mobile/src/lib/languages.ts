// [BCP-47 code used for speech recognition / TTS, native label, English name sent to the model]
export type Lang = readonly [code: string, label: string, name: string];

export const LANGS: readonly Lang[] = [
  ["zh-TW", "繁體中文（台灣）", "Traditional Chinese (Taiwan)"],
  ["zh-HK", "粵語（香港）", "Cantonese / Traditional Chinese (Hong Kong)"],
  ["zh-CN", "简体中文", "Simplified Chinese"],
  ["en-US", "English (US)", "American English"],
  ["en-GB", "English (UK)", "British English"],
  ["vi-VN", "Tiếng Việt", "Vietnamese"],
  ["ja-JP", "日本語", "Japanese"],
  ["ko-KR", "한국어", "Korean"],
  ["th-TH", "ไทย", "Thai"],
  ["id-ID", "Bahasa Indonesia", "Indonesian"],
  ["ms-MY", "Bahasa Melayu", "Malay"],
  ["fil-PH", "Filipino", "Filipino"],
  ["km-KH", "ខ្មែរ", "Khmer"],
  ["lo-LA", "ລາວ", "Lao"],
  ["my-MM", "မြန်မာ", "Burmese"],
  ["hi-IN", "हिन्दी", "Hindi"],
  ["bn-BD", "বাংলা", "Bengali"],
  ["ur-PK", "اردو", "Urdu"],
  ["ta-IN", "தமிழ்", "Tamil"],
  ["ne-NP", "नेपाली", "Nepali"],
  ["fr-FR", "Français", "French"],
  ["de-DE", "Deutsch", "German"],
  ["es-ES", "Español (España)", "Spanish (Spain)"],
  ["es-MX", "Español (México)", "Mexican Spanish"],
  ["pt-BR", "Português (BR)", "Brazilian Portuguese"],
  ["pt-PT", "Português (PT)", "European Portuguese"],
  ["it-IT", "Italiano", "Italian"],
  ["nl-NL", "Nederlands", "Dutch"],
  ["sv-SE", "Svenska", "Swedish"],
  ["nb-NO", "Norsk", "Norwegian"],
  ["da-DK", "Dansk", "Danish"],
  ["fi-FI", "Suomi", "Finnish"],
  ["pl-PL", "Polski", "Polish"],
  ["cs-CZ", "Čeština", "Czech"],
  ["sk-SK", "Slovenčina", "Slovak"],
  ["hu-HU", "Magyar", "Hungarian"],
  ["ro-RO", "Română", "Romanian"],
  ["bg-BG", "Български", "Bulgarian"],
  ["el-GR", "Ελληνικά", "Greek"],
  ["uk-UA", "Українська", "Ukrainian"],
  ["ru-RU", "Русский", "Russian"],
  ["tr-TR", "Türkçe", "Turkish"],
  ["ar-SA", "العربية", "Arabic"],
  ["he-IL", "עברית", "Hebrew"],
  ["fa-IR", "فارسی", "Persian"],
  ["sw-KE", "Kiswahili", "Swahili"],
  ["af-ZA", "Afrikaans", "Afrikaans"],
  ["zu-ZA", "isiZulu", "Zulu"],
  ["am-ET", "አማርኛ", "Amharic"],
  ["wo-SN", "Wolof", "Wolof"],
];

const find = (code: string) => LANGS.find((l) => l[0] === code);
export const langLabel = (code: string) => (code === "auto" ? "自動偵測" : find(code)?.[1] ?? code);
export const langName = (code: string) => (code === "auto" ? "auto" : find(code)?.[2] ?? code);

export const STYLES = [
  { value: "natural", label: "自然" },
  { value: "casual", label: "口語" },
  { value: "social", label: "社群道地" },
  { value: "formal", label: "正式" },
  { value: "business", label: "商務" },
] as const;
export type Style = (typeof STYLES)[number]["value"];
