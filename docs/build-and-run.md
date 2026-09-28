# Build, test, and run

## 1. Prerequisites

- Python 3.10 or later. Development verification used Python 3.14.6.
- A terminal; the Windows examples below use PowerShell. The masked API-key prompt requires PowerShell 7.
- The project files, including `support_lab/data/` and `tests/`.
- Only for live Jev: an existing TypeSafe API key and HTTPS access to `api.typesafe.ai`.

No Node.js, npm, Docker, database, third-party Python packages, or frontier-model API key is needed. The project is a command-line application, not a web server.

## 2. Open the project

From the directory containing your checkout:

```powershell
Set-Location ./jev-playground
python --version
python -m support_lab --help
```

If your checkout has a different name, substitute that directory name. If you are already in the project root, skip `Set-Location`. Run all subsequent commands from that root directory. If Windows recognizes `py` but not `python`, use `py -3` instead of `python` throughout and confirm it selects Python 3.10 or newer.

An isolated environment is optional because there are no dependencies to install:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m support_lab --help
```

When using the environment, replace `python` in subsequent commands with `.\.venv\Scripts\python.exe`. Activation is unnecessary, so no PowerShell execution-policy changes are required. There is no `pip install` step or requirements file.

## 3. Build and verify

Python executes this project's source directly. There is no required build step, wheel, executable, or `dist` artifact. Validate a checkout with the test suite:

```powershell
python -m unittest discover -s tests -v
```

Expected result: 16 passing tests and `OK`. All tests run offline, including Jev integration tests, which substitute synthetic HTTP responses. Tests neither need a key nor call a paid model.

An optional syntax-compilation check is available:

```powershell
python -m compileall -q support_lab
```

Successful compilation exits without output and creates ignored `__pycache__` files; it does not package the application. After code changes, rerun the test suite.

## 4. Execute offline — no key or charges

List the bundled tickets and run the first example:

```powershell
python -m support_lab tickets
python -m support_lab run --ticket T01
```

The ticket list contains T01–T12. The T01 run should show `Category: exports`, `Outcome: human_review`, blockage/deadline reasons, and a draft citing local knowledge documents. It displays a mock disclaimer and API spend of $0. Nothing is sent to a customer.

Inspect the full trace and try a custom ticket:

```powershell
python -m support_lab run --ticket T01 --json
python -m support_lab run --text "Something is wrong"
python -m support_lab run --ticket T02 --threshold 0.95
```

The ambiguous custom ticket routes to human review. Raising the confidence threshold makes routing more conservative. Mock probabilities are illustrative, not real Jev results.

## 5. Inspect Jev requests for free

```powershell
python -m support_lab run --ticket T01 --dry-run
```

Expected JSON contains `dry_run: true`, `api_calls: 0`, and two request payloads with typed questions. No key or network access is required. The initial payload is exact; the second uses an illustrative draft because real triage may select different evidence.

## 6. Execute with real Jev

This is the only documented execution path that calls a paid API. Draft generation still uses the local mock. In PowerShell 7, enter your existing TypeSafe key through a masked prompt and run one ticket:

```powershell
$env:TYPESAFE_API_KEY = Read-Host 'TypeSafe API key' -MaskInput
python -m support_lab run --ticket T01 --jev real --json
```

Keep the key in your environment; do not put it in source code, command-line arguments, saved traces, or chat. The application does not load `.env` files. A configured key alone does not turn on live mode: each live command must specify `--jev real`.

Inspect these fields in a successful live trace:

| Field | What it tells you |
| --- | --- |
| `stages[].provider` | `jev-api` for triage/review; `mock-frontier` for drafting |
| `triage.category` | Jev's selected area, probabilities, and confidence |
| `triage.impact` | Fractional score and probability for each impact level |
| `review` | Jev's diagnostic-request and unverified-promise checks |
| `usage.live_api_calls` | Two successful live calls for a completed run |
| `usage.jev_responses` | Actual model IDs and per-call token counts |
| `usage.api_cost_usd` | Null: actual billing is unknown to the application |

The default is pinned to `jev-1.13.0`. To explicitly choose the moving stable alias and a different timeout instead of the default command:

```powershell
python -m support_lab run --ticket T01 --jev real --model jev-latest --timeout 20 --json
```

Each invocation can make up to two billable attempts. It has no automatic retries; timeouts and failures may still incur charges. The default timeout is 30 seconds per request, and allowed values are greater than zero through 120 seconds. The two-call limit is not a dollar budget, and free credits are not assumed. Review actual spend in your TypeSafe account.

Remove the key from this shell when finished:

```powershell
Remove-Item Env:TYPESAFE_API_KEY
```

Real model answers need not match mock answers. The adapter has been verified using synthetic HTTP responses, not a live account smoke test.

## 7. Save traces and compare workflows

```powershell
python -m support_lab run --ticket T01 --output trace-offline-t01.json
python -m support_lab run --ticket T01 --mode frontier-only --json
python -m support_lab evaluate --split dev
python -m support_lab evaluate --split test --json --output trace-evaluation-test.json
```

Output files are JSON regardless of console format. Use a new filename each time; existing files are never overwritten. The parent directory must already exist. Traces contain ticket and draft text, so use fictional or otherwise appropriate input when saving or sharing them.

`evaluate` compares two mock workflows and stays offline. It does not accept `--jev real`. The frontier-only mode is also mocked and cannot be combined with real Jev. Offline evaluation metrics are a plumbing demonstration, not a real model benchmark.

To save a real result, configure the key as in step 6 and explicitly opt in:

```powershell
python -m support_lab run --ticket T01 --jev real --output trace-real-t01.json
```

This is another potentially billable run, not a conversion of a previous trace.

## 8. Troubleshooting

| Symptom | Action |
| --- | --- |
| `python` is not recognized | Try `py -3 --version`; otherwise install/configure Python 3.10+ before proceeding. |
| `No module named support_lab` | Change to the project root containing the `support_lab` directory. |
| `-MaskInput` is not recognized | Use PowerShell 7 for the documented masked prompt, or configure the process environment through your existing secret-management workflow. |
| Missing `TYPESAFE_API_KEY` | Set it in the same shell as the live command; `.env` files are not read. |
| HTTP 401 or 403 | Check the key or account access. Do not include the key in error reports. |
| HTTP 422 | Check the selected model and request schema against TypeSafe's API documentation. |
| HTTP 429 or 529 | Wait before manually trying again; the application does not retry automatically. |
| Timeout or connection error | Check connectivity; a request may have been billed even if no result arrived. |
| Schema-validation error | The API response did not match the required contract. No mock fallback is used. |
| Output already exists / filesystem error | Choose a new filename in an existing writable directory. A filesystem failure after inference does not undo API charges. |
| Unknown ticket or invalid threshold | Run `tickets`; use T01–T12 and a threshold between 0 and 1. |

For available options:

```powershell
python -m support_lab run --help
python -m support_lab evaluate --help
```

Commands exit when finished; there is no server to stop. Return to the [README](../README.md), [requirements](requirements.md), or [architecture](architecture.md) for the learning goals and design.
