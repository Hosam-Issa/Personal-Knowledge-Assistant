import json
import re
import sys
from pathlib import Path

from personal_knowledge_assistant.rag import ingest, retrieve, collection

KS = (1, 3, 5, 8)
lines = []

def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).lower()


def found(hits: list[dict], source: str, phrase: str) -> bool:
    return any(h["source"] == source and norm(phrase) in norm(h["text"]) for h in hits)

def first_rank(question: str, source: str, phrase: str):
    hits = retrieve(question, k=collection.count())
    for rank, h in enumerate(hits, 1):
        if h["source"] == source and norm(phrase) in norm(h["text"]):
            return rank
    return None

def main() -> None:
    ingest()
    log(f"chunks: {collection.count()}")
    with open("evals/eval_set.json", encoding="utf-8") as f:
        items = json.load(f)

    answerable = [q for q in items if q["expected"]]
    unanswerable = [q for q in items if not q["expected"]]

    hits_at = {k: 0 for k in KS}
    top_sims_answerable = []
    for q in answerable:
        hits = retrieve(q["question"], k=max(KS))
        top_sims_answerable.append(hits[0]["sim"])
        for k in KS:
            if all(found(hits[:k], e["source"], e["phrase"]) for e in q["expected"]):
                hits_at[k] += 1
        if not all(found(hits[:4], e["source"], e["phrase"]) for e in q["expected"]):
            ranks = [first_rank(q["question"], e["source"], e["phrase"]) for e in q["expected"]]
            log(f"MISS@4  [{q['id']}]  ranks of expected chunk: {ranks}")
        if not all(found(hits[:8], e["source"], e["phrase"]) for e in q["expected"]):
            log(f"Miss@8 [{q['id']}] {q['question']}")

    log(f"\nRetrieval hit rate over {len(answerable)} answerable questions:")
    for k in KS:
        log(f"  top-{k}: {hits_at[k] / len(answerable):.0%}")

    for q in unanswerable:
        sim = retrieve(q["question"], k=1)[0]["sim"]
        log(f"  unanswerable [{q['id']}] top sim {sim:.3f}")

    label = sys.argv[1] if len(sys.argv) > 1 else "scratch"
    path = Path("evals/results") / f"{label}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()