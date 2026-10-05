// DECISIONS 17: system voices first, behind an interface so a cloud provider can replace it.

export interface TtsProvider {
  available(): boolean;
  speak(text: string, opts?: { rate?: number }): void;
  stop(): void;
}

class WebSpeechProvider implements TtsProvider {
  private voice(): SpeechSynthesisVoice | undefined {
    return speechSynthesis.getVoices().find((v) => v.lang.replace("_", "-").startsWith("ko"));
  }

  available() {
    return typeof speechSynthesis !== "undefined";
  }

  speak(text: string, { rate = 1.0 } = {}) {
    if (!this.available()) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    u.rate = rate;
    const v = this.voice();
    if (v) u.voice = v;
    speechSynthesis.speak(u);
  }

  stop() {
    if (this.available()) speechSynthesis.cancel();
  }
}

export const tts: TtsProvider = new WebSpeechProvider();
