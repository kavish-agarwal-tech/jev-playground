"""Transparent mocks: architecture demonstrations, not model emulation."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Protocol

DATA = Path(__file__).parent / "data"
KEYWORDS = {
    "authentication": {"login", "password", "sso", "signin"},
    "billing": {"invoice", "charge", "refund", "billing"},
    "exports": {"export", "exports", "csv", "reports"},
    "integrations": {"integration", "sync", "webhook", "endpoint"},
}
LIMITATION = "Deterministic mocks; probabilities are illustrative, not calibrated. No real model or paid API was called."


def load_data(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def tokens(text):
    return set(re.findall(r"[a-z]+", text.lower()))


@dataclass
class Triage:
    category: dict
    impact: dict
    multiple_users: dict
    deadline: dict


class DecisionProvider(Protocol):
    name: str
    def triage(self, text: str) -> Triage: ...
    def review(self, text: str, draft: str) -> dict: ...


class DraftProvider(Protocol):
    name: str
    def draft(self, text: str, category: str, evidence: list) -> str: ...


class MockJev:
    name = "mock-jev"

    def triage(self, text):
        words = tokens(text)
        hits = {key: len(words & values) for key, values in KEYWORDS.items()}
        matched = [key for key, value in hits.items() if value]
        options = [*KEYWORDS, "other"]
        if not matched:
            probabilities = {key: 0.15 for key in KEYWORDS}
            probabilities["other"] = 0.4
        elif len(matched) == 1:
            probabilities = {key: 0.025 for key in options}
            probabilities[matched[0]] = 0.9
        else:
            remaining = len(options) - len(matched)
            probabilities = {key: (0.8 / len(matched) if key in matched else 0.2 / remaining) for key in options}
        category = max(probabilities, key=probabilities.get)
        lower = text.lower()
        blocked = any(phrase in lower for phrase in ("can't", "cannot", "blocked", "nobody can"))
        degraded = bool(words & {"slow", "warning", "error", "fails", "failure"})
        level = 2 if blocked else 1 if degraded else 0
        impact_probs = [0.05, 0.05, 0.05]
        impact_probs[level] = 0.9
        return Triage(
            category={"choice": category, "probabilities": probabilities, "confidence": max(probabilities.values())},
            impact={"score": level, "legend": ["No explicit blockage", "Partial degradation", "Complete blockage reported"], "probabilities": impact_probs, "confidence": 0.9},
            multiple_users={"noul": 0.95 if any(p in lower for p in ("entire team", "all users", "nobody can")) else 0.15},
            deadline={"noul": 0.95 if any(p in lower for p in ("urgent", "deadline", "two hours", "today")) else 0.1},
        )

    def review(self, text, draft):
        lower = draft.lower()
        return {
            "unverified_fix_promise": {"noul": 0.95 if any(p in lower for p in ("guaranteed", "will be fixed", "already fixed")) else 0.05},
            "requests_diagnostics": {"noul": 0.95 if "please share" in lower else 0.1},
        }


class MockFrontier(MockJev):
    name = "mock-frontier"

    def draft(self, text, category, evidence):
        steps = "\n".join(f"- {doc['body']} [{doc['id']}]" for doc in evidence)
        return (
            "Thanks for reporting this. We need a few details to investigate.\n\n"
            f"Suggested checks from our support guidance:\n{steps}\n\n"
            "Please share the exact error, when it started, and whether others are affected. "
            "Exclude passwords, tokens, and payment details. "
            "These are diagnostic suggestions; the cause and resolution are not yet verified."
        )


def retrieve(text, category, knowledge):
    stopwords = {"the", "a", "an", "and", "or", "to", "for", "of", "in", "is", "it", "our", "my", "we", "i", "with", "can", "are", "this", "from"}
    words = tokens(text) - stopwords
    ranked = []
    for doc in knowledge:
        if doc["category"] not in (category, "other"):
            continue
        score = len(words & tokens(doc["title"] + " " + doc["body"])) + (5 if doc["category"] == category else 0)
        if score:
            ranked.append((score, doc))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [doc for _, doc in ranked[:3]]


def route(triage, review, threshold):
    reasons = []
    if triage.category["confidence"] < threshold or triage.category["choice"] == "other":
        reasons.append("Category is uncertain or outside known areas.")
    impact_probabilities = triage.impact["probabilities"]
    blocked_probability = impact_probabilities.get("2", 0) if isinstance(impact_probabilities, dict) else impact_probabilities[2]
    if blocked_probability >= 0.5:
        reasons.append("Complete blockage is reported.")
    if triage.deadline["noul"] >= 0.8:
        reasons.append("An urgent deadline is reported.")
    if review["unverified_fix_promise"]["noul"] >= 0.8:
        reasons.append("Draft may promise an unverified fix.")
    return {"action": "human_review" if reasons else "draft_ready", "reasons": reasons or ["Draft is ready for a support reviewer to use."], "sent": False}


def run(text, mode="hybrid", threshold=0.75, knowledge=None, decision_provider=None, frontier_provider=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 10000:
        raise ValueError("Ticket text must contain 1–10,000 characters.")
    if mode not in ("hybrid", "frontier-only"):
        raise ValueError("Mode must be hybrid or frontier-only.")
    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1.")
    started = perf_counter()
    frontier = frontier_provider or MockFrontier()
    decision = (decision_provider or MockJev()) if mode == "hybrid" else frontier
    stages = []

    def step(name, provider, operation):
        start = perf_counter()
        result = operation()
        stages.append({"stage": name, "provider": provider, "elapsed_ms": round((perf_counter() - start) * 1000, 4)})
        return result

    triage = step("triage", decision.name, lambda: decision.triage(text))
    evidence = step("retrieve", "local-lexical", lambda: retrieve(text, triage.category["choice"], load_data("knowledge") if knowledge is None else knowledge))
    draft = step("draft", frontier.name, lambda: frontier.draft(text, triage.category["choice"], evidence))
    review = step("review", decision.name, lambda: decision.review(text, draft))
    routing = route(triage, review, threshold)
    live = bool(getattr(decision, "is_live", False))
    records = list(getattr(decision, "records", []))
    return {
        "mode": mode, "limitation": "Real Jev decisions; frontier drafting is mocked. Probabilities require domain evaluation. API charges may apply." if live else LIMITATION, "ticket": text, "threshold": threshold,
        "triage": asdict(triage), "evidence": evidence, "draft": draft,
        "review": review, "routing": routing, "stages": stages,
        "usage": {"jev_calls": 2 if mode == "hybrid" else 0, "frontier_calls": 1 if mode == "hybrid" else 3,
                  "live_api_calls": len(records), "api_cost_usd": None if live else 0,
                  "jev_responses": records, "input_tokens": sum(r["usage"]["input_tokens"] for r in records),
                  "output_tokens": sum(r["usage"]["output_tokens"] for r in records),
                  "elapsed_ms": round((perf_counter() - started) * 1000, 4)},
    }


def evaluate(split="test", threshold=0.75):
    if split not in ("dev", "test"):
        raise ValueError("Split must be dev or test.")
    fixtures = [t for t in load_data("tickets") if t["split"] == split]
    report = {"split": split, "threshold": threshold, "limitation": LIMITATION + " Both mock decision adapters share heuristics; differences do not measure real model quality.", "modes": {}}
    for mode in ("hybrid", "frontier-only"):
        rows = []
        for fixture in fixtures:
            result = run(fixture["text"], mode, threshold)
            rows.append({"id": fixture["id"], "expected_category": fixture["category"], "predicted_category": result["triage"]["category"]["choice"], "urgent": fixture["urgent"], "human_review": result["routing"]["action"] == "human_review", "elapsed_ms": result["usage"]["elapsed_ms"]})
        urgent = [r for r in rows if r["urgent"]]
        report["modes"][mode] = {
            "count": len(rows), "category_accuracy": sum(r["expected_category"] == r["predicted_category"] for r in rows) / len(rows),
            "urgent_recall": sum(r["human_review"] for r in urgent) / len(urgent) if urgent else None,
            "review_rate": sum(r["human_review"] for r in rows) / len(rows),
            "mean_local_elapsed_ms": sum(r["elapsed_ms"] for r in rows) / len(rows), "api_cost_usd": 0, "tickets": rows,
        }
    return report
