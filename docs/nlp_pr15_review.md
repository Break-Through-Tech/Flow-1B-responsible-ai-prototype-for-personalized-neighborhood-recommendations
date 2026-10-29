# NLP PR #15 review

Reviewed October 21, 2026. [PR #15](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/pull/15), head `d915eece2e0029ab402e663e6c617e614655a948`, against main `fdd2c9a`. This is a local review; no comments were posted and the PR was not merged.

## P1: Reject unsupported quotes before indexing

Location: `src/nlp/tag_index.py:28-37` and `parse_response` in `src/nlp/tagging.py`.

Parsing marks quotes absent from the snippet as `evidence_found=false`, but retains the tags. The index counts those tags and publishes their quotes without checking or preserving the flag. Consequently `crowd_themes` returns invented quotes as normal evidence, and `tag_matrix` counts unsupported tags.

Offline reproduction: snippet `Not quiet at night.`; fake model result assigning `quiet` with quote `Peaceful streets`. Parsing marks evidence false, but the tool returns `status=ok`, quiet count 1, and that invented quote.

Fix: reject empty/unmatched quotes at the index boundary, including entries loaded from cache. Add an end-to-end regression proving unsupported tags are absent from both published evidence and counts.

## P1: Preserve demo provenance for mixed-source ZIPs

Location: `src/nlp/tag_index.py:24-26` and `36-37`.

The aggregate uses `loc['is_demo'] and s['is_demo']`. Adding one real snippet turns the ZIP's flag false while demo evidence remains. Evidence records omit their own source and demo flag, so consumers cannot distinguish the synthetic records.

Offline reproduction: two snippets for 33130 with demo flags true and false produce aggregate `is_demo=false`, with both evidence records still present.

Fix: preserve source and demo status per evidence record and explicitly represent mixed provenance. If retaining an aggregate boolean, define it as "contains demo evidence" with OR. Test real-only, demo-only, and mixed input.

## Integration observations

- A simulated merge confirms a `.gitignore` content conflict. Preserve main's exclusions while reviewing the additions.
- PR imports use `src.nlp`; main packages `src/flow_neighborhoods` with `src` as the import root. Agree a supported package layout and test installed-package imports before MCP integration.
- Engine evidence uses `evidence_id`, `source_label`, `is_demo`, and `polarity`; PR output groups `tags` with `snippet_id` and `quote`. Define an explicit adapter with contract tests.
- VADER correctly labels `Not quiet at night.` negative. The separate tag path accepts a fake `quiet` tag quoting just `quiet` from that sentence and supplies no polarity. This demonstrates a validation gap, not live Gemini behavior. Preserve full context/per-theme polarity or mark tags as topic-only and keep them out of positive preference scoring.
- The initial path concern was ruled out: `parents[2]` resolves correctly to the repository root, and default demo loading succeeds.

## Verification

Exported PR files into ignored `outputs/nlp-review-d915eece/`; no PR source or branch was modified. Installed its declared VADER dependency in the existing venv. All 27 NLP unittest cases pass. Additional offline probes reproduced the two findings above and checked negation. No live model calls were made.

At review time Om passed 43 pytest cases. After Om approved density cleanup, the three prototype-only tests were removed; the remaining 40 pass with Ruff lint and formatting checks. The NLP PR review findings are unchanged.
