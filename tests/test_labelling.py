import json
from unittest.mock import patch

import pytest

from c1.labelling import generate, kappa


def _sample_pool():
    return [
        {
            "hardtests": {"pid": "p1", "question_content": "Compute a+b."},
            "validated_solution": "print(sum(map(int, input().split())))",
        },
        {
            "hardtests": {"pid": "p2", "question_content": "Reverse a string."},
            "validated_solution": "print(input()[::-1])",
        },
    ]


def test_build_labelling_batch_writes_items_and_hidden_answer_key(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "BATCH_FILE", tmp_path / "batch.json")
    monkeypatch.setattr(generate, "ANSWER_KEY_FILE", tmp_path / "answer_key.json")
    monkeypatch.setattr(generate.time, "sleep", lambda _seconds: None)  # skip the real inter-call pacing delay

    with patch.object(generate, "run_solver_ensemble", return_value={"groq/x": "print('solved')"}):
        generate.build_labelling_batch(_sample_pool(), solver_model="groq/x")

    items = json.loads((tmp_path / "batch.json").read_text())
    answer_key = json.loads((tmp_path / "answer_key.json").read_text())

    # labeller-facing items must never reveal source, per docs/labelling_protocol.md
    for item in items:
        assert set(item) == {"item_id", "instructions", "candidate"}

    assert set(answer_key) == {item["item_id"] for item in items}
    assert {v["source"] for v in answer_key.values()} <= {"E1", "E5", "solver_ensemble"}
    solver_items = [k for k, v in answer_key.items() if v["source"] == "solver_ensemble"]
    assert len(solver_items) == 2  # one per pool problem


def test_build_labelling_batch_skips_a_failed_solver_call(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "BATCH_FILE", tmp_path / "batch.json")
    monkeypatch.setattr(generate, "ANSWER_KEY_FILE", tmp_path / "answer_key.json")
    monkeypatch.setattr(generate.time, "sleep", lambda _seconds: None)

    with patch.object(generate, "run_solver_ensemble", return_value={"groq/x": ""}):
        generate.build_labelling_batch(_sample_pool(), solver_model="groq/x")

    answer_key = json.loads((tmp_path / "answer_key.json").read_text())
    assert all(v["source"] != "solver_ensemble" for v in answer_key.values())


def test_make_labels_template_maps_every_item_to_null(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "BATCH_DIR", tmp_path)
    monkeypatch.setattr(generate, "BATCH_FILE", tmp_path / "batch.json")
    (tmp_path / "batch.json").write_text(json.dumps([{"item_id": "a"}, {"item_id": "b"}]))

    path = generate.make_labels_template("tester")

    assert json.loads(path.read_text()) == {"a": None, "b": None}


def test_make_labels_template_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "BATCH_DIR", tmp_path)
    monkeypatch.setattr(generate, "BATCH_FILE", tmp_path / "batch.json")
    (tmp_path / "batch.json").write_text(json.dumps([{"item_id": "a"}]))
    (tmp_path / "labels_tester.json").write_text("{}")

    with pytest.raises(FileExistsError):
        generate.make_labels_template("tester")


def test_kappa_is_one_for_perfect_agreement_with_mixed_categories():
    a = {"1": "CORRECT", "2": "WRONG", "3": "CORRECT", "4": "WRONG"}
    b = {"1": "CORRECT", "2": "WRONG", "3": "CORRECT", "4": "WRONG"}
    assert kappa.cohen_kappa(a, b) == pytest.approx(1.0)


def test_kappa_is_one_when_both_always_pick_the_same_single_category():
    a = {"1": "CORRECT", "2": "CORRECT"}
    b = {"1": "CORRECT", "2": "CORRECT"}
    assert kappa.cohen_kappa(a, b) == pytest.approx(1.0)


def test_kappa_matches_hand_computed_partial_agreement():
    a = {"1": "CORRECT", "2": "CORRECT", "3": "CORRECT", "4": "WRONG", "5": "WRONG", "6": "CORRECT", "7": "WRONG"}
    b = {"1": "CORRECT", "2": "CORRECT", "3": "CORRECT", "4": "WRONG", "5": "WRONG", "6": "WRONG", "7": "CORRECT"}
    # observed = 5/7 agree; a: CORRECT=4/7,WRONG=3/7; b: CORRECT=4/7,WRONG=3/7
    # expected = (4/7)^2 + (3/7)^2 = 25/49
    observed, expected = 5 / 7, 25 / 49
    want = (observed - expected) / (1 - expected)
    assert kappa.cohen_kappa(a, b) == pytest.approx(want)


def test_kappa_ignores_unlabelled_items():
    a = {"1": "CORRECT", "2": None}
    b = {"1": "CORRECT", "2": "WRONG"}
    assert kappa.cohen_kappa(a, b) == pytest.approx(1.0)  # only item "1" counted, both agree


def test_kappa_raises_when_nothing_overlaps():
    with pytest.raises(ValueError):
        kappa.cohen_kappa({"1": None}, {"1": None})


def test_print_disagreements_reports_only_mismatches(capsys):
    a = {"1": "CORRECT", "2": "WRONG"}
    b = {"1": "CORRECT", "2": "CORRECT"}

    kappa.print_disagreements(a, b)

    out = capsys.readouterr().out
    assert "1 disagreement" in out
    assert "2: a='WRONG' b='CORRECT'" in out
