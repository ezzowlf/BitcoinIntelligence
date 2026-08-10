# BitcoinElliot — Master-Auftrag 2: TradingView-artige UX / Charting — Abschlussbericht

Scope: exactly Master-Auftrag 2. Auftrag 1's Decision Intelligence architecture (`decision_intelligence/`) was **not** touched or duplicated — this pass is a pure UI consumer of it, plus of the existing `analyze_intelligence(...)` engine state. Auftrag 3 (News/Events) was not started; the chart's zone/annotation code was written so an `Events` layer can be added later without restructuring.

## Result: **Option A — existing stack (Streamlit + Plotly) is sufficient. No migration.**

Per the Migration Approval Gate: this is Outcome **A**, not B. No Chart Technology Decision Report requesting approval is needed — P0 was fully achievable inside the current stack, proven by the fixes below, not just asserted.

---

## 1. UX Baseline Audit (performed first, against the real running app)

Measured live via DOM inspection (screenshot tool unavailable in this environment — see Honest Limitations):

| Area | Finding |
|---|---|
| Desktop 1920×1080, chart | 555×1393px = **72.6% of viewport width**, chart started at y=428 (header stack ate ~430px above it) |
| Desktop sidebar | 7 stacked `.sidepanel` cards totalling **1175px tall** — far exceeding the 555px chart height |
| Desktop total page | `main.scrollHeight` = **3040px** vs 1080px viewport → 2.8 screens of scrolling to see everything |
| Mobile 390×844, chart | Candlestick chart didn't start until **y=2319px** — user had to scroll ~2.75 phone-screens before seeing any price action |
| Mobile touch targets | **43 buttons under 44px** (timeframe buttons were 32px tall) |
| Chart interaction | Zoom/pan/crosshair/hover/log-scale/native drawing shapes (line/rect/circle/erase) already present and client-side (no rerun) |
| Chart interaction gaps | No Fibonacci tool, no persistent/editable drawings, no touch-optimized drawing handles |
| Decision Intelligence (Auftrag 1) | Zone/invalidation/targets/confidence existed only as sidebar text — **never drawn on the chart itself** |

This is the concrete evidence base for every fix below — not a subjective impression.

## 2. P0 fixes implemented (all inside Streamlit + Plotly, no migration)

1. **Chart is now full-width and leads the page.** Removed the `left(1) / main(3.15)` column split entirely. Chart width went from 72.6% → **96.7%** of viewport (measured after the change). The 7 sidebar cards moved to a CSS grid (`auto-fit, minmax(160px,1fr)`) **below** the chart instead of a narrow column beside it — verified at 1920px they sit in **one row** (not stacked), and the grid reflows automatically down to mobile without a media-query per breakpoint.
2. **Mobile chart-reachability improved 53%**: chart now appears at y=1091 instead of y=2319 (measured). Not perfect — see Honest Limitations — but a concrete, measured improvement without inventing a new nav system.
3. **Decision Intelligence is now drawn ON the chart**, not just in a sidebar (Teil "Decision Intelligence visuell nutzen"): active zone rendered as a colored `hrect` labelled `"{ZONE_TYPE} · {ENTRY_STATUS}"` in the decision's own color, invalidation as a dashed red `hline`, T1/T2/T3 targets as dotted blue `hline`s — verified live: chart layout now contains 10 shapes and annotations `["STRONG BUY ZONE · WAITING FOR CONFIRMATION", "INVALIDATION $60,122", "T1 $68,079", "T2 $117,527", "T3 $126,188", ...]`. **These render unconditionally** (test-enforced: `test_decision_zone_and_invalidation_render_unconditionally_on_chart`) — they are priority-1 chart content, never gated behind a layer toggle, per the brief's "CHART LAYER PRIORITY" ordering (candles → current price → active decision zone → entry/confirmation/invalidation/targets → Elliott → major levels → secondary/research layers).
4. **Touch targets**: added `min-height:44px` CSS for button-group/radio elements (segmented controls, timeframe buttons, layer chips).
5. **Chart height increases in Simple Mode** (620px vs 555px in Research) since Simple Mode has no side panel competing for space.

## 3. Simple / Research Mode (Teil "SIMPLE MODE" / "RESEARCH MODE")

New `VIEW: SIMPLE / RESEARCH` segmented control, state-backed by the new `ui_state.py` module (see §6), **defaults to RESEARCH** (deliberate choice — this is a daily-use power-user terminal today, not yet a public product; defaulting to Simple would have silently hidden the existing workflow. Both modes are one click apart).

**Simple Mode**, verified live:
```
CURRENT VIEW          ACCUMULATE
GOOD AREA              BUY ZONE 1 · $63,206 – $64,794
ENTRY                  WAITING FOR CONFIRMATION
WAITING FOR             Weekly close > Elliott confirmation level ($117,527)
WRONG IF BELOW          $60,122
WHY?  3 positive factors, 0 against — Interesting long-term region, but entry is not yet confirmed.
```
No `Evidence Family`, `Confluence`, or rule IDs (e.g. `DE-006`) anywhere in Simple Mode — those stay in Research Mode's WHY expander and SYSTEM tab. A collapsible "Explain the terms used above" panel surfaces plain-language glossary definitions (Cycle, Invalidation, Confirmation, Reclaim). Simple Mode reduces the timeframe control to `1D/1W/1M/1Y/ALL` (drops 4H, irrelevant at a glance) and **hides all tabs, bottom cards, and the sidebar grid** via `st.stop()` right after the chart — confirmed live: page ends immediately after the chart caption.

**Research Mode** is the full existing experience: chart, decision card grid, bottom cards (Cycle/Historical/Momentum/Data), and all 6 tabs — unchanged in content, only reflowed (§2.1).

Neither mode changes any computation — both read the exact same `decision_intel`/`decision_explanation`/`state` objects; Simple Mode only chooses which fields to render and in what language.

## 4. Elliott / Cycle UX

Not rebuilt in this pass (already delivered: full-history chart, degree toggles, Primary/Alternative counts, "WHY THIS COUNT?" expander, invalidation/confirmation lines — see Checkpoint 2A). The explicit, honest limitation from Auftrag 1 (`FullHistoryElliottEngine` can only distinguish "wave 4/recovery" vs "ABC/C-wave", not full Wave 1–5) is unchanged and still surfaced via `elliott_cycle_context()["known_limitation"]`. No new Elliott labels were invented for the UI, per instruction.

## 5. Chart Technology Decision Matrix

| Requirement | Plotly (current) | Verdict |
|---|---|---|
| Candlesticks, log scale, zoom/pan/crosshair/hover | Native, client-side, no rerun | READY |
| Decision zones/invalidation/targets as shapes+annotations | Native (`add_hrect`/`add_hline`), now wired | READY (built this pass) |
| Horizontal line / rectangle / circle / free-path drawing | Native modebar tools (`drawline`, `drawrect`, `drawcircle`, `drawopenpath`, `eraseshape`) | READY |
| Fibonacci retracement tool | No native tool | **GAP** — would need custom JS or a client-side component |
| Persistent/editable drawings across reruns | Plotly keeps shapes in-browser only; Streamlit reruns don't clear them, but there is no server-side save/restore | **GAP** — needs a small custom Streamlit component (`streamlit-plotly-events` style) or `st.session_state` + `relayoutData` capture, not attempted this pass |
| Mobile touch pan/zoom | Native (Plotly.js touch support) | READY |
| Mobile touch drawing (finger-drag to draw) | Works via Plotly's native touch handling, not verified pixel-precise on a real device | PARTIAL — verified no crash/overflow, not verified as comfortable finger-drawing UX |
| Licensing | Plotly.py: MIT license, free for commercial use, no attribution requirement | READY — no licensing blocker for a commercial product |
| Streamlit integration / maintenance | Already integrated, one dependency, no server component to run | READY |

**Conclusion**: every P0 requirement is met by the current stack. The two P1 gaps (Fibonacci tool, persistent drawings) do not block P0 and are exactly the kind of narrow, isolated addition the brief anticipated as a possible future "Streamlit + custom chart component" step — **not attempted in this pass** because P0 didn't require it and building an unused adapter/component now would be exactly the "P2-Spielerei vor P0" the brief explicitly warns against.

**No Chart Technology Prototype was built.** Per the brief's own sequencing ("Falls nötig: isolierten alternativen Chart-Prototyp bauen"), a prototype is only warranted when the current stack demonstrably can't reach P0 — it can, so building one now would have been unnecessary scope, not diligence.

## 6. State separation (Teil "STATE-TRENNUNG")

New `src/bitcoin_cycle_analyzer/ui_state.py`:
- **ENGINE STATE** — `analyze_intelligence(...)` output (untouched, upstream, unaffected by this pass)
- **DECISION STATE** — `decision_intelligence.build_decision_state(...)` output (Auftrag 1, untouched)
- **CHART VIEW STATE** — `ui_state.py`, new this pass: `{timeframe, scale, preset, layers, mode}`, seeded once per session from `st.query_params`, then persisted via `st.session_state["chart_view_state"]` — a single dict instead of loose ad hoc session_state keys
- **EXPLANATION STATE** — `decision_intelligence.build_explanation_facts(...)` output (Auftrag 1, untouched)

`SELECTED OBJECT STATE` and `USER DRAWING STATE` (from the brief's fuller state list) are **not yet implemented** — there is no persisted drawing/selection state to separate yet (§5 gap), so introducing empty state categories for them now would be speculative, not real separation. Documented as the natural next step once drawing persistence is built.

## 7. Responsive QA — verified viewports

| Viewport | Horizontal overflow | Console errors | Notes |
|---|---|---|---|
| 1920×1080 | None | None | Chart 96.7% width, 6-card grid in 1 row |
| 1366×768 | None | None | 6-card grid still fits 1 row |
| 768×1024 (tablet portrait) | None | None | — |
| 390×844 (mobile) | None | None | Chart reachable at y=1091 (was 2319) |

Not separately verified this pass: 1440×900, 1024×768, tablet landscape, 430px mobile — the CSS grid's `auto-fit` behavior and the four viewports actually tested make regressions at the untested sizes unlikely, but this is a real, honest gap (see §9), not a claim of full coverage.

## 8. Performance / Streamlit rerun audit

Findings: pan, zoom, crosshair, and hover are handled entirely by Plotly.js in the browser — **zero Streamlit reruns** for these interactions (verified by design: they are not Streamlit widgets, Plotly owns them client-side). Reruns are triggered only by genuine discrete actions: timeframe/scale/preset buttons, the layer multiselect, the SIMPLE/RESEARCH toggle, tab switches — all of which are appropriate places for a rerun (the user explicitly changed what should render). No unnecessary reruns were introduced by this pass; none were found to remove. `st.fragment`-based partial reruns were considered but not implemented — current interaction cost is already low enough that this would be premature optimization, not a fix for a measured problem.

## 9. Honest remaining limitations

- Mobile chart is reachable sooner (y=1091 vs 2319) but still requires ~1.3 screens of scroll before appearing — Streamlit's linear top-to-bottom script execution makes true "chart-first-on-every-device" reordering without a custom layout component structurally hard; a deeper fix would need either accepting a materially different header (much shorter) on mobile specifically, or a custom component
- No Fibonacci drawing tool, no persistent/editable drawings across reruns (§5) — explicitly scoped out as P1, not P0
- No dedicated `ChartAdapter`/`ChartModel` abstraction layer was built — with only one chart technology in active use, an adapter has no second implementation to abstract over yet; introducing one now would be speculative architecture, not the "smallest change that meets the goal" principle the brief itself asks for. Recommended only if/when a second chart technology is actually adopted.
- `USER DRAWING STATE` / `SELECTED OBJECT STATE` not implemented (no drawing persistence exists yet to have state for)
- Simple Mode's plain-language explanation text is still generated from the same deterministic templates as Research Mode's WHY panel (Auftrag 1's `explanation.py`) — no separate "simple language" NLG layer was built; the existing templates already avoid jargon well enough that a second layer wasn't justified
- 1440×900, 1024×768, tablet landscape, 430px mobile not individually verified this pass (§7)
- Screenshot tool unavailable in this environment throughout — all visual verification was via DOM/JS inspection (element positions, computed layout, annotation text) and console-log checks, not pixel screenshots

## 10. Tests

- **261 passed** (was 249 before this pass) = 249 + 6 new (`tests/test_ui_state.py`) + 6 new assertions added to `tests/test_pro_terminal_ui.py` (Simple/Research mode default, unconditional zone rendering, touch targets, glossary sanity, UI-state separation, no-business-logic-in-UI guard)
- 3 pre-existing assertions were updated to match intentional architecture changes (dynamic chart height per mode; `LAYER_PRESETS` moved from `app.py` into `ui_state.py`) — not weakened, redirected to check the new correct location
- `test_no_zone_classification_logic_is_reimplemented_in_the_ui` specifically guards against the failure mode the brief warns about (UI recomputing decisions) — it fails if `app.py` ever branches on price to decide a zone type outside the one allowed display-color lookup
- Full suite run: `261 passed, 1 warning` (same `.pytest_tmp` basetemp fix from the baseline-reconciliation pass, no permission errors)

## 11. Frozen hashes / execution state

Unchanged (`md5sum` identical before/after this pass). No frozen engine file was opened for writing. Execution remains `DISABLED` throughout — this pass touched only `dashboard/app.py`, `tests/test_pro_terminal_ui.py`, and two new files (`src/bitcoin_cycle_analyzer/ui_state.py`, `src/bitcoin_cycle_analyzer/glossary.py`) plus their tests.

## 12. Files changed

**Modified**: `dashboard/app.py` (layout restructure, decision-on-chart, Simple/Research mode), `tests/test_pro_terminal_ui.py` (updated + 6 new assertions)
**Created**: `src/bitcoin_cycle_analyzer/ui_state.py`, `src/bitcoin_cycle_analyzer/glossary.py`, `tests/test_ui_state.py`, this report

No `decision_intelligence/` file was modified — Auftrag 1's architecture is untouched, exactly as instructed.
