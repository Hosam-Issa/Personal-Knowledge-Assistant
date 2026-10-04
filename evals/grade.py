"""Grade an answer-eval results file by hand, one question at a time.

Usage (from the project root):
    uv run python -m evals.grade <label>

Keys: y = pass, n = fail, s = skip for now, q = save and quit.
Questions that already have a grade are skipped, so you can stop and resume.

Use this for the holdout runs: the grades come from you reading each answer,
not from a table written in advance.
"""
import json
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show(text: str, indent: str = "    ") -> None:
    for para in text.split("\n"):
        if para.strip():
            print(textwrap.fill(para, width=100, initial_indent=indent, subsequent_indent=indent))
        else:
            print()


def summary(results: list[dict]) -> None:
    by_type = defaultdict(lambda: [0, 0, 0])  # passes, graded, total
    for r in results:
        t = by_type[r["type"]]
        t[2] += 1
        if r["manual_pass"] is not None:
            t[1] += 1
            t[0] += bool(r["manual_pass"])
    graded = sum(t[1] for t in by_type.values())
    passed = sum(t[0] for t in by_type.values())
    print(f"\nManual pass: {passed}/{graded} graded ({len(results)} questions in total)")
    for name, (p, g, n) in sorted(by_type.items()):
        print(f"  {name:<13} {p}/{g} graded  ({n} total)")
    failed = [r["id"] for r in results if r["manual_pass"] is False]
    if failed:
        print(f"Failed: {failed}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python -m evals.grade <label>")
    path = Path("evals/results") / f"{sys.argv[1]}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data["results"]

    todo = [r for r in results if r["manual_pass"] is None]
    print(f"{len(todo)} of {len(results)} questions left to grade.")
    print("Check: is it correct? does it cite the right file? any guessed or unsupported detail? "
          "did it decline when it should have?\n")

    for i, r in enumerate(todo, 1):
        print("=" * 100)
        print(f"[{i}/{len(todo)}] {r['id']}  ({r['type']})  auto-check: {'pass' if r['auto_pass'] else 'CHECK'}")
        print(f"QUESTION:  {r['question']}")
        print(f"REFERENCE: {r['reference_answer']}")
        for s in r.get("searches", []):
            print(f"  search: {s}")
        if r.get("guard_fired"):
            print("  (the command guard dropped an answer)")
        print("ANSWER:")
        show(r["answer"])

        key = ""
        while key not in {"y", "n", "s", "q"}:
            key = input("\npass? [y/n/s/q] ").strip().lower()
        if key == "q":
            break
        if key == "s":
            continue
        r["manual_pass"] = key == "y"
        note = input("note (optional): ").strip()
        if note:
            r["note"] = note
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    if all(r["manual_pass"] is not None for r in results):
        data["meta"]["manual_pass"] = sum(bool(r["manual_pass"]) for r in results)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    summary(results)


if __name__ == "__main__":
    main()