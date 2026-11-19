"""Seed labeled synthetic fixtures through the authenticated upload and update APIs."""

import json
import os
from pathlib import Path

import httpx


def seed(client):
    records = {}
    for doc in json.loads(Path("fixtures/documents.json").read_text()):
        headers = {"Authorization": f"Bearer local-{doc['tenant']}-admin"}
        existing = client.get("/api/documents", headers=headers)
        existing.raise_for_status()
        found = next((r for r in existing.json() if r["source"] == doc["source"]), None)
        if not found:
            response = client.post(
                "/api/documents",
                headers=headers,
                data={"groups": ",".join(doc["groups"]), "source": doc["source"]},
                files={"file": (doc["filename"], doc["old_content"].encode(), "text/markdown")},
            )
            response.raise_for_status()
            found = response.json()
        response = client.put(
            f"/api/documents/{found['id']}",
            headers=headers,
            files={"file": (doc["filename"], doc["content"].encode(), "text/markdown")},
        )
        response.raise_for_status()
        assert response.json()["status"] == "ready", response.text
        records[doc["source"]] = response.json()
    return records


if __name__ == "__main__":
    with httpx.Client(
        base_url=os.getenv("API_URL", "http://localhost:8010"), timeout=180
    ) as client:
        print(f"Seeded {len(seed(client))} synthetic documents across 3 tenants")
