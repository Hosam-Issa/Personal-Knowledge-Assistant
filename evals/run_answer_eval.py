"""End-to-end answer eval: runs the pipeline or the agent on every question and saves the results.

Usage (from the project root):
    uv run python -m evals.run_answer_eval <label> [k] [eval_path] [mode]

    mode: "pipeline" (default, fixed retrieve-then-answer) or "agent" (tool-using agent)

Examples:
    uv run python -m evals.run_answer_eval 05_answers_v2_k8 8
    uv run python -m evals.run_answer_eval 06_answers_agent 8 evals/eval_set.json agent
    uv run python -m evals.run_answer_eval 99_holdout_answers 8 evals/holdout_set.json agent

In agent mode, k is how many chunks each search returns (it sets agent.K).
Output: evals/results/<label>.json
Delete chroma_db/ before running if you changed the chunker.
"""
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from personal_knowledge_assistant.rag import answer, collection, ingest

LABEL = sys.argv[1] if len(sys.argv) > 1 else "scratch_answers"
K = int(sys.argv[2]) if len(sys.argv) > 2 else 4
EVAL_PATH = sys.argv[3] if len(sys.argv) > 3 else "evals/eval_set.json"
MODE = sys.argv[4] if len(sys.argv) > 4 else "pipeline"
if MODE not in ("pipeline", "agent"):
    sys.exit("mode must be 'pipeline' or 'agent'")

MIN_SIM = 0.2  # keep in sync with the default in rag.answer()
if MODE == "agent":
    from personal_knowledge_assistant import agent as agent_mod

    agent_mod.K = K  # search_documents reads K at call time
    MIN_SIM = agent_mod.MIN_SIM

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
        trace = [] if MODE == "agent" else None
        t0 = time.perf_counter()
        if MODE == "agent":
            reply = agent_mod.run_agent(item["question"], trace=trace)
        else:
            reply = answer(item["question"], k=K, min_sim=MIN_SIM, verbose=False)
        seconds = round(time.perf_counter() - t0, 1)

        ok = auto_check(item, reply)
        gated = reply.startswith(GATE_MESSAGE)
        by_type[item["type"]][0] += ok
        by_type[item["type"]][1] += 1

        row = {
            "id": item["id"],
            "type": item["type"],
            "question": item["question"],
            "reference_answer": item["reference_answer"],
            "answer": reply,
            "gated": gated,          # True = retrieval gate rejected it, no API call made
            "seconds": seconds,
            "auto_pass": ok,
            "manual_pass": None,     # fill in by hand (or with apply_grades)
            "note": "",
        }
        flags = ""
        if MODE == "agent":
            row["searches"] = [t for t in trace if "query" in t]    # {'query': ..., 'source': ...}
            row["guard_fired"] = any("guard" in t for t in trace)   # command guard dropped an answer
            flags = f"  ({len(row['searches'])} searches" + (", guard" if row["guard_fired"] else "") + ")"
        results.append(row)
        print(f"{'PASS ' if ok else 'CHECK'}  [{item['id']}]" + ("  (gated)" if gated else "") + flags)

    total_pass = sum(p for p, _ in by_type.values())
    avg_seconds = round(sum(r["seconds"] for r in results) / len(results), 1)
    print(f"\nAuto-check: {total_pass}/{len(items)}  (mode={MODE}, k={K}, min_sim={MIN_SIM})")
    for t, (p, n) in sorted(by_type.items()):
        print(f"  {t:<13} {p}/{n}")
    print(f"Average seconds per question: {avg_seconds}")

    meta = {
        "label": LABEL,
        "mode": MODE,
        "k": K,
        "min_sim": MIN_SIM,
        "chunks": collection.count(),
        "eval_set": EVAL_PATH,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "auto_pass": total_pass,
        "total": len(items),
        "avg_seconds": avg_seconds,
    }
    if MODE == "agent":
        meta["avg_searches"] = round(sum(len(r["searches"]) for r in results) / len(results), 2)
        meta["guard_fired"] = sum(r["guard_fired"] for r in results)
        meta["zero_search_questions"] = [r["id"] for r in results if not r["searches"]]
        print(f"Average searches per question: {meta['avg_searches']}   guard fired: {meta['guard_fired']}")
        print(f"Answered without searching: {meta['zero_search_questions']}")

    path = Path("evals/results") / f"{LABEL}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {path}. Review the CHECK items and fill in manual_pass.")


if __name__ == "__main__":
    main()