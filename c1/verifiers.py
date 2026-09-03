"""V0 verifier: 3 public tests only (plan.md §2's "weak - special-casing
trivially passes" condition).

SANDBOXING CAVEAT - read before pointing this at anything but a trusted
editorial solution: `make_v0_grader` runs candidate code as a real Python
subprocess with no filesystem/network isolation, just a wall-clock timeout.
That's an acceptable minimum for smoke-testing against HardTests' own
editorial solutions (curated, not adversarial) on this Windows box, which has
no container runtime available right now (docs/LEARNING_LOG.md). It is NOT
safe to run against model-generated or hacker-generated candidates - those
need a real sandbox (Docker/bwrap), same as harden-v0 and HardTestGen's own
pipeline both require. Don't reuse this for V3 or for grading real rollouts
without swapping in a sandboxed executor first.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(lines)


def _to_lf(text: str) -> str:
    """Collapse to bare \\n line endings before handing input to a subprocess.

    HardTests' public_test_cases ship with literal "\\r\\n" inside the input
    string. Python's text-mode subprocess pipes apply universal-newline
    translation on write, which turns each "\\n" into os.linesep - on Windows
    that means the existing "\\r\\n" becomes "\\r\\r\\n", which the child's own
    text-mode *read* side then collapses into two newlines instead of one,
    inserting a phantom blank line and shifting every input() call after it.
    Confirmed by hand: a 2-line test input silently became "line 1" + "" on
    the child's second input() call. Normalizing to bare \\n before the pipe
    write sidesteps the round-trip translation entirely.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _run_script(code: str, stdin_text: str, timeout_s: float) -> str | None:
    """Run `code` as a real Python subprocess with `stdin_text` on stdin,
    return stdout, or None on a non-zero exit or timeout.

    Written to a temp file rather than passed via `-c`: a long enough
    candidate's source blew the Windows command-line length limit
    (CreateProcess -> WinError 206, "filename or extension too long")
    partway through a 150-problem run - not a rare pathological input, a real
    editorial solution. `-c` puts the whole program on the command line; a
    temp file has no such size ceiling. See this module's docstring for the
    sandboxing caveat - shared by every caller of this function.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script_path = f.name
    try:
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return None
        return result.stdout if result.returncode == 0 else None
    finally:
        Path(script_path).unlink(missing_ok=True)


def make_grader_from_tests(tests: list[dict], timeout_s: float = 5.0):
    """Build a Grader (candidate: str) -> float in [0, 1] from a flat list of
    {"input": ..., "output": ...} pairs, graded by exact string match. Reward
    is the fraction passed - matches envcheck.core.types.Grader's signature
    so this can be wrapped in an envcheck Task later if useful (plan.md §1a).
    V0 and V1 differ only in which test list they pass in here - same
    execution/grading mechanics. V2 needs a different grader (see
    make_v2_grader) since some of its problems require a custom checker
    instead of exact match - see this module's "Concepts" cross-reference in
    docs/LEARNING_LOG.md.
    """

    def grade(candidate_code: str) -> float:
        if not tests:
            return 0.0
        passed = 0
        for test in tests:
            stdout = _run_script(candidate_code, _to_lf(test["input"]), timeout_s)
            if stdout is not None and _normalize(stdout) == _normalize(test["output"]):
                passed += 1
        return passed / len(tests)

    return grade


def make_v0_grader(problem: dict, timeout_s: float = 5.0):
    """V0: the problem's public_test_cases only (plan.md §2's "3 public tests,
    special-casing trivially passes" condition)."""
    return make_grader_from_tests(problem.get("public_test_cases") or [], timeout_s)


def make_v1_grader(codecontests_row: dict, timeout_s: float = 5.0):
    """V1: the problem's original test suite - deepmind/code_contests'
    public_tests + private_tests for the matched Codeforces problem (see
    c1/codeforces.py for the match). Deliberately excludes generated_tests:
    those are CodeContests' own synthetic additions, not part of what the
    original Codeforces judge actually ran - see docs/LEARNING_LOG.md's "V1
    isn't a free lookup" entry for why this distinction matters.
    """
    pub = codecontests_row.get("public_tests") or {"input": [], "output": []}
    priv = codecontests_row.get("private_tests") or {"input": [], "output": []}
    tests = [
        {"input": i, "output": o}
        for i, o in zip(pub["input"] + priv["input"], pub["output"] + priv["output"])
    ]
    return make_grader_from_tests(tests, timeout_s)


_JUDGE_RUNNER_TEMPLATE = """
import json, sys
{judge_code}
input_str, candidate_output, reference_output = json.loads(sys.stdin.read())
print("PASS" if output_judging_function(input_str, candidate_output, reference_output) else "FAIL")
"""


def make_v2_grader(hardtests_tests_row: dict, timeout_s: float = 5.0):
    """V2: HardTests-generated tests (plan.md §2, "HackGen included") - the
    problem's decoded test_cases from sigcp/hardtests_tests (see
    c1/hardtests_tests.py's decode_testcases), covering all four generator
    strategies (LLMGen/RPGen/SPGen/HackGen), not just HackGen's adversarial
    subset - HackGen is what makes V2 *hardened* relative to V0/V1, but the
    grader itself runs every generated case, same as V0/V1 run every case in
    their own lists.

    Unlike V0/V1, grading isn't always exact-match: test_cases_kit's
    output_judging_function is None for many problems (plain exact match
    applies then) but real code for others - confirmed empirically
    (docs/LEARNING_LOG.md) with signature
    `output_judging_function(input_str, candidate_output, reference_output) -> bool`.
    When present, it's executed as its own subprocess (same sandboxing
    caveat as the candidate - this module's docstring - applies to it too:
    it's LLM-generated code from the dataset, not hand-vetted).
    """
    tests = hardtests_tests_row.get("_decoded_test_cases") or []
    ojf_code = hardtests_tests_row["test_cases_kit"].get("output_judging_function")

    def judge(input_str: str, candidate_output: str, reference_output: str) -> bool:
        if ojf_code is None:
            return _normalize(candidate_output) == _normalize(reference_output)
        runner = _JUDGE_RUNNER_TEMPLATE.format(judge_code=ojf_code)
        stdin_payload = json.dumps([input_str, candidate_output, reference_output])
        stdout = _run_script(runner, stdin_payload, timeout_s)
        return stdout is not None and stdout.strip() == "PASS"

    def grade(candidate_code: str) -> float:
        if not tests:
            return 0.0
        passed = 0
        for test in tests:
            stdout = _run_script(candidate_code, _to_lf(test["input"]), timeout_s)
            if stdout is not None and judge(test["input"], stdout, test["output"]):
                passed += 1
        return passed / len(tests)

    return grade
