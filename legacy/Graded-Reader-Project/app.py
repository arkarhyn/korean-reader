import os
import re
import json
import logging
import sqlite3
import asyncio
import time
import httpx

logging.Formatter.converter = time.gmtime  # All log timestamps in UTC
from contextlib import asynccontextmanager, contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "data/vocab.db"

# ── "Studying" tag ──────────────────────────────────────────────────────────
# Every lookup tags a word 'studying'. The tag clears automatically once the
# word stops needing lookups, or manually from the vocab table.
STUDYING_IDLE_DAYS = 14          # graduate after this many days without a lookup
STUDYING_GRADUATE_INTERVAL = 16  # or when the SRS review interval reaches this many days

IMPORT_LOOKUP_CAP = 25  # max LLM definitions per vocab-list import request

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_LOOKUP_MODEL = os.getenv("OLLAMA_LOOKUP_MODEL", OLLAMA_MODEL)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

LOOKUP_PROMPT = (
    "You are a Korean dictionary for a learner who also knows Japanese. "
    "Given a Korean word, return ONLY a JSON object with these fields:\n"
    '  "reading": pronunciation in hangul (or empty string if same as the word),\n'
    '  "definition": concise English definition. If the word has several distinct common\n'
    '      meanings — especially Sino-Korean homonyms from DIFFERENT hanja (e.g. 자신 =\n'
    '      自身 "oneself" AND 自信 "self-confidence") — list each sense on its own,\n'
    '      noting the hanja so the learner can tell them apart. Otherwise 1-3 sentences.\n'
    '  "pos": part of speech in English (noun, verb, adjective, adverb, etc.),\n'
    '  "grade": TOPIK level if known (초급/중급/고급), else empty string,\n'
    '  "japanese": an object with:\n'
    '      "word": the Japanese equivalent in kanji/kana (use the most natural Japanese word),\n'
    '      "reading": hiragana reading of the Japanese word,\n'
    '      "note": one short sentence on the connection — e.g. shared hanja/kanji origin,\n'
    '              same English loanword root, or structural parallel. Omit if self-evident.\n'
    '    Set "japanese" to null if the Korean word has no meaningful Japanese equivalent\n'
    '    (e.g. pure native Korean with no cognate or loan parallel).\n'
    "Do not include markdown, code fences, or any text outside the JSON object."
)

REFINE_PROMPT = (
    "You are a native Korean speaker reviewing a language learning passage. "
    "The passage below was AI-generated and may sound formulaic or unnatural. "
    "Rewrite it so it reads like authentic Korean — the kind found in real Korean textbooks, "
    "drama scripts, or everyday writing at the same proficiency level.\n\n"
    "Fix these common AI issues while keeping the same vocabulary level, topic, and length:\n"
    "- Repetitive sentence starters or identical sentence patterns\n"
    "- Stilted, overly symmetric structures no native writer would use\n"
    "- Dialogue that sounds scripted rather than genuine speech\n"
    "- Inconsistent speech register (pick one — 해요체 or 반말 — and stay consistent)\n"
    "- Anything that sounds like translated English rather than natural Korean thought\n\n"
    "Output ONLY the improved Korean passage — no commentary, no English, no explanations.\n\n"
    "Original passage:\n{draft}"
)

GRAMMAR_PROMPT = (
    "You are a Korean grammar reference for an intermediate learner who also knows Japanese. "
    "Given a Korean grammar pattern or ending, return ONLY a JSON object with these fields:\n"
    '  "pattern": canonical form (e.g. "-(으)면", "-아/어서"),\n'
    '  "meaning": one-sentence English description of its function,\n'
    '  "formation": how to attach it — consonant/vowel rules, stem changes (1-2 sentences),\n'
    '  "examples": array of exactly 3 objects, each with "korean" and "english" keys,\n'
    '  "japanese": the closest Japanese grammatical equivalent as a short string\n'
    '    (e.g. "〜たら／〜ば (conditional)"), or null if no meaningful parallel,\n'
    '  "notes": important nuance, formality level, or common mistakes (1-2 sentences), or "".\n'
    "Do not include markdown, code fences, or any text outside the JSON object."
)

# ── Morpheme analyzer (kiwipiepy) ──────────────────────────────────────────
try:
    from kiwipiepy import Kiwi as _Kiwi
    _KIWI_AVAILABLE = True
except ImportError:
    _Kiwi = None
    _KIWI_AVAILABLE = False

kiwi = None  # initialised in lifespan; None if kiwipiepy not installed

_NOUN_TAGS = {"NNG", "NNP", "NNB"}
_PREDICATE_TAGS = {"VV", "VA", "VCP", "VCN", "VX"}
_GRAMMAR_TAGS = {"EC", "EF", "EP", "ETM", "ETN", "JX", "JC", "JKS", "JKO", "JKB", "JKC"}
_NEGATION_ADVERBS = {"안", "못"}  # short-form negation; attach to the predicate they negate


def _base_tag(token) -> str:
    """Kiwi's POS tag for a token, with the irregular/regular suffix stripped.
    Irregular predicates are tagged VV-I / VA-I (e.g. 걷다→걸어 is 걷/VV-I); without
    this the whole app silently dropped every irregular verb and adjective."""
    raw = token.tag
    name = raw.name if hasattr(raw, "name") else str(raw).split(".")[-1]
    return name.split("-")[0]


def _content_lemmas(tokens, text):
    """Yield (lemma, start, end) for each content word in a Kiwi token list.

    Consecutive nouns written with no gap are merged into one compound-noun lemma
    (애견 + 용품 → 애견용품) — Kiwi over-splits compounds, and looking up only the
    first half is wrong. Nouns use the surface slice (so 사이시옷 spellings like
    나뭇잎 survive); predicates use the normalised stem + 다 (so irregulars resolve).
    `text` is the string the token offsets index into."""
    n = len(tokens)
    i = 0
    while i < n:
        tag = _base_tag(tokens[i])
        # Long-form auxiliaries after -지/-고 are their own word (separated by a space):
        # [verb]지 말다 (don't), [verb]지 않다 (not), [verb]지 못하다 (can't), [verb]고 말다
        # (end up doing). Resolve the auxiliary token to the whole construction so a click
        # explains the grammar pattern instead of a bare/ambiguous 말다/않다.
        prev_ec = tokens[i - 1].form if i > 0 and _base_tag(tokens[i - 1]) == "EC" else ""
        if prev_ec in ("지", "고"):
            form = tokens[i].form
            if form == "말" and tag == "VX":
                yield f"-{prev_ec} 말다", tokens[i].start, tokens[i].start + tokens[i].len
                i += 1
                continue
            if prev_ec == "지" and form == "않" and tag == "VX":
                yield "-지 않다", tokens[i].start, tokens[i].start + tokens[i].len
                i += 1
                continue
            if prev_ec == "지" and form == "못" and tag == "MAG":
                end = tokens[i].start + tokens[i].len
                j = i + 1
                if j < n and tokens[j].form == "하" and _base_tag(tokens[j]) in _PREDICATE_TAGS:
                    end = tokens[j].start + tokens[j].len
                    j += 1
                yield "-지 못하다", tokens[i].start, end
                i = j
                continue
        if tag in _NOUN_TAGS:
            j = i + 1
            while (j < n and _base_tag(tokens[j]) in _NOUN_TAGS
                   and tokens[j].start == tokens[j - 1].start + tokens[j - 1].len):
                j += 1
            start = tokens[i].start
            noun_end = tokens[j - 1].start + tokens[j - 1].len
            # A noun immediately followed by a verb/adjective-deriving suffix is a single
            # derived predicate: 긴장 + 하/XSV → 긴장하다, 산책 + 시키/XSV → 산책시키다,
            # 자연 + 스럽/XSA → 자연스럽다. Otherwise it's just the (compound) noun.
            if (j < n and _base_tag(tokens[j]) in ("XSV", "XSA")
                    and tokens[j].start == noun_end):
                suf = tokens[j]
                yield text[start:noun_end] + suf.form + "다", start, suf.start + suf.len
                i = j + 1
            else:
                yield text[start:noun_end], start, noun_end
                i = j
        elif tag in _PREDICATE_TAGS:
            yield tokens[i].form + "다", tokens[i].start, tokens[i].start + tokens[i].len
            i += 1
        elif tag == "MAG" and tokens[i].form in _NEGATION_ADVERBS:
            # Short negation 안/못 is a separate word from the verb it negates. Attach
            # it to that predicate so a click gives the whole expression (안 되다 =
            # "not allowed"), not the unrelated noun 안 (安, "inside/safe").
            k = i + 1
            while k < n and _base_tag(tokens[k]) == "MAG":
                k += 1
            if k < n and _base_tag(tokens[k]) in _PREDICATE_TAGS:
                lemma = tokens[i].form + " " + tokens[k].form + "다"
            else:
                lemma = tokens[i].form
            yield lemma, tokens[i].start, tokens[i].start + tokens[i].len
            i += 1
        else:
            i += 1


def get_lemma(word: str) -> Optional[str]:
    """Return the dictionary base form of a Korean word, or None if unavailable."""
    if kiwi is None:
        return None
    try:
        result = kiwi.analyze(word)
        if not result:
            return None
        first = result[0]
        tokens = first.tokens if hasattr(first, "tokens") else first[0]
        if not tokens:
            return None
        lemmas = list(_content_lemmas(tokens, word))
        if not lemmas:
            return None
        candidate = lemmas[0][0]  # dictionary form of the first content word (compound-aware)
        return candidate if candidate != word else None
    except Exception as e:
        print(f"[kiwi] Error analysing '{word}': {e}")
        return None


def get_grammar_hints(word: str) -> list:
    """Return grammar endings/particles detected in word, as clickable hint strings."""
    if kiwi is None:
        return []
    try:
        result = kiwi.analyze(word)
        if not result:
            return []
        tokens = result[0].tokens if hasattr(result[0], "tokens") else result[0][0]
        seen, hints = set(), []
        for token in tokens:
            tag = _base_tag(token)
            if tag in _GRAMMAR_TAGS and token.form not in seen:
                seen.add(token.form)
                hints.append(f"-{token.form}")
        return hints
    except Exception:
        return []


# ── Database ───────────────────────────────────────────────────────────────
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS passages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            level TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vocab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE,
            reading TEXT DEFAULT '',
            definition TEXT DEFAULT '',
            part_of_speech TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            first_seen TEXT DEFAULT (datetime('now', 'localtime')),
            last_seen TEXT DEFAULT (datetime('now', 'localtime')),
            lookup_count INTEGER DEFAULT 1,
            japanese TEXT DEFAULT ''
        )
    """)
    # Migrations: add columns to existing DBs
    cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab)")}
    if "japanese" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN japanese TEXT DEFAULT ''")
    if "example_sentence" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN example_sentence TEXT DEFAULT ''")
    if "next_review" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN next_review TEXT DEFAULT NULL")
    if "review_interval" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN review_interval INTEGER DEFAULT 1")
    if "status" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN status TEXT DEFAULT ''")
        # Backfill: words looked up within the idle window are still being studied
        conn.execute(
            "UPDATE vocab SET status = 'studying' "
            "WHERE lookup_count >= 1 AND last_seen > datetime('now', ?, 'localtime')",
            (f"-{STUDYING_IDLE_DAYS} days",),
        )
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kiwi
    init_db()
    if _KIWI_AVAILABLE:
        print("[kiwi] Loading morpheme analyser (first run may take a moment)…")
        kiwi = _Kiwi()
        print("[kiwi] Ready.")
    else:
        print("[kiwi] kiwipiepy not installed — run 'pip install kiwipiepy' to enable auto-lemmatisation.")
    yield


app = FastAPI(lifespan=lifespan)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def closing_db():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def auto_graduate(conn) -> int:
    """Clear the 'studying' tag on words that no longer need it: not looked up
    for STUDYING_IDLE_DAYS, or SRS interval reached STUDYING_GRADUATE_INTERVAL."""
    cur = conn.execute(
        """UPDATE vocab SET status = ''
           WHERE status = 'studying'
             AND (last_seen <= datetime('now', ?, 'localtime')
                  OR review_interval >= ?)""",
        (f"-{STUDYING_IDLE_DAYS} days", STUDYING_GRADUATE_INTERVAL),
    )
    conn.commit()
    return cur.rowcount


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some models wrap around JSON responses."""
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return text


def _passage_coverage_inline(text: str, vocab_set: set) -> tuple[float, list[str]]:
    """Return (coverage_ratio, unknown_lemmas) using Kiwi. Falls back to (1.0, []) if unavailable."""
    if kiwi is None or not text.strip():
        return 1.0, []
    try:
        result = kiwi.analyze(text)
        tokens = result[0].tokens if hasattr(result[0], "tokens") else result[0][0]
    except Exception:
        return 1.0, []
    seen: dict[str, bool] = {}
    for lemma, _s, _e in _content_lemmas(tokens, text):
        if lemma not in seen:
            seen[lemma] = lemma in vocab_set
    if not seen:
        return 1.0, []
    known_count = sum(1 for v in seen.values() if v)
    unknown = [lemma for lemma, known in seen.items() if not known]
    return known_count / len(seen), unknown


# ── Pydantic models ────────────────────────────────────────────────────────
class PassageCreate(BaseModel):
    title: str
    content: str
    level: str = ""


class LookupRequest(BaseModel):
    word: str
    passage_id: Optional[int] = None
    example_sentence: Optional[str] = None
    refresh: bool = False  # bypass the cache to regenerate a wrong/stale definition


class ReviewAnswer(BaseModel):
    word_id: int
    correct: bool


class StatusUpdate(BaseModel):
    status: str  # 'studying' or '' (known / vocab bank)


class MarkWord(BaseModel):
    word: str
    status: str  # '' (known) or 'studying'


class GrammarRequest(BaseModel):
    pattern: str


class CoverageRequest(BaseModel):
    words: list[str]


class PassageTextRequest(BaseModel):
    text: str


class GenerateRequest(BaseModel):
    level: str = "beginner"
    topic: str = ""
    grammar_focus: str = ""
    register: str = "polite"
    use_vocab: bool = True
    refine: bool = False


# ── Passage endpoints ──────────────────────────────────────────────────────
@app.get("/api/passages")
def list_passages():
    with closing_db() as conn:
        rows = conn.execute(
            "SELECT id, title, level, created_at FROM passages ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/passages")
def create_passage(p: PassageCreate):
    with closing_db() as conn:
        cur = conn.execute(
            "INSERT INTO passages (title, content, level) VALUES (?, ?, ?)",
            (p.title, p.content, p.level),
        )
        conn.commit()
        pid = cur.lastrowid
    return {"id": pid}


@app.get("/api/passages/{pid}")
def get_passage(pid: int):
    with closing_db() as conn:
        row = conn.execute("SELECT * FROM passages WHERE id = ?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Passage not found")
    return dict(row)


@app.put("/api/passages/{pid}")
def update_passage(pid: int, p: PassageCreate):
    with closing_db() as conn:
        conn.execute(
            "UPDATE passages SET title=?, content=?, level=? WHERE id=?",
            (p.title, p.content, p.level, pid),
        )
        conn.commit()
    return {"ok": True}


@app.delete("/api/passages/{pid}")
def delete_passage(pid: int):
    with closing_db() as conn:
        conn.execute("DELETE FROM passages WHERE id = ?", (pid,))
        conn.commit()
    return {"ok": True}


# ── LLM abstraction (Ollama or Gemini) ────────────────────────────────────
async def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 1024, model: str = "") -> str:
    """Call the configured LLM and return raw text. Raises on unrecoverable error."""
    ollama_model = model or OLLAMA_MODEL
    if ollama_model:
        payload = {
            "model": ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
        return _strip_fences(raw)

    # Gemini fallback
    if not GEMINI_API_KEY:
        raise RuntimeError("No LLM configured — set OLLAMA_MODEL or GEMINI_API_KEY in .env")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    for attempt in range(3):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload, timeout=30.0
            )
        if resp.status_code == 429 and attempt < 2:
            await asyncio.sleep(4 * (attempt + 1))
            continue
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return _strip_fences(raw)
    raise RuntimeError("Still rate-limited after retries")


# ── Word lookup ────────────────────────────────────────────────────────────
async def lookup_definition(word: str) -> dict:
    try:
        raw = await call_llm(f"{LOOKUP_PROMPT}\n\nWord: {word}", temperature=0.1, max_tokens=256, model=OLLAMA_LOOKUP_MODEL)
    except Exception as e:
        print(f"[lookup] LLM error for '{word}': {e}")
        return {"word": word, "reading": "", "definition": f"Lookup error: {e}", "pos": "", "grade": "", "not_found": True}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[lookup] Bad JSON for '{word}': {raw[:200]}")
        return {"word": word, "reading": "", "definition": raw, "pos": "", "grade": ""}
    return {
        "word": word,
        "reading": data.get("reading", ""),
        "definition": data.get("definition", ""),
        "pos": data.get("pos", ""),
        "grade": data.get("grade", ""),
        "japanese": data.get("japanese"),
    }


@app.post("/api/define")
async def define_word(req: LookupRequest):
    # Auto-lemmatize with Kiwi before lookup
    lemma = get_lemma(req.word)
    lookup_target = lemma if lemma else req.word
    grammar_hints = get_grammar_hints(req.word)

    # ── Cache check: return stored definition without hitting Gemini ──────────
    conn = get_db()
    try:
        cached = conn.execute("SELECT * FROM vocab WHERE word = ?", (lookup_target,)).fetchone()
        if cached and cached["definition"] and not req.refresh:
            # A lookup records activity but must NOT change an existing word's status —
            # clicking a known word to peek at it should keep it known, not re-study it.
            update_sql = "UPDATE vocab SET lookup_count = lookup_count + 1, last_seen = datetime('now','localtime')"
            params: list = [lookup_target]
            # Update example_sentence if a better (non-empty) one is provided
            if req.example_sentence and not cached["example_sentence"]:
                update_sql += ", example_sentence = ?"
                params.insert(0, req.example_sentence)
            conn.execute(update_sql + " WHERE word = ?", params)
            conn.commit()
            result = {
                "word": cached["word"],
                "reading": cached["reading"],
                "definition": cached["definition"],
                "pos": cached["part_of_speech"],
                "grade": cached["grade"],
                "example_sentence": req.example_sentence or cached["example_sentence"] or "",
                "status": cached["status"] or "",
            }
            if cached["japanese"]:
                try:
                    result["japanese"] = json.loads(cached["japanese"])
                except Exception:
                    pass
            if lemma:
                result["analyzed_from"] = req.word
            result["grammar_hints"] = grammar_hints
            return result
    finally:
        conn.close()

    # ── Fresh lookup via Gemini ───────────────────────────────────────────────
    result = await lookup_definition(lookup_target)
    if lemma:
        result["analyzed_from"] = req.word
    result["grammar_hints"] = grammar_hints

    if not result.get("not_found"):
        ja_json = json.dumps(result["japanese"]) if result.get("japanese") else ""
        ex = req.example_sentence or ""
        result["example_sentence"] = ex
        conn = get_db()
        try:
            # New words start as 'studying'; existing words keep whatever status they
            # already have (a lookup never demotes a known word — status is untouched
            # in the ON CONFLICT branch).
            conn.execute(
                """INSERT INTO vocab (word, reading, definition, part_of_speech, grade, japanese, example_sentence, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'studying')
                   ON CONFLICT(word) DO UPDATE SET
                     lookup_count = lookup_count + 1,
                     last_seen = datetime('now','localtime'),
                     definition = excluded.definition,
                     reading = excluded.reading,
                     part_of_speech = excluded.part_of_speech,
                     grade = excluded.grade,
                     japanese = excluded.japanese,
                     example_sentence = CASE WHEN excluded.example_sentence != '' THEN excluded.example_sentence ELSE vocab.example_sentence END""",
                (lookup_target, result["reading"], result["definition"], result["pos"], result.get("grade", ""), ja_json, ex),
            )
            conn.commit()
            row = conn.execute("SELECT status FROM vocab WHERE word = ?", (lookup_target,)).fetchone()
            result["status"] = (row["status"] if row else "") or ""
        except Exception as e:
            print(f"[define] DB error for '{lookup_target}': {type(e).__name__}: {e}")
            result["status"] = "studying"
        finally:
            conn.close()

    return result


# ── Vocab endpoints ────────────────────────────────────────────────────────
@app.get("/api/vocab")
def get_vocab():
    with closing_db() as conn:
        auto_graduate(conn)
        rows = conn.execute("SELECT * FROM vocab ORDER BY last_seen DESC").fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/vocab/{vid}")
def delete_vocab_entry(vid: int):
    with closing_db() as conn:
        conn.execute("DELETE FROM vocab WHERE id = ?", (vid,))
        conn.commit()
    return {"ok": True}


@app.put("/api/vocab/{vid}/status")
def set_vocab_status(vid: int, s: StatusUpdate):
    if s.status not in ("", "studying"):
        raise HTTPException(400, "status must be '' or 'studying'")
    with closing_db() as conn:
        cur = conn.execute("UPDATE vocab SET status = ? WHERE id = ?", (s.status, vid))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "Word not found")
    return {"ok": True}


@app.post("/api/vocab/mark")
def mark_vocab_by_word(m: MarkWord):
    """Set a word's status by surface form — used for inline marking while reading.
    Resolves to the dictionary form (like /api/define) and creates a bare entry
    for words that aren't in the bank yet, so confident words can be marked known
    without ever looking them up."""
    if m.status not in ("", "studying"):
        raise HTTPException(400, "status must be '' or 'studying'")
    lemma = get_lemma(m.word)
    base = lemma if lemma else m.word
    with closing_db() as conn:
        # Prefer an existing row under the surface form or its lemma
        row = conn.execute(
            "SELECT word FROM vocab WHERE word = ? OR word = ? LIMIT 1", (m.word, base)
        ).fetchone()
        target = row[0] if row else base
        if row:
            conn.execute("UPDATE vocab SET status = ? WHERE word = ?", (m.status, target))
        else:
            conn.execute(
                "INSERT INTO vocab (word, lookup_count, status) VALUES (?, 0, ?)",
                (target, m.status),
            )
        conn.commit()
    return {"ok": True, "word": target, "status": m.status}


# ── Passage coverage check ────────────────────────────────────────────────
@app.post("/api/coverage")
def check_coverage(req: CoverageRequest):
    with closing_db() as conn:
        status_by_word = {
            r[0]: (r[1] or "") for r in conn.execute("SELECT word, status FROM vocab").fetchall()
        }
    known, studying = [], []
    for word in set(req.words):
        target = word if word in status_by_word else None
        if target is None:
            lemma = get_lemma(word)
            if lemma and lemma in status_by_word:
                target = lemma
        if target is None:
            continue
        known.append(word)
        if status_by_word[target] == "studying":
            studying.append(word)
    return {"known": known, "studying": studying}


@app.post("/api/lemmatize")
def lemmatize_passage(req: PassageTextRequest):
    """Analyse a whole passage and return the dictionary form of each content word
    with its character span. Analysing the full text (not isolated tokens) gives
    Kiwi the context to disambiguate correctly — so irregulars (걷다→걸어서, 춥다→추워),
    ㄴ/ㄹ modifiers (한/할), and particle-fused nouns (학교에서→학교) all resolve to
    their base form. The frontend aligns each span to its on-screen token by offset."""
    if kiwi is None or not req.text.strip():
        return {"spans": []}
    try:
        result = kiwi.analyze(req.text)
        tokens = result[0].tokens if hasattr(result[0], "tokens") else result[0][0]
    except Exception as e:
        print(f"[kiwi] lemmatize failed: {e}")
        return {"spans": []}
    spans = [
        {"start": start, "len": end - start, "lemma": lemma}
        for lemma, start, end in _content_lemmas(tokens, req.text)
    ]
    return {"spans": spans}


@app.post("/api/passage-coverage")
def check_passage_text_coverage(req: PassageTextRequest):
    """Analyze raw Korean text and return vocab coverage stats using Kiwi."""
    import re
    with closing_db() as conn:
        vocab_set = {r[0] for r in conn.execute("SELECT word FROM vocab").fetchall()}

    if kiwi is None:
        # Rough fallback: split on non-hangul boundaries
        raw_words = re.findall(r'[가-힣]+', req.text)
        if not raw_words:
            return {"coverage": 1.0, "known": 0, "total": 0, "unknown_words": []}
        unique = list(set(raw_words))
        known = [w for w in unique if w in vocab_set]
        unknown = [w for w in unique if w not in vocab_set]
        return {"coverage": len(known) / len(unique), "known": len(known), "total": len(unique), "unknown_words": unknown[:20]}

    try:
        result = kiwi.analyze(req.text)
        tokens = result[0].tokens if hasattr(result[0], "tokens") else result[0][0]
    except Exception as e:
        print(f"[kiwi] passage-coverage analysis failed: {e}")
        return {"coverage": None, "known": 0, "total": 0, "unknown_words": [], "error": True}

    seen_lemmas: dict[str, str] = {}  # lemma -> display form
    for lemma, _s, _e in _content_lemmas(tokens, req.text):
        if lemma not in seen_lemmas:
            seen_lemmas[lemma] = lemma

    if not seen_lemmas:
        return {"coverage": 1.0, "known": 0, "total": 0, "unknown_words": []}

    known_count = sum(1 for lemma in seen_lemmas if lemma in vocab_set)
    unknown_lemmas = [display for lemma, display in seen_lemmas.items() if lemma not in vocab_set]
    total = len(seen_lemmas)
    return {
        "coverage": known_count / total,
        "known": known_count,
        "total": total,
        "unknown_words": unknown_lemmas[:20],
    }


# ── Vocab list / passage import ───────────────────────────────────────────
_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪◦]|\d+[.)])\s*")
_HANGUL_CHAR = re.compile(r"[가-힣]")
_LATIN_CHAR = re.compile(r"[A-Za-z]")


def _split_pair(line: str) -> Optional[tuple[str, str]]:
    """Split a 'korean SEP english' line into (korean, english), else None."""
    for sep in ("=", "\t", " — ", " – ", " : ", " - "):
        if sep in line:
            kr, en = line.split(sep, 1)
            if _HANGUL_CHAR.search(kr) and _LATIN_CHAR.search(en) and not _HANGUL_CHAR.search(en):
                return kr.strip(), en.strip()
    return None


def _clean_word(kr: str) -> str:
    kr = re.sub(r"\([^)]*\)", "", kr)  # drop hanja / usage notes in parens
    kr = kr.split("/")[0]              # first variant of "김밥 / 삼각김밥"
    # keep only the hangul span: "Common Usages: 음식점" -> "음식점"
    m = re.search(r"[가-힣][가-힣\s~]*[가-힣]|[가-힣]", kr)
    return m.group(0).strip() if m else ""


def _attach_example(entries: list, korean: str, full_line: str) -> bool:
    """Attach an example sentence to the most recent entry whose word it contains."""
    for e in reversed(entries[-3:]):
        w = e["word"]
        stems = [w]
        if w.endswith("다") and len(w) > 1:
            stems.append(w[:-1])
            if w.endswith("하다") and len(w) > 2:
                stems.append(w[:-2])
        if any(s and s in korean for s in stems):
            if not e["example_sentence"]:
                e["example_sentence"] = full_line
            return True
    return False


def parse_vocab_import(text: str) -> tuple[list[dict], list[str]]:
    """Parse pasted text into (vocab entries, residual Korean lines).

    Handles HTSK-style lists ("음식 = food"), example sentences under entries
    ("저는 음식을 먹었어요 = I ate food" attaches to 먹다), and plain Korean
    passage lines, which are returned as residual for lemma mining."""
    entries: list[dict] = []
    residual: list[str] = []
    for raw in text.splitlines():
        line = _BULLET_RE.sub("", raw).strip()
        if not line or not _HANGUL_CHAR.search(line):
            continue  # blank lines and pure-English headers like "Examples:"
        pair = _split_pair(line)
        if pair:
            kr, en = pair
            word = _clean_word(kr)
            if not word:
                continue
            # Short Korean side without sentence punctuation = a vocab entry;
            # anything longer is an example sentence for a previous entry
            if len(word.split()) <= 2 and not re.search(r"[.!?。]$", kr):
                entries.append({"word": word, "definition": en, "example_sentence": ""})
            else:
                _attach_example(entries, kr, line)
            continue
        if not _attach_example(entries, line, line):
            residual.append(line)
    return entries, residual


class VocabImportRequest(BaseModel):
    text: str
    lookup_missing: bool = True


@app.post("/api/vocab/import")
async def import_vocab_list(req: VocabImportRequest):
    entries, residual = parse_vocab_import(req.text)

    added, updated = [], []
    with closing_db() as conn:
        for e in entries:
            exists = conn.execute("SELECT 1 FROM vocab WHERE word = ?", (e["word"],)).fetchone()
            conn.execute(
                """INSERT INTO vocab (word, definition, example_sentence, lookup_count, status)
                   VALUES (?, ?, ?, 0, 'studying')
                   ON CONFLICT(word) DO UPDATE SET
                     status = 'studying',
                     definition = CASE WHEN vocab.definition = ''
                                       THEN excluded.definition ELSE vocab.definition END,
                     example_sentence = CASE WHEN vocab.example_sentence = '' AND excluded.example_sentence != ''
                                             THEN excluded.example_sentence ELSE vocab.example_sentence END""",
                (e["word"], e["definition"], e["example_sentence"]),
            )
            (updated if exists else added).append(e["word"])
        conn.commit()
        vocab_set = {r[0] for r in conn.execute("SELECT word FROM vocab").fetchall()}

    # Mine plain Korean lines for dictionary words not yet in the bank
    unknown: list[str] = []
    if residual:
        _, unknown = _passage_coverage_inline("\n".join(residual), vocab_set)

    defined, skipped = [], []
    if unknown and req.lookup_missing and (OLLAMA_LOOKUP_MODEL or GEMINI_API_KEY):
        conn = get_db()
        try:
            for lemma in unknown[:IMPORT_LOOKUP_CAP]:
                result = await lookup_definition(lemma)
                if result.get("not_found") or not result.get("definition"):
                    skipped.append(lemma)
                    continue
                ja_json = json.dumps(result["japanese"]) if result.get("japanese") else ""
                conn.execute(
                    """INSERT INTO vocab (word, reading, definition, part_of_speech, grade, japanese, lookup_count, status)
                       VALUES (?, ?, ?, ?, ?, ?, 0, 'studying')
                       ON CONFLICT(word) DO UPDATE SET status = 'studying'""",
                    (lemma, result["reading"], result["definition"], result["pos"],
                     result.get("grade", ""), ja_json),
                )
                conn.commit()
                defined.append(lemma)
        finally:
            conn.close()
        skipped.extend(unknown[IMPORT_LOOKUP_CAP:])
    else:
        skipped = unknown

    return {
        "pairs_added": added,
        "pairs_updated": updated,
        "defined": defined,
        "skipped": skipped,
    }


# ── Grammar lookup ────────────────────────────────────────────────────────
@app.post("/api/grammar")
async def lookup_grammar(req: GrammarRequest):
    try:
        raw = await call_llm(f"{GRAMMAR_PROMPT}\n\nPattern: {req.pattern}", temperature=0.2, max_tokens=1024, model=OLLAMA_LOOKUP_MODEL)
    except Exception as e:
        raise HTTPException(500, f"Grammar lookup failed: {e}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, f"Bad response from LLM: {raw[:200]}")
    return data


# ── Flashcard review ─────────────────────────────────────────────────────────
@app.get("/api/review/queue")
def get_review_queue():
    """Return up to 20 words due for review today (SRS-lite)."""
    with closing_db() as conn:
        rows = conn.execute(
            """SELECT id, word, reading, definition, part_of_speech, grade, japanese,
                      example_sentence, review_interval, next_review
               FROM vocab
               WHERE definition != ''
                 AND (next_review IS NULL OR next_review <= date('now'))
               ORDER BY CASE WHEN next_review IS NULL THEN 1 ELSE 0 END, next_review
               LIMIT 20"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/review/answer")
def submit_review_answer(ans: ReviewAnswer):
    """Record a review answer and schedule the next review."""
    with closing_db() as conn:
        row = conn.execute(
            "SELECT review_interval FROM vocab WHERE id = ?", (ans.word_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Word not found")
        current_interval = row["review_interval"] or 1
        if ans.correct:
            new_interval = min(current_interval * 2, 60)
        else:
            new_interval = 1
        conn.execute(
            """UPDATE vocab
               SET review_interval = ?,
                   next_review = date('now', ? || ' days')
               WHERE id = ?""",
            (new_interval, str(new_interval), ans.word_id),
        )
        if ans.correct and new_interval >= STUDYING_GRADUATE_INTERVAL:
            conn.execute("UPDATE vocab SET status = '' WHERE id = ?", (ans.word_id,))
        conn.commit()
    return {"interval": new_interval}


# ── Stats ──────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    with closing_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM vocab").fetchone()[0]
        by_day = conn.execute(
            """SELECT DATE(first_seen) as date, COUNT(*) as count
               FROM vocab GROUP BY DATE(first_seen) ORDER BY date"""
        ).fetchall()
        top_words = conn.execute(
            "SELECT word, lookup_count FROM vocab ORDER BY lookup_count DESC LIMIT 10"
        ).fetchall()
        this_week = conn.execute(
            "SELECT COUNT(*) FROM vocab WHERE first_seen >= datetime('now', '-7 days', 'localtime')"
        ).fetchone()[0]
        passage_count = conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
    return {
        "total_words": total,
        "this_week": this_week,
        "passage_count": passage_count,
        "by_day": [dict(r) for r in by_day],
        "top_words": [dict(r) for r in top_words],
    }


# ── Gemini generation ──────────────────────────────────────────────────────
@app.get("/api/gemini-models")
async def list_gemini_models():
    if not GEMINI_API_KEY:
        raise HTTPException(400, "GEMINI_API_KEY not set")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=10.0,
        )
    resp.raise_for_status()
    models = resp.json().get("models", [])
    names = [m["name"] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
    return {"models": names}


@app.post("/api/generate")
async def generate_passage(req: GenerateRequest):
    if not OLLAMA_MODEL and not GEMINI_API_KEY:
        raise HTTPException(400, "Set OLLAMA_MODEL or GEMINI_API_KEY in your .env file")

    level_map = {
        "beginner": (
            "초급 (Beginner): Very simple sentences only. Common everyday vocabulary "
            "(food, school, family, greetings, weather). Basic particles (이/가, 을/를, 은/는, 에, 에서). "
            "Present tense only. Short sentences."
        ),
        "intermediate": (
            "중급 (Intermediate): Mix of simple and compound sentences. Varied vocabulary. "
            "Past, present, and future tenses. Connective endings like -아서/어서, -지만, -는데, -려고."
        ),
        "advanced": (
            "고급 (Advanced): Complex grammar, idiomatic expressions, varied speech levels, "
            "subordinate clauses, nuanced vocabulary."
        ),
    }
    register_map = {
        "formal": (
            "합쇼체/합니다체 (formal). "
            "EVERY sentence must end in: 합니다 / 입니다 / 하십시오 / 습니까 / 겠습니다. "
            "FORBIDDEN endings: -해요, -아요, -어요, -야, -어, -아."
        ),
        "polite": (
            "해요체 (polite). "
            "EVERY sentence must end in: -해요 / -아요 / -어요 / -예요 / -이에요 / -죠. "
            "FORBIDDEN endings: -합니다, -입니다, -야, -어, -아 (bare stem)."
        ),
        "casual": (
            "반말/해체 (casual). This is the speech used between close friends and romantic partners. "
            "EVERY sentence must end in the bare casual form: -아 / -어 / -해 / -야 / -지 / -거든 / -잖아 / -네 / -걸 / -는데. "
            "Past tense: -았어 / -었어 (NOT -았어요 / -었어요). "
            "STRICTLY FORBIDDEN: -해요, -아요, -어요, -예요, -이에요, -합니다, -입니다. "
            "Examples of correct casual endings: 먹었어, 갔어, 좋아, 재미있어, 그래, 알겠어, 할게, 보자."
        ),
        "mixed": (
            "해요체 for narration; 반말 for all dialogue. "
            "Narration ends in -해요/-아요/-어요. "
            "All quoted speech ends in bare casual -아/-어/-해/-야."
        ),
    }
    register_desc = register_map.get(req.register, register_map["polite"])

    level_desc = level_map.get(req.level, level_map["intermediate"])
    spec_lines = [f"Level: {level_desc}"]
    if req.topic:
        spec_lines.append(f"Topic: {req.topic}")
    if req.grammar_focus:
        spec_lines.append(f"Grammar focus: naturally weave in usage of {req.grammar_focus}")

    vocab_set: set[str] = set()
    vocab_block = ""
    if req.use_vocab:
        with closing_db() as conn:
            words = [r[0] for r in conn.execute("SELECT word FROM vocab ORDER BY lookup_count DESC").fetchall()]
        vocab_set = set(words)
        if words:
            word_list = ", ".join(words)
            vocab_block = (
                f"\n\nThe learner already knows these {len(words)} Korean words "
                f"(given in dictionary form — use natural conjugations in the passage):\n"
                f"{word_list}\n\n"
                "Coverage rule: at least 95% of content words must come from that list. "
                "You may introduce 3–6 new words the learner hasn't seen — "
                "these will be their learning targets for this passage."
            )

    # Register constraint is stated at the top and repeated at the bottom so small models don't forget it
    register_rule = f"SPEECH REGISTER — {register_desc}"

    base_prompt = (
        "LANGUAGE: 한국어로만 작성하세요. Write ONLY in Korean (한국어). "
        "Do NOT use Chinese characters, Chinese language, or Japanese. Korean only.\n\n"
        f"{register_rule}\n\n"
        "Write a Korean language learning passage with these specifications:\n\n"
        + "\n".join(spec_lines)
        + vocab_block
        + "\n\nLength: 3-5 short paragraphs\n\n"
        "Rules:\n"
        "- Output ONLY the Korean passage — no title, no English, no romanization, no explanations\n"
        "- Natural, authentic Korean for the specified level\n"
        "- Culturally relevant and interesting\n"
        "- End with a complete sentence\n"
        f"- CRITICAL: {register_rule}\n"
        "- CRITICAL: 반드시 한국어로만 작성하세요. Korean only — no Chinese, no Japanese."
    )

    COVERAGE_THRESHOLD = 0.82
    MAX_RETRIES = 2  # up to 3 total attempts

    async def ollama_stream(content: str, buf: list | None = None):
        """Yield SSE chunks from Ollama. If buf is a list, also collect tokens into it."""
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": content}],
            "stream": True,
            "options": {"temperature": 0.85, "num_predict": 1024},
        }
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", OLLAMA_URL, json=payload, timeout=120.0) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        if buf is not None:
                            buf.append(chunk)
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    if data.get("done"):
                        break

    async def stream():
        current_prompt = base_prompt
        draft = ""

        for attempt in range(MAX_RETRIES + 1):
            draft_buf: list[str] = []
            try:
                if OLLAMA_MODEL:
                    # Stream tokens so the user sees progress; also collect for coverage check
                    async for event in ollama_stream(current_prompt, buf=draft_buf):
                        yield event
                    draft = "".join(draft_buf)
                else:
                    # Batch: hold output until coverage is confirmed
                    draft = await call_llm(current_prompt, temperature=0.85, max_tokens=1024)
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            # Coverage check — retry if below threshold and attempts remain
            if req.use_vocab and vocab_set and attempt < MAX_RETRIES and draft:
                cov, unknown = _passage_coverage_inline(draft, vocab_set)
                if cov < COVERAGE_THRESHOLD:
                    unknown_str = ", ".join(unknown[:20])
                    yield f"data: {json.dumps({'status': 'retry', 'attempt': attempt + 2, 'coverage': round(cov * 100)})}\n\n"
                    current_prompt = (
                        base_prompt
                        + f"\n\nYour previous attempt used these words the learner does NOT know: {unknown_str}. "
                        "Do NOT use any of these words. Strictly reuse only vocabulary from the learner's list above.\n"
                        "IMPORTANT: 한국어로만 작성하세요. Write ONLY in Korean. Do NOT use Chinese or Japanese."
                    )
                    continue  # try again

            # Coverage acceptable (or last attempt, or vocab check disabled)
            if not OLLAMA_MODEL:
                yield f"data: {json.dumps({'chunk': draft})}\n\n"
            break

        # Optional naturalness refine pass
        if req.refine and draft:
            yield f"data: {json.dumps({'status': 'refining'})}\n\n"
            try:
                if OLLAMA_MODEL:
                    async for event in ollama_stream(REFINE_PROMPT.format(draft=draft)):
                        yield event
                else:
                    refined = await call_llm(
                        REFINE_PROMPT.format(draft=draft), temperature=0.4, max_tokens=1024
                    )
                    yield f"data: {json.dumps({'chunk': refined})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Static / root ──────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")
