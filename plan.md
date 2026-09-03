# Plan v4 — Does Verifier Hardening Change What RL Learns?

Owners: Blitz + Pragathi · Advisor: Dr. Shylaja · Hardware: RTX 4090 (24 GB) + API + one optional cloud run · Window: 24–28 weeks

**v4 changes (after repo/paper verification):** C1 pilot moves from terminal environments to algorithmic coding (small models can't learn on Terminal Wrench tasks); training stack fixed to Unsloth GRPO on a single GPU; exact repos, datasets and detectors named; hypothesis support cited (2604.15149, HardTestGen).

**Changed again, this pass:** two gaps closed after review — an explicit cut order for the weeks 19–23 run volume (§5a), since up to ~30 training runs on a single 4090 in 5 weeks is the single largest unaddressed schedule risk in the plan; and a map from the already-built `envcheck` code to v4's C2/C3 components (§1a), since the v2→v4 rewrite dropped the envcheck architecture section (v2 §3) without saying what becomes of the eight commits already written against it. Everything else below is v4 as received. All named external repos/datasets (harden-v0, terminal-wrench, HardTestGen/HardTests, ImpossibleBench, evilgenie_inspect) were independently verified real and current before adopting this plan.

---

## 0. The three claims

- **C1 (headline):** Policies RL-trained against hardened verifiers hack less on held-out and impossible tasks, and generalize no worse, than policies trained against the original verifiers.
- **C2 (method):** A validity-preserving hardener — certified adversary + solver ensemble + explicit validity constraint — matches the baseline loop's attack-success reduction with < 3 pp legitimate-solution loss (baseline loses ~11 pp).
- **C3 (extension):** Hardening for state-checked and rubric-graded environments — new fixer mechanics, first measurement of hackability before/after.

Fallback if C1 shows no effect: paper = C2 + C3 + C1 negative result → D&B / ACL / ICSE instead of main track.

---

## 1. Stack (all verified public)

| Component | Use | Notes |
|---|---|---|
| github.com/few-sh/harden-v0 | Baseline hardening loop; fork for C2 | Py ≥3.12, Docker, Harbor, litellm keys. Actively changing — pin a commit. |
| github.com/few-sh/terminal-wrench | 331 hackable envs + 3,632 hack trajectories | Exploit taxonomy source; 8B cloud experiment; monitor training data |
| github.com/LeiLiLab/HardTestGen (+ HardTests dataset) | Hardened test generation for coding; problem pool for C1 | ICLR 2026; HackGen adversarial inputs; precedent for downstream RL gains |
| ImpossibleBench (Zhong et al.) | Post-training hack-propensity measure | Conflicting/one-off mutations; pass = hack |
| github.com/JonathanGabor/evilgenie_inspect | Hack detection: holdout tests + LLM judge + file-edit detection | Human-validated detectors; reuse verbatim |
| PrimeIntellect-ai/verifiers + Environments Hub | Environment format for C3; publish envs | GRPO trainer needs ≥2 GPUs — do NOT use its trainer on the 4090 |
| Unsloth GRPO (or TRL GRPOTrainer, vllm_mode=colocate) | Single-4090 training | Qwen3-1.7B full-param; Qwen3-4B/8B LoRA; reward_funcs = env verifier |
| prime-rl | Cloud 8B run only | 1× A100-80GB/H200 rental |
| τ-bench (sierra-research) | C3 state-checked env | pass^k protocol |
| 2605.12474 protocol | C3 rubric eval | Cross-family 3-judge panel; self-internalization gap diagnostic |

---

### 1a. envcheck: what's already built and where it plugs in (new)

Eight commits exist under `envcheck/` implementing v2's tool architecture (Task/Evidence/Verdict model, an adapter, two probes, an exploit pack, scoring, report + CLI) — written before the v2→v4 rewrite dropped that architecture section (v2 §3) and repointed the project at forking `harden-v0` instead. That code was never retargeted at v4. None of it touches C1 (which needs HardTests + the Unsloth GRPO training stack, neither of which exist in this repo yet). It maps onto C2/C3 like this:

| Built | File | Maps to |
|---|---|---|
| Task/Evidence/Verdict/Grader model | `core/types.py` | Generic wrapper any grader can sit behind (harden-v0 verifiers, τ-bench state predicates, rubric judges) without new probe code per format. |
| `gold_sanity` probe | `probes/gold_sanity.py` | Pre-flight check (gold passes, null fails). Cheap sanity gate to run against V0–V4 coding verifiers before spending GPU-hours training on them, and against τ-bench / the rubric env before C3 audits them. |
| `hackability` probe + exploit pack v0 (E1/E5/E6/E9/E10) | `probes/hackability.py`, `exploits/pack_v0.py` | The hand-written, pre-LLM adversary v2 described as a placeholder. This is what C2's certified adversary (§3) is meant to extend, not duplicate — and it already has stand-ins for the mechanical/semantic families (E6 claim-completion, E9 rubric-parroting) C3 needs for τ-bench and the rubric env, which harden-v0 itself doesn't cover (coding-only). |
| verifiers-format adapter | `adapters/verifiers_adapter.py` | Direct match to the Stack table's "PrimeIntellect-ai/verifiers + Environments Hub — Environment format for C3." Already does Rubric/State → Task. |
| scoring (worst-wins verdict, Trust Score) | `scoring/types.py` | Not in v4's design as written. Optional: a cheap per-task KEEP/FIX/DROP diagnostic while auditing/hardening the τ-bench and rubric envs in C3, ahead of Hub publication — not required for any C1/C2/C3 measurement in this plan. |
| report + CI demo | `report/`, `cli.py` | Not in v4's design as written. No current use identified; keep or drop later. |

Still missing even for this reduced scope: certification (gold-diff / cross-family judge check on a candidate — C2 item 1), the solver ensemble (C2 item 2), the validity constraint / ε sweep (C2 item 3), and any state-checked exploit generator for τ-bench predicates (C3). None of that exists in the exploit pack yet — building it is C2/C3 work, not a rename of what's here.

One measurement distinction to keep straight: the `hackability` probe measures whether a *fixed grader* accepts a *hand-crafted wrong answer* — a static, adversarial-search proxy. C1's hack rate measures whether a *trained RL policy* learns to exploit the grader — a behavioral, post-training result. They're complementary (the probe is a cheap pre-screen for candidate verifier conditions before burning a training run on them), not interchangeable — a KEEP verdict from this probe is not evidence for C1's "policy doesn't hack" claim.

---

## 2. C1 design (the experiment that decides the paper)

**Domain (pilot):** algorithmic coding, ~500 problems from HardTests where Qwen3-1.7B/4B base pass@8 is 20–70% (learnable band).

**Verifier conditions (the manipulated variable):**
- V0 *weak*: 3 public tests only (special-casing trivially passes).
- V1 *original*: the problem's original tests.
- V2 *baseline-hardened*: HardTests-generated tests (HackGen included).
- V3 *validity-preserving-hardened* (C2 output): V2 + certified-adversary-derived blocking tests, filtered by solver-ensemble validity constraint.
- Optional V4: injected-defect verifier with a *known* exploit (controlled, as in 2606.04923) — cleanest causal reading.

**Training:** Unsloth GRPO, Qwen3-1.7B full-param and Qwen3-4B LoRA; 300–600 steps; group size 8; 3 seeds per condition; identical prompts/data across conditions — only the reward function differs. Rollout/train alternate on one GPU.

**Post-training measures (all held-out):**
1. Hack rate on ImpossibleBench-style impossible variants (pass = hack).
2. Hack rate on EvilGenie-style hackable tasks: holdout-test failure + LLM-judge "reward_hacking" label + file-edit detection; human-verify 100 trajectories.
3. Legitimate accuracy on LiveCodeBench v5 held-out + HumanEval.
4. Hack-onset step during training (reward vs holdout accuracy divergence).
5. Generalization of hacking: School-of-Reward-Hacks-style transfer probes (2508.17511).

**Prediction:** V0 ≫ V1 > V2 ≈ V3 on hack rate; V3 ≥ V2 ≥ V1 on legitimate accuracy; V0 shows earliest onset.

**Stats:** mean ± CI over 3 seeds; two-proportion tests on hack rates; pre-registered conditions. What we can claim afterwards: *verifier hardening measurably changes the policy's hacking propensity, not just its benchmark score.*

**Scale-up (cloud, weeks 19–23):** Qwen3-8B via prime-rl on a Terminal Wrench subset with original vs hardened verifiers (their hardened KernelBench/TB verifiers + ours). ~100–200 GPU-h.

---

## 3. C2 design

- Fork harden-v0. Add: (1) **certified adversary** — every hack passed to the fixer must fail a gold-diff or cross-family judge check (removes false exploits that cause over-tightening); (2) **solver ensemble** — ≥2 model families, ≥2 solution styles, replacing their single reference solver; (3) **validity constraint** — reject a patch if ensemble benign pass drops > ε; sweep ε.
- Eval on their corpora: Terminal Bench 77 + KernelBench L1, hinted/unhinted ASR + benign pass. Output: ASR–validity Pareto frontier. Target: within ~3 pp of their ASR reduction, benign-pass loss < 3 pp.
- Also feeds C1's V3 verifiers for coding.

---

## 4. C3 design

- **State-checked:** τ-bench retail/airline + one hub tool env. Adversary with mechanical (claim-completion, minimal-action shortcuts) and semantic exploits; fixer patches state predicates. Validity via solver ensemble; pass^k reported.
- **Rubric-graded:** Corecraft if Surge grants access, else a constructed 100-task support/finance-ops env in `verifiers`. Fixer patches rubric criteria + judge prompt. Eval with cross-family 3-judge panel (2605.12474). Ground truth: 200 labels, κ ≥ 0.7, adversary precision reported.
- Publish both envs (original + hardened) on the Environments Hub.

---

## 5. Timeline (28 weeks)

**Wk 1–2 · Infrastructure.** Pin harden-v0; run on 5 TB tasks; reproduce one number. Unsloth GRPO on Qwen3-1.7B with a HardTests subset — 50-step run completes. Build V0/V1/V2 verifiers for 100 problems. Emails: advisor (venue/authorship), 2606.08960 authors (extension note), bandr (8B run).
**Gate:** trainer runs; verifiers produce different rewards on the same solutions.

**Wk 3–6 · C1 pilot.** V0/V1/V2 × 1.7B × 2 seeds, 300 steps. Measure hack rate (Impossible + EvilGenie detectors) and held-out accuracy.
**Gate:** ≥10 pp hack-rate gap V0 vs V2, consistent across seeds → A* track. <3 pp → C2+C3 paper; one confirmatory run only. Post the result publicly either way.

**Wk 7–12 · C2.** Certified adversary, solver ensemble, validity constraint, ε sweep on TB-77 + KernelBench L1. Produce V3 coding verifiers. **Workshop submission (C1 pilot + C2) by wk 12.**

**Wk 13–18 · C3.** τ-bench + hub env audit/harden; rubric env build/audit/harden; 200 labels; hub publish.

**Wk 19–23 · C1 full.** V0–V3 (+V4) × {1.7B, 4B} × 3 seeds; 8B cloud run on Terminal Wrench subset; onset + generalization measures.

**Wk 24–28 · Write & submit.** Ablations (certification on/off, ensemble size, ε, verifier-aware vs blind), stats, release (code, verifiers, envs, labels, trajectories). Internal review. Submit.

Venues: main track (NeurIPS 2027 / ICML 2027 / ICLR 2028) if C1 holds; NeurIPS D&B / ACL / ICSE otherwise; workshop at wk 12. Verify deadlines at commit.

### 5a. Run-volume cut order for weeks 19–23 (new)

V0–V3(+V4) × {1.7B, 4B} × 3 seeds is up to ~30 sequential training runs on a single 4090 inside a 5-week window — the largest unaddressed schedule risk in the plan; GRPO instability has a mitigation (§7), the sheer volume of runs doesn't. If wall-clock time is blowing up by week 20, cut in this order, decided now rather than mid-crunch:
1. **Drop to 2 seeds before dropping anything else.** Weakens the CI but keeps every condition and both model scales represented.
2. **Drop the 4B LoRA scale next**, keeping 1.7B full-param across all conditions — the core V0-vs-V2/V3 comparison survives on one scale.
3. **Drop optional V4 (injected-defect) last among the verifier conditions** — it's explicitly marked optional in §2 and was always the cleanest-but-not-required causal reading.
Never cut: V0, V1, V2, V3 at the 1.7B scale, or the 3-seed requirement for whichever conditions remain — the paper's headline comparison lives entirely in that cell.

---

## 6. Budget

| Item | Cost |
|---|---|
| API (hacker/fixer/solver/judges; open models for bulk, frontier for certification) | $600–1,200 |
| Cloud 8B run (A100-80GB/H200, 100–200 GPU-h) | $300–700 |
| Expert labels (C3 rubric) | $300–600 |
| **Total** | **$1.2k–2.5k** |

---

## 7. Risks

| Risk | Likelihood | Response |
|---|---|---|
| 2606.08960 group runs the downstream-RL study first | Med-high | Pilot public by wk 6; contact them; C2/C3 remain yours |
| Small models don't learn enough to hack | Medium | Learnable-band problem selection; V0 weak-tests condition guarantees a hackable signal |
| GRPO on one 4090 unstable | Medium | Unsloth; LoRA on 4B; shorter completions; alternate phases |
| **Weeks 19–23 run volume (~30 runs) doesn't fit a single 4090 in 5 weeks** | **Real, previously unaddressed** | **§5a: pre-decided cut order — seeds first, then 4B scale, then optional V4 — never the core 1.7B V0-V3 comparison** |
| Hack detectors disagree | Real | Report all three (holdout, judge, file-edit) + 100 human labels, as EvilGenie does |
| Reviewer: "HardTestGen already showed better tests help" | Real | Distinguish: they measure accuracy; we measure hacking propensity, onset, and generalization, and compare hardening methods |
| Reviewer: "2604.15149 already showed verifier design induces shortcuts" | Real | Cite as motivation; ours is automated hardening on agentic/coding tasks at scale with a validity-preserving method |
| Rubric ground truth subjective | Real | κ; cross-family panel; tool-use env as clean case |

---

## 8. Week-1 checklist

- [ ] `git clone few-sh/harden-v0` (pin commit) + terminal-wrench; Docker + Harbor + litellm key; run loop on 5 tasks.
- [ ] Download HardTests; select 100 problems; write V0 (3 public tests) / V1 (original) / V2 (HardTests) verifiers as `reward_funcs`.
- [ ] Unsloth GRPO + Qwen3-1.7B; 50-step smoke test; log reward and holdout accuracy.
- [ ] Set up EvilGenie detectors and 20 ImpossibleBench-style mutations for the pilot problems.
- [ ] Emails: advisor, 2606.08960 authors, bandr. Public repo (Apache-2.0) with the three claims.
