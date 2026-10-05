// Mirrors server/app/api/schemas.py.

export type Token = { s: number; e: number; lex?: number; g?: string };

export type Lexeme = {
  lemma: string;
  pos: string;
  gloss_en: string;
  gloss_ja: string | null;
  hanja: string | null;
  /** Known regardless of its own state: a story name, or known under another tag. */
  counts_known?: boolean;
};

export type Question = {
  id: number;
  kind: "comprehension" | "meaning_check" | "grammar_check";
  prompt_ko: string;
  prompt_en: string;
  options: string[];
  answer_idx: number;
  target_ref: string | null;
};

export type Paragraph = { idx: number; ko: string; en: string; tokens: Token[] };

export type Episode = {
  id: string;
  series: string;
  title_ko: string;
  title_en: string;
  register_tags: string[];
  target_grammar: string | null;
  coverage: number | null;
  updated_at: string;
  paragraphs: Paragraph[];
  questions: Question[];
  lexemes: Record<string, Lexeme>;
};

export type LexemeState = { lexeme_id: number; state: string; updated_at: string };

export type Completed = { episode_id: string; completed_at: string };

export type SyncPull = {
  server_time: string;
  episodes: Episode[];
  lexeme_states: LexemeState[];
  completed?: Completed[]; // read marks from every device
};

export type EventType =
  | "episode_open"
  | "word_tap"
  | "episode_complete"
  | "question_answer"
  | "mine_word"
  | "flag_sentence"
  | "placement_answer"
  | "grammar_drill_answer"
  | "set_state"
  | "word_untap";

export type Device = "laptop" | "iphone";

export type QueuedEvent = {
  id: string;
  ts: string;
  device: Device;
  type: EventType;
  payload: Record<string, unknown>;
};

/** How the word popover describes a word's known status. */
export type WordStatus =
  | { kind: "unknown" } // offer "I know this word"
  | { kind: "known" } // own state known: offer "I forgot this"
  | { kind: "fixed" } // counts known (story name / other tag): nothing to change
  | { kind: "changed"; to: string }; // changed this visit: offer Undo
