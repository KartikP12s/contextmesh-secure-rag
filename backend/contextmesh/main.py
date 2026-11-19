import hmac
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from .config import settings
from .db import Audit, Chunk, Document, Evaluation, database, now
from .ingestion import MAX_BYTES, chunk, extract
from .providers import Answerer, Embedder
from .retrieval import access, retrieve


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1500)
    k: int = Field(default=5, ge=1, le=20)
    source: str | None = Field(default=None, max_length=250)


class Permissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groups: list[str] = Field(max_length=20)


def create_app(cfg=None, embedder=None, answerer=None):
    cfg = cfg or settings()
    engine, sessions = database(cfg.database_url)
    embedder = embedder or Embedder(cfg)
    answerer = answerer or Answerer(cfg)
    identities = json.loads(cfg.demo_tokens_json)
    windows = defaultdict(deque)
    lock = Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="ContextMesh", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cfg.cors_origin],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.sessions = sessions

    def identity(authorization: str = Header(default="")):
        for token, user in identities.items():
            if hmac.compare_digest(authorization, f"Bearer {token}"):
                with lock:
                    queue = windows[user["user"]]
                    while queue and queue[0] < time.monotonic() - 60:
                        queue.popleft()
                    if len(queue) >= 300:
                        raise HTTPException(429, "Rate limit exceeded")
                    queue.append(time.monotonic())
                return user
        raise HTTPException(401, "Valid development bearer credential required")

    def log(db, user, action, reference):
        db.add(Audit(tenant=user["tenant"], user=user["user"], action=action, reference=reference))

    def visible(db, did, user, write=False):
        doc = db.scalar(select(Document).where(Document.id == did, access(user)))
        if not doc:
            raise HTTPException(404, "Document not found")
        if write and doc.owner != user["user"] and user["role"] != "admin":
            raise HTTPException(403, "Document owner or tenant admin required")
        return doc

    def serialize(d):
        return {
            "id": d.id,
            "tenant": d.tenant,
            "owner": d.owner,
            "groups": d.groups,
            "filename": d.filename,
            "source": d.source,
            "version": d.version,
            "status": d.status,
            "error": d.error,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
            "embedding_provider": d.embedding_provider,
        }

    def index(doc, data, filename, db):
        try:
            parts = chunk(extract(filename, data))
            vectors = embedder.encode(parts)
            if len(vectors) != len(parts) or any(len(v) != 384 for v in vectors):
                raise ValueError("Invalid embedding response")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "index_failed", extra={"document_id": doc.id, "error_type": type(exc).__name__}
            )
            doc.status = "error"
            doc.error = (
                f"Indexing failed ({type(exc).__name__}); check file format or embedding provider"
            )
            return
        db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        for pos, (part, vector) in enumerate(zip(parts, vectors, strict=True)):
            db.add(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc.id,
                    version=doc.version,
                    position=pos,
                    text=part,
                    embedding=vector,
                )
            )
        doc.status = "ready"
        doc.error = None

    def parse_groups(raw, user):
        groups = sorted(set(g.strip() for g in raw.split(",") if g.strip()))
        if len(groups) > 20 or any(len(g) > 80 or not g.replace("-", "").isalnum() for g in groups):
            raise HTTPException(422, "Invalid groups")
        if user["role"] != "admin" and not set(groups) <= set(user["groups"]):
            raise HTTPException(403, "Cannot grant groups outside your membership")
        return groups

    @app.get("/health")
    def health():
        with sessions() as db:
            db.execute(select(1))
        return {
            "status": "ok",
            "embedding_provider": cfg.embedding_provider,
            "answer_provider": cfg.answer_provider,
        }

    @app.get("/api/me")
    def me(user=Depends(identity)):
        return user

    @app.get("/api/documents")
    def documents(user=Depends(identity)):
        with sessions() as db:
            return [
                serialize(d)
                for d in db.scalars(
                    select(Document)
                    .where(access(user))
                    .order_by(Document.created_at.desc())
                    .limit(500)
                )
            ]

    @app.post("/api/documents", status_code=201)
    def upload(
        file: UploadFile = File(),
        groups: str = Form(default=""),
        source: str = Form(default="", max_length=250),
        user=Depends(identity),
    ):
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Maximum upload is 8 MiB")
        filename = Path(file.filename or "document.txt").name[:200]
        allowed = parse_groups(groups, user)
        with sessions.begin() as db:
            doc = Document(
                id=str(uuid.uuid4()),
                tenant=user["tenant"],
                owner=user["user"],
                groups=allowed,
                filename=filename,
                source=source or filename,
                content=data,
                embedding_provider=cfg.embedding_provider,
            )
            db.add(doc)
            db.flush()
            index(doc, data, filename, db)
            log(db, user, "upload", doc.id)
            return serialize(doc)

    @app.put("/api/documents/{did}")
    def update(did: str, file: UploadFile = File(), user=Depends(identity)):
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Maximum upload is 8 MiB")
        with sessions.begin() as db:
            # Serialize updates to prevent two writers producing mixed versions.
            db.execute(
                select(Document.id).where(Document.id == did, access(user)).with_for_update()
            )
            doc = visible(db, did, user, True)
            doc.version += 1
            doc.updated_at = now()
            doc.content = data
            doc.filename = Path(file.filename or doc.filename).name[:200]
            doc.embedding_provider = cfg.embedding_provider
            doc.status = "indexing"
            index(doc, data, doc.filename, db)
            log(db, user, "update", did)
            return serialize(doc)

    @app.put("/api/documents/{did}/permissions")
    def permissions(did: str, payload: Permissions, user=Depends(identity)):
        allowed = parse_groups(",".join(payload.groups), user)
        with sessions.begin() as db:
            doc = visible(db, did, user, True)
            doc.groups = allowed
            doc.updated_at = now()
            log(db, user, "permissions", did)
            return serialize(doc)

    @app.delete("/api/documents/{did}", status_code=204)
    def remove(did: str, user=Depends(identity)):
        with sessions.begin() as db:
            doc = visible(db, did, user, True)
            db.execute(delete(Chunk).where(Chunk.document_id == did))
            db.delete(doc)
            log(db, user, "delete", did)

    @app.get("/api/documents/{did}/download")
    def download(did: str, user=Depends(identity)):
        with sessions.begin() as db:
            doc = visible(db, did, user)
            log(db, user, "download", did)
            # Fixed safe attachment name; original filename is displayed separately.
            return Response(
                doc.content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": "attachment; filename=document"},
            )

    @app.get("/api/chunks/{cid}")
    def citation(cid: str, user=Depends(identity)):
        with sessions.begin() as db:
            row = db.execute(
                select(Chunk, Document)
                .join(Document)
                .where(
                    Chunk.id == cid,
                    access(user),
                    Chunk.version == Document.version,
                    Document.status == "ready",
                )
            ).first()
            if not row:
                raise HTTPException(404, "Citation unavailable or superseded")
            c, d = row
            log(db, user, "citation", cid)
            return {
                "chunk_id": c.id,
                "document_id": d.id,
                "source": d.source,
                "version": d.version,
                "text": c.text,
            }

    def search(payload, user):
        try:
            vector = embedder.encode([payload.question])[0]
        except Exception:
            raise HTTPException(503, "Embedding provider unavailable")
        with sessions.begin() as db:
            result = retrieve(
                db, user, vector, cfg.embedding_provider, payload.k, cfg.min_score, payload.source
            )
            for row in result:
                log(db, user, "retrieve", row["chunk_id"])
            return result

    @app.post("/api/search")
    def searching(payload: Query, user=Depends(identity)):
        return {"results": search(payload, user)}

    @app.post("/api/chat")
    def chat(payload: Query, user=Depends(identity)):
        context = search(payload, user)
        try:
            return answerer.answer(payload.question, context)
        except Exception:
            raise HTTPException(502, "Answer provider failed validation or is unavailable")

    @app.get("/api/evaluations")
    def evaluations(user=Depends(identity)):
        if user["role"] != "admin":
            raise HTTPException(403, "Tenant admin required")
        with sessions() as db:
            return [
                {"id": r.id, "report": r.report, "created_at": r.created_at.isoformat()}
                for r in db.scalars(
                    select(Evaluation)
                    .where(Evaluation.tenant == user["tenant"])
                    .order_by(Evaluation.id.desc())
                    .limit(20)
                )
            ]

    @app.get("/api/audit")
    def audit(user=Depends(identity)):
        if user["role"] != "admin":
            raise HTTPException(403, "Tenant admin required")
        with sessions() as db:
            return [
                {
                    "action": e.action,
                    "user": e.user,
                    "reference": e.reference,
                    "at": e.created_at.isoformat(),
                }
                for e in db.scalars(
                    select(Audit)
                    .where(Audit.tenant == user["tenant"])
                    .order_by(Audit.id.desc())
                    .limit(100)
                )
            ]

    return app
