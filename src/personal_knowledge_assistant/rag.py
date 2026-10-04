import json
from pathlib import Path
import re

import anthropic
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
client = anthropic.Anthropic()
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma = chromadb.PersistentClient(path="chroma_db")
collection = chroma.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})

def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks

def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs, ignoring '#' lines inside code fences."""
    sections, heading, lines, in_fence = [], "", [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and re.match(r"#{1,3} ", line):
            if lines:
                sections.append((heading, "\n".join(lines).strip()))
            heading, lines = line.lstrip("# ").strip(), [line]
        else:
            lines.append(line)
    if lines:
        sections.append((heading, "\n".join(lines).strip()))
    return sections


def chunk_markdown(text: str, doc_name: str, max_size: int = 800, min_size: int = 150) -> list[str]:
    sections = split_sections(text)
    title = sections[0][0] if sections and sections[0][0] else doc_name

    merged = []
    for heading, body in sections:
        if merged and len(body) < min_size:
            prev_h, prev_b = merged[-1]
            merged[-1] = (prev_h, prev_b + "\n\n" + body)
        else:
            merged.append((heading, body))

    chunks = []
    for heading, body in merged:
        label = title if heading == title else f"{title} / {heading}"
        for piece in (chunk_text(body, max_size, 100) if len(body) > max_size else [body]):
            chunks.append(f"[{label}]\n{piece}")
    return chunks

def ingest(folder: str = "docs") -> None:
    for path in Path(folder).glob("**/*"):
        if path.suffix not in {".md", ".txt"}:
            continue
        collection.delete(where={"source": path.name})
        chunks = chunk_markdown(path.read_text(encoding="utf-8"), path.stem)
        if not chunks:
            continue
        collection.upsert(
            ids=[f"{path.name}:{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embedder.encode(chunks).tolist(),
            metadatas=[{"source": path.name, "chunk": i} for i in range(len(chunks))],
        )
    print(f"Collection now has {collection.count()} chunks")


def retrieve(question: str, k: int = 4, source: str | None = None) -> list[dict]:
    res = collection.query(
        query_embeddings=embedder.encode([question]).tolist(),
        n_results=k,
        where={"source": source} if source else None,
    )
    return [
        {"text": t, "source": m["source"], "chunk": m["chunk"], "sim": 1 - d}
        for t, m, d in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


SYSTEM = """You answer questions using ONLY the provided context excerpts.
Never suggest commands or facts that aren't in the excerpts.
Cite the source file for each claim, like [notes.md].
If the context doesn't contain the answer, say you couldn't find it in the documents. Do not guess."""


def answer(question: str, k: int = 8, min_sim: float = 0.2, verbose: bool = True) -> str:
    hits = retrieve(question, k)
    if verbose:
        for h in hits:
            print(f"  {h['sim']:.3f}  {h['source']} #{h['chunk']}")
    if not hits or hits[0]["sim"] < min_sim:
        return "I couldn't find anything relevant in your documents."
    context = "\n\n".join(f"[{h['source']} #{h['chunk']}]\n{h['text']}" for h in hits)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return resp.content[0].text


if __name__ == "__main__":
    ingest()
    while True:
        q = input("\nAsk (or 'quit'): ")
        if q.strip().lower() == "quit":
            break
        print(answer(q))