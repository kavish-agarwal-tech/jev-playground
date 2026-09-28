# Requirements: Support Decision Lab

## Purpose
Learn how a decision model (Jev) and a frontier language model cooperate in a SaaS support workflow. The fictional product is ReportFlow, a team reporting application. The first release must run offline, with no API keys, subscriptions, external services, or third-party Python packages.

## User and use cases
The learner runs sample or custom tickets, inspects routing and model boundaries, changes the decision threshold, and compares hybrid and frontier-only workflows. A support reviewer receives a draft and evidence, never an automatically sent message.

## Functional requirements
1. List bundled tickets and run a ticket by ID or supply custom text.
2. Hybrid workflow: triage with a mock Jev adapter; retrieve relevant local documents; draft with a mock frontier adapter; review the draft with Jev; apply routing rules in code.
3. Demonstrate Choice (product area), Score (reported impact), and Noul (multiple users affected). Batch independent questions against the same state.
4. Include other/uncertain categories and route uncertain cases to human review. Recognize reported urgent deadlines separately from impact.
5. Retrieve documents using a transparent lexical method and attach source IDs to draft recommendations.
6. Check drafts for an unverified fix promise and a request for diagnostics. These checks occur after generation.
7. Expose triage, evidence, draft, review, routing reasons, provider names, calls, and measured local execution time in JSON traces.
8. Run a frontier-only baseline on identical tickets and knowledge documents. Compare category accuracy, urgent-case recall, review rate, and local execution time.
9. Separate development and held-out fixtures. Labels are evaluation-only and never passed to providers.
10. Save a trace or evaluation report only when an explicit output path is supplied.
11. Never send customer messages, change accounts, or issue refunds. Paid API access is disabled by default and permitted only through `run --jev real`.
12. Support real Jev triage and review with mocked drafting; require TYPESAFE_API_KEY and explicit live selection. Limit each adapter to two attempted calls, with timeouts and no automatic retries.
13. Provide a key-free, network-free request preview via `--dry-run`. Keep bulk evaluation offline.
14. Validate API response types, options, distributions, and usage; fail closed on API errors. Preserve actual response model IDs and token counts. Report unknown live cost as null, never zero.

## Acceptance criteria
- `python -m support_lab tickets` lists realistic scenarios.
- `python -m support_lab run --ticket T01` produces a complete hybrid trace with evidence and a draft.
- `python -m support_lab run --text "Something is wrong"` routes to review.
- `python -m support_lab run --ticket T01 --mode frontier-only` skips Jev entirely.
- `python -m support_lab evaluate --split test` evaluates both modes on the same held-out tickets.
- Threshold input outside [0,1], empty text, unknown IDs, and invalid output paths produce useful errors.
- Automated tests cover routing, uncertainty, retrieval, draft checks, baseline separation, and metric calculation.

## Boundaries and limitations
Mocks exercise the architecture; they do not reproduce Jev or frontier-model intelligence. Mock probabilities are hand-authored illustrative distributions, not calibrated estimates. Offline timings do not predict API latency. Offline spend is zero; live calls may incur charges and actual billing is not calculated. No imaginary token-cost savings are reported. Draft quality needs human assessment; routing accuracy is not a proxy for correctness of advice. Synthetic fixtures are small and not a production benchmark.

## Future scope
Real Jev is now an opt-in feature; a real frontier adapter remains future scope. Before broad live use, evaluate calibration on manually labeled domain data and configure account-level spending controls if available. The local two-call cap is not a monetary budget. Add a browser interface or persistent review queue only when useful for the learner.
