import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from personal_knowledge_assistant.rag import answer, collection, ingest

LABEL = sys.argv[1] if len(sys.argv) > 1 else "scratch_answers"
K = int(sys.argv[2]) if len(sys.argv) > 2 else 4
EVAL_PATH = sys.argv[3] if len(sys.argv) > 3 else "evals/eval_set.json"
MIN_SIM = 0.2  # keep in sync with the default in rag.answer()

GATE_MESSAGE = "I couldn't find anything relevant"
DECLINE = re.compile(
    r"couldn't find|could not find|not find|no information|don't have|"
    r"doesn't contain|does not contain|not (?:mentioned|stated|specified)",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).lower()


def auto_check(item: dict, reply: str) -> bool:
    """Crude check. A False here means 'read this one', not 'wrong'."""
    if item["expected"]:
        return all(norm(e["phrase"]) in norm(reply) for e in item["expected"])
    return bool(DECLINE.search(reply))


def main() -> None:
    ingest()
    with open(EVAL_PATH, encoding="utf-8") as f:
        items = json.load(f)

    results = []
    by_type = defaultdict(lambda: [0, 0])  # type -> [auto passes, total]

    for item in items:
        reply = answer(item["question"], k=K, min_sim=MIN_SIM, verbose=False)
        ok = auto_check(item, reply)
        gated = reply.startswith(GATE_MESSAGE)

        by_type[item["type"]][0] += ok
        by_type[item["type"]][1] += 1
        results.append({
            "id": item["id"],
            "type": item["type"],
            "question": item["question"],
            "reference_answer": item["reference_answer"],
            "answer": reply,
            "gated": gated,          # True = retrieval gate rejected it, no API call made
            "auto_pass": ok,
            "manual_pass": None,     # fill in by hand: true / false
            "note": "",              # one line on why, for failures
        })
        print(f"{'PASS ' if ok else 'CHECK'}  [{item['id']}]" + ("  (gated)" if gated else ""))

    total_pass = sum(p for p, _ in by_type.values())
    print(f"\nAuto-check: {total_pass}/{len(items)}  (k={K}, min_sim={MIN_SIM})")
    for t, (p, n) in sorted(by_type.items()):
        print(f"  {t:<13} {p}/{n}")

    out = {
        "meta": {
            "label": LABEL,
            "k": K,
            "min_sim": MIN_SIM,
            "chunks": collection.count(),
            "eval_set": EVAL_PATH,
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "auto_pass": total_pass,
            "total": len(items),
        },
        "results": results,
    }
    path = Path("evals/results") / f"{LABEL}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {path}. Review the CHECK items and fill in manual_pass.")


if __name__ == "__main__":
    main()