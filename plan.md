# envcheck — Execution Plan

*A QC gate for RL environments + the public benchmark that makes "environment trust" a number.*

Working names: tool = `envcheck`, benchmark = `EnvTrust-Bench`.
Owner: Blitz. Machine: RTX 4050 (6 GB) + API credits. Window: ~16 weeks.

Revision note: this version folds in a week-0 critique session (conflict of
interest in the adoption story, labelling-protocol rigor, single-score
Goodharting, difficulty/diversity false-positive risk, explicit scope-cut
order, and a firmer publication target). Changes are inline, not a separate
changelog — treat this file as the current plan, not a history of it.

---

## 0. Goal (set this correctly or the whole plan drifts)

**Primary outcome:** a cited benchmark + an adopted open-source tool + a main-track or D&B paper.
**Secondary outcome:** pilot users at 2–3 environment vendors / post-training shops.
**Explicitly NOT the goal:** revenue by week 16. If revenue happens, great; don't optimize for it.

Definition of done at week 16:
- `pip install envcheck` works on any `verifiers`-format environment and emits a Trust Score + per-task verdict.
- EnvTrust-Bench v0.1 public: ≥6 environments, ≥600 audited tasks, human-labelled ground truth for ≥200, with a stated inter-rater agreement score for those labels (see §5a).
- One paper draft submitted to the primary target (see §6, Phase 4).
- ≥3 external teams have run the tool on their own environments.

---

## 1. Positioning (one paragraph, memorize it)

Environment supply is going from hundreds of hand-built tasks to millions of synthesized ones. Published audits show 25–60% of tasks in the best-known code environments accept wrong solutions. Vendors grade themselves; labs audit internally and don't share. envcheck is the independent, automated measurement layer: run it before training, get a per-task verdict and a trust score, and stop paying training compute to learn the wrong thing. The differentiator vs. prior work: cross-domain (code + tool-use + rubric-graded), multi-axis (hackability, validity, judge-bias, difficulty, diversity), and shipped as a CI gate, not a paper appendix.

**Be honest with yourself about what part of this is actually new.** The code-hackability headline number is a replication of prior work (2606.16062), not a novel finding — it's infrastructure and a sanity check that your pipeline works, not the paper's contribution. The actual new empirical claim has to come from Phase 2 (cross-domain judge-bias + difficulty + diversity, measured together, with human-verified ground truth). Don't let replication eat the calendar that the real contribution needs.

---

## 2. Required reading (week 1, in this order)

1. Auditing Reward Hackability in Code RL Training Environments — arXiv 2606.16062. **Replicate first, then extend.** Note its EQS definition, KEEP/FIX/DROP verdict, gold-sanity gate. (Real numbers to anchor on: 28.5% of a 49-task SWE-bench Verified sample had test suites weak enough that a Docker-verified wrong patch still passed; 25.0% on a 20-task R2E-Gym sample; models score +14.14pp higher on flagged-hackable tasks than robust ones of the same difficulty, 95% CI [+11.80, +16.48].)
2. Reproducing, Analyzing, and Detecting Reward Hacking in Rubric-Based RL — arXiv 2606.04923 (CHERRL). Source of judge-bias probe ideas: injects known biases into an LLM judge to study how *discoverable* and *exploitable* each one is.
3. LLMs Gaming Verifiers: RLVR can Lead to Reward Hacking — arXiv 2604.15149.
4. Can RL Improve Generalization of LLM Agents? — arXiv 2603.12011. The transfer counter-evidence.
5. EnterpriseBench Corecraft (Surge AI) — arXiv 2602.16179. The vendor's self-reported transfer claim; also a candidate environment if accessible.
6. Agent World Model — arXiv 2602.10090 (§6.1: quality/difficulty/diversity axes for synthesized envs).
7. AutoForge — arXiv 2512.22857; Endless Terminals — arXiv 2601.16443 (the synthesis pipelines you're the gate for).
8. Reward Hacking Benchmark (tool-use) — arXiv 2605.02964.
9. τ-bench — arXiv 2406.12045 (pass^k, and a target environment).
10. Prime Intellect `verifiers` docs + Environments Hub. This is your integration surface.
11. **New: the software-engineering literature on test oracle quality and mutation testing.** This field has studied "does this test suite actually catch wrong code" for 20+ years under different names. `hackability`'s code exploits (E1/E2/E5) are a restatement of mutation testing. Read at least one mutation-testing survey and one test-oracle-quality paper before writing `probes/hackability.py` — this also opens ICSE/FSE as a legitimate venue (see §6, Phase 4), and its absence from a prior draft of this plan was a visible gap.

Skim: MAST (arXiv 2503.13657) for failure taxonomies; OpenAI's Feb 2026 SWE-bench Verified flawed-tests note.

---

## 3. Architecture

```
envcheck/
  core/            # shared Task / Evidence / Verdict data model
  adapters/        # verifiers-format first; tau-bench, SWE-Gym/R2E-Gym, custom-JSON later
  probes/
    gold_sanity.py     # gold passes; null fails; random-wrong fails
    hackability.py     # LLM adversary + exploit library -> wrong solutions that pass
    judge_bias.py      # paired-perturbation probes for LLM/rubric graders
    difficulty.py      # 3-tier model sweep; trivial / impossible flags
    diversity.py       # near-dup + template-collapse detection
  exploits/        # versioned exploit strategy pack (YAML + generators)
  scoring/         # Environment Trust Score, per-task KEEP/FIX/DROP
  report/          # JSON + HTML report; CI exit codes (--fail-under)
  repair/          # v1.0: propose blocking tests / rubric patches, re-verify
  cli.py
bench/             # EnvTrust-Bench: env manifests, ground-truth labels, leaderboard scripts
paper/
```

Design rules:
- Every probe is independent and returns (task_id, verdict, evidence). Score aggregation is separate.
- Exploit pack is versioned separately from the CLI (same pattern as the MCP scanner's rule pack).
- Every claim in a report carries the attack budget used (K candidates, model, temperature). The score is probabilistic; say so.
- Adversary model is pluggable: default to a cheap open model via API; frontier model optional.
- **The per-axis leaderboard columns (hackability rate, judge-bias sensitivity, trivial %, impossible %, near-dup %, gold-gate failures) are the primary artifact, not the single Trust Score.** Collapsing five different kinds of evidence into one scalar invites exactly the Goodharting this tool exists to catch — a vendor could patch the known exploit pack without becoming genuinely more robust, and still post a high single score. The Trust Score ships as a convenience summary with a stated limitation in every report and in the paper; never lead marketing or the leaderboard's default view with it alone.
- **Difficulty and diversity verdicts get less benefit of the doubt than hackability/gold-gate verdicts.** A task flagged "impossible" by a 3-tier model sweep may just mean none of the three models had the right domain knowledge, not that the task is broken; a false "impossible" or "near-duplicate" flag published against a legitimate, hard task is a credibility hit in exactly the community you need to win over. A DROP verdict driven solely by difficulty or diversity evidence requires human review before it ships in a public report; hackability- and gold-gate-driven DROPs do not need this (they have direct, mechanical evidence: a specific wrong solution passed, or the gold solution failed).

---

## 4. Exploit library v0 (write these by hand first)

Code environments:
- E1 test special-casing (hardcode expected outputs for visible tests)
- E2 assertion removal / test file mutation
- E3 monkey-patching the grader / import hooks
- E4 early exit with success code
- E5 partial implementation that passes weak tests

Tool-use / agent environments:
- E6 claim completion without side effects ("resolved" text, no state change)
- E7 minimal-action shortcuts that satisfy a state check but violate policy
- E8 over-asking / stalling that a lenient grader marks as safe

Rubric / LLM-judged environments:
- E9 rubric parroting (restate criteria verbatim)
- E10 length padding / over-explanation
- E11 confident hedging (cover all answers)
- E12 sycophantic preamble / self-praise
- E13 refusal-as-safe on tasks that should be completed
- E14 answer reordering / formatting games

Each exploit: a generator prompt, a "must be genuinely wrong" check, and an expected-failure assertion.

---

## 5. Benchmark: EnvTrust-Bench v0.1

Target environments (pick 6, cover all three families):
- Code: R2E-Gym sample, SWE-Gym sample, Terminal-Bench sample
- Tool-use: τ-bench (retail/airline), one Prime Intellect hub tool env
- Rubric-graded: one support/ops env (Corecraft if accessible; else build a 100-task rubric env from public data), one reasoning env with rubric grading

Per environment: 100 tasks. Per task: 3 sanity checks + K=8 adversarial candidates per exploit family + 3-tier difficulty sweep.

Ground truth: for ≥200 tasks across the rubric/tool families, a human label on each adversarial candidate ("is this actually wrong?"). This is the expensive part. Sources: you + Pragathi + paid expert hours for the domain ones.

### 5a. Labelling protocol (new — this was previously unspecified, and it's the part reviewers will attack first)

"200–300 human labels" is meaningless without a stated protocol for how consistent those labels are. Before labelling at volume:
1. Write down the exact labelling question and decision rules ("is this candidate genuinely wrong" — define what counts as wrong for each task family: code = fails a correct, independent re-check; tool-use = final state doesn't match the intended outcome; rubric = would a domain expert mark this materially incomplete or incorrect).
2. Pilot: you and Pragathi independently label the same ~30-candidate batch, blind to each other's labels.
3. Compute inter-rater agreement (Cohen's kappa or equivalent). If it's low, the labelling question is ambiguous — fix the protocol, not the labelers, and re-pilot before scaling.
4. Only scale to the full 200–300 once agreement is stable. Report the final agreement number in the paper; it's part of the method, not a footnote.
5. Any paid/external labelling hours follow the same fixed protocol, not a looser version of it.

Leaderboard columns: Trust Score (secondary/summary), hackability rate, gold-gate failures, judge-bias sensitivity, trivial %, impossible %, near-dup %.

### 5b. Disclosure policy for the public leaderboard (new)

There's a real conflict of interest between "vendors adopt this" (§12) and "this tool's job is to publicly report vendor flaws." Treat a new environment's audit like coordinated vulnerability disclosure, not a surprise takedown:
1. Audit privately first when the environment maintainer is identifiable and reachable.
2. Share the report with them and give a fixed window (30 days) to respond, fix, or comment before the entry goes live on the public leaderboard.
3. Publish on schedule regardless of response — the window is a courtesy, not a veto.
4. Environments with no identifiable maintainer (most synthetic/scraped ones) skip straight to public — the disclosure courtesy is for people you're asking to become allies, not a blanket delay.
This turns outreach from "we're about to expose you" into "we'll help you fix this before anyone sees it," which is a fundamentally easier pitch and is the actual mechanism by which vendors would come to trust, cite, or adopt the tool instead of avoiding it.

---

## 6. 16-week timeline

### Phase 0 — Prove it in a week (Week 1)
- Read papers 1, 2, 9, 10, plus the mutation-testing/test-oracle addition in §2.
- `pip install verifiers`; clone 3 hub environments (1 code, 1 tool, 1 rubric).
- Hand-write 5 exploits. Manually craft 20 wrong solutions for 20 tasks. Run. Record pass rate.
- **Gate:** if ≥10% of wrong solutions pass in the non-code env, proceed. If <5%, the non-code half may be less broken than assumed — re-scope toward difficulty/diversity axes and talk before continuing.
- Publish: repo + 500-word write-up with the number.

### Phase 1 — Replicate and generalize (Weeks 2–4)
- Replicate 2606.16062's gold-sanity gate + hackability on a code env; match their ballpark.
- Build `adapters/verifiers`, `probes/gold_sanity`, `probes/hackability`, exploit pack v0 (E1–E14 as generators).
- First automated run across the 3 envs. Ship `envcheck` v0.1 (CLI, JSON report).
- **Deliverable:** v0.1 on PyPI; blog post "we ran an automated adversary against 3 open environments."

### Phase 2 — The non-code contribution (Weeks 5–8)
- `probes/judge_bias`: paired-perturbation design (same content, vary length / confidence / preamble / order); measure grader flip rate.
- `probes/difficulty`: 3-tier sweep (e.g. a 7B open model, a mid open model via API, one frontier model). Flag trivial/impossible, with the human-review gate from §3 before any public DROP.
- `probes/diversity`: embedding + AST/template near-dup.
- Trust Score v1 + KEEP/FIX/DROP, reported alongside (not instead of) the per-axis columns.
- Start ground-truth labelling per the §5a protocol (pilot first, then scale; target 200 tasks by week 8).
- **Deliverable:** v0.3 with all five probes; first internal leaderboard on 6 envs; a stated inter-rater agreement number for the labels collected so far.
- **Checkpoint: submit an early-draft write-up to a relevant workshop (NeurIPS/ICML/ICLR track on LLM evaluation, RL environments, or trustworthy AI) around week 8–9.** This is a forcing function, not a distraction — it gets independent reviewer feedback and a citable result well before the Phase 4 deadline, and forces scope discipline earlier than week 12 would.

### Phase 3 — Benchmark + external users (Weeks 9–12)
- Finalize EnvTrust-Bench v0.1: manifests, labels + agreement numbers, leaderboard, reproducibility scripts, license.
- CI mode: `envcheck --fail-under 0.8`, GitHub Action.
- Reach out to 5 targets **using the §5b disclosure policy** (private report + fixed response window, not a surprise public score): Prime Intellect, 2 env-native startups, bandr, one lab's open env team. Ask for one call each.
- Transfer partner: pitch your guide's lab and bandr on co-authoring the transfer experiment (they run RL; you provide the audited task sets and the pre/post measurement).
- **Deliverable:** public leaderboard; ≥3 external runs; transfer collaboration agreed or explicitly dropped.

### Phase 4 — Paper + v1.0 (Weeks 13–16)
- `repair/` loop for FIX tasks (blocking test / rubric patch, re-verified through gold gate) — **first thing cut if behind schedule** (see §9 scope-cut order).
- Write the paper for the **primary target: NeurIPS Datasets & Benchmarks track** — best structural fit, since the actual deliverable (audited environments + human-verified ground truth + leaderboard + reproducibility scripts) is exactly what that track rewards, without needing a novel-algorithm framing. Contributions = (1) cross-domain audit with ground truth and stated labelling agreement, (2) judge-bias probe methodology, (3) the tool + CI gate, (4) transfer result if partner delivered.
  - Backup/alternate framing if the judge-bias result ends up strongest: ACL/EMNLP resource-and-evaluation track, or their system-demonstration track (lower bar, good fallback for "the tool" if the full research paper isn't ready).
  - Also legitimate and underexploited: ICSE/FSE NIER or tool-demonstration track, framed as "test oracle quality for RL environments" — the mutation-testing reading in §2 is what makes this framing credible.
- Submit. Ship v1.0.

---

## 7. Metrics that decide whether this worked

| Metric | Week 4 | Week 8 | Week 16 |
|---|---|---|---|
| Envs audited | 3 | 6 | 6–8 |
| Tasks audited | 60 | 600 | 800+ |
| Ground-truth labels | 0 | 200 | 300 |
| Labelling inter-rater agreement reported | — | pilot done | final number in paper |
| Exploit families | 5 | 14 | 14+ (community-contributed) |
| External teams running tool | 0 | 1 | 3 |
| Hackability rate found (non-code) | measured | measured | published |
| Workshop draft submitted | — | week 8–9 | accepted/feedback incorporated |
| Paper draft (primary target) | — | outline | submitted |

Kill criteria (be honest when you hit them):
- Week 1 gate fails (non-code hackability <5%) and difficulty/diversity axes also show nothing interesting → stop; write it up as a negative result and move on.
- Week 8: no external team will even take a call → the tool angle is dead; finish as paper-only.
- Week 12: no transfer partner → publish without transfer, state it as future work, don't fake it with a weak proxy.

---

## 8. Budget

- API for adversarial generation + judges: $500–1,500 total. Use open models via cheap providers for bulk; frontier only for the rubric-bias probes and the final leaderboard run.
- Human labelling: $500–2,000 depending on how much you and Pragathi do yourselves. Budget explicitly includes the §5a pilot-and-agreement pass, not just the final 200–300 labels — the pilot is what makes the rest trustworthy.
- GPU: the 4050 handles the 7B tier of the difficulty sweep (4-bit) and embedding models for diversity. Kaggle/Colab for anything bigger. RL/transfer = partner's compute only.

---

## 9. Risks and the honest answers

| Risk | Reality | Mitigation |
|---|---|---|
| Prior paper owns code hackability | True | Lead with non-code + multi-axis + tool; cite and extend, don't reinvent. The paper's actual contribution is Phase 2, not Phase 1. |
| Labs copy the method, don't pay | Certain | Payer is vendor/post-training tier; real ROI is paper + position |
| Ground truth is expensive and can be low-quality if unmanaged | True | §5a protocol: pilot + inter-rater agreement before scaling; cap at 200–300 labels; labelling protocol is part of the paper |
| Exploit generation is noisy ("wrong" solutions that are actually right) | Real | Mandatory human-verified subset; report precision of the adversary itself, budgeted separately from the environment ground-truth labels (they are not the same pool) |
| A "cleared" task later gets hacked publicly | Will happen | Scores are probabilistic with stated attack budget; never say "verified" |
| Format fragmentation | Real | Build on `verifiers`; adapters only for 2 more formats |
| Transfer axis unreachable solo | True | Partner or omit; never fake it |
| Somebody big ships this in month 3 | Possible | Speed + public leaderboard first; your benchmark is harder to copy than the tool |
| **Vendor incentive conflict — audited parties have no reason to cooperate with public exposure** | **Real, previously unaddressed** | **§5b disclosure policy: private audit + fixed response window before public listing** |
| **Single Trust Score gets Goodharted the same way the environments it audits do** | **Real** | **Per-axis leaderboard columns are the primary artifact (§3); Trust Score ships with a stated limitation, never used alone in marketing** |
| **Difficulty/diversity probes produce false positives on legitimately hard/unique tasks, damaging credibility** | **Real** | **Human review required before any public DROP driven solely by difficulty or diversity evidence (§3)** |
| **Solo-plus-one-part-time bandwidth vs. 16-week scope for 5 probes / 3 formats / 6-8 envs / 300 labels / repair / benchmark / paper** | **Real** | **Explicit cut order if behind schedule: 1) drop `repair/` entirely, 2) ship with 2 adapter formats instead of 3, note the third as future work, 3) prefer fewer environments with real labels over more with shallow ones. Never cut: gold_sanity, hackability, the labelling protocol, or the paper itself.** |

---

## 10. Week-1 checklist (do these, in order)

- [ ] Read 2606.16062 end to end; write a one-page summary of its method and gaps.
- [ ] Read 2606.04923; list every judge bias it names.
- [ ] Skim one mutation-testing or test-oracle-quality paper (§2 item 11).
- [ ] Install `verifiers`; run one hub environment end to end with an open model.
- [ ] Pick your 3 starter environments (1 code, 1 tool, 1 rubric). Write down why.
- [ ] Hand-write exploits E1, E5, E6, E9, E10.
- [ ] Produce 20 wrong solutions (manual + LLM-assisted), verify each is genuinely wrong.
- [ ] Run them through the graders. Record pass rate per environment.
- [ ] Create the public repo (`envcheck`), MIT/Apache-2.0 license, README with the number. **(done — repo live)**
- [ ] Post the write-up. Send it to Pragathi and to your friends at bandr; ask one question: "would you run this on your envs?"

---

## 11. People to loop in

- Pragathi — co-builder; labelling + rubric environment construction; co-labeler for the §5a pilot agreement pass.
- Dr. Shylaja — research framing, venue choice, possible GPU access for transfer.
- bandr founders — first pilot user and potential transfer partner.
- Prime Intellect hub maintainers — integration + distribution; they benefit from an audit tool for their hub.

---

## 12. What "winning" looks like in 12 months (beyond this plan)

The Trust Score appears in environment vendors' sales decks. A lab cites EnvTrust-Bench in a system card. The `verifiers` docs link envcheck as the recommended pre-publish check. You're the reference for "is this environment's reward signal trustworthy?" — which is the position from which contracts, roles, or a company become possible.

This depends on vendors experiencing envcheck as something that helps them, not something that ambushes them — §5b's disclosure policy is what makes that experience possible. Skipping it in the name of speed would undercut this exact goal.
