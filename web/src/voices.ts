// Per-character read-aloud voices (DECISIONS 91). Devices usually have one or two Korean
// system voices, so characters differ mainly by pitch and speed; when a second voice exists,
// the male cast uses it (`alt`). Narration and anyone outside the main cast use the default.

export type VoiceProfile = { pitch: number; rate: number; alt: boolean };

export const DEFAULT_VOICE: VoiceProfile = { pitch: 1, rate: 1, alt: false };

const PROFILES: Record<string, VoiceProfile> = {
  이선: { pitch: 0.8, rate: 1, alt: true },
  서윤: { pitch: 1.15, rate: 1.05, alt: false },
  어머니: { pitch: 1.05, rate: 0.95, alt: false },
  엄마: { pitch: 1.05, rate: 0.95, alt: false },
  아버지: { pitch: 0.65, rate: 0.92, alt: true },
  아빠: { pitch: 0.65, rate: 0.92, alt: true },
  준수: { pitch: 0.9, rate: 1.1, alt: true },
  서현: { pitch: 1.25, rate: 1, alt: false },
  마이클: { pitch: 0.75, rate: 0.95, alt: true },
  할머니: { pitch: 0.95, rate: 0.8, alt: false },
};

/** Voice for a speaker label ("아버지: " or "아버지"); empty / unlisted -> the default voice. */
export function voiceFor(label: string): VoiceProfile {
  const name = label.replace(/:\s*$/, "").trim();
  return PROFILES[name] ?? DEFAULT_VOICE;
}

export type VoiceRole = "default" | "alt"; // women & narration / men
export type VoicePrefs = Partial<Record<VoiceRole, string>>; // voice name per role
const PREFS_KEY = "tts.voices";

export function loadVoicePrefs(): VoicePrefs {
  try {
    return JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") as VoicePrefs;
  } catch {
    return {};
  }
}

export function saveVoicePrefs(prefs: VoicePrefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* preference only */
  }
}

export function koreanVoices<V extends { lang: string }>(voices: V[]): V[] {
  return voices.filter((v) => v.lang.replace("_", "-").toLowerCase().startsWith("ko"));
}

/**
 * Pick a Korean voice for a role: the one chosen in the voice picker if this device has it,
 * else the second Korean voice for `alt` (when there are two or more), else the first.
 */
export function pickVoice<V extends { lang: string; name: string }>(
  voices: V[],
  alt: boolean,
  prefs: VoicePrefs = {},
): V | undefined {
  const ko = koreanVoices(voices);
  if (ko.length === 0) return undefined;
  const chosen = ko.find((v) => v.name === prefs[alt ? "alt" : "default"]);
  if (chosen) return chosen;
  return alt && ko.length > 1 ? ko[1] : ko[0];
}
