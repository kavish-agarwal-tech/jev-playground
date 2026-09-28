# Support Decision Lab

A learning project exploring **Jev typed decisions + mocked frontier-LLM drafting** for SaaS support. By default both providers are deterministic mocks and everything is offline and free. Opt in to the real Jev API for targeted learning. No third-party Python packages are required.

## Build and execution guide

See [Build, test, and run](docs/build-and-run.md) for prerequisites, Windows setup, expected output, real-Jev configuration, and troubleshooting.

There is no compilation, dependency installation, or server to start. With Python 3.10+ installed, open PowerShell in the directory containing your checkout and verify the application:

```powershell
Set-Location ./jev-playground
python --version
python -m unittest discover -s tests -v
python -m support_lab run --ticket T01
```

## Run

From the project directory:

```powershell
python -m support_lab tickets
python -m support_lab run --ticket T01
python -m support_lab run --ticket T01 --json
python -m support_lab run --text "Something is wrong"
python -m support_lab run --ticket T02 --threshold 0.95
python -m support_lab run --ticket T01 --mode frontier-only
python -m support_lab evaluate --split dev
python -m support_lab evaluate --split test --json
python -m support_lab run --ticket T01 --output trace.json
python -m unittest discover -s tests -v
```

Output files must not already exist. Use a new filename for each saved experiment.

## What to inspect
In JSON output, compare `triage.category` (Choice), `triage.impact` (Score), and `triage.multiple_users` (Noul). Follow evidence into the draft, then inspect post-draft checks and routing reasons. `stages` shows which provider owns each step. A `draft_ready` result still never sends a message.

Try T01 for severe impact, T04 for ambiguity, and T06 for urgency without blocked work. Raise the threshold and watch routine tickets move to review. Use the development split for these experiments and the held-out test split to check a selected policy.

## Use real Jev
First inspect the typed questions and payloads without making API calls:

```powershell
python -m support_lab run --ticket T01 --dry-run
```

For an existing TypeSafe API key, set it in the current PowerShell session. PowerShell 7's masked prompt avoids placing the key itself in shell command history:

```powershell
$env:TYPESAFE_API_KEY = Read-Host 'TypeSafe API key' -MaskInput
python -m support_lab run --ticket T01 --jev real --json
Remove-Item Env:TYPESAFE_API_KEY
```

The application reads the process environment only, not `.env` files. Do not paste your key into chat or source files. Without a key, live mode stops with a clear error. Having a key configured does not enable live mode automatically.

`--jev real` sends the ticket to TypeSafe for four batched triage questions, then sends the ticket and locally generated draft for two batched review questions. This makes at most **two billable API calls per ticket**, with a 30-second timeout per call and no automatic retries. A failed or timed-out request may still be billed. There is no dollar-budget guarantee or assumed free credit. The frontier model remains mocked. The `evaluate` command remains entirely offline so a benchmark cannot accidentally trigger a batch of paid calls.

The default model is pinned to `jev-1.13.0`; override with `--model jev-latest` when desired. Inspect `usage.jev_responses` for the actual model version and token usage. Live `api_cost_usd` is null because the application does not know your billing terms; check your account for actual spend. `--timeout` accepts a value greater than zero up to 120 seconds. HTTP errors, malformed responses, and timeouts stop the run without silently falling back to a mock.

Try the same ticket once with `--jev mock` and once with `--jev real`. Compare category probabilities, the fractional impact score, and routing reasons. In particular, test paraphrases and negation that the keyword mock misses. `--dry-run` shows the exact initial payload and an illustrative second payload; actual triage can change the retrieved evidence and draft.

HTTP contract: [TypeSafe API reference](https://docs.typesafe.ai/api). Model selection: [Models](https://docs.typesafe.ai/models). Checked September 28, 2026. Automated integration tests use synthetic HTTP responses; no live API smoke test has been performed.

## Honest limits
Offline mode demonstrates architecture, not actual Jev inference. Its mocks use lexical rules and canned, evidence-based drafts; they cannot perform frontier reasoning. Mock scores and probabilities are invented demonstration values. The two mock decision adapters intentionally share heuristics, so an offline benchmark tie says nothing about real providers. Offline timings measure local execution and spend is $0; live timings include network time. Negation, paraphrases, and subtle policy violations may fool the mocks. Real probabilities also need domain evaluation. Human review of drafts remains necessary.

## Design documents

- [Build, test, and run](docs/build-and-run.md)
- [Requirements](docs/requirements.md)
- [Architecture and learning sequence](docs/architecture.md)

The initial dataset has 12 manually labeled synthetic tickets and 10 knowledge documents. Expand and independently review the dataset before drawing conclusions about model quality. A real frontier adapter and a browser interface are future extensions, not included features.
