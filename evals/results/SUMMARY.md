# Evaluation summary

Personal Knowledge Assistant: RAG over four project READMEs.
Embeddings: all-MiniLM-L6-v2 (cosine). Vector store: ChromaDB. LLM: claude-haiku-4-5.

- **Dev set:** `evals/eval_set.json`, 35 questions (23 fact, 5 paraphrase, 3 multi-project, 4 unanswerable).
- **Holdout set:** `evals/holdout_set.json`, 16 questions (9 fact, 3 paraphrase, 2 multi-project, 2 unanswerable). Written after the settings were frozen (git tag `pre-holdout`) and not tuned on.
- **Grades:** manual unless stated. The auto-check is a crude phrase match and disagrees with manual grading in both directions, so manual is the headline number.

## 1. Retrieval (dev set, 31 answerable questions)

A question is a hit if every expected phrase appears in the top-k chunks from the expected file.

| run | chunker | chunks | top-1 | top-3 | top-4 | top-5 | top-8 |
|---|---|---|---|---|---|---|---|
| 01 | 800 chars, overlap 100 | 31 | 42% | 65% | 77% | 81% | 94% |
| 02 / 02b | markdown v0 (buggy: splits on `#` comments inside code fences) | 65 | 35% | 68% | 71% | 84% | 87% |
| 03 | markdown v1 (fence-aware, merges sections under 150 chars) | 55 | 35% | 65% | 71% | 84% | 90% |
| 04 | markdown v2 (v1 + `[Title / Heading]` prefix on every chunk) | 55 | 48% | 74% | 77% | 84% | 90% |

- 02b reran 02 on a clean index and gave identical numbers, so stale chunks did not affect 02.
- The prefix (04) improved ranking (top-1 35% to 48%, top-3 65% to 74%) but not recall: top-8 is 90%, below the 94% of the plain 800-character chunker.
- Every expected phrase exists in some chunk (no run returned a `None` rank), so all misses are ranking problems.
- The similarity gate cannot separate answerable from unanswerable questions. Run 04: lowest top similarity among answerable questions 0.315, highest among unanswerable 0.518. `min_sim=0.2` only filters junk queries.
- The retrieval eval accepts one phrase per question, so a question with several valid source chunks can count as a miss. `discord-storage` is a retrieval miss (rank 15) but the model answers it correctly from another chunk.

## 2. Answer quality (dev set, 35 questions)

| run | mode | k | auto | manual | fact | paraphrase | multi | unanswerable |
|---|---|---|---|---|---|---|---|---|
| 05 k4 | pipeline | 4 | 28/35 | 30/35 | 19/23 | 5/5 | 2/3 | 4/4 |
| 05 k4 rerun | pipeline | 4 | 27/35 | 30/35 | 19/23 | 5/5 | 2/3 | 4/4 |
| 05 k6 | pipeline | 6 | 29/35 | 31/35 | 19/23 | 5/5 | 3/3 | 4/4 |
| 05 k8 | pipeline | 8 | 32/35 | 33/35 | 21/23 | 5/5 | 3/3 | 4/4 |
| 06 agent | agent | 8 | 29/35 | 33/35 | 22/23 | 5/5 | 3/3 | 3/4 |
| 06 agent rerun | agent | 8 | 29/35 | 32/35 | 21/23 | 5/5 | 3/3 | 3/4 |
| 06 agent k4 | agent | 4 | 29/35 | 31/35 | 20/23 | 5/5 | 3/3 | 3/4 |

In agent mode, k is the number of chunks returned per search.

Agent cost (pipeline time was only recorded on the holdout run):

| run | avg searches | avg seconds | guard fired |
|---|---|---|---|
| 06 agent k8 | 1.66 | 3.0 | 0 |
| 06 agent k8 rerun | 1.49 | 2.7 | 1 |
| 06 agent k4 | 1.49 | 2.6 | 0 |

Findings:
- **Pipeline:** raising k from 4 to 8 improved manual pass from 30 to 33 of 35. k=6 fixed `multi-systemd` (the Discord deployment chunk ranks 5th). k=8 also fixed `defect-run-app` and `pi-interval`. The two remaining misses, `discord-run` (chunk rank 13) and `discord-pillow` (rank 9), were declined, not hallucinated.
- **Unanswerable questions:** the pipeline declined all four at every k, although the similarity gate blocked none of them. The system prompt is doing that work.
- **Agent vs pipeline (k=8):** a tie overall (33 and 32 vs 33) with different failures. The agent fixed `discord-pillow` (both runs) and `discord-run` (one run). It regressed on `ide-unanswerable` (presented the VS Code dev-container recommendation as the IDE used) and `treasure-build` (omitted `source env.sh`). It averages about 2.5 API calls per question vs 1.
- **Agent k=4** loses `pi-interval` and saves little time, so k=8 is kept.
- **Command guard:** it dropped an invented command once (`discord-run`, rerun), correctly. It only checks fenced code blocks, so a guessed command written in prose gets through (`discord-run` at k=4).
- **Borderline grades:** `treasure-build` (strict), `defect-accuracy` (minor wrong detail in an extra sentence).

## 3. Holdout (16 questions, not tuned on)

| run | mode | k | auto | manual | fact | paraphrase | multi | unanswerable | avg seconds | avg searches |
|---|---|---|---|---|---|---|---|---|---|---|
| 99 pipeline | pipeline | 8 | 14/16 | 14/16 | 9/9 | 3/3 | 1/2 | 1/2 | 1.4 | n/a |
| 99 agent | agent | 8 | 14/16 | 14/16 | 9/9 | 3/3 | 1/2 | 1/2 | 2.6 | 1.38 |

Dev vs holdout (manual pass): pipeline 94% (33/35) vs 88% (14/16); agent 94% and 91% (33 and 32 of 35) vs 88% (14/16). The two modes tie on both sets, and the gaps between dev and holdout are one or two questions, so there is no clear sign of overfitting, but the samples are small.

- **Both modes failed `h-multi-raspberry`:** the answer names only the Pi monitor and omits the Discord bot, which mentions the Raspberry Pi once as a deployment example. The auto-check passed both.
  - Pipeline: the unfiltered top-8 was crowded out by Pi monitor chunks.
  - Agent: a Discord-only search for "Raspberry Pi" returned the right chunk (#16) as its top result, but with similarity 0.196, just under the 0.2 gate in `search_documents`. The tool therefore returned "No relevant results found" and the model correctly reported what it had been given. The failure is the gate, not the model.
- **Pipeline failed `h-discord-dashboard-port`:** it declined correctly, but wrongly said the Pi monitor's docs don't give a port (they give 5000).
- **Agent `h-defect-train-time` (graded fail, borderline):** it noted that wall-clock time isn't given, then speculated that training was quick.
- **Traps handled by both modes:** HTTPS (future-only), Docker (current in Treasure Runner, future-only in the Pi monitor).

## Decisions

- **Chunker:** heading-aware markdown with title/heading prefix (run 04).
- **Pipeline default k:** 8.
- **Agent:** k=8 per search, behind an `--agent` flag. The fixed pipeline is the default: it is cheaper (about 1.4 vs 2.6 seconds per question), more stable between runs, and handled unanswerable questions better.

## Caveats and limitations

- Small samples: one question is about 3% on the dev set and 6% on the holdout. The agent was run twice at k=8.
- k and the chunker were chosen on the dev set. The holdout (13 questions drafted by an AI assistant after it had seen which dev questions fail, 3 written by me and edited) is the check on that, with a small sample.
- Grades are my own manual judgments.
- The "Run the bot" chunk (`Discord_Bot.md #11`) is rarely retrieved for "start"-style queries, even when the search is restricted to that file.
- The command guard checks fenced code blocks only.
- The similarity gate in the agent's search tool rejects valid short-keyword matches (top similarity 0.196 vs a 0.2 threshold for "Raspberry Pi" in `Discord_Bot.md`), so a source-filtered search can come back empty. Untested fix: skip the gate when a `source` is given. Evaluating it would need a new holdout, since this one is spent.
- The agent sometimes adds explanation that is not in the docs, presents a recommendation as what was used, speculates on unanswerable questions, and leaves out a project that only mentions a topic in passing.
- The retrieval eval accepts one phrase per question, so questions with several valid source chunks can be undercounted.

## Result files (`evals/results/`)

| file | what it is |
|---|---|
| `01_char800_baseline.txt` | retrieval, 800-character chunks |
| `02_markdown_v0_buggy.txt`, `02b_markdown_v0_clean_index.txt` | retrieval, first markdown chunker, and its rerun on a clean index |
| `03_markdown_v1_fences_merge.txt` | retrieval, fence-aware chunker with merging |
| `04_markdown_v2_context_prefix.txt` | retrieval, with title/heading prefix |
| `05_answers_v2_k4.json`, `_k4_rerun`, `_k6`, `_k8` | answer eval, pipeline, dev set |
| `06_answers_agent.json`, `_rerun`, `_k4` | answer eval, agent, dev set |
| `06a` to `06f_agent_manual_*.txt` | manual agent transcripts while building it |
| `99_holdout_pipeline.json`, `99_holdout_agent.json` | holdout runs |

## Reproducing

```
uv run python -m evals.run_retrieval_eval <label>
uv run python -m evals.run_answer_eval <label> <k> [eval_path] [agent]
uv run python -m evals.apply_grades <label>   # dev runs (grade tables in the script)
uv run python -m evals.grade <label>          # holdout runs, graded by hand
```