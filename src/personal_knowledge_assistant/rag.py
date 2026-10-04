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

def chunk_markdown(text: str, max_size: int = 800) -> list[str]:
    chunks = []
    for section in re.split(r"\n(?=#{1,3} )", text):
        heading = section.split("\n", 1)[0].strip()
        if len(section) <= max_size:
            chunks.append(section)
        else:
            for i, piece in enumerate(chunk_text(section, max_size, 100)):
                chunks.append(piece if i == 0 else f"{heading}\n{piece}")
    return chunks

def ingest(folder: str = "docs") -> None:
    for path in Path(folder).glob("**/*"):
        if path.suffix not in {".md", ".txt"}:
            continue
        collection.delete(where={"source": path.name})
        chunks = chunk_markdown(path.read_text(encoding="utf-8"))
        if not chunks:
            continue
        collection.upsert(
            ids=[f"{path.name}:{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embedder.encode(chunks).tolist(),
            metadatas=[{"source": path.name, "chunk": i} for i in range(len(chunks))],
        )
    print(f"Collection now has {collection.count()} chunks")


def retrieve(question: str, k: int = 4) -> list[dict]:
    res = collection.query(
        query_embeddings=embedder.encode([question]).tolist(),
        n_results=k,
    )
    return [
        {"text": t, "source": m["source"], "chunk": m["chunk"], "sim": 1 - d}
        for t, m, d in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


SYSTEM = """You answer questions using ONLY the provided context excerpts.
Never suggest commands or facts that aren't in the excerpts.
Cite the source file for each claim, like [notes.md].
If the context doesn't contain the answer, say you couldn't find it in the documents. Do not guess."""


def answer(question: str, k: int = 4, min_sim: float = 0.2) -> str:
    hits = retrieve(question, k)
    for h in hits:  # keep this while developing
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