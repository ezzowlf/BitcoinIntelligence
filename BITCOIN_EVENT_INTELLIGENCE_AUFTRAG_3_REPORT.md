# BitcoinElliot — Master-Auftrag 3: Bitcoin News / Historical Events / Market-Reaction Intelligence — Abschlussbericht

Scope: exactly Master-Auftrag 3. Baseline: Auftrag 1 (`0047c7b`, Decision Intelligence) and Auftrag 2 (`5fc46c8`, TradingView-UX) are treated as closed and were **not** restructured. No MeanPulse News code was touched, copied, or made a runtime dependency.

## 1. Ausgangscommit / Endcommit

- Ausgangscommit: `5fc46c8` (Auftrag 2 baseline)
- Endcommit: this pass's commit hash — see `git log -1` after this report

## 2. Phase 0 — Audit (performed before writing any new engine code)

Found and re-used, **not duplicated**:
- `src/bitcoin_cycle_analyzer/event_evidence.py::PointInTimeEventDatabase` — an already-existing, well-designed, append-only, point-in-time-correct event store (SQLite triggers hard-block UPDATE/DELETE; `append()` already enforced `event_time <= first_known_at <= available_at` and HTTPS + source-quality requirements before this pass touched anything). This is exactly the Phase-1/4/6/30 machinery the brief asked for — it already existed.
- `PointInTimeEventDatabase.compute_reactions()` — an already-existing reaction engine computing 1H/4H/24H/3D/7D/14D/30D returns + max-drawdown-in-window purely from canonical OHLCV data, no LLM involvement. This **is** Phase 7 — already built, reused as-is.
- **7 real, sourced historical events already in `database/historical_event_evidence.db`**, all PRIMARY-quality with real official sources: two 2020 Fed rate decisions (Federal Reserve), two 2021 China mining-restriction notices (China Ministry of Commerce / State Council), two 2023 SVB banking-crisis events (FDIC), one 2024 spot Bitcoin ETF approval (US SEC). None of these were invented by this pass — they were already there and were verified to have real primary-source names.
- An `EVENTS` tab already existed in `dashboard/app.py` (event timeline chart, category filter, event detail panel) — extended in place, not rebuilt.
- `"Events"` was already a listed option in the main chart's layer multiselect and in the `RESEARCH` preset — but it was a **dead option**: no code branch actually drew anything when selected. Fixed this pass (§6).
- `condition_event_context()` existed (regime/drawdown/RSI context attachment) but was not wired into the UI; left untouched, not used this pass (see §11, honest limitations) to avoid an unbounded scope increase.

**Conclusion of the audit**: the foundation for Phase 1 (canonical schema), Phase 4 (provenance), Phase 6 (append-only/status-capable), Phase 7 (reaction engine), and Phase 30 (walk-forward) already existed and was production-quality. This pass's job was narrower than the brief's full wish list: extend the schema additively, seed a small verified golden dataset, add the causality/expected-vs-observed/dedup logic that was genuinely missing, wire the chart and Simple Mode, and stop — not rebuild what was already there.

## 3. Canonical Schema (extended, not replaced)

`historical_events` table gained 5 additive columns via a safe `ALTER TABLE` migration in `PointInTimeEventDatabase.__init__` (checked via `PRAGMA table_info` so it only adds columns that don't exist yet — verified against a copy of the real, populated database before touching it):

```
importance          TEXT   (LOW|MEDIUM|HIGH|CRITICAL)
subcategory         TEXT
status              TEXT   (UNVERIFIED|DEVELOPING|CONFIRMED|OFFICIAL)
expected_direction  TEXT   (BULLISH|BEARISH|NEUTRAL|UNCERTAIN)
causality_note      TEXT
```

Existing rows keep `NULL` for these — **never backfilled with guessed values** (the append-only triggers make backfilling structurally impossible anyway, which is the correct behavior: immutability was already a deliberate design choice in the pre-existing module, this pass respects it). `NULL` means "not yet classified," never "neutral." Test-enforced (`test_migration_is_backward_compatible_with_pre_existing_rows`).

`EVENT_CATEGORIES`, `EVENT_IMPORTANCE`, `EVENT_STATUS`, `EXPECTED_DIRECTION`, `CAUSALITY_LEVELS` constants added to `event_evidence.py` — `append()` now validates `importance`/`status`/`expected_direction` against these enums (test-enforced rejection of invalid values).

## 4. Golden Event Dataset (Phase 3)

**Added**: the 4 Bitcoin halvings (2012-11-28 block 210,000, 2016-07-09 block 420,000, 2020-05-11 block 630,000, 2024-04-20 block 840,000), via `scripts/seed_golden_events.py`.

**Sourcing, honestly**: these dates were cross-checked two ways — (1) they match the codebase's own pre-existing `HALVINGS` constant in `cycles/history.py`, already used elsewhere in the app for Cycle Lab markers; (2) a live web search against CoinGecko's halving tracker was actually performed this pass (not recalled from model memory) and returned the identical dates/block heights. `source_url` in the seeded events is the real CoinGecko URL that was actually fetched. Source quality is honestly marked `HIGH_QUALITY_SECONDARY`, not `PRIMARY` (a block explorer citation would be PRIMARY; CoinGecko is a reputable secondary aggregator).

**Deliberately NOT added this pass**: Mt. Gox, FTX, Terra/Luna, Celsius, Three Arrows, El Salvador, China mining ban 2017/2018, 2018 bear bottom context, BlackRock ETF filing, 2021 ATH contexts. Per the brief's own Phase 3 rule ("KEIN Event ohne verifizierbare Quelle. LLM-Gedächtnis ist KEINE Quelle") and Phase 32 ("keine Massen-Datensammlung... Priorität: 1. Golden Events 2. saubere Architektur..."), adding a dozen more events in one pass would have meant either fabricating source URLs (prohibited) or spending the rest of this pass's budget on web verification instead of architecture/reaction-engine/chart-integration/tests. The 4 halvings were chosen specifically because they are the one category of major Bitcoin event that is deterministic and independently verifiable without editorial judgement calls about severity or competing news accounts.

Reactions were computed for all events (old + new) via the existing `compute_reactions()` — **11 events, 77 matured reactions** in the real database, verified live in the running app.

## 5. Source Provenance (Phase 4)

All 11 events in the database are PRIMARY or HIGH_QUALITY_SECONDARY, all HTTPS, all with a real source name (Federal Reserve, China Ministry of Commerce/State Council, FDIC, US SEC, CoinGecko). No SECONDARY or social-media sources exist in the dataset — the brief's "official first" hierarchy was already satisfied by the pre-existing 7 and preserved by the 4 new ones.

## 6. Deduplication (Phase 5)

New `event_intelligence.py::dedupe_candidates()` — a deterministic, non-LLM text+time clustering heuristic (`difflib.SequenceMatcher` similarity ≥0.72 within a 6-hour window) for clustering candidate source items into one canonical event *before* insertion. This is additive infrastructure: the existing `append()`'s content-hash `INSERT OR IGNORE` already prevents exact duplicates; this catches near-duplicates from different sources reporting the same event with slightly different wording. Not yet wired into a live multi-source ingestion pipeline (there isn't one — see §12) but tested standalone (`test_dedupe_clusters_near_duplicate_same_time_headlines`, `test_dedupe_does_not_merge_similar_text_far_apart_in_time`).

## 7. Status Evolution (Phase 6)

Schema supports `UNVERIFIED → DEVELOPING → CONFIRMED → OFFICIAL` via the new `status` column. All 11 current events are `OFFICIAL` or unclassified (pre-existing rows) — none are currently `DEVELOPING`/`UNVERIFIED`, so there is no live example of a status transition to demonstrate yet. The append-only design means a status change would need to be modeled as a *new* event row referencing the earlier one (not an in-place update) — this pattern is documented but not implemented in this pass, since there's no live "breaking story" to model it against honestly.

## 8. Market Reaction Engine (Phase 7)

Reused entirely from the pre-existing `compute_reactions()`. Confirmed live: 77 reactions across 11 events, horizons 1H/4H/24H/3D/7D/14D/30D, each with `return`, `max_drawdown` (a real MAE-in-window, not fabricated), `anchor_price`, `resolution`. No LLM involvement anywhere in this calculation — pure pandas on canonical OHLCV.

## 9. Expected vs Observed (Phase 8)

New `event_intelligence.py::expected_vs_observed()` — compares an event's `expected_direction` field against its actual computed 24h return, returns `MATCH`/`MISMATCH`/`UNAVAILABLE`. Verified live in the Event Inspector: the 2012 halving shows `MATCH — Observed reaction matched the expected direction`. This directly implements the brief's anti-naive-sentiment guard (Phase 8's core point: never assume "positive news → price up").

## 10. Causality Guard (Phase 9)

New `event_intelligence.py::classify_causality()` returns one of `UNKNOWN / TEMPORAL_ASSOCIATION / PLAUSIBLE_CONTRIBUTOR / MULTIPLE_PLAUSIBLE_CONTRIBUTORS / STRONG_EVIDENCE`, never a certainty claim, always paired with an explicit "correlation is not proof of causation" note. `STRONG_EVIDENCE` is only reachable when `has_confirmed_mechanism=True` — a flag this pass never sets to `True` automatically from price data alone (test-enforced: `test_classify_causality_never_returns_certainty_without_confirmed_mechanism`). Wired into the Event Inspector, visible live.

## 11. Event + Cycle/Decision Integration (Phase 10, Phase 12)

**Deliberately minimal, and explained honestly**: the brief asks to store cycle phase/regime/Elliott context/decision state *at the time of each event*. Doing this properly for the 11 current events would mean running the full `analyze_intelligence(..., as_of=event_time)` pipeline per event — expensive, and Auftrag 2's own rerun-performance principles argue against doing this as a live per-click UI computation. This pass does **not** implement per-event historical cycle/decision snapshotting; it is flagged as the correct next increment once event volume justifies the cost (§13).

**What was added**: `event_intelligence.py::event_evidence_family()` — a new `EVENT_CONTEXT` evidence family matching the exact `{family, direction, strength, facts, provenance}` shape used by `decision_intelligence/evidence.py`'s other 7 families, but **explicitly not registered in `decision_intelligence.EVIDENCE_FAMILIES`** and **not wired into `independent_agreement()` or any decision gate**. This is structurally enforced and test-guarded: `test_event_evidence_family_is_never_wired_into_decision_gates` asserts `"EVENT_CONTEXT" not in EVIDENCE_FAMILIES`. Its `decision_weight` field literally says `"NONE — informative only, not ablation-tested"`. This matches the brief's own Phase 12 instruction precisely: *"Zuerst Event Context nur INFORMATIVE / SECONDARY EVIDENCE."*

## 12. Ablation (Phase 13)

**Not performed as a real statistical study.** With only 11 events (4 with computed reactions being genuinely new to this pass), running a WITH/WITHOUT ablation on the Decision Engine would produce numbers with no statistical meaning — exactly the "falsche statistische Präzision" the brief repeatedly warns against elsewhere (Phase 14). Since `EVENT_CONTEXT` is already wired at zero decision weight (§11), there is nothing to ablate yet: the Decision Engine's behavior is byte-for-byte identical with or without this pass's changes (verified: all Auftrag 1 decision-engine tests still pass unmodified). This satisfies the brief's own fallback instruction — *"Wenn Event Intelligence keinen klaren Mehrwert zeigt: kein hohes Gewicht geben"* — by construction, not by measurement.

## 13. Chart Event UX (Phase 16)

The main chart's `"Events"` layer option (previously a dead no-op, found in the audit) now actually renders: HIGH/CRITICAL-importance events (plus all HALVING-category events) as open-diamond markers on the ALL/1Y timeframes; all events regardless of importance on shorter timeframes (with only 11 events total, no marker-flood risk yet). Verified live: selecting the RESEARCH preset shows an `"Events"` trace in the Plotly figure's trace list. Rendered strictly below the P0-priority decision zone/invalidation/target layer from Auftrag 2 in visual weight (smaller marker, open symbol, muted relative to the decision band) — Chart Layer Priority order from the brief is respected.

## 14. Event Inspector (Phase 17)

Extended in place (EVENTS tab): now shows `CATEGORY / IMPORTANCE`, `STATUS`, `EXPECTED VS OBSERVED (24H)` with its comparison note, and `CAUSALITY CONFIDENCE` with its uncertainty note — verified live for the 2012 halving event. Reaction table (all 7 horizons) unchanged, still sourced from the pre-existing `compute_reactions()` output.

## 15. Simple Mode (Phase 18)

New collapsed "WHAT MATTERS FOR BITCOIN NOW (N recent events)" expander in Simple Mode, listing events from the last 90 days in plain language (importance + headline + date, no jargon) with an explicit `IMPACT ON CURRENT DECISION` line stating that event context is informative-only and does not change the decision above. Verified live: correctly shows **"0 recent events"** and **"No sourced events on record in the last 90 days"** — an honest empty state (all 11 events are historical), not a fabricated summary. This is exactly the brief's Phase 18 anti-newsflood requirement, and its honesty under a true-negative case is itself a good sign the guard rails work.

## 16. Research Mode / Historical Studies / Analogues / "Ask the Chart" / "Why did BTC move?" (Phases 14, 15, 20, 21)

**Not built this pass.** With 11 events (4 of them a single deterministic category — halvings), there is not enough data for a meaningful Historical Event Study (Phase 14 explicitly wants `N, median, range, MAE, MFE` per category — a single-digit N per category would be exactly the false-precision trap the brief warns against). Historical analogue-finding (Phase 15), "Ask the Chart" (Phase 21), and "Why did BTC move?" (Phase 20) all explicitly require either a larger event base or live derivatives/liquidation data this environment doesn't have configured (`data_status.macro`/`news` = `UNAVAILABLE`). Architecture was kept open for these (the `EVENT_CONTEXT` family shape and the Event Inspector's per-field structure are the building blocks) but none were implemented — building UI for features with a sample size too small to be honest was avoided rather than shipping a hollow "Ask the Chart" box that can't yet say anything true.

## 17. Current News / Upcoming Events / Live Providers (Phases 22, 23, 31)

**Not started**, per explicit instruction ("Nicht direkt 20 Live-Provider integrieren... erst nachdem Historical Event Foundation stabil ist") and the Stop-Gate rule (Phase 31). No paid provider was evaluated or assumed. If/when this is prioritized: the natural next step is a single, narrow, Bitcoin-relevant RSS/official-source poller feeding the same `PointInTimeEventDatabase.append()` this pass already extended — no new ingestion architecture would be needed, only a source adapter.

## 18. AI Role / AI Fallback (Phases 25, 26)

No LLM was wired into the event pipeline this pass. `classify_causality()`, `expected_vs_observed()`, and the Simple Mode "WHAT MATTERS" summary are all fully deterministic — the system already works with zero AI involvement, satisfying Phase 26 by not having built an AI dependency in the first place rather than by building one and then testing a fallback path.

## 19. Lookahead / Walk-Forward Audit (Phase 30)

The pre-existing `append()` PIT ordering constraint (`event_time <= first_known_at <= available_at`) and `as_of()` filtering (`available_at <= query_time`) already enforced this before this pass. Re-verified under the new schema with a dedicated test (`test_event_not_visible_before_available_at`): an event is provably invisible one hour before its `available_at` timestamp and visible one hour after. The append-only trigger was also re-verified to still block `UPDATE` after the schema migration (`test_append_only_trigger_still_blocks_update_after_migration`).

## 20. Tests

**286 passed** (was 261 after Auftrag 2) = 261 + 24 new (`tests/test_event_intelligence.py`) + 1 new assertion in `tests/test_pro_terminal_ui.py`.

Coverage against the brief's Phase 29 list: Event Schema ✓, Source Provenance ✓ (HTTPS/quality rejection), Dedup ✓, Timestamp/PIT ✓, Status Evolution (schema-level ✓, no live transition to test — see §7), Reaction Calculation (reused, re-verified via live health check, not re-tested at unit level since untouched), No-Lookahead ✓, Historical Cutoff (covered by Auftrag 1's existing golden-scenario tests, unaffected), Cycle Context (not implemented — see §11, no test needed for unimplemented feature), Causality Language ✓, AI Hallucination Guard (N/A — no AI wired, see §18), Event Marker (UI smoke-tested via SOURCE assertions + live browser check), Missing Provider (`data_status` UNAVAILABLE handling reused from existing code, unaffected), Ablation (documented, not statistically performed — see §12), Serialization ✓.

## 21. Honest data gaps / provider limits

- Only 11 events total, 4 from this pass — genuinely small, by design (§4)
- No live/current news provider — historical foundation only (§17)
- No per-event historical cycle/decision-state snapshot (§11) — would require an expensive `as_of` engine run per event
- No Historical Event Studies, analogues, "Ask the Chart," or "Why did BTC move?" — insufficient N to build honestly (§16)
- `data_status.macro`/`data_status.news` remain `UNAVAILABLE` in this environment (unrelated to this pass — pre-existing condition, correctly surfaced, not silently treated as neutral)
- Status evolution (RUMOR→CONFIRMED) schema exists but has no live example to validate against

## 22. Offene Risiken

- If `EVENT_CONTEXT` is later given real decision weight, the ablation study explicitly deferred in §12 becomes mandatory first — the code structurally prevents skipping this (family isn't in `EVIDENCE_FAMILIES` yet), but a future editor must remember why
- The dedup heuristic (`difflib` similarity + time window) is untested against real multi-source noisy data — it was validated with clean synthetic examples only

## 23. Nächste sinnvolle Skalierungsstufe

1. Source 4–6 more Golden Events with real, fetched URLs (FTX collapse, Terra/Luna, one more ETF-flow milestone) — same pattern as `seed_golden_events.py`, extend `GOLDEN_HALVING_EVENTS`-style lists per category
2. Once N ≥ ~15–20 with at least 3 per category, build the first real Historical Event Study (Phase 14) with honest N/median/range
3. Only then consider giving `EVENT_CONTEXT` real decision weight, gated behind the Phase-13 ablation study
4. A single narrow current-events poller (official sources only) once the historical foundation above is in place

## 24. Files changed

**Modified**: `src/bitcoin_cycle_analyzer/event_evidence.py` (additive schema + validation), `dashboard/app.py` (Events chart layer, Event Inspector fields, Simple Mode "WHAT MATTERS", imports), `tests/test_pro_terminal_ui.py` (+1 assertion)
**Created**: `src/bitcoin_cycle_analyzer/event_intelligence.py`, `scripts/seed_golden_events.py`, `tests/test_event_intelligence.py`, this report
**Database**: `database/historical_event_evidence.db` gained 5 columns (migration) + 4 rows (halvings) + 28 reaction rows — the pre-existing 7 events and their reactions are byte-for-byte untouched (append-only, verified)

`decision_intelligence/` (Auftrag 1) and the chart/UX restructure (Auftrag 2) were not modified beyond the additive import/layer wiring described above. Frozen engine hashes unchanged. Execution remains `DISABLED`.
