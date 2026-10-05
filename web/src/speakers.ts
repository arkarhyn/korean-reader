// Speaker colors for "화자: 대사" lines (DECISIONS 73). Fixed per character so the
// colors stay the same across episodes; tokens live in styles.css (light + dark).

const SPEAKER_SLOT: Record<string, number> = {
  이선: 1,
  서윤: 2,
  어머니: 3,
  엄마: 3,
  아버지: 4,
  아빠: 4,
  준수: 5,
  서현: 6,
  마이클: 7,
  할머니: 8,
};

/** CSS color for a speaker label ("어머니: " -> var(--spk-3)); unlisted labels are neutral. */
export function speakerColor(label: string): string {
  const name = label.replace(/:\s*$/, "").trim();
  const slot = SPEAKER_SLOT[name];
  return slot ? `var(--spk-${slot})` : "var(--ink-soft)";
}
