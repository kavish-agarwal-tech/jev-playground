import copy
import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from support_lab.core import run
from support_lab.jev import (DEFAULT_MODEL, ENDPOINT, JevError, RealJev,
                             TRIAGE_QUESTIONS, http_post, preview_requests)


def response_for(body):
    """Synthetic HTTP response fixture, not a captured Jev result."""
    answers = {}
    for key, question in body["questions"].items():
        kind = question["type"]
        if kind == "choice":
            answers[key] = {"type": kind, "choice": "exports", "confidence": .82,
                            "probabilities": {k: .9 if k == "exports" else .025 for k in question["criteria"]}}
        elif kind == "score":
            answers[key] = {"type": kind, "score": 1.7, "confidence": .7,
                            "probabilities": {"0": .1, "1": .1, "2": .8},
                            "legend": {str(i): label for i, label in enumerate(question["criteria"])}}
        else:
            answers[key] = {"type": kind, "noul": .95 if key in ("multiple_users", "requests_diagnostics") else .05}
    return {"model": DEFAULT_MODEL, "answers": answers, "usage": {"input_tokens": 300, "output_tokens": 30}}


class JevTests(unittest.TestCase):
    def test_two_batches_fractional_score_and_usage(self):
        bodies = []
        def transport(body, key, timeout):
            self.assertEqual(key, "test-secret")
            bodies.append(body)
            return response_for(body)
        provider = RealJev(api_key="test-secret", transport=transport)
        result = run("Our team cannot export", decision_provider=provider)
        self.assertEqual(len(bodies), 2)
        self.assertEqual(set(bodies[0]["questions"]), set(TRIAGE_QUESTIONS))
        self.assertEqual(bodies[1]["state"]["draft"], result["draft"])
        self.assertEqual(result["triage"]["impact"]["score"], 1.7)
        self.assertEqual(result["routing"]["action"], "human_review")
        self.assertEqual(result["usage"]["input_tokens"], 600)
        self.assertEqual(result["usage"]["live_api_calls"], 2)
        self.assertIsNone(result["usage"]["api_cost_usd"])
        self.assertNotIn("test-secret", json.dumps(result))
        self.assertEqual(result["stages"][2]["provider"], "mock-frontier")
        with self.assertRaisesRegex(JevError, "Two-call limit"):
            provider.triage("invoice")
        self.assertEqual(len(bodies), 2)

    def test_invalid_responses_fail_closed(self):
        body = {"questions": TRIAGE_QUESTIONS}
        valid = response_for(body)
        invalids = [None, {}, {**valid, "answers": {}}, {**valid, "usage": {}}]
        for value in (float("nan"), -1, 2, True):
            bad = copy.deepcopy(valid)
            bad["answers"]["deadline"]["noul"] = value
            invalids.append(bad)
        bad = copy.deepcopy(valid)
        bad["answers"]["category"]["probabilities"]["exports"] = .4
        invalids.append(bad)
        for response in invalids:
            with self.subTest(response=response):
                provider = RealJev(api_key="test", transport=lambda *args: response)
                with self.assertRaisesRegex(JevError, "schema validation"):
                    provider.triage("test")
                self.assertEqual(provider.calls, 1)

    def test_http_contract(self):
        with patch("support_lab.jev.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"ok":true}'
            self.assertEqual(http_post({"model": DEFAULT_MODEL}, "test-secret", 10), {"ok": True})
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, ENDPOINT)
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
            self.assertEqual(json.loads(request.data)["model"], DEFAULT_MODEL)
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 10)

    def test_http_failures_do_not_leak_or_retry(self):
        errors = [HTTPError(ENDPOINT, 401, "test-secret", {}, io.BytesIO(b"test-secret")),
                  HTTPError(ENDPOINT, 429, "test-secret", {}, io.BytesIO(b"test-secret")),
                  URLError("test-secret"), TimeoutError("test-secret")]
        for error in errors:
            with patch("support_lab.jev.build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(JevError) as caught:
                    http_post({}, "test-secret", 10)
                self.assertNotIn("test-secret", str(caught.exception))
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_preview_and_defaults_never_call_network(self):
        with patch("support_lab.jev.http_post", side_effect=AssertionError("Network forbidden")):
            result = preview_requests("export is slow")
            self.assertEqual(result["api_calls"], 0)
            self.assertEqual(len(result["requests"]), 2)
            self.assertEqual(run("invoice")["usage"]["api_cost_usd"], 0)

    def test_cli_real_requires_key_and_dry_run_does_not(self):
        env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
        base = [sys.executable, "-m", "support_lab", "run", "--ticket", "T01", "--jev", "real"]
        result = subprocess.run(base, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("TYPESAFE_API_KEY", result.stderr)
        result = subprocess.run(base + ["--dry-run"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["dry_run"])
        result = subprocess.run(base + ["--mode", "frontier-only"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_settings_validation(self):
        for timeout in (0, -1, float("nan"), 121):
            with self.assertRaises(JevError):
                RealJev(api_key="test", timeout=timeout)
        with self.assertRaises(JevError):
            RealJev(api_key="test\r\ninvalid")


if __name__ == "__main__":
    unittest.main()
