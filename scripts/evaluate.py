"""Deterministic retrieval/access evaluation against real PostgreSQL pgvector."""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from seed import seed


def evaluate(client, records):
    outcomes = []
    for q in json.loads(Path("fixtures/queries.json").read_text()):
        group = q["group"]
        tenant = q["tenant"]
        category = q["category"]
        if category.startswith("group_denied"):
            group = "engineering" if group == "hr" else "hr"
        if category.startswith("cross_tenant"):
            tenant = {"acme": "northstar", "northstar": "orbit", "orbit": "acme"}[tenant]
        # Each tenant has admin plus both group identities in the evaluation settings.
        token = f"local-{tenant}-{group}"
        headers = {"Authorization": "Bearer " + token}
        payload = {"question": q["question"], "k": 5}
        if category == "insufficient":
            payload["source"] = "unindexed-subsidiary/" + q["source"]
        result = client.post("/api/search", headers=headers, json=payload)
        result.raise_for_status()
        rows = result.json()["results"]
        chat = client.post("/api/chat", headers=headers, json=payload)
        chat.raise_for_status()
        answer = chat.json()
        expected = records[q["expected_source"]]["id"]
        relevant = [i for i, r in enumerate(rows) if r["document_id"] == expected]
        leaks = [
            r
            for r in rows + answer["citations"]
            if records[r["source"]]["tenant"] != tenant
            or group not in records[r["source"]]["groups"]
        ]
        current = all(
            r["version"] == records[r["source"]]["version"] and "OBSOLETE" not in r["text"]
            for r in rows
        )
        citation_ok = all(
            any(c["chunk_id"] == r["chunk_id"] for r in rows) for c in answer["citations"]
        )
        passed = (
            not leaks
            and current
            and citation_ok
            and (
                bool(relevant) if q["allowed"] else expected not in [r["document_id"] for r in rows]
            )
        )
        if category == "insufficient":
            passed = passed and answer["uncertain"] and not answer["citations"]
        outcomes.append(
            {
                "id": q["id"],
                "tenant": q["tenant"],
                "category": category,
                "passed": passed,
                "allowed": q["allowed"],
                "recall_at_5": float(bool(relevant)) if q["allowed"] else None,
                "precision_at_5": len(relevant) / len(rows) if q["allowed"] and rows else 0,
                "mrr": 1 / (relevant[0] + 1) if relevant and q["allowed"] else 0,
                "access_violations": len(leaks),
                "citation_correct": citation_ok,
                "current_version": current,
            }
        )
    return outcomes


def report(outcomes):
    positives = [r for r in outcomes if r["allowed"]]
    categories = defaultdict(lambda: {"passed": 0, "failed": 0})
    for r in outcomes:
        categories[r["category"]]["passed" if r["passed"] else "failed"] += 1
    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "queries": len(outcomes),
        "passed": sum(r["passed"] for r in outcomes),
        "failed": sum(not r["passed"] for r in outcomes),
        "recall_at_5": sum(r["recall_at_5"] for r in positives) / len(positives),
        "precision_at_5": sum(r["precision_at_5"] for r in positives) / len(positives),
        "mrr": sum(r["mrr"] for r in positives) / len(positives),
        "access_violations": sum(r["access_violations"] for r in outcomes),
        "citation_correctness": sum(r["citation_correct"] for r in outcomes) / len(outcomes),
        "stale_violations": sum(not r["current_version"] for r in outcomes),
        "categories": dict(categories),
    }


if __name__ == "__main__":
    with httpx.Client(
        base_url=os.getenv("API_URL", "http://localhost:8010"), timeout=180
    ) as client:
        outcomes = evaluate(client, seed(client))
    summary = report(outcomes)
    from contextmesh.config import settings
    from contextmesh.db import Evaluation, database

    engine, sessions = database(settings().database_url)
    with sessions.begin() as db:
        for tenant in {r["tenant"] for r in outcomes}:
            db.add(
                Evaluation(
                    tenant=tenant, report=report([r for r in outcomes if r["tenant"] == tenant])
                )
            )
    engine.dispose()
    Path("docs/evaluation.json").write_text(
        json.dumps({"summary": summary, "queries": outcomes}, indent=2) + "\n"
    )
    Path("docs/EVALUATION.md").write_text(
        "# Retrieval evaluation\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n"
    )
    print(json.dumps(summary, indent=2))
    raise SystemExit(bool(summary["failed"]))
