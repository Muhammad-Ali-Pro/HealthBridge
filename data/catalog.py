"""Small curated, synthetic drug catalog used for name normalisation and rule-based checks."""

import json
from functools import lru_cache

from core.config import DATA_DIR


@lru_cache(maxsize=1)
def load_drug_catalog() -> list[dict]:
    with open(DATA_DIR / "drugs.json", encoding="utf-8") as f:
        return json.load(f)


def drug_names() -> list[str]:
    return [d["name"] for d in load_drug_catalog()]
