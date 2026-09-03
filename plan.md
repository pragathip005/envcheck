# envcheck / EnvTrust-Bench — Execution Plan v2

*Research-first. Direction 1: reward-signal validity in non-code RL environments.*

Owners: Blitz + Pragathi. Advisor: Dr. Shylaja. Hardware: RTX 4090 (24 GB) confirmed; + API credits. Window: ~24 weeks to main-track submission.

**Changed from v1:** the tool is now a by-product, not the goal. Judge-bias probes demoted to a sub-result. Adversary precision added as a first-class measurement. Timeline extended from 16 to 24 weeks to reach a publishable result. GPU plan added.

**Changed from v1 again, this pass:** three gaps closed after comparing v1 and v2 side by side — a validation step for the certification pipeline itself (§1a), an explicit scope-cut order now that ambition grew faster than the timeline did (§7a), and a one-line disclosure norm for named environments now that the vendor-pilot angle is gone but the research-access asks (Corecraft/Surge AI) aren't (§6a). Everything else below is v2 as received.

---

## 0. Goal

**Primary:** a main-track or D&B paper answering: *under a fixed attack budget, what fraction of reward in tool-use and rubric-graded RL environments goes to expert-judged-incorrect solutions, how does it compare to code, and how reliable is the automated auditor itself?*
**Secondary:** the released benchmark (EnvTrust-Bench), labelled exploit set, and the `envcheck` tool.
**Now in scope (4090):** the causal result at small scale — do grader defects become policy defects after RL? Partner/cloud only for the 7B+ headline version.
**Not the goal:** revenue.

Done means: ≥4 environments audited, ≥300 expert-labelled items with κ reported, adversary precision measured, validity metric defined, replication of the prior code result, synthesized-vs-hand-built comparison, paper submitted.

---

## 1. Research design (fixed before code)

**Hypotheses.**
- H1: non-code environments leak reward to incorrect solutions at rates ≥ code environments at K=8.
- H2: semantic exploits dominate in rubric environments; mechanical exploits dominate in code.
- H3: automated adversary precision is lower on rubric tasks than on code/tool-use.
- H4 (optional): synthesized tasks show higher gold-gate failure and near-dup rates than hand-built ones.

**Baselines.** Human-authored wrong solutions; the 2606.16062 pipeline on code; a random-wrong adversary.

**Environments.** τ-bench retail/airline (tool-use, state-checked); one Prime Intellect hub tool env; one rubric-graded env (Corecraft if accessible, else constructed 100-task support/finance-ops env); R2E-Gym sample (code control); one synthesized env (AutoForge/AWM-style output). 100 tasks each.

**Metrics.** Task-level defect rate; score-level reward leakage (graded tasks); adversary precision; κ; gold-gate failure rate; near-dup rate; cost per audited task. Wilson CIs, bootstrap over tasks, K budget pre-registered.

**Ablations.** Drop each exploit family; K ∈ {2,4,8,16}; swap adversary model; swap certification judge family; disable gold gate.

**Stress tests.** Injected-defect environments (recall); deliberately hardened environments (false-positive rate).

**Generalization.** Hold out one family; does the taxonomy transfer?

**Claim after the experiment:** a quantified, ground-truthed defect rate for non-code environments with the auditor's own error bar — which nobody can state today.

### 1a. Certifier validation (new — closes a reflexivity gap)

`probes/certify.py` (§3) decides whether an adversary-generated candidate is genuinely wrong using cross-family LLM judges. That certifying judge is itself an LLM, subject to the same trust problem this paper studies — a sharp reviewer's obvious question is "how do you know your certifier is right?" Answer it before they ask: run the certifier against the same human-labelled subset used for κ, report the certifier's own agreement/error rate against those human labels, and carry that number in the paper alongside adversary precision. Without this, the paper's headline defect rate silently inherits an unmeasured judge-bias error term from the one component meant to guard against exactly that.

---

## 2. Reading (week 1)

Core: 2606.16062 (replicate), 2606.04923 (rubric RL hacking — template for causal study), 2604.15149, 2605.02964, 2603.12011, 2602.16179, 2602.10090, 2512.22857, 2601.16443, τ-bench 2406.12045.
Judge bias (cite, don't reinvent): 2410.02736 (CALM), 2410.12784 (JudgeBench), 2606.19544.
Theory: mutation testing (DeMillo, Lipton & Sayward 1978) — frame hackability as mutation adequacy for reward functions.
Method: MAST 2503.13657 for taxonomy + κ methodology.
Tooling: Prime Intellect `verifiers` docs + Environments Hub.

---

## 3. Architecture (minimal — build only what the paper needs)

```
envcheck/
  adapters/verifiers.py        # only format for now
  probes/gold_sanity.py        # gold passes; null/random-wrong fail
  probes/adversary.py          # exploit taxonomy -> K wrong candidates per task
  probes/certify.py            # is the candidate genuinely wrong? gold-diff + cross-family judges + human queue
  probes/difficulty.py         # 3-tier sweep (7B open / mid / frontier)
  probes/diversity.py          # near-dup + template collapse
  scoring/validity.py          # task-level defect + score-level leakage; Trust Score
  report/                      # JSON + HTML; --fail-under for CI (last)
bench/                         # manifests, labels, leaderboard scripts
paper/
```

Rules: probes independent; exploit pack versioned separately; every report states K, adversary model, certification model; score is probabilistic — never say "verified". Per §1a, every report that cites a certify.py verdict also carries the certifier's own measured agreement rate against the human-labelled subset — the certification model is a probe with an error rate too, not ground truth.

Note on what's already built: the code so far (`adapters/verifiers_adapter.py`, `probes/gold_sanity.py`, `probes/hackability.py`, `scoring/`, a demo `cli.py`) maps directly onto this architecture — `hackability.py` is `probes/adversary.py` in substance. `probes/certify.py` is the one genuinely new component; `scoring/validity.py` additionally needs score-level (continuous) leakage, not just the binary KEEP/FIX/DROP verdict our `scoring/` currently produces.

---

## 4. Exploit taxonomy v0 (mechanical vs semantic)

Mechanical (code/tool): test special-casing; assertion removal; grader monkey-patching; early exit; partial implementation; claim-completion-without-side-effects; minimal-action shortcuts.
Semantic (rubric/reasoning): rubric parroting; length padding; confident hedging; sycophantic preamble/self-praise; refusal-as-safe; answer reordering/format games; exploiting the verifier's implicit correctness assumptions (2604.15149).
Each: generator prompt, "must be genuinely wrong" certification path, expected-failure assertion.

---

## 5. Hardware and budget (RTX 4090, 24 GB)

What the 4090 changes:
- **Bulk adversarial generation moves local.** Serve Qwen3-14B or Qwen2.5-Coder-14B in 4-bit via vLLM/SGLang on the 4090 for the K-candidate adversary; use frontier APIs only for certification and the final leaderboard. Cuts API spend roughly in half.
- **Difficulty sweep is trivial.** 7B/14B tiers run locally at full speed.
- **Direction 3 (causal RL) is on the table at small scale.** Recipe: GRPO via TRL or verl on Qwen3-1.7B / Qwen2.5-1.5B-Instruct full-parameter, or Qwen3-4B with LoRA; rollouts with vLLM on the same card, alternating rollout/train phases (don't try to co-host both at once). Environments: injected-defect variants of τ-bench-style tool tasks with a known defect profile. Target: 200–500 RL steps per condition × 3 defect conditions + 1 clean control. Expect 1–3 days wall-clock per condition — but budget calendar time for RL infrastructure debugging (vLLM/TRL integration, OOMs from co-hosting rollout and train) separately from raw GPU-hours; a first-time setup's debugging time reliably dwarfs the run time itself.
- **Still out of reach locally:** 7–8B full RL on real environments for a headline result — 1× A100-80GB/H100, 150–300 GPU-h — $400–900, or a partner cluster.

| Work | Where |
|---|---|
| Adversary generation (bulk) | 4090, 14B 4-bit local |
| Certification | Frontier API (cross-family) |
| Difficulty sweep | 4090 |
| Small-scale causal RL (≤4B) | 4090 |
| 7B+ causal RL | Cloud A100/H100 or partner |

Budget: API $400–800 (down from $800–1,500); expert labelling $300–800; cloud GPU $0–900 (optional). Total: $0.7k–2.5k.

## 6. People and asks (do in week 2)

- Pragathi: co-builder, second annotator, rubric env construction.
- Dr. Shylaja: venue + authorship agreement; GPU/cluster access for Direction 3.
- bandr / lab partner: "if I deliver audited environments with known defect profiles, will you run the RL and co-author?"
- Prime Intellect hub maintainers: integration + a pre-publish check; distribution.
- Surge AI: request Corecraft access for research.

### 6a. Disclosure norm for named environments (new)

v1 had a vendor-pilot angle and, with it, a real conflict of interest (audit-and-expose vs. audit-and-sell), mitigated there with a coordinated-disclosure policy. v2 drops the vendor pitch, but the tension didn't fully disappear — the paper will still publish a measured defect rate against named environments (Corecraft, hub environments) whose maintainers you're asking for research access. Keep it simple here rather than reviving the full v1 policy: share the relevant measured results with an identifiable environment's maintainer before publication, as a courtesy and good-faith gesture for research access granted, not as something that can block or delay publication. State this plainly in the paper's methodology section. Environments with no identifiable maintainer (scraped/synthetic ones) need no such step.

---

## 7. Timeline (24 weeks)

**Week 1 — go/no-go.** 20 hand-crafted plausible-wrong solutions on τ-bench retail; count acceptances; two independent labels; κ. Publish the number.
- GO if ≥10% accepted and κ ≥ 0.7. PIVOT to H4 (synthesized envs) if <5%. Talk before continuing if in between.

**Weeks 2–4 — replicate + automate.** Reproduce 2606.16062's gold gate + hackability on R2E-Gym sample; build adapter, gold gate, adversary with full taxonomy; first automated run on τ-bench. Send partner asks.

**Weeks 5–8 — three environments + precision.** Add hub tool env; defect rates with CIs on ≥300 tasks; adversary precision on 50-item human subset; certification pipeline v1 (with the §1a self-check against the human-labelled subset). **Workshop-paper-ready.** Submit to the nearest workshop as a marker.

**Weeks 9–12 — the novel half.** Rubric-graded environment (Corecraft or constructed); score-level leakage metric; 150+ labelled rubric items; semantic-vs-mechanical rates per family.

**Weeks 13–16 — breadth + comparison.** Synthesized environment audit (H4); ≥300 total labels; difficulty + diversity probes; internal leaderboard; **main-track draft outline.** Tool v0.1 on PyPI (one week of polish, no more).

**Weeks 17–20 — rigor.** Ablations (exploit family, K, adversary model, judge family, gold gate); injected-defect recall and hardened-env FPR; held-out-family generalization; bootstrap CIs. Direction 3 on the 4090: GRPO on Qwen3-1.7B across 3 injected-defect conditions + clean control; measure post-training behaviour against the pre-training defect profile. Partnered 7B run if available.

**Weeks 21–24 — write + submit.** Full draft, internal review by advisor + one external reader, release benchmark + labelled set + audit logs, submit.

Venue targets: workshop (week 8 result) at ICLR 2027 / NeurIPS 2026 workshops; main track (week 24) at NeurIPS 2027 D&B, ACL 2027 systems, or ICSE/FSE 2027–28 cycle. Verify exact deadlines at commit time.

Effort assumption: 15–20 hrs/week each. Below that, multiply by 1.5.

### 7a. Scope-cut order if behind schedule (new)

Ambition grew more than the timeline did in v2 (formal hypotheses, ablations, stress tests, a generalization check, a full certification pipeline, *and* real RL training runs, for +50% more time). If week 16–18 arrives behind schedule, cut in this order — decide it now, not under deadline pressure:
1. **Direction 3 (causal RL) first.** It's the single riskiest, most infrastructure-heavy line item and the plan already has an honest exit ("report as negative result, scope as future work" — §8 kill criteria) — use it rather than fighting to keep the RL runs alive alongside everything else.
2. **H4 (synthesized-vs-hand-built comparison)** next — it's explicitly marked optional in §1.
3. **Environment count** — 4 environments with full rigor (ablations, CIs, certifier validation) beats 5–6 audited shallowly.
Never cut: the gold gate, adversary precision measurement, κ-reported human labelling, or the certifier validation from §1a — these are the paper's actual evidentiary core.

---

## 8. Milestone metrics

| | Wk 4 | Wk 8 | Wk 16 | Wk 24 |
|---|---|---|---|---|
| Environments | 2 | 3 | 5 | 5–6 |
| Tasks audited | 200 | 300 | 500 | 600+ |
| Labelled items (κ reported) | 20 | 50 | 300 | 300+ |
| Adversary precision measured | — | yes | yes | yes |
| Certifier agreement vs. human labels (§1a) | — | yes | yes | yes |
| Validity metric defined | — | draft | final | final |
| Replication of 2606.16062 | done | — | — | — |
| Synthesized-vs-hand-built | — | — | done | done |
| RL causal result | — | — | — | small-scale or partnered |
| Paper | number posted | workshop | draft | submitted |

Kill criteria: week-1 gate fails on both H1 and H4 — write negative result, stop. Week 12: rubric labels can't reach κ ≥ 0.6 — narrow to tool-use only, state limitation. Week 16: small-scale RL shows no measurable defect–behaviour link — report as negative result, scope Direction 3 as future work.

---

## 9. Risks

| Risk | Reality | Mitigation |
|---|---|---|
| Code half already published | Certain | Replicate and cite; lead with non-code |
| "It's mutation testing" | Certain | Say so; frame as mutation adequacy for reward functions; novelty = semantic mutants + graded rewards + auditor precision |
| Judge-bias probes not novel | Certain | Sub-result only; use CALM/JudgeBench protocols |
| Adversary produces correct "exploits" | Real | Certification pipeline + reported precision |
| **Certifier judge inherits the same trust problem being studied** | **Real, previously unaddressed** | **§1a: validate the certifier against the human-labelled subset; report its own agreement rate, not just the adversary's precision** |
| Rubric ground truth subjective | Real | 2–3 annotators, κ, disagreement category |
| No RL evidence | Likely solo | 4090 small-scale or partner; otherwise honest scoping |
| API cost overrun | Likely | Open models for bulk; frontier for certification only |
| **Scope grew faster than the timeline (Direction 3 especially)** | **Real** | **§7a: explicit cut order, Direction 3 first, decided now rather than under deadline pressure** |
| Someone bigger publishes first | Possible | Post week-1 and week-8 results publicly |

---

## 10. Week-1 checklist

- [ ] Set up vLLM on the 4090 with a 14B 4-bit model; confirm throughput for K=8 generation.
- [ ] Read 2606.16062 fully; one-page method + gaps summary.
- [ ] Read 2606.04923; list injected biases and the drift metrics.
- [ ] `pip install verifiers`; run τ-bench retail end to end with an open model.
- [ ] Write 20 plausible-wrong solutions for 20 τ-bench tasks (manual + LLM-assisted).
- [ ] Two people label each independently; compute κ.
- [ ] Run through the state checker; record acceptance rate.
- [ ] Create public repo (Apache-2.0), README with the number. **(repo already live, MIT — revisit license choice against this plan's Apache-2.0 preference before the public benchmark release)**
- [ ] Message advisor (venue/authorship) and bandr (RL partner ask).
