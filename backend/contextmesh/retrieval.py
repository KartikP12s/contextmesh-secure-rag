from sqlalchemy import and_, or_, select

from .db import Chunk, Document


def access(user):
    # Tenant is always required, including for admins. ACL is evaluated inside SQL.
    return and_(
        Document.tenant == user["tenant"],
        or_(
            Document.owner == user["user"],
            Document.groups.overlap(user["groups"]),
            user["role"] == "admin",
        ),
    )


def retrieve(db, user, vector, provider, k=5, min_score=0.35, source=None):
    distance = Chunk.embedding.cosine_distance(vector)
    statement = (
        select(Chunk, Document, (1 - distance).label("score"))
        .join(Document, Document.id == Chunk.document_id)
        .where(
            access(user),
            Document.status == "ready",
            Chunk.version == Document.version,
            Document.embedding_provider == provider,
            distance <= 1 - min_score,
        )
    )
    if source:
        statement = statement.where(Document.source == source)
    rows = db.execute(statement.order_by(distance, Chunk.id).limit(k))
    return [
        {
            "chunk_id": c.id,
            "document_id": d.id,
            "filename": d.filename,
            "source": d.source,
            "version": d.version,
            "text": c.text,
            "score": float(score),
        }
        for c, d, score in rows
    ]
