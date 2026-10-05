import { useEffect, useState } from "react";
import { tts } from "../tts";
import { koreanVoices, loadVoicePrefs, pickVoice, saveVoicePrefs, type VoicePrefs, type VoiceRole } from "../voices";

const SAMPLE = "안녕하세요. 오늘 같이 저녁 먹어요.";
const ROLES: { role: VoiceRole; title: string; pitch: number }[] = [
  { role: "default", title: "Women & narration", pitch: 1 },
  { role: "alt", title: "Men", pitch: 0.85 },
];

/** Korean system voices on this device; they can load after the page does. */
function useKoreanVoices(): SpeechSynthesisVoice[] {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() =>
    typeof speechSynthesis === "undefined" ? [] : koreanVoices(speechSynthesis.getVoices()),
  );
  useEffect(() => {
    if (typeof speechSynthesis === "undefined") return;
    const update = () => setVoices(koreanVoices(speechSynthesis.getVoices()));
    speechSynthesis.addEventListener("voiceschanged", update);
    update();
    return () => speechSynthesis.removeEventListener("voiceschanged", update);
  }, []);
  return voices;
}

/** Bottom sheet: choose which device voice reads women/narration and which reads men (saved per device). */
export default function VoicePicker({ onClose }: { onClose: () => void }) {
  const voices = useKoreanVoices();
  const [prefs, setPrefs] = useState<VoicePrefs>(loadVoicePrefs);

  function choose(role: VoiceRole, name: string) {
    const next = { ...prefs, [role]: name };
    setPrefs(next);
    saveVoicePrefs(next);
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/30" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Voices"
        className="max-h-[80vh] w-full max-w-[36rem] overflow-y-auto rounded-t-2xl border-t border-rule bg-card px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-title text-lg font-bold">Voices</h2>
          <button type="button" onClick={onClose} className="min-h-11 px-3 text-sm text-ink-soft">
            Done
          </button>
        </div>
        {voices.length === 0 ? (
          <p className="mt-2 text-sm text-ink-soft">
            No Korean voices on this device. On iPhone: Settings → Accessibility → Spoken Content → Voices → Korean.
            On a PC, Microsoft Edge offers more Korean voices than Chrome.
          </p>
        ) : (
          <>
            <p className="mt-1 text-xs text-ink-soft">
              Saved on this device. Each character still gets their own pitch and speed.
            </p>
            {ROLES.map(({ role, title, pitch }) => {
              const current = pickVoice(voices, role === "alt", prefs)?.name;
              return (
                <section key={role} className="mt-4">
                  <h3 className="mb-1 font-ui text-xs tracking-wide text-ink-soft uppercase">{title}</h3>
                  <ul className="divide-y divide-rule border-y border-rule">
                    {voices.map((v) => (
                      <li key={v.name} className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => choose(role, v.name)}
                          aria-pressed={current === v.name}
                          className="flex min-h-12 flex-1 items-center gap-3 text-left text-[15px]"
                        >
                          <span
                            className={`inline-block size-4 shrink-0 rounded-full border ${
                              current === v.name ? "border-seal bg-seal" : "border-rule"
                            }`}
                          />
                          <span className="min-w-0 flex-1 truncate">{v.name}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => tts.speak(SAMPLE, { voiceName: v.name, pitch })}
                          aria-label={`Preview ${v.name}`}
                          className="flex size-10 shrink-0 items-center justify-center rounded-full border border-rule active:bg-paper-deep"
                        >
                          ▶
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
