"""Local markdown RAG. sqlite-vec if installed, otherwise tf-idf."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from noncast.config import Config
from noncast.hashing import sha256_text
from noncast.models import ChunkHit
from noncast.textutil import chunk_text, strip_front_matter, title_from_markdown, tokenize

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  hash TEXT NOT NULL,
  title TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  doc_id INTEGER NOT NULL,
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  tf TEXT NOT NULL,
  FOREIGN KEY(doc_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS idf (
  token TEXT PRIMARY KEY,
  value REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
"""

VEC_DIM = 384


def _hashed_vec(tokens: list[str], dim: int = VEC_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in tokens:
        h = int(sha256_text(tok)[:8], 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@dataclass
class Index:
    path: Path
    backend: str
    conn: sqlite3.Connection
    use_vec: bool

    def close(self) -> None:
        self.conn.close()

    def stats(self) -> dict[str, int | str]:
        docs = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"backend": self.backend, "documents": docs, "chunks": chunks}


def open_index(cfg: Config) -> Index:
    cfg.index.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.index)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    use_vec = False
    backend = cfg.rag_backend
    if backend in ("auto", "sqlite-vec"):
        try:
            import sqlite_vec  # type: ignore

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(embedding float[{VEC_DIM}])"
            )
            use_vec = True
            backend = "sqlite-vec"
        except Exception:
            if backend == "sqlite-vec":
                raise
            backend = "tf-idf"
    else:
        backend = "tf-idf"
    return Index(path=cfg.index, backend=backend, conn=conn, use_vec=use_vec)


def ingest(cfg: Config, corpus: Path | None = None) -> dict[str, int | str]:
    folder = Path(corpus) if corpus else cfg.corpus
    if not folder.exists():
        raise FileNotFoundError(f"corpus not found: {folder}")
    index = open_index(cfg)
    added = 0
    updated = 0
    skipped = 0
    seen_paths: set[str] = set()
    try:
        for md in sorted(folder.rglob("*.md")):
            rel = str(md.resolve())
            seen_paths.add(rel)
            text = md.read_text(encoding="utf-8")
            body, _ = strip_front_matter(text)
            title = title_from_markdown(md, text)
            if body.startswith("# "):
                body = body.split("\n", 1)[-1].lstrip()
            digest = sha256_text(body)
            row = index.conn.execute("SELECT id, hash FROM documents WHERE path = ?", (rel,)).fetchone()
            if row and row["hash"] == digest:
                skipped += 1
                continue
            if row:
                _delete_doc(index, row["id"])
                updated += 1
            else:
                added += 1
            cur = index.conn.execute(
                "INSERT INTO documents(path, hash, title, text) VALUES (?, ?, ?, ?)",
                (rel, digest, title, body),
            )
            doc_id = int(cur.lastrowid)
            for i, chunk in enumerate(chunk_text(body, cfg.chunk_size, cfg.chunk_overlap)):
                tokens = tokenize(chunk)
                tf = json.dumps(dict(Counter(tokens)))
                ccur = index.conn.execute(
                    "INSERT INTO chunks(doc_id, ordinal, text, tf) VALUES (?, ?, ?, ?)",
                    (doc_id, i, chunk, tf),
                )
                if index.use_vec:
                    vec = _hashed_vec(tokens)
                    cid = int(ccur.lastrowid)
                    try:
                        index.conn.execute(
                            "INSERT INTO chunk_vec(rowid, embedding) VALUES (?, ?)",
                            (cid, json.dumps(vec)),
                        )
                    except sqlite3.Error:
                        index.use_vec = False
        stale = index.conn.execute("SELECT id, path FROM documents").fetchall()
        for row in stale:
            if row["path"] not in seen_paths:
                _delete_doc(index, row["id"])
        _rebuild_idf(index)
        index.conn.commit()
        stats = index.stats()
        stats.update({"added": added, "updated": updated, "skipped": skipped})
        return stats
    finally:
        index.close()


def retrieve(cfg: Config, query: str, k: int | None = None) -> list[ChunkHit]:
    k = k or cfg.rag_top_k
    if not cfg.index.is_file():
        return []
    index = open_index(cfg)
    try:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        if index.use_vec:
            hits = _retrieve_vec(index, q_tokens, k)
            if hits:
                return hits
        return _retrieve_tfidf(index, q_tokens, k)
    finally:
        index.close()


def all_source_text(cfg: Config) -> str:
    if not cfg.index.is_file():
        return _raw_corpus(cfg)
    index = open_index(cfg)
    try:
        rows = index.conn.execute("SELECT text FROM documents").fetchall()
        if not rows:
            return _raw_corpus(cfg)
        return "\n\n".join(r["text"] for r in rows)
    finally:
        index.close()


def _raw_corpus(cfg: Config) -> str:
    if not cfg.corpus.exists():
        return ""
    parts = []
    for md in sorted(cfg.corpus.rglob("*.md")):
        parts.append(md.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _delete_doc(index: Index, doc_id: int) -> None:
    chunk_ids = [r[0] for r in index.conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))]
    if index.use_vec:
        for cid in chunk_ids:
            try:
                index.conn.execute("DELETE FROM chunk_vec WHERE rowid = ?", (cid,))
            except sqlite3.Error:
                pass
    index.conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    index.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def _rebuild_idf(index: Index) -> None:
    n = index.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    df: Counter[str] = Counter()
    for (tf_json,) in index.conn.execute("SELECT tf FROM chunks"):
        df.update(json.loads(tf_json).keys())
    index.conn.execute("DELETE FROM idf")
    if n == 0:
        return
    rows = [(tok, math.log((1 + n) / (1 + df_t)) + 1.0) for tok, df_t in df.items()]
    index.conn.executemany("INSERT INTO idf(token, value) VALUES (?, ?)", rows)


def _idf_map(index: Index) -> dict[str, float]:
    return {r["token"]: r["value"] for r in index.conn.execute("SELECT token, value FROM idf")}


def _tfidf_vec(tf: dict[str, int], idf: dict[str, float]) -> dict[str, float]:
    vec = {t: (c / max(sum(tf.values()), 1)) * idf.get(t, 1.0) for t, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def _retrieve_tfidf(index: Index, q_tokens: list[str], k: int) -> list[ChunkHit]:
    idf = _idf_map(index)
    q = _tfidf_vec(dict(Counter(q_tokens)), idf)
    scored: list[ChunkHit] = []
    sql = """
      SELECT chunks.id, chunks.text, documents.path, documents.title, chunks.tf
      FROM chunks JOIN documents ON documents.id = chunks.doc_id
    """
    for row in index.conn.execute(sql):
        vec = _tfidf_vec(json.loads(row["tf"]), idf)
        score = _cosine(q, vec)
        if score <= 0:
            continue
        scored.append(
            ChunkHit(
                chunk_id=int(row["id"]),
                path=row["path"],
                title=row["title"],
                text=row["text"],
                score=score,
            )
        )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:k]


def _retrieve_vec(index: Index, q_tokens: list[str], k: int) -> list[ChunkHit]:
    vec = _hashed_vec(q_tokens)
    try:
        rows = index.conn.execute(
            """
            SELECT rowid, distance FROM chunk_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (json.dumps(vec), k),
        ).fetchall()
    except sqlite3.Error:
        return []
    hits: list[ChunkHit] = []
    for row in rows:
        chunk = index.conn.execute(
            """
            SELECT chunks.id, chunks.text, documents.path, documents.title
            FROM chunks JOIN documents ON documents.id = chunks.doc_id
            WHERE chunks.id = ?
            """,
            (row["rowid"],),
        ).fetchone()
        if not chunk:
            continue
        dist = float(row["distance"])
        score = 1.0 / (1.0 + dist)
        hits.append(
            ChunkHit(
                chunk_id=int(chunk["id"]),
                path=chunk["path"],
                title=chunk["title"],
                text=chunk["text"],
                score=score,
            )
        )
    return hits
