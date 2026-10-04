"""Write manual grades into an answer-eval results file.

Usage (from the project root):
    uv run python -m evals.apply_grades 05_answers_v2_k4
    uv run python -m evals.apply_grades 05_answers_v2_k4_rerun
    uv run python -m evals.apply_grades 05_answers_v2_k6

Every question is marked manual_pass=true unless it is listed as a failure
below. The grades are a DRAFT: read the answers yourself, then edit the
dictionaries if you disagree with any of them. For other runs (k=8, holdout),
add new entries to RUN_FAILS.
"""
import json
import sys
from pathlib import Path

# Failed in every run: the right chunk was not retrieved, so the model
# (correctly) declined. These are retrieval failures, not model failures.
COMMON_FAILS = {
    "discord-run": "retrieval miss: run-command chunk ranked 13th; model declined",
    "discord-pillow": "retrieval miss: Pillow chunk ranked 9th; model declined",
}

_MISS_K4 = {
    "defect-run-app": "retrieval miss: 'python app.py' chunk ranked 8th; model declined",
    "pi-interval": "retrieval miss: '10 seconds' chunk ranked 7th; model declined",
}

_SYSTEMD_K4 = "incomplete: named only the Pi monitor; Discord deployment chunk (rank 5) was outside top-4"
# Failures that only happen in specific runs.
RUN_FAILS = {
    "05_answers_v2_k4": {**_MISS_K4, "multi-systemd": _SYSTEMD_K4},
    "05_answers_v2_k4_rerun": {**_MISS_K4, "multi-systemd": _SYSTEMD_K4},
    "05_answers_v2_k6": _MISS_K4,
    "05_answers_v2_k8": {},
}

# Passes that deserve a note.
PASS_NOTES = {
    "multi-sqlite": "correct projects; minor misreading: says bingo.db 'stores all queries' (database.py holds the queries)",
}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python -m evals.apply_grades <label>")
    label = sys.argv[1]
    path = Path("evals/results") / f"{label}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    fails = {**COMMON_FAILS, **RUN_FAILS.get(label, {})}
    unknown = set(fails) - {r["id"] for r in data["results"]}
    if unknown:
        sys.exit(f"Unknown question ids in grade tables: {sorted(unknown)}")

    for r in data["results"]:
        r["manual_pass"] = r["id"] not in fails
        if r["id"] in fails:
            r["note"] = fails[r["id"]]
        elif r["id"] in PASS_NOTES:
            r["note"] = PASS_NOTES[r["id"]]
        elif not r["auto_pass"]:
            r["note"] = "auto-check false negative: answer judged correct"

    by_type = {}
    for r in data["results"]:
        p, n = by_type.get(r["type"], (0, 0))
        by_type[r["type"]] = (p + r["manual_pass"], n + 1)

    data["meta"]["manual_pass"] = sum(r["manual_pass"] for r in data["results"])
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{label}: manual {data['meta']['manual_pass']}/{data['meta']['total']} "
          f"(auto {data['meta']['auto_pass']})")
    for t, (p, n) in sorted(by_type.items()):
        print(f"  {t:<13} {p}/{n}")


if __name__ == "__main__":
    main()