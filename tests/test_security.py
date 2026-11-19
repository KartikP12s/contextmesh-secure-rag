import io
import os
import uuid

import pytest
from contextmesh.config import Settings
from contextmesh.db import Base
from contextmesh.main import create_app
from contextmesh.providers import Answerer
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


@pytest.fixture
def client():
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://contextmesh:local-only@localhost:5440/contextmesh",
    )
    schema = "test_" + uuid.uuid4().hex
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text(f"CREATE SCHEMA {schema}"))
    cfg = Settings(
        database_url=url + f"?options=-csearch_path%3D{schema},public",
        embedding_provider="hash",
        min_score=0.25,
    )
    isolated = create_engine(cfg.database_url)
    Base.metadata.create_all(isolated, checkfirst=False)
    isolated.dispose()
    with TestClient(create_app(cfg)) as c:
        yield c
    with engine.begin() as db:
        db.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    engine.dispose()


def auth(name="acme-admin"):
    return {"Authorization": "Bearer local-" + name}


def upload(
    c,
    content=b"Travel reimbursement covers train tickets within fourteen days.",
    name="policy.txt",
    groups="hr",
):
    response = c.post(
        "/api/documents",
        headers=auth(),
        data={"groups": groups, "source": "acme/travel"},
        files={"file": (name, content)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_sql_acl_before_answer_and_download(client):
    doc = upload(client)
    for identity in ["acme-engineering", "northstar-admin", "orbit-admin"]:
        h = auth(identity)
        assert client.get("/api/documents", headers=h).json() == []
        assert client.get(f"/api/documents/{doc['id']}/download", headers=h).status_code == 404
        for endpoint in ["search", "chat"]:
            result = client.post(
                "/api/" + endpoint,
                headers=h,
                json={"question": "Travel reimbursement train tickets", "source": "acme/travel"},
            )
            assert result.status_code == 200
            assert result.json().get("results", result.json().get("citations")) == []
    response = client.post(
        "/api/chat",
        headers=auth("acme-hr"),
        json={"question": "Travel reimbursement train tickets"},
    )
    assert response.json()["citations"][0]["document_id"] == doc["id"]
    assert (
        client.post(
            "/api/search",
            headers=auth("acme-engineering"),
            json={"question": "travel", "tenant": "acme", "groups": ["hr"]},
        ).status_code
        == 422
    )


def test_version_and_permission_revocation(client):
    doc = upload(client)
    query = {"question": "Travel reimbursement train tickets"}
    old = client.post("/api/search", headers=auth("acme-hr"), json=query).json()["results"][0]
    updated = client.put(
        f"/api/documents/{doc['id']}",
        headers=auth(),
        files={
            "file": ("new.txt", b"Travel reimbursement now covers train tickets within seven days.")
        },
    ).json()
    assert updated["version"] == 2
    result = client.post("/api/search", headers=auth("acme-hr"), json=query).json()["results"][0]
    assert result["version"] == 2 and "seven" in result["text"] and "fourteen" not in result["text"]
    assert client.get("/api/chunks/" + old["chunk_id"], headers=auth()).status_code == 404
    assert (
        client.put(
            f"/api/documents/{doc['id']}/permissions", headers=auth("acme-hr"), json={"groups": []}
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/documents/{doc['id']}/permissions", headers=auth(), json={"groups": []}
        ).status_code
        == 200
    )
    assert client.post("/api/search", headers=auth("acme-hr"), json=query).json()["results"] == []
    assert client.delete(f"/api/documents/{doc['id']}", headers=auth()).status_code == 204


def test_formats_and_errors(client):
    from docx import Document
    from pypdf import PdfWriter

    document = Document()
    document.add_paragraph("Synthetic employee training allowance is 1200 credits.")
    data = io.BytesIO()
    document.save(data)
    assert upload(client, data.getvalue(), "policy.docx")["status"] == "ready"
    assert (
        upload(
            client,
            b"# Synthetic handbook\nEmployee learning allowance is 1200 credits.",
            "policy.md",
        )["status"]
        == "ready"
    )
    assert upload(client, b"not a PDF", "policy.pdf")["status"] == "error"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = io.BytesIO()
    writer.write(pdf)
    assert upload(client, pdf.getvalue(), "empty.pdf")["status"] == "error"
    assert upload(client, b"\x00broken", "file.txt")["status"] == "error"
    assert upload(client, b"hello world", "file.exe")["status"] == "error"
    assert (
        client.post(
            "/api/documents",
            headers=auth(),
            files={"file": ("big.txt", b"x" * (8 * 1024 * 1024 + 1))},
        ).status_code
        == 413
    )


def test_provider_never_receives_denied_chunks(client):
    upload(client)
    from unittest.mock import patch

    seen = []

    def spy(self, question, context):
        seen.extend(context)
        return {"answer": "No evidence", "citations": context, "uncertain": not context}

    with patch.object(Answerer, "answer", spy):
        result = client.post(
            "/api/chat",
            headers=auth("northstar-admin"),
            json={"question": "Travel reimbursement train tickets"},
        )
        assert result.status_code == 200
    assert seen == []
    assert client.get("/api/audit", headers=auth("acme-hr")).status_code == 403
    assert client.get("/api/documents").status_code == 401


def test_pdf_text_extraction(client):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 50 700 Td (Synthetic travel reimbursement covers rail tickets.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    doc = upload(client, output.getvalue(), "policy.pdf")
    assert doc["status"] == "ready"
    result = client.post(
        "/api/search",
        headers=auth("acme-hr"),
        json={"question": "travel reimbursement rail tickets"},
    ).json()
    assert any(r["document_id"] == doc["id"] for r in result["results"])
