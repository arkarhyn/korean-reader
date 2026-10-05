// DECISIONS 17: system voices first, behind an interface so a cloud provider can replace it.
import { pickVoice } from "./voices";

export type SpeakOpts = { rate?: number; pitch?: number; /** prefer the device's second Korean voice */ alt?: boolean };

export interface TtsProvider {
  available(): boolean;
  speak(text: string, opts?: SpeakOpts): void;
  stop(): void;
}

class WebSpeechProvider implements TtsProvider {
  available() {
    return typeof speechSynthesis !== "undefined";
  }

  speak(text: string, { rate = 1.0, pitch = 1.0, alt = false }: SpeakOpts = {}) {
    if (!this.available()) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    u.rate = rate;
    u.pitch = pitch;
    const v = pickVoice(speechSynthesis.getVoices(), alt);
    if (v) u.voice = v;
    speechSynthesis.speak(u);
  }

  stop() {
    if (this.available()) speechSynthesis.cancel();
  }
}

export const tts: TtsProvider = new WebSpeechProvider();
