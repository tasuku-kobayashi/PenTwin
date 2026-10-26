# Role-conditioned style cards (experimental v0.8)

PenTwin now attempts to represent **choices made in the same writing situation**. The card has three axes: fixed-vocabulary connector and reporting-verb preferences within reviewed rhetorical moves; first-person, hedge and passive-like rates that differ across moves; and repeated transitions between moves within a section. It is a candidate description for prompting, not an author-identity certificate.

## Local extraction

The sealed corpus contains reviewed section and move labels for each extracted row. Two independent development families must each contain at least five measurable sentences for a move. A word must appear at least twice in each of two families, its across-paper rate cannot vary by more than 0.25 per sentence, and only the predefined generic vocabulary can leave the local process. A stance rate must be stable within a move (across-paper range at most 0.15) and differ by at least 0.10 between supported moves. A move transition needs independent support from at least two families. Flow uses the source extraction order frozen in the candidate lock, even if the review CSV is reordered. Holdout rows never enter the card.

`author_style_card(section, move="")` returns the candidates and their paper support through MCP. `rewrite_plan` includes that card, instructions to plan explanation order before word choice, and a prompt for one critique/revision cycle. If no supported role-specific feature exists, the card returns `insufficient_role_evidence` and the plan tells the LLM not to invent a role habit. Existing numeric diagnostics remain visible, but do not prove writer likeness. No paper excerpts, learned n-grams or names are returned.

An optional local comparator accepts two sealed author runs:

```powershell
python -m pentwin.cli contrast-card C:\private\pentwin\author-a C:\private\pentwin\author-b --section discussion
```

It keeps candidate wording or move transitions absent from the comparison writer and stance differences of at least 0.12, only where the same reviewed role exists in both corpora. The server can still operate with only the target writer; without a comparator, repeated habits cannot be called distinctive.

## Verification and current data limit

Synthetic tests cover two writers with opposing move orders and different recurring words, role-specific stance, unsupported-role abstention, holdout isolation, review-sheet reordering and MCP stdio calls. **They verify behavior of the code, not effectiveness on research manuscripts.**

Two existing private anonymous cohorts were also inspected (two writers with two reference articles each per cohort). Their extracted editorial texts have no confirmed, paragraph-level move labels. Treating each entire article as one provisional role gives **zero supported word choices and zero move transitions for all four writer profiles**. The card therefore abstains in all four cases. Earlier 5/6 whole-paper attribution and the generated-text rhythm pilot cannot fill this gap. The original articles also have time/topic and writing-role confounds.

The next decisive test needs reviewed, ordered paragraphs from several independently drafted life-sciences papers per writer, with at least two development families supporting each target move. Freeze the extraction rules, then compare target cards with same-field rivals and generate identical new briefs with GPT and Claude. Score lexical, move-order and stance outcomes separately from sentence length on untouched cases. Report abstentions and writer-level failures. These instructions follow the distinction between **describing** a style and **eliciting** it in generation: [Kim and Jurgens (2026)](https://aclanthology.org/2026.findings-acl.2039/), and the use of failure explanations for personalization: [Cho et al. (2025)](https://aclanthology.org/2025.findings-naacl.326/). Biomedical rhetorical-move annotation is an established analysis target: [Alliheedi et al. (2019)](https://aclanthology.org/W19-4514/). None of these publications validates PenTwin's new card.
