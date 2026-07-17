"""Load route sheets (job cards) from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from known_path.fixtures import demo_job_card
from known_path.models import JobCard


def load_card(path: Path | str) -> JobCard:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return JobCard.from_dict(data)


def load_card_or_demo(path: Path | str | None = None) -> JobCard:
    if path is None:
        return demo_job_card()
    p = Path(path)
    if not p.exists():
        return demo_job_card()
    return load_card(p)


def match_card_for_intent(intent: str, cards: list[JobCard]) -> JobCard | None:
    intent_l = intent.lower()
    best: JobCard | None = None
    best_hits = 0
    for card in cards:
        corpus = " ".join([card.id] + card.intent_examples).lower()
        hits = sum(1 for tok in intent_l.split() if len(tok) > 2 and tok in corpus)
        if hits > best_hits:
            best_hits = hits
            best = card
    if best_hits == 0 and cards:
        # default first demo card if intent mentions revenue/region/finance
        keys = ("revenue", "region", "omzet", "finance", "quarter")
        if any(k in intent_l for k in keys):
            return cards[0]
        return None
    return best
