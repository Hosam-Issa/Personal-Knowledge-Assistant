| run         |          chunker            | chunks | top-1 | top-3 | top-4 | top-5 | top-8 |
| ---         |            ---              |  ---   |  ---  |  ---  |  ---  |  ---  |  ---  |
| 01          |          char800            |   31   |  42%  |  65%  |  77%  |  81%  |  94%  |
| 02/02b      |     markdown v0 (buggy)     |   65   |  35%  |  68%  |  71%  |  84%  |  87%  |
| 03          | markdown v1 (fences, merge) |   55   |  35%  |  65%  |  71%  |  84%  |  90%  |
| 04          |   markdown v2 (+ prefix)    |   55   |  48%  |  74%  |  77%  |  84%  |  90%  |
| 05 k4       |             4               | 28/35  | 30/35 | 19/23 |  5/5  |  2/3  |  4/4  |
| 05 k4 rerun |             4               | 27/35  | 30/35 | 19/23 |  5/5  |  2/3  |  4/4  |
| 05 k6       |             6               | 29/35  | 31/35 | 19/23 |  5/5  |  3/3  |  4/4  |
| 05 k8       |             8               | 32/35  | 33/35 | 21/23 |  5/5  |  3/3  |  4/4  |

Decision: default k=8 (manual pass 30 -> 31 -> 33 of 35 for k=4/6/8; unanswerable 4/4 at every k).
Remaining failures at k=8: discord-run (chunk rank 13) and discord-pillow (rank 9); both declined, none hallucinated.
Caveats: k was tuned on this same set (confirm on the holdout); the auto-check disagrees with manual grading in both directions, so the manual score is the headline; the retrieval eval counts discord-storage as a miss (rank 15), but the model answered it from another chunk.