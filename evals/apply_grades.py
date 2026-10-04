"""Write manual grades into an answer-eval results file.

Usage (from the project root):
    uv run python -m evals.apply_grades <label>

Every question is marked manual_pass=true unless it is listed under that run's
"fails" below. The grades are a DRAFT: read the answers yourself and edit the
tables if you disagree. A label with no entry is refused, so a new run can't
silently inherit another run's grades.
"""
import json
import sys
from pathlib import Path

# ---- notes shared by several runs ------------------------------------------
DEFECT_RUN_APP_MISS = "retrieval miss: 'python app.py' chunk ranked 8th; model declined"
DISCORD_RUN_MISS = "retrieval miss: run-command chunk ranked 13th; model declined"
DISCORD_PILLOW_MISS = "retrieval miss: Pillow chunk ranked 9th; model declined"
PI_INTERVAL_MISS = "retrieval miss: '10 seconds' chunk ranked 7th; model declined"
SYSTEMD_K4 = "incomplete: named only the Pi monitor; Discord deployment chunk (rank 5) was outside top-4"
SQLITE_NOTE = "correct projects; minor misreading: says bingo.db 'stores all queries' (database.py holds the queries)"
TREASURE_BUILD = "incomplete: omits `source env.sh` and says `make dist` itself sources the environment"
ELABORATION = "correct core answer; adds explanation not in the docs (customer harm, extra inspection)"

RUNS = {
    "05_answers_v2_k4": {
        "fails": {
            "defect-run-app": DEFECT_RUN_APP_MISS,
            "discord-run": DISCORD_RUN_MISS,
            "discord-pillow": DISCORD_PILLOW_MISS,
            "pi-interval": PI_INTERVAL_MISS,
            "multi-systemd": SYSTEMD_K4,
        },
        "notes": {"multi-sqlite": SQLITE_NOTE},
    },
    "05_answers_v2_k4_rerun": {
        "fails": {
            "defect-run-app": DEFECT_RUN_APP_MISS,
            "discord-run": DISCORD_RUN_MISS,
            "discord-pillow": DISCORD_PILLOW_MISS,
            "pi-interval": PI_INTERVAL_MISS,
            "multi-systemd": SYSTEMD_K4,
        },
        "notes": {"multi-sqlite": SQLITE_NOTE},
    },
    "05_answers_v2_k6": {
        "fails": {
            "defect-run-app": DEFECT_RUN_APP_MISS,
            "discord-run": DISCORD_RUN_MISS,
            "discord-pillow": DISCORD_PILLOW_MISS,
            "pi-interval": PI_INTERVAL_MISS,
        },
        "notes": {"multi-sqlite": SQLITE_NOTE},
    },
    "05_answers_v2_k8": {
        "fails": {
            "discord-run": DISCORD_RUN_MISS,
            "discord-pillow": DISCORD_PILLOW_MISS,
        },
        "notes": {"multi-sqlite": SQLITE_NOTE},
    },
    "06_answers_agent": {
        "fails": {
            "treasure-build": TREASURE_BUILD,
            "ide-unanswerable": "presented the VS Code dev-container recommendation as IDE information for the projects",
        },
        "notes": {
            "defect-accuracy": "correct; minor error in extra detail: says precision was 1.00 for both classes (ok_front is 0.99)",
            "defect-recall-paraphrase": ELABORATION,
        },
    },
    "06_answers_agent_rerun": {
        "fails": {
            "discord-run": "retrieval miss; the guard dropped an invented command, so the answer was a safe decline",
            "treasure-build": TREASURE_BUILD,
            "ide-unanswerable": "stated VS Code 'was used as the primary IDE'; the docs only recommend it for the dev-container option",
        },
        "notes": {
            "defect-recall-paraphrase": ELABORATION,
            "players-unanswerable": "declined correctly, but suggests checking bingo.db, which the prompt says not to do",
        },
    },
    "06_answers_agent_k4": {
        "fails": {
            "discord-run": "retrieval miss at k=4; hedged with guessed commands in prose, which the guard does not check (auto-check false positive)",
            "pi-interval": "retrieval miss at k=4 after 3 searches; declined and suggested checking the source code",
            "treasure-build": TREASURE_BUILD,
            "ide-unanswerable": "stated VS Code 'was used' for Treasure Runner; the docs only recommend it for the dev-container option",
        },
        "notes": {
            "defect-accuracy": "correct; minor error in extra detail: says precision was 1.00 for both classes (ok_front is 0.99)",
            "defect-recall-paraphrase": ELABORATION,
        },
    },
}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python -m evals.apply_grades <label>")
    label = sys.argv[1]
    if label not in RUNS:
        sys.exit(f"No grade table for '{label}'. Read its answers, then add an entry to RUNS.")

    path = Path("evals/results") / f"{label}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fails, notes = RUNS[label]["fails"], RUNS[label]["notes"]

    unknown = (set(fails) | set(notes)) - {r["id"] for r in data["results"]}
    if unknown:
        sys.exit(f"Unknown question ids in grade tables: {sorted(unknown)}")

    for r in data["results"]:
        r["manual_pass"] = r["id"] not in fails
        if r["id"] in fails:
            r["note"] = fails[r["id"]]
        elif r["id"] in notes:
            r["note"] = notes[r["id"]]
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