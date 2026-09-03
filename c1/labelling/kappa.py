"""Cohen's kappa for two labellers' independent judgments on the same
labelling-pilot batch, plus a printout of exactly what they disagreed on -
per docs/labelling_protocol.md, a disagreement is something to diagnose
(usually the protocol was ambiguous for that item), not average away.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from c1.labelling.generate import BATCH_DIR


def load_labels(labeler_name: str) -> dict[str, str | None]:
    path = BATCH_DIR / f"labels_{labeler_name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def cohen_kappa(labels_a: dict[str, str | None], labels_b: dict[str, str | None]) -> float:
    """Corrects observed agreement for the agreement expected by chance
    given each labeller's own label distribution - raw percent-agreement
    can look deceptively high if one label (e.g. WRONG) just dominates both
    labellers' answers regardless of whether they're really tracking the
    same judgment.
    """
    common_ids = set(labels_a) & set(labels_b)
    pairs = [
        (labels_a[i], labels_b[i])
        for i in common_ids
        if labels_a[i] is not None and labels_b[i] is not None
    ]
    n = len(pairs)
    if n == 0:
        raise ValueError("no items have been labelled by both labellers yet")

    observed_agreement = sum(1 for a, b in pairs if a == b) / n

    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    categories = set(count_a) | set(count_b)
    expected_agreement = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)

    if expected_agreement >= 1.0:
        return 1.0  # both labellers used exactly one, identical category - no room for chance disagreement
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def print_disagreements(labels_a: dict[str, str | None], labels_b: dict[str, str | None]) -> None:
    common_ids = sorted(set(labels_a) & set(labels_b))
    disagreements = [
        i for i in common_ids
        if labels_a[i] is not None and labels_b[i] is not None and labels_a[i] != labels_b[i]
    ]
    if not disagreements:
        print("no disagreements on the items labelled by both")
        return
    print(f"{len(disagreements)} disagreement(s):")
    for item_id in disagreements:
        print(f"  {item_id}: a={labels_a[item_id]!r} b={labels_b[item_id]!r}")


def main(labeler_a: str, labeler_b: str) -> None:
    labels_a = load_labels(labeler_a)
    labels_b = load_labels(labeler_b)
    kappa = cohen_kappa(labels_a, labels_b)
    print(f"Cohen's kappa ({labeler_a} vs {labeler_b}): {kappa:.3f}")
    print_disagreements(labels_a, labels_b)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m c1.labelling.kappa <labeler_a> <labeler_b>")
    main(sys.argv[1], sys.argv[2])
