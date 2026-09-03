# Learning Log

A running reference for this project: what we've done, why, and the concepts
behind it. Update this alongside the code — don't let it drift the way
`plan.md`'s architecture section drifted from the repo (see plan.md §1a).

How to use this file: **Progress** is a dated log of what got done and what
it unblocked. **Concepts** is written the first time we actually need the
idea, in terms of the code we just touched — not an upfront glossary. Look
things up here before re-deriving them from scratch.

(Note to self, 2026-09-03: earlier edits let Progress entries get appended
after a "## Concepts" header instead of into the Progress section, splitting
it into two disconnected `## Concepts` blocks. Rewrote the whole file once to
fix the ordering — Progress entries chronological under one `## Progress`,
Concepts entries in the order first needed under one `## Concepts`. Keep
appending under the correct header from here on rather than blindly matching
old tail text.)

---

## Progress

### 2026-09-03 — Reconciled plan.md v4 with the existing envcheck code
Added plan.md §1a mapping the 8 existing commits (Task/Evidence/Verdict
model, adapter, probes, exploit pack, scoring, report/cli) onto v4's C2/C3,
since the v2→v4 rewrite had dropped the section that code was written
against. See plan.md §1a for the table.

### 2026-09-03 — Confirmed this machine is the v4 dev environment
RTX 4090 (24GB, driver 595.97, CUDA 13.2), Docker 28.5.1, Python 3.12.9, git,
and network access to `github.com/few-sh/harden-v0` all confirmed present.
Starting plan.md §8's Week 1-2 checklist for real, in order.

### 2026-09-03 — Cloned + inspected harden-v0 and terminal-wrench; hit a Windows blocker
- `harden-v0` cloned to `external/harden-v0`, pinned to `342b8474e0c0cf96e4a8313fd2e26c7a11d51193`
  (2026-07-03, "Fix patch extraction for Modal sandbox runs") per plan.md §1's "actively
  changing — pin a commit" instruction.
- `terminal-wrench` cloned to `external/terminal-wrench-tmp` (name: a stray empty
  `external/terminal-wrench` directory kept refusing `rmdir`/`rm -rf`/`mv` with
  "Device or resource busy" — most likely OneDrive or Defender transiently locking a
  freshly-touched folder under `Projects/`. Not worth fighting; the clone works fine
  under the `-tmp` name. If it becomes annoying, moving the whole `external/` tree
  outside any synced folder would remove the cause.) HEAD is
  `d8a29613235a0ef56a8b70b3142626a533da28c2` (2026-04-18). 331 task dirs confirmed
  under `tasks/`.
- Read harden-v0's README + CLAUDE.md in full — see **Concepts: the hacker-fixer loop**
  below.
- Read terminal-wrench's README — see **Concepts: terminal-wrench's task format**.
- Created a venv at `external/harden-v0/.venv` and installed `requirements.txt`
  cleanly (harbor, litellm, pydantic, tenacity, PyYAML, python-dotenv, tqdm — no
  errors, no pinned versions).
- **Blocker found:** `python -m harden --help` fails immediately —
  `harden/durable.py` does a bare `import fcntl` at module load time. `fcntl` is
  POSIX-only; it doesn't exist on Windows. This isn't a corner case we could route
  around — it's imported unconditionally by `harden/loop.py`, which `batch.py` and
  `__main__.py` both pull in, so the CLI can't even parse `--help` on native Windows
  Python. Consistent with CLAUDE.md separately noting pooled mode needs
  `host.docker.internal:host-gateway`, which is "Linux-only" — harden-v0 was written
  assuming a Linux host throughout, not just for pooled mode.
- **Second blocker found:** `docker ps` fails from this shell — "the docker client
  must be run with elevated privileges to connect" / can't find the named pipe.
  Docker Desktop's Windows-side daemon isn't reachable here right now (separate from
  the fcntl issue).
- **Checked:** `wsl --status` shows WSL2 as the default *version* (the feature is
  enabled), but `wsl -l -v` reports no distro installed. So there's no Linux
  environment on this machine yet for harden-v0 to actually run in.
- **Where this leaves us:** harden-v0 needs a real Linux userspace. The practical
  fix is a WSL2 distro (Ubuntu) with Docker either installed inside it directly or
  reachable via Docker Desktop's WSL2 integration, and — since training also needs
  the GPU — NVIDIA's WSL2 CUDA passthrough (well-supported for RTX cards, but it's
  an environment-provisioning step, not a code change). Installing a distro needs
  admin elevation and is a real change to this machine's setup, so this is a
  checkpoint to confirm with the user rather than something to just do silently.

### 2026-09-03 — WSL2 attempt: user has no admin rights; hit a deeper wall
User confirmed no admin rights on this machine. Checked whether that actually
blocks a distro install — it didn't, at first: `wsl --install -d Ubuntu` ran as
the current user, downloaded and installed Ubuntu without any elevation prompt,
and got as far as "Please create a default UNIX user account" (interactive).
That prompt can't be answered from a non-interactive shell (stdin closed), and
retrying it endlessly spun into a `Catastrophic failure / Wsl/Service/E_UNEXPECTED`
loop — killed that background task (`TaskStop`) rather than let it keep
respawning.

The distro *did* register (`wsl -l -v` shows `Ubuntu`, state Stopped, version 2).
But `wsl -d Ubuntu -u root -- whoami` — bypassing the interactive prompt
entirely by logging in as root — hit the same `E_UNEXPECTED` error. That's not
the username prompt anymore; it's the WSL service itself failing on a basic
operation. Checking why (`Get-WindowsOptionalFeature` for VirtualMachinePlatform
/ the Linux subsystem feature) itself requires elevation — "The requested
operation requires elevation" — so confirming root cause (Hyper-V/VM Platform
not actually enabled despite `wsl --status` claiming default-version 2,
possibly a stuck `LxssManager` service, possibly BIOS-level virtualization) is
also blocked without admin.

**Conclusion: this needs the machine's admin/IT, not a workaround.** Recommend
asking them to either (a) fix WSL2 (restart `LxssManager`, confirm Hyper-V/VM
Platform are genuinely on, finish `wsl -d Ubuntu` user creation once), or (b)
add this account to the local `docker-users` group and get Docker Desktop
running — confirmed not currently running, and this account isn't in that group
(`whoami /groups` — only default low-privilege groups). Until one of those
happens, harden-v0 (and by extension the whole C2 track, which forks it) is
blocked on this machine. **Pivoting to C1 prep** (plan.md §8 item 2: download
HardTests, select 100 problems, write V0/V1/V2 verifiers) — pure Python, needs
no Docker or Linux, fully unblocked.

### 2026-09-03 — Started C1 prep: HardTestGen repo + HardTests dataset
- Cloned `LeiLiLab/HardTestGen` to `external/HardTestGen`. Its own pipeline
  (`test_cases_kit_generation.py` → `test_cases_generation.py`) is for
  *synthesizing new* hardened tests from scratch and needs Bubblewrap — Linux
  sandboxing again, same wall as harden-v0. We don't need it: the problems and
  the already-generated test cases are published as two separate HuggingFace
  datasets, `sigcp/hardtests_problems` and `sigcp/hardtests_tests`, which we can
  just download.
- Created a project venv at `envcheck/.venv` (separate from harden-v0's, and
  already covered by `.gitignore`), installed `datasets` + `huggingface_hub`.
- Pulled one row of `sigcp/hardtests_problems` to see the real schema:
  `pid, question_title, question_content, question_content_all_languages,
  platform, contest_date, difficulty_ratings, public_test_cases, time_limit,
  memory_limit, url, tags, source_dataset_info, solutions, starter_code`.
  `solutions` and `public_test_cases` map directly onto what V0/V1 need — see
  Concepts below.
- `sigcp/hardtests_tests` schema check is running (background task
  `b8hkiacnw`) — its rows are presumably the HardTestGen-produced test cases
  (V2's material) keyed by `pid` back to the problems dataset.
- **Worth flagging now, before it becomes a surprise later:** V0/V1/V2/V3
  verifiers don't just need the test *data*, they need to *execute* candidate
  solutions against it to grade them. Running arbitrary (eventually
  model-generated) code safely needs a sandbox — this is exactly why
  HardTestGen's own pipeline uses Bubblewrap and why harden-v0 uses Docker. So
  the "pure Python, no Linux needed" description is true for downloading data
  and writing verifier *logic*, but actually *running* those verifiers against
  real candidate solutions during GRPO training will hit the same WSL2/Docker
  wall documented above. Not blocking today's work, but don't expect this pivot
  to fully route around the infra problem — it defers it, for the pieces that
  don't need execution yet (data selection, problem-band analysis, test
  parsing).

### 2026-09-03 — Built and verified V0; found the real `hardtests_tests` schema
- New `c1/` directory (not part of the `envcheck` package - see `c1/README.md`
  for why): `c1/data.py` (streams + JSONL-caches `sigcp/hardtests_problems`)
  and `c1/verifiers.py` (`make_v0_grader`).
- **V0 built and actually tested against live data**, not just written and
  assumed correct. First run: gold (real editorial) solutions scored 0.333,
  0.0, 0.0, 0.0 across 4 problems - clearly broken, since these are supposed
  to be *correct* solutions. Found the real bug: `public_test_cases` inputs
  ship with literal `"\r\n"` inside the string, and Windows text-mode
  subprocess pipes apply universal-newline translation on *write*, turning
  each `"\n"` into `os.linesep` (`"\r\n"` on Windows) - so an existing
  `"\r\n"` became `"\r\r\n"`, which the child's own text-mode *read* side
  then collapses into two newlines, silently inserting a blank line and
  shifting every subsequent `input()` call. Confirmed by hand with a 2-line
  repro before touching the real code (see `verifiers.py::_to_lf`'s
  docstring) - fixed by normalizing to bare `\n` before the pipe write.
  Re-ran: 4/5 gold solutions now score exactly 1.000, wrong candidates score
  0.000. The one gold solution that still scores 0.667 isn't a grader bug -
  that entry is tagged `source_reliability: medium`, i.e. a possibly-flawed
  scraped solution, and the grader correctly caught it failing a test. A
  discriminating grader that sometimes fails a "gold" solution because the
  gold itself is imperfect is doing its job - see gold_sanity's whole point
  in plan.md §1a.
- **Real schema of `sigcp/hardtests_tests`, without downloading a full
  shard.** Streaming it directly kept hanging (123 parquet files, evidently
  large - each row carries generator *code*, not just data). Fetched the
  schema instead via `HfApi().dataset_info()` + reading just one parquet
  file's footer with `pyarrow.parquet.read_schema` over an `fsspec` HTTP
  handle - no full-file download needed. Per row:
  - `pid` - joins back to `hardtests_problems`.
  - `test_cases_kit` - **not raw test data, generator code**: `HackGen`
    (code + function names), `LLMGen` (list of generator code strings),
    `RPGen`, `SPGen`, plus an `input_validator` and an
    `output_judging_function` (also code, not a string-equality flag).
  - `mapping` - which generated inputs came from which generator strategy.
  - `test_cases` - the concrete generated cases (haven't pulled a real row's
    content yet - next step, see below).
  - **This directly confirms plan.md §2's "V2: HardTests-generated tests
    (HackGen included)" isn't a metaphor** - `HackGen` is a literal named
    field in this dataset, a specific adversarial-input generator alongside
    the more benign `LLMGen`/`RPGen`/`SPGen` ones. See Concepts below on why
    V2 needs to run `output_judging_function` rather than exact-match, unlike
    V0.
- **Still open, not resolved yet:** what "V1 original tests" (plan.md §2)
  actually means as data. `hardtests_problems` only ships `public_test_cases`
  (2-4 tiny samples per problem, same one V0 uses) and `solutions` - no
  larger "private/original judge tests" field. Competitive-programming
  platforms generally don't republish their private judge data, so V1 may
  need to come from a different source per problem (e.g. some
  `source_dataset_info.dataset_name` values may point at datasets like
  CodeContests that *do* ship larger held-out test sets) - haven't checked
  the distribution of `source_dataset_info` values yet. Don't build V1 by
  guessing; check that distribution first.

### 2026-09-03 — Resolved V1 ("original tests"): it isn't a free lookup
Checked three things before concluding: `hardtests_problems`' own official
field docs (fetched its HF dataset card - confirms the schema really has no
field beyond `public_test_cases`, so this isn't a case of us missing a
column); the true `source_dataset_info.dataset_name` distribution (streaming
row-by-row was useless here - the dataset isn't shuffled, so the first 2000
rows sequentially were 100% AtCoder; had to sample the first row-group of
each of the 12 parquet shards independently via direct `pyarrow` + `fsspec`
reads over HTTP, without downloading full shards, to get a real cross-section);
and the schema of the two datasets HardTests' own card names as oracle-program
sources, `deepmind/code_contests` and `BAAI/TACO`.

**What the cross-shard sample actually showed:** two `dataset_name` values
only, `original` (~66% of the sample) and `taco` (~34%). `original` rows
(direct-from-OJ: AtCoder, Luogu, and *most* Codeforces problems) carry
`source_dataset_info.idx = None` - no join key back to anything richer.
`taco`-tagged rows (some Codeforces, plus Aizu/GeeksforGeeks/CodeChef/Kattis/
etc.) *do* carry a real join key (`idx` + `split="train"` into
`BAAI/TACO`'s `train` split) - but every single one sampled had
`public_test_cases` empty in `hardtests_problems` itself. So even V0 needs
that join for taco-sourced problems, before V1 is even a question.

**`deepmind/code_contests`' actual schema** (fetched, not assumed) has
exactly the three-tier split plan.md's V1 wants: `public_tests`,
`private_tests`, `generated_tests` (plus, notably, an `incorrect_solutions`
field - genuinely-wrong reference solutions someone already curated; worth
remembering for envcheck's own exploit pack later, plan.md §1a). But
`hardtests_problems` doesn't expose a `dataset_name == "codecontests"` join
key anywhere in the sample - per its own dataset card, CodeContests
contributed *solutions* to Codeforces problems, not a tracked test-provenance
link. The real join path for those has to go around `source_dataset_info`
entirely: match on the problem `url` (`codeforces.com/contest/<id>/problem/<letter>`)
against `code_contests`' own `cf_contest_id` + `cf_index` fields.

**Conclusion - V1 is not one uniform thing across the dataset:**
1. For AtCoder/Luogu-direct problems (`dataset_name="original"`, no join
   key): there is no richer "original" test set reachable from any dataset
   here. V1 would equal V0 for these unless we scraped the live judge
   ourselves - out of scope, possibly against platform ToS.
2. For Codeforces problems: joinable to `deepmind/code_contests` via
   `cf_contest_id`/`cf_index` parsed from the problem URL, which gives a real
   public/private/generated three-way split - genuine V1 material.
3. For TACO-routed problems (Aizu, GeeksforGeeks, CodeChef, Kattis, etc.):
   joinable to `BAAI/TACO` via `idx`, but TACO's `input_output` field is a
   single JSON string of unconfirmed internal structure (not yet parsed) -
   may or may not distinguish a "public" subset from the rest.

**Recommendation put to the user and confirmed:** build the 100-problem C1
pilot pool from Codeforces problems specifically, since that's the one
platform with a confirmed, real three-tier test split reachable by a URL
match - gives an honest V0/V1(/V2 via hardtests_tests)/V3 pipeline for a
coherent subset, instead of V1 silently degrading to "= V0" for most of a
mixed-platform pool. This does narrow the pilot away from plan.md §2's
"algorithmic coding, ~500 problems from HardTests" framing (which didn't
specify single-platform) - flagged for confirmation rather than done
silently. **User confirmed: restrict the pilot to Codeforces.**

### 2026-09-03 — Built and verified the real V0+V1 pipeline on Codeforces
- `c1/codeforces.py`: parses `contest_id`/`index` out of each Codeforces
  problem's URL (`codeforces.com/problemset/problem/<id>/<letter>`), streams
  `sigcp/hardtests_problems` filtered to `platform == "codeforces"`, then
  streams `deepmind/code_contests` (train/valid/test splits) looking for
  matching `(cf_contest_id, cf_index)` pairs, caching the joined pool to
  `c1/data/codeforces_pool.jsonl`.
- **First real run: 35/35 matched (100%)** - every sampled Codeforces problem
  in HardTests had a `code_contests` counterpart, with real depth (1-40
  private tests vs. 1-4 public ones per problem, plus hundreds of `solutions`
  and `incorrect_solutions` per problem).
- Refactored `c1/verifiers.py` so V0 and V1 share one grading function
  (`make_grader_from_tests`), differing only in which test list they're
  built from - V0 from HardTests' `public_test_cases`, V1 from
  `code_contests`' `public_tests + private_tests` (deliberately excluding
  `generated_tests`, which are CodeContests' own synthetic additions, not
  part of what the original judge ran).
- **Found a second real bug before trusting any result**, same
  "verify, don't assume" habit as the CRLF fix: a naive "does this solution
  look like Python" content-sniff (checking for the substring `"print("`)
  matched a **Java** solution, because `pw.print(x)` (a `PrintWriter` call)
  contains that substring too. Fixed properly by using `code_contests`'
  actual `solutions.language` field instead of sniffing - confirmed the enum
  values empirically against real code rather than trusting memory:
  `1`=Python (old-style), `2`=C++, `3`=Python 3 (`input()`-based), `4`=Java.
  `find_python3_solution` in `c1/codeforces.py` now filters on `language == 3`
  directly.
- **Result across 30 problems with a real Python 3 solution: 23/30 (77%)
  score exactly gold=1.0 / wrong=0.0 on both V0 and V1**, as they should.
  7 didn't, and they're genuinely informative, not just noise - two distinct
  patterns:
  1. **V0 fails (0.0) while V1 partially passes** (`1003_b`, `1003_c`): V0
     uses HardTests' own copy of the public tests, V1 uses `code_contests`'
     copy - two independently-scraped copies of nominally "the same" public
     tests, from different pipelines. They can disagree (formatting,
     whitespace, an off-by-one in how each source captured the sample) even
     when both graders are implemented correctly.
  2. **V0 passes fully but V1 only partially** (`1005_e1`, `1005_f`,
     `1006_b`, and `1004_b` failing both): hypothesized (wrongly, see next
     entry) to be a subprocess-timeout artifact.
- Not yet done at this point: scaling the pool from 35 to the full ~150 (100
  target + buffer), and V2 (still needs a real `hardtests_tests` row decoded
  - see its base64/zlib/pickle encoding in that dataset's card, captured
  earlier in this log).

### 2026-09-03 — Chased the timeout hypothesis; it was wrong. Found the real cause.
Timed every test (public + private) for the 6 anomalous problems, recording
timeout/wrong/error/elapsed separately instead of just the pass/fail
fraction. **The timeout theory is refuted, cleanly:** `max_elapsed` across
every single test, every problem, was 0.03s. Zero `TimeoutExpired`s. Worth
stating plainly that the hypothesis was wrong rather than quietly moving on -
that's what checking it was for.

The real breakdown per problem (`ok`/`wrong`/`error` out of total tests):
`1003_b` 16/43 ok, all rest wrong; `1003_c` 3/8 ok; `1004_b` 0/15 ok (all
wrong); `1005_e1` 31/44 ok + 7 real runtime errors; `1005_f` 9/24 ok;
`1006_b` 9/28 ok. All genuine wrong-output or runtime-error failures, not a
harness artifact.

**Traced `1004_b` (the cleanest case - fails 100% of tests, including its
own public ones) down to the actual solution source.** Its "Python 3"
solution has the real algorithm - which reads extra input, builds two
candidate strings, and picks whichever scores higher via `calc()` - sitting
inside a `"""..."""` triple-quoted block, i.e. **commented out**. The one
live line just prints a hardcoded `'10' * (n//2)` pattern unconditionally.
Ran it by hand: input `"6 3\n5 6\n1 4\n4 6"` produces `"101010"`, expected
`"010101"` - deterministic, not flaky. This is a genuinely broken solution
*string* sitting in `deepmind/code_contests`' `solutions` field, not a grader
bug - `code_contests` calls its own solutions "High reliability" as a
dataset-level claim, which doesn't mean every individual entry is defect-free.

**Conclusion:** the V0/V1 grading mechanics are correct (confirmed by the
23/30 clean pass rate plus this one now fully explained). The remaining
anomalies split into two real, different causes, neither a harness bug:
independently-scraped "public" tests disagreeing between HardTests and
`code_contests` (`1003_b`/`1003_c`), and individual flawed/incomplete
solution strings in `code_contests` itself (`1004_b`, plausibly others -
Codeforces' own post-contest "hacking phase," where other competitors submit
counter-examples against accepted solutions after the contest ends, is a
plausible reason a solution that was genuinely accepted at submission time
could still fail some of `code_contests`' broader private/generated tests -
not verified this session, flagged as a hypothesis not a fact).

**The actual fix, and it's a direct callback to code already in this repo:**
don't trust the first `language == 3` solution found - validate it the way
`envcheck/probes/gold_sanity.py` already validates a gold solution (does it
actually pass?) before treating it as ground truth.

### 2026-09-03 — Added the gold-sanity-style fix; measured its actual effect
`find_validated_python3_solution` in `c1/codeforces.py`: tries up to 8
`language == 3` candidates per problem, keeps the first that scores 1.0 on
both V0 and V1 - exactly `envcheck/probes/gold_sanity.py`'s check ("does the
known-correct answer actually pass?"), applied here before trusting a
solution as a problem's gold reference.

**Measured, not assumed, how much it actually helped:** of the 30 problems
with at least one Python 3 solution, 24 now get a validated gold solution
(up from the prior 23/30 that happened to pass on the *first* untried
solution). One problem (`1003_b`) that failed before is now fixed by trying
a later candidate. The other 6 - `1003_c`, `1003_e`, `1004_b`, `1005_e1`,
`1005_f`, `1006_b` - still have no solution that cleanly passes both within
the 8-candidate budget. Not chasing these further right now: 24/30 (80%) is
a reasonable, honest number for real third-party data with the known-real
causes already identified (independent-scrape test mismatches, genuinely
flawed solution entries) - further gains would mean either raising
`max_candidates` past 8 or building actual per-problem diagnosis, both
lower-value than moving forward with a pool that already excludes the
unvalidated 20%.

**Practical effect on pool-building going forward:** a pilot problem is only
usable once it has a validated solution. Filtering to that is `c1/`'s next
integration step (not yet wired into `build_pool` - currently a separate
function callers must call themselves), before scaling from 35 to the full
~150-problem target.

### 2026-09-03 — Wired validation into a real build_validated_pool; found a fourth real bug scaling to 150
Added `build_validated_pool` (`c1/codeforces.py`): fetches, joins, and
validates in one call, keeping only problems with a confirmed-passing
solution, with a round-based retry that overfetches more if the yield rate
undershoots the measured ~0.6 (see the constant `_MEASURED_YIELD_RATE`,
labeled explicitly as a measurement from one run, not a guarantee).

**First attempt at target_count=150 crashed** with
`FileNotFoundError: [WinError 206] The filename or extension is too long`,
from deep inside `subprocess.run` -> `_winapi.CreateProcess`. Cause: every
grader call ran candidates via `python -c <candidate_code>`, which puts the
*entire source* on the command line - fine for short solutions, but Windows
has a real command-line length ceiling, and one genuine editorial solution
partway through the 150-problem run was long enough to blow past it. Not a
malformed or adversarial input - an ordinary, if verbose, real solution.

Fixed in `c1/verifiers.py`'s `make_grader_from_tests`: write the candidate to
a temp `.py` file and run `python <path>` instead of `-c <code>` - the
standard fix, no length ceiling, cleans up the temp file in a `finally`.
Re-ran the 35-problem validated-solution check after the fix: still 24/30,
confirming the fix changed nothing about correctness, only removed a failure
mode that hadn't been triggered yet at n=35 but was always latent - one more
instance of the same lesson as the CRLF and Java-detection bugs: an approach
that works on a small sample can still have a real ceiling that only shows up
at scale, and the fix each time was to stop taking a shortcut (loose sniffing,
literal `-c`, implicit newline handling) that happened to work in the cases
tested so far.

**Reran the full 150-problem build after the fix: succeeded, one round,
150/150.** Scanned 262 distinct Codeforces problems to get there - a 57.3%
yield (150/262), close to the 60% estimate `_MEASURED_YIELD_RATE` was set
from, so that constant is holding up at 4x the scale it was measured at.
Took 806s (~13.4 min) - each of 150 problems needed up to 8 validation
candidates x up to ~45 tests x a real `python <tempfile>` subprocess spawn,
so multi-minute runtime for this step is expected, not a red flag. Cached to
`c1/data/validated_codeforces_pool.jsonl` (gitignored, ~150 rows, each with
`hardtests`, `codecontests`, and `validated_solution`). **This is the actual
plan.md §8 checklist item, done for real:** "select 100 problems; write
V0/V1 verifiers" - 150 (buffer over the 100 target), each with a grader for
both conditions and a confirmed-passing reference solution, not synthetic or
assumed data.

### 2026-09-03 — Built and verified V2 (HardTests-generated tests, HackGen included)
Decoding a real `sigcp/hardtests_tests` row needed two separate fixes beyond
just calling `load_dataset(..., streaming=True)` (which had already been
shown to hang on this dataset - see the earlier "Built and verified V0"
entry): plain row-by-row streaming stayed stuck with no progress, so found
matches for our pool's pids by reading just the cheap `pid` column of each
shard via direct `fsspec` range-reads (fast - found a match in shard 0
almost immediately) - then, once a shard was confirmed relevant, pulling its
*other* columns (`test_cases_kit`, `mapping`, the actual `test_cases` blob)
via range-reads timed out repeatedly (`FSTimeoutError`) even at a 300s
limit - that data is evidently too large for partial HTTP range fetches to
reliably assemble. Fixed by downloading the whole shard file locally with
`huggingface_hub.hf_hub_download` (a proper single resumable download)
instead of fighting range-reads for columns already known to be present.
Both pieces now live in `c1/hardtests_tests.py`.

**Confirmed the full generator -> mapping -> test_cases chain by hand, not
just by reading the schema.** For `codeforces_1047_d`: `HackGen` produced
two real Python functions,
`gen_hacking_input_edge_case` (fixes n=1, randomizes the rest) and
`gen_hacking_input_large_values` (n=m=10^9, a max-scale stress test).
`mapping.HackGen` pointed the first at test_cases indices [28..37] and the
second at [38]. Decoded `test_cases[38]` by hand:
`{"input": "1000000000 1000000000", "output": "1000000000000000000"}` -
exactly what `gen_hacking_input_large_values` should produce. The pipeline
does what the schema says it does.

**`output_judging_function`'s real signature, confirmed from three actual
examples, not the dataset card alone:**
`output_judging_function(input_str, candidate_output, reference_output) -> bool`.
It's `None` for many problems (plain problems where exact string match is
correct - not every V2 problem needs a custom checker, refining what the
earlier "Why V2 can't just be string-compare" concept entry implied). Wired
into `make_v2_grader` (`c1/verifiers.py`): when present, it's executed as
its own subprocess (input/candidate/reference passed as JSON over stdin, to
avoid the same command-line-length problem the fourth bug hit) - same
sandboxing caveat as candidate code, since it's LLM-generated too, not
hand-vetted.

**End-to-end test: 15/15 pool problems fully clean across V0, V1, *and*
V2 simultaneously** (gold=1.0 / wrong=0.0 on all three), including 3 of the
15 that have a real custom `output_judging_function` - confirming that path
works, not just plain exact-match. Only checked 15 of 150 so far (V2 data
was only fetched for 17/150 within a 30-shard scan budget - fetching the
rest is straightforward, same function, no new blocker). **V0, V1, and V2
are now all real and independently verified** - the three conditions
plan.md §2 needs before V3 (which depends on C2, still blocked).

---

## Concepts

### The hacker-fixer loop (harden-v0)
Three LLM agents play fixed roles against one task (a directory with
`tests/`, `solution/`, and either a `reference.py` or an agent-based solver):

- **Hacker** — told explicitly to earn full reward *without* solving the task.
  Attacks up to `--hacker-retries` times (default 3) per iteration.
- **Fixer** — sees the hack trajectory + verifier source, patches *any* task file
  to block that specific exploit. Its edits only count if committed to a git repo
  at `/logs/artifacts/` inside its container — editing `/tests/` directly is
  silently thrown away when the container exits. Can mark a hack `.legitimate`
  instead of patching, if it decides the "exploit" was actually a valid solution
  the verifier under-rewarded (`--no-legitimate-marker` turns this off, forcing
  every flagged hack to be patched).
- **Solver / Oracle** — the validity check. Either a deterministic reference
  solution copied in (`--oracle`) or an actual agent trying to solve the patched
  task (default). Must still pass after every fixer patch, or the patch is
  reverted and the fixer gets another turn.

One iteration = hacker attacks → fixer patches → solver validates. Up to
`--max-iterations` (default 10). A task is **robust** once the hacker fails every
retry in an iteration; it hits **max_iterations** if the loop exhausts its budget
first without the hacker running dry.

This is the mechanism plan.md's C2 wants to extend: harden-v0's fixer patches
until the hacker gives up, but nothing here checks whether patches over-tighten
the verifier and reject *legitimate* solutions along the way — that's exactly the
gap C2's "certified adversary" (reject false exploits before they reach the
fixer) and "solver ensemble + validity constraint" (reject a patch that drops
too much legitimate-solution pass rate) are designed to close. Baseline loses
~11pp legitimate accuracy per plan.md §0 — that number is presumably measured by
running harden-v0 as-is and watching the oracle/solver pass rate fall across
iterations.

**Optional `--replay-enabled`:** after the solver accepts a fix, a constrained
hacker re-attempts the *original* exploit against the patched task. If it still
lands, the fix is rejected even though the solver approved it — catches patches
that satisfy the solver by accident without actually closing the hole.

**Pooled ("jumper") mode (`--pool-enabled`):** fixes found on one task are pushed
to a shared git repo (served by a host-side `git daemon`) that other tasks pull
from, so a fix discovered on task A can pre-empt task B's hacker without B ever
having to rediscover it. Linux-only (needs `host.docker.internal:host-gateway`).
Not needed for the Week 1-2 "run loop on 5 tasks" smoke test — that's plain
per-task hardening, pool mode is an optimization for hardening *many* tasks that
share exploit families.

### terminal-wrench's task format
Each of terminal-wrench's 331 tasks stores, per model that attacked it,
`original_task/{instruction.md, tests/, solution/, environment/}` — this is
already Harbor's expected task-directory shape, which is exactly what
harden-v0's `--tasks-dir` wants. So "run loop on 5 tasks" (plan.md §8) means:
pick 5 `<task_id>/<model>/original_task/` dirs, copy them into a flat
`tasks/<task_id>/` pool, and point harden-v0 at that — no format conversion
needed. Each task also ships real hack trajectories and an 11-category exploit
taxonomy (hollow-implementation, output-spoofing, constraint-loophole,
structural-extraction, binary-hijacking, keyword-gaming,
algorithmic-simplification, mutable-input-tampering, metric-spoofing,
security-downgrading, deceptive-rationalization) — worth comparing against
envcheck's own E1-E14 exploit pack (plan.md §1a) for gaps once we're back in
that code.

### `--oracle` vs agent solver, `--kernelbench-mode`
Two independent flags (CLAUDE.md spells this out explicitly since it's an easy
thing to get backwards): `--oracle` picks *how validity is checked*
(deterministic reference vs. an actual solving agent); `--kernelbench-mode`
picks *which prompts/thresholds* are used (speedup-based KernelBench framing vs.
generic pass/fail). They usually travel together for KernelBench tasks
specifically (which need both: `--hack-threshold 10 --solver-threshold 0.5`) but
nothing forces the pairing. For C1's coding verifiers (plan.md §2, V0-V4) the
generic pass/fail framing is the relevant one, not KernelBench.

### Why harden-v0 needs Linux, not just "Docker installed"
Two independent things assume a POSIX host: `harden/durable.py` imports `fcntl`
(Windows has no equivalent — file-locking is a genuinely different API) for its
JSON-backed resume/durability mechanism, and pooled mode's container-to-host
networking depends on `host.docker.internal:host-gateway`, a value Docker only
added on Linux Engine ≥20.10. Docker Desktop on Windows runs containers inside a
managed Linux VM already, but that doesn't help here — the `fcntl` import happens
in the *host* Python process running `python -m harden`, before any container is
even started. The fix has to be running harden-v0's own Python process inside a
real Linux environment (WSL2), not just pointing Docker somewhere Linux-y.

### Why V2 can't just be "more input/output pairs to string-compare"
V0 does exact string comparison because public test cases are small,
hand-picked, unambiguous samples. HardTestGen's `output_judging_function`
being *code*, not a boolean flag, means some problems have multiple valid
correct outputs (e.g. "any valid topological order", "any of several optimal
solutions") and grading them requires running a real checker, not `==`. This
is a materially different verifier shape from V0 - V2's grader has to execute
two pieces of untrusted-ish code per candidate (the candidate itself, and the
judge function), not one. Worth remembering when V2 actually gets built: it's
not V0 with a bigger test list, it's a different grading mechanism.

### HackGen vs LLMGen/RPGen/SPGen
Four generator strategies produce candidate test *inputs* for a problem
before validation: `HackGen` is explicitly adversarial (built to probe for
verifier weaknesses - the plan cites it as the source of exploit-hardening
signal in V2); `LLMGen`, `RPGen`, `SPGen` read as more general-purpose input
generation (LLM-written, random-program-based, and a fourth strategy,
respectively - names alone, haven't read the generator code itself to
confirm). All four get filtered through the same `input_validator` before
becoming real test cases, per the `mapping` field linking generator ->
accepted input indices.

### A general lesson from the CRLF bug: don't trust subprocess text-mode I/O silently
`subprocess.run(..., text=True)` does newline translation on both write and
read, and that translation composes badly with data that already contains
platform-specific line endings baked into a string literal - not a rare edge
case here, since HardTests' inputs universally ship with literal `\r\n`. The
symptom (a gold solution scoring 33% instead of 100%) looked like it could
have been the solution being wrong, the data being wrong, or the grader being
wrong - only checking by hand with a minimal 2-line repro (`c1/verifiers.py`'s
`_to_lf` docstring) separated those. General habit worth keeping for the rest
of this project: when a "known-correct" thing fails a check, suspect the
harness before the thing.

### Language labels in scraped solution datasets aren't reliable enough to trust blindly
Two separate instances now: `sigcp/hardtests_problems` had a solution whose
`language` field said `"cpp"` but whose `code` was plainly Python
(`c1/data.py`'s `python_solution` docstring); naive content-sniffing on
`deepmind/code_contests` matched a Java solution because `pw.print(x)`
contains the substring `"print("`. The fix in both cases was the same shape:
don't infer the language from a loose signal (a metadata field that can be
wrong, or a substring that can appear in the wrong language) - either use a
dataset's own reliable enum field once you've confirmed what its values
actually mean (`code_contests.solutions.language`, confirmed empirically
against real code, not from memory), or validate the *result* directly
(gold-sanity-style: does it actually pass?) rather than trusting the label
that got you there.
