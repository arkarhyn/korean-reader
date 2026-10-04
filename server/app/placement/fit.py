"""Placement model (pure functions; DB access lives in service.py).

Vocab: P(known | lexeme) = sigmoid(a + b * (log rank - log 1000)), fitted by
penalised maximum likelihood over
  - yes/no answers on real words, corrected for guessing:
    P(yes | real) = p + (1 - p) * fa, fa = pseudoword false-alarm rate;
  - calibration passages: an untapped lexeme is known, a tapped one unknown.
Grammar: count of "got it" per point -> solid / practicing / new.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

RANK_CENTER = math.log(1000)
PRIOR_SD = 3.0  # weak Gaussian prior on (a, b): keeps the fit finite under perfect separation
# 0.5 under-counted unknowns by ~3.6 pp in simulation (many words sit just above 0.5); 0.6 is ~unbiased.
KNOWN_THRESHOLD = 0.6


@dataclass(frozen=True)
class VocabParams:
    a: float
    b: float
    fa: float  # false-alarm rate on pseudowords

    def p_known(self, rank: float) -> float:
        return float(_sigmoid(self.a + self.b * (math.log(rank) - RANK_CENTER)))

    def rank_at(self, p: float) -> float:
        """Rank where P(known) == p (the model's 'vocabulary edge')."""
        if self.b >= 0:
            return math.inf
        return math.exp((math.log(p / (1 - p)) - self.a) / self.b + RANK_CENTER)


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def false_alarm_rate(pseudo_yes: int, pseudo_total: int) -> float:
    """Laplace-smoothed share of pseudowords claimed as known."""
    return (pseudo_yes + 1) / (pseudo_total + 2)


def _log_posterior(yes_no: Iterable[tuple[float, bool]], observed: Iterable[tuple[float, bool]], fa: float):
    """Unnormalised log posterior over (a, b); a and b broadcast over a grid."""
    yn, ob = list(yes_no), list(observed)
    xy = np.array([math.log(r) - RANK_CENTER for r, _ in yn])
    y = np.array([float(v) for _, v in yn])
    xo = np.array([math.log(r) - RANK_CENTER for r, _ in ob])
    o = np.array([float(v) for _, v in ob])

    def logpost(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        total = -(a ** 2 + b ** 2) / (2 * PRIOR_SD ** 2)
        if len(xy):
            p = _sigmoid(a[..., None] + b[..., None] * xy)
            p_yes = np.clip(p + (1 - p) * fa, 1e-9, 1 - 1e-9)
            total = total + (y * np.log(p_yes) + (1 - y) * np.log(1 - p_yes)).sum(-1)
        if len(xo):
            p = np.clip(_sigmoid(a[..., None] + b[..., None] * xo), 1e-9, 1 - 1e-9)
            total = total + (o * np.log(p) + (1 - o) * np.log(1 - p)).sum(-1)
        return total

    return logpost


def fit_vocab(yes_no: Iterable[tuple[float, bool]], observed: Iterable[tuple[float, bool]],
              fa: float) -> VocabParams:
    """MAP (a, b). yes_no: (rank, answered yes) for real test words; observed: (rank, known) from calibration."""
    logpost = _log_posterior(yes_no, observed, fa)
    # Coarse grid, then two refinements around the best cell.
    ca, cb, ha, hb = 0.0, -1.0, 12.0, 6.0
    for _ in range(3):
        A, B = np.meshgrid(np.linspace(ca - ha, ca + ha, 121), np.linspace(cb - hb, cb + hb, 121), indexing="ij")
        ll = logpost(A, B)
        i, j = np.unravel_index(np.argmax(ll), ll.shape)
        ca, cb = float(A[i, j]), float(B[i, j])
        ha, hb = ha / 12, hb / 12
    return VocabParams(a=ca, b=cb, fa=fa)


def posterior_draws(yes_no: Iterable[tuple[float, bool]], observed: Iterable[tuple[float, bool]],
                    map_params: VocabParams, n: int = 200, seed: int = 0) -> list[VocabParams]:
    """(a, b) samples from the grid posterior around the MAP, for predictive intervals."""
    logpost = _log_posterior(yes_no, observed, map_params.fa)
    A, B = np.meshgrid(np.linspace(map_params.a - 4, map_params.a + 4, 81),
                       np.linspace(map_params.b - 2, map_params.b + 2, 81), indexing="ij")
    lp = logpost(A, B).ravel()
    w = np.exp(lp - lp.max())
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(w), size=n, p=w / w.sum())
    return [VocabParams(float(A.ravel()[k]), float(B.ravel()[k]), map_params.fa) for k in idx]


def posterior_known_given_yes(p: float, fa: float) -> float:
    return p / (p + (1 - p) * fa) if p > 0 else 0.0


def grammar_state(got_it: int, total: int) -> str:
    """Austin's mapping (2026-10-03): all got -> solid, none -> new, else practicing."""
    if total and got_it >= total:
        return "solid"
    return "new" if got_it == 0 else "practicing"


def lexeme_states(params: VocabParams, ranks: Mapping[int, float], yes_no: Mapping[int, bool],
                  calibration: Mapping[int, bool]) -> dict[int, str]:
    """Target placement state per lexeme id; lexemes absent from the result get no state.

    Direct evidence wins: calibration (untapped -> known, tapped -> seen), then the yes/no
    test (yes -> known if the guessing-corrected posterior >= threshold; no -> no state),
    then the model for every ranked lexeme.
    """
    out: dict[int, str] = {}
    for lex_id, rank in ranks.items():
        if params.p_known(rank) >= KNOWN_THRESHOLD:
            out[lex_id] = "known"
    for lex_id, yes in yes_no.items():
        p = params.p_known(ranks[lex_id]) if lex_id in ranks else 0.5
        if yes and posterior_known_given_yes(p, params.fa) >= KNOWN_THRESHOLD:
            out[lex_id] = "known"
        else:
            out.pop(lex_id, None)
    for lex_id, known in calibration.items():
        out[lex_id] = "known" if known else "seen"
    return out


def unknown_rate_interval(p_known_draws: Sequence[Mapping[int, float]], token_lex_ids: list[int],
                          level: float = 0.95, sims: int = 4000, seed: int = 0) -> tuple[float, float]:
    """Predictive interval for a passage's tapped-token rate. Each simulation picks one posterior
    draw of P(known) per lexeme, then each distinct lexeme is unknown with probability 1 - p
    (all its occurrences together)."""
    ids = sorted(set(token_lex_ids))
    counts = np.array([token_lex_ids.count(i) for i in ids], dtype=float)
    P = np.array([[d[i] for i in ids] for d in p_known_draws])
    rng = np.random.default_rng(seed)
    rows = rng.integers(len(P), size=sims)
    unknown = rng.random((sims, len(ids))) >= P[rows]
    rates = (unknown * counts).sum(axis=1) / counts.sum()
    tail = (1 - level) / 2
    return float(np.quantile(rates, tail)), float(np.quantile(rates, 1 - tail))
