"""Document library: PDF ingestion, scanned-page reading, embeddings, search, summaries."""
import hashlib
import json
import re

import numpy as np
import ollama
import pymupdf

from config import DOCS_DIR, EMBED_MODEL, MODEL

MAX_PAGES = 300
CHUNK_CHARS = 1800          # roughly 450 tokens
SCANNED_BELOW = 30          # a page with fewer characters than this is treated as an image
SECTION_CHARS = 6000        # text handed to the model per summary step

_cache: dict[str, dict] = {}


# ---------- model helpers ----------

def _generate(prompt: str, images=None, num_ctx=8192) -> str:
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = images
    resp = ollama.chat(model=MODEL, messages=[msg], think=False,
                       options={"num_ctx": num_ctx})
    return (resp.message.content or "").strip()


def _embed(texts: list[str], prefix: str):
    """Returns a normalised float32 matrix, or None if the embedding model is unavailable."""
    try:
        out = []
        for i in range(0, len(texts), 16):
            batch = [prefix + t for t in texts[i:i + 16]]
            out.extend(ollama.embed(model=EMBED_MODEL, input=batch).embeddings)
        m = np.array(out, dtype=np.float32)
        return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
    except Exception:
        return None


# ---------- ingestion ----------

def _read_scanned_page(page) -> str:
    png = page.get_pixmap(dpi=110).tobytes("png")
    return _generate(
        "Transcribe all the text on this page exactly as written. "
        "If there is little or no text, briefly describe what the page shows "
        "(charts, diagrams, photos). Output only the transcription or description.",
        images=[png], num_ctx=4096,
    )


def _page_text(page) -> tuple[str, bool]:
    text = page.get_text().strip()
    if len(text) >= SCANNED_BELOW:
        try:
            for t in page.find_tables().tables:
                text += "\n\n[Table]\n" + t.to_markdown()
        except Exception:
            pass
        return text, False
    try:
        return _read_scanned_page(page), True
    except Exception:
        return text, True


def _chunk_page(text: str, page_no: int) -> list[dict]:
    chunks, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        while len(para) > CHUNK_CHARS:                      # very long paragraph
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:CHUNK_CHARS])
            para = para[CHUNK_CHARS:]
        if len(cur) + len(para) > CHUNK_CHARS and cur:
            chunks.append(cur)
            cur = ""
        cur = (cur + "\n\n" + para).strip()
    if cur:
        chunks.append(cur)
    return [{"page": page_no, "text": c} for c in chunks if c.strip()]


def ingest_pdf(data: bytes, filename: str) -> dict:
    doc_id = hashlib.sha1(data).hexdigest()[:10]
    existing = get_doc(doc_id)
    if existing:
        return {**_info(existing), "already": True}

    pdf = pymupdf.open(stream=data, filetype="pdf")
    pages, scanned, chunks = [], 0, []
    for i, page in enumerate(pdf):
        if i >= MAX_PAGES:
            break
        text, was_scanned = _page_text(page)
        scanned += was_scanned
        pages.append(text)
        chunks.extend(_chunk_page(text, i + 1))
    pdf.close()

    emb = _embed([c["text"] for c in chunks], "search_document: ") if chunks else None
    doc = {"id": doc_id, "name": filename, "pages": pages, "chunks": chunks,
           "scanned_pages": scanned, "embedded": emb is not None}
    (DOCS_DIR / f"{doc_id}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    if emb is not None:
        np.save(DOCS_DIR / f"{doc_id}.npy", emb)
    _cache[doc_id] = {**doc, "emb": emb}
    return _info(doc)


def _info(doc: dict) -> dict:
    return {"id": doc["id"], "name": doc["name"], "pages": len(doc["pages"]),
            "scanned_pages": doc["scanned_pages"], "embedded": doc["embedded"]}


# ---------- library access ----------

def _valid_id(doc_id) -> bool:
    return isinstance(doc_id, str) and bool(re.fullmatch(r"[0-9a-f]{10}", doc_id))


def get_doc(doc_id: str) -> dict | None:
    if not _valid_id(doc_id):
        return None
    if doc_id in _cache:
        return _cache[doc_id]
    path = DOCS_DIR / f"{doc_id}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    npy = DOCS_DIR / f"{doc_id}.npy"
    doc["emb"] = np.load(npy) if npy.exists() else None
    _cache[doc_id] = doc
    return doc


def delete_doc(doc_id: str) -> bool:
    if not _valid_id(doc_id):
        return False
    _cache.pop(doc_id, None)
    found = False
    for ext in ("json", "npy"):
        try:
            (DOCS_DIR / f"{doc_id}.{ext}").unlink()
            found = True
        except FileNotFoundError:
            pass
    return found


def all_docs() -> list[dict]:
    docs = []
    for p in sorted(DOCS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        d = get_doc(p.stem)
        if d:
            docs.append(d)
    return docs


def find_doc(name: str = "") -> dict | str:
    """Resolve a document by id or part of its filename. With no name, works only if there is one document."""
    docs = all_docs()
    if not docs:
        return "No documents have been uploaded yet."
    if not name:
        return docs[0] if len(docs) == 1 else \
            "Several documents exist; say which one: " + ", ".join(d["name"] for d in docs)
    name = name.lower()
    hits = [d for d in docs if d["id"] == name or name in d["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        return f"No document matches '{name}'. Available: " + ", ".join(d["name"] for d in docs)
    return "Several documents match: " + ", ".join(d["name"] for d in hits)


def library_block() -> str:
    docs = all_docs()
    if not docs:
        return ""
    names = "\n".join(f"- {d['name']} ({len(d['pages'])} pages)" for d in docs)
    return f"\n\nDocuments Thisen has uploaded (use the document tools to read them):\n{names}"


# ---------- search ----------

def _keyword_scores(query: str, chunks: list[dict]) -> np.ndarray:
    words = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2}
    return np.array([sum(w in c["text"].lower() for w in words) for c in chunks], dtype=np.float32)


def search(query: str, doc_name: str = "", k: int = 4) -> list[dict]:
    if doc_name:
        d = find_doc(doc_name)
        if isinstance(d, str):
            raise ValueError(d)
        targets = [d]
    else:
        targets = all_docs()

    q = _embed([query], "search_query: ")
    scored = []
    for d in targets:
        if not d["chunks"]:
            continue
        if q is not None and d.get("emb") is not None and len(d["emb"]) == len(d["chunks"]):
            scores = d["emb"] @ q[0]
        else:
            scores = _keyword_scores(query, d["chunks"])
        for c, s in zip(d["chunks"], scores):
            scored.append((float(s), d["name"], c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"doc": n, "page": c["page"], "text": c["text"]} for _, n, c in scored[:k]]


# ---------- summaries (map-reduce) ----------

def _sections(pages: list[str], label: bool = True) -> list[str]:
    out, cur = [], ""
    for i, text in enumerate(pages, 1):
        piece = (f"[Page {i}]\n" if label else "") + f"{text}\n\n"
        if len(cur) + len(piece) > SECTION_CHARS and cur:
            out.append(cur)
            cur = ""
        cur += piece[:SECTION_CHARS]
    if cur:
        out.append(cur)
    return out


def summarize(doc: dict, focus: str = "") -> str:
    goal = f" Focus on: {focus}." if focus else ""
    parts = _sections(doc["pages"])
    for _ in range(4):
        partials = [
            _generate(f"Summarise this part of a document in a few concise bullet points, "
                      f"keeping key facts, numbers and page references.{goal}\n\n{part}")
            for part in parts
        ]
        joined = "\n\n".join(partials)
        if len(partials) == 1 or len(joined) <= SECTION_CHARS:
            break
        parts = _sections(partials, label=False)
    if len(partials) == 1:
        return partials[0]
    return _generate(f"Combine these partial summaries into one clear summary of the whole "
                     f"document ('{doc['name']}').{goal}\n\n{joined}")
