"""Record raw krdict XML for the offline tests (tests/fixtures/krdict/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import KRDICT_API_KEY  # noqa: E402
from app.krdict.cache import KrdictCache  # noqa: E402
from app.krdict.client import KrdictClient  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "krdict"
WORDS = sys.argv[1:] or ["시간", "있다", "돌보다", "설레다", "공부하다", "말씀드리다", "없는단어"]

cache = KrdictCache(":memory:")
client = KrdictClient(KRDICT_API_KEY, cache)
for w in WORDS:
    client.search(w)
    (OUT / f"{w}.xml").write_text(cache.get(w), encoding="utf-8")
    print(w, [(e.word, e.pos, e.sup_no, e.origin, e.gloss_en, e.gloss_ja) for e in client.search(w)])
