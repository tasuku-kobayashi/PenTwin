# Role-conditioned and graded style cards (experimental v0.9)

PenTwin now attempts to represent **choices made in the same writing situation**. The card has three axes: fixed-vocabulary connector and reporting-verb preferences within reviewed rhetorical moves; first-person, hedge and passive-like rates that differ across moves; and repeated transitions between moves within a section. It is a candidate description for prompting, not an author-identity certificate.

## Local extraction

The sealed corpus contains reviewed section and move labels for each extracted row. In **strict mode**, two independent development families must each contain at least five measurable sentences for a move. A word must appear at least twice in each of two families, its across-paper rate cannot vary by more than 0.25 per sentence, and only the predefined generic vocabulary can leave the local process. A stance rate must be stable within a move (across-paper range at most 0.15) and differ by at least 0.10 between supported moves. A move transition needs independent support from at least two families. Flow uses the source extraction order frozen in the candidate lock, even if the review CSV is reordered. Holdout rows never enter the card.

In **exploratory mode**, five sentences in each of two development papers suffice for a section-level card. A one-paper word is retained with low confidence, not called an established habit. The card also includes rates of surface rhetorical cues and can represent zero occurrences. This lets us test weak evidence without pretending it is a verified explanation-order rule. See the [first graded-card probe](WEAK_CARD_ABLATION.md).

`author_style_card(section, move="", evidence_mode="exploratory")` returns graded clues by default; `strict` returns the higher-threshold role card. `rewrite_plan` includes both, an explicit low-confidence warning, and a prompt for one critique/revision cycle. `axis_plan` provides instructions for only one axis so comparisons can isolate wording, cue order or stance. If strict role evidence is absent, the plan does not claim a verified role habit. Existing numeric diagnostics remain visible, but do not prove writer likeness. No paper excerpts, learned n-grams or names are returned.

An optional local comparator accepts two sealed author runs:

```powershell
python -m pentwin.cli contrast-card C:\private\pentwin\author-a C:\private\pentwin\author-b --section discussion
```

It keeps candidate wording or move transitions absent from the comparison writer and stance differences of at least 0.12, only where the same reviewed role exists in both corpora. The server can still operate with only the target writer; without a comparator, repeated habits cannot be called distinctive.

## Verification and current data limit

Synthetic tests cover two writers with opposing move orders and different recurring words, role-specific stance, unsupported-role abstention, holdout isolation, review-sheet reordering and MCP stdio calls. **They verify behavior of the code, not effectiveness on research manuscripts.**

Two existing private anonymous cohorts were also inspected (two writers with two reference articles each per cohort). Their extracted editorial texts have no confirmed, paragraph-level move labels. Treating each entire article as one provisional role gives **zero strictly supported word choices and zero reviewed move transitions for all four writer profiles**. The strict card therefore abstains in all four cases; the new exploratory card retains weaker clues. An initial ablation gave 0/4 improvement for wording and 2/4 each for cue order and stance against held-out surface cues. Earlier 5/6 whole-paper attribution and the generated-text rhythm pilot cannot establish author voice. The original articles also have time/topic and writing-role confounds.

The next decisive test needs reviewed, ordered paragraphs from several independently drafted life-sciences papers per writer, with at least two development families supporting each target move. Freeze the extraction rules, then compare target cards with same-field rivals and generate identical new briefs with GPT and Claude. Score lexical, move-order and stance outcomes separately from sentence length on untouched cases. Report abstentions and writer-level failures. These instructions follow the distinction between **describing** a style and **eliciting** it in generation: [Kim and Jurgens (2026)](https://aclanthology.org/2026.findings-acl.2039/), and the use of failure explanations for personalization: [Cho et al. (2025)](https://aclanthology.org/2025.findings-naacl.326/). Biomedical rhetorical-move annotation is an established analysis target: [Alliheedi et al. (2019)](https://aclanthology.org/W19-4514/). None of these publications validates PenTwin's new card.
