# BitcoinElliot — P1 Chart Interaction: Persistent Drawings + Fibonacci — Abschlussbericht

Scope: exactly this focused pass — persistent user drawings + a Fibonacci retracement tool. Decision Engine, Cycle/Elliott Intelligence, Event Intelligence, global UX structure, navigation, and information hierarchy were not touched.

## 1. Ausgangscommit / Endcommit

- Ausgangscommit: `d815222` (Auftrag 4 baseline)
- Endcommit: this pass's commit — see `git log -1` after this report

## 2. Technischer Ist-Stand-Audit (Phase 1, performed before writing code)

Checked directly against the installed Streamlit version's `st.plotly_chart` signature (not assumed from memory):

```
on_select: "ignore" | "rerun" | callable
selection_mode: "points", "box", "lasso" or an Iterable of these
```

**Finding**: `on_select`/`selection_mode` exists only for Plotly *data-point* selection (click/box-select/lasso-select on traces). It does **not** expose Plotly's shape-`relayout` events — the events the native drawing-toolbar buttons (`drawline`, `drawrect`, `drawcircle`, `drawopenpath`, `eraseshape`, already wired since Auftrag 2) generate when a user drags a shape onto the chart. Streamlit has no built-in way to read those shapes back into Python. Capturing them would require a custom JS component (`Plotly.react` + a `relayout` listener posting through `Streamlit.setComponentValue`) — real engineering work, not a config flag.

**Consequence for scope**: mouse-drag-drawn shapes from the native toolbar remain **scratch-only** (visible while drawing, gone on the next rerun) — unchanged from before this pass, and honestly re-labelled in the UI caption to say so explicitly. Editable/persistent drawings were instead implemented via **form-defined** drawings: the user enters a price (and, for Fibonacci, two prices) through ordinary Streamlit number inputs, and the resulting shape is rendered on the chart and saved to disk. This is not a workaround or a downgrade — it fully satisfies the actual requirement ("persistent, editable, deletable drawings") entirely inside the existing Plotly/Streamlit stack, with zero new dependencies, zero custom components, and identical behavior on desktop and mobile (number inputs are naturally touch-friendly, unlike freehand mouse dragging). Per the brief's own fallback clause, this does **not** trigger the "DRAWING TECHNOLOGY LIMITATION — APPROVAL REQUIRED" gate, because no migration or even a prototype component was needed to deliver real persistence — only the *mechanism* for creating a shape changed from "drag" to "type a number."

Editability: implemented as **Lock / Unlock / Delete** (attempting to edit a locked drawing raises, enforced in the store layer, not just the UI) rather than drag-to-move, for the same reason — there is no drag-capture path without a custom component. A locked drawing survives accidental deletion; an unlocked one can be deleted and its exact JSON re-inserted via Undo.

Reruns: every drawing mutation (add/update/delete/lock) is a discrete Streamlit widget action (button click), so it already only fires once per user action — never per pixel of mouse movement, since there is no mouse-drag capture in the first place. No debouncing was needed because there is nothing continuous to debounce.

## 3. Minimaler Drawing Scope — was wurde gebaut

- **Horizontal Line** — price + optional label
- **Rectangle / Custom Zone** — low/high price + optional label
- **Fibonacci Retracement** — Point A price + Point B price, computes and renders all 7 required ratios (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
- **Delete**, **Lock/Unlock** (doubles as the edit-guard), **Undo** (restores the last deleted drawing, or removes the last added one)
- **Trendline**: not implemented as a persistent tool — a trendline fundamentally needs two (time, price) points captured by direct chart interaction to feel usable; a "type two dates and two prices" form is technically possible but was judged to produce a worse UX than the value it adds in this pass, and the brief explicitly allowed dropping it ("Trendline, sofern im aktuellen Stack sauber möglich") given the same relayout-capture limitation. Documented here rather than shipped as a degraded form.

No 20-tool toolbar — exactly the three types above, plus the pre-existing scratch-only native toolbar (unchanged).

## 4. Drawing Persistence — `UserDrawingState`

New `src/bitcoin_cycle_analyzer/drawing_state.py`, `UserDrawingStore`:

```
drawing_id, type (HLINE|RECTANGLE|FIB), timeframe, coordinates (dict),
text, locked, style, created_at, updated_at
```

Never imported by `decision_intelligence/`, `event_evidence.py`, or `event_intelligence.py` — test-enforced (`test_drawing_state_module_is_never_imported_by_decision_intelligence`, which greps those modules' source for any mention of `drawing_state`/`UserDrawingStore`). `build_decision_state()`'s signature was also directly inspected to confirm it has no drawing-related parameter.

## 5. Save / Restore

Verified live, not just unit-tested: added a horizontal line in the browser, confirmed it appeared on disk (`runtime/drawings/BTCUSD.json`), reloaded the page (full Streamlit rerun from a fresh HTTP request, not just a rerun-in-session), and confirmed via `gd.layout.shapes` inspection that the shape reappeared on the chart automatically. No drawing is ever silently lost — `list()` reads directly from disk on every script run, there is no in-memory-only state.

Scope semantics: **per symbol, per timeframe** — a drawing added while viewing `1D` will not appear on `1W` unless its `timeframe` is explicitly `ALL_TIMEFRAMES` (supported by the store, not yet exposed as a UI checkbox — see Limitations). This was a deliberate choice, documented directly in the UI (`"N saved on {timeframe}"` in the expander header), not left implicit.

## 6. Drawing Storage

Reused the existing `runtime/` directory convention (already used by `ai_cache`, `production8`) rather than introducing a new database — one JSON file per symbol (`runtime/drawings/BTCUSD.json`). No new SQLite database, no schema migration, no new infrastructure dependency.

## 7. Fibonacci Retracement

`compute_fib_levels(price_a, price_b)` — pure arithmetic (`price_a + (price_b - price_a) * ratio` for each of the 7 required ratios), verified both directions (A above or below B) produce correct anchor-to-1.0 mapping. Rendered on the chart as purple dotted lines labelled `MY FIB {ratio}`.

## 8. MY FIB vs SYSTEM FIB

Explicitly disambiguated in the UI: the Fibonacci form carries the caption *"MY FIB — your own retracement, independent of any Elliott/engine-derived target (see SYSTEM zones/targets above for those)."* The chart's decision zone/invalidation/target lines (Auftrag 2) remain visually and semantically separate — different colors, different annotation prefix (`MY` vs none/`SYSTEM`), never mixed into the same trace or computation.

## 9. Fib Persistence

Covered by the same `UserDrawingStore` — a `FIB` drawing stores `price_a`/`price_b` (not pre-computed levels), so the ratios are recomputed from the two anchors on every render. Verified live: added, reloaded, still present (`runtime/drawings/BTCUSD.json` retained the `FIB` entry across a full page reload).

## 10. No Decision Side Effect

Structurally guarded, not just promised:
- `test_drawing_state_module_is_never_imported_by_decision_intelligence` — greps `decision_intelligence`, `decision_engine`, `evidence` module source for any reference to the drawing module
- `test_decision_engine_signature_has_no_drawing_parameter` — inspects `build_decision_state`'s actual parameter list
- The chart's decision-zone/invalidation/target rendering code (Auftrag 2) and the user-drawing rendering code are two separate, sequential blocks in `app.py` that both read from `di`/`drawing_store` respectively — neither writes to the other

## 11. "Analyze This Zone" (optional, Section 10)

Implemented in small form, as the brief allowed ("nur wenn klein umsetzbar"): each `RECTANGLE` drawing gets an **Analyze** button that checks, using only already-computed values (no new engine call), whether the zone overlaps the 200W moving average, the currently active decision zone, or the Elliott invalidation level — and reports the result as plain informational text (*"This zone overlaps 200W, overlaps active buy zone — informational only, does not create a signal"*). No new signal, score, or decision path is created; verified by inspection that this code path never calls into `decision_intelligence`.

## 12. Toolbar

Compact: a `TOOL` radio (Horizontal Line / Rectangle Zone / Fibonacci) plus the relevant input fields, inside one `DRAWING TOOLS (N saved on {timeframe})` expander — collapsed by default, not competing with the primary chart/decision view for space (consistent with Auftrag 4's information-hierarchy work, which this pass did not otherwise touch).

## 13. Undo / Redo

**Undo implemented** (restores the last deleted drawing, or removes the last added one, via a per-session `st.session_state["drawing_undo_stack"]` LIFO list). **Redo not implemented** — a true redo would need to track undone actions separately and is meaningfully more state-machine complexity for a feature whose primary value (not losing a drawing to an accidental click) is already delivered by Undo. Documented as a deliberate scope cut, not an oversight.

## 14. Mobile

Tested live at 390×844: no horizontal overflow; the `DRAWING TOOLS` expander opens correctly (confirmed via DOM inspection: `keyboard_arrow_down` state + form fields visible); the saved-drawing count updates correctly after a delete performed earlier in the same session. Because drawing creation is form-based (number inputs, not mouse-drag), there is no touch-specific drawing interaction to test separately — the same code path works identically on desktop and mobile, which is a direct benefit of the technology choice in §2.

## 15. Performance

No dragging exists in this implementation (see §2), so there is no per-pixel recompute risk to mitigate. Each drawing action is one discrete Streamlit rerun triggered by a button click — the same cost class as any other button in the app (timeframe switch, preset button), not a new performance concern.

## 16. Tests

**324 passed** (was 303 after Auftrag 4) = 303 + 20 new (`tests/test_drawing_state.py`) + 1 new (`test_terminal_apptest_renders_without_exception_with_mixed_drawing_types` in `tests/test_pro_terminal_ui.py`).

Coverage: serialization round-trip, restore-after-reopen (simulating app restart), invalid-type rejection, update/delete, locked-drawing edit/delete guards, timeframe isolation (including the `ALL_TIMEFRAMES` marker), per-symbol file separation, undo/restore, Fibonacci ratio coverage and both-direction anchor correctness, and three no-decision-side-effect guards (§10).

**A real bug was found and fixed during live QA, not by the unit tests**: the per-drawing description line originally used a Python dict literal (`{"HLINE": ..., "RECTANGLE": ..., "FIB": ...}[type]`) to pick a description string — but dict literals evaluate *every* value eagerly, so as soon as two different drawing types coexisted (e.g. one `HLINE` + one `FIB`), building the `RECTANGLE` branch's f-string raised `KeyError: 'low'` even though that branch was never selected. This crashed the entire app for any user with more than one drawing type saved. Fixed by replacing the dict literal with a plain if/elif chain, and a regression test was added that seeds all three drawing types into the real `runtime/drawings/BTCUSD.json` path and runs a full `AppTest` — this is exactly the scenario the unit tests (which each tested one drawing type in isolation) did not catch, and exactly why the brief's "Live QA" step (§17 below) is not redundant with the test suite.

## 17. Live QA (Desktop + Mobile, performed against the real running app)

- **Desktop**: added a horizontal line → confirmed on disk → reloaded the page → confirmed the shape reappeared on the chart (read `gd.layout.shapes` directly)
- **Desktop**: added a Fibonacci retracement → confirmed 7 shapes with the correct color rendered on the chart → confirmed the JSON anchors persisted on disk
- **Desktop**: deleted a drawing → confirmed removal on disk and in the UI's saved-count
- **Desktop**: locked a drawing → confirmed `"locked": true` persisted on disk
- **Mobile 390×844**: confirmed no horizontal overflow, confirmed the `DRAWING TOOLS` expander opens and reflects the correct saved-count after a prior desktop-session delete (proving the same on-disk state is shared correctly across viewport sizes, as expected since both are the same server-side file)
- Found and fixed the mixed-drawing-type crash (§16) during this process — confirms the value of doing live QA rather than trusting green unit tests alone

## 18. Tests vorher/nachher

- Vorher (Auftrag 4 Endstand): 303 passed
- Nachher: **324 passed**
- Vollständiger Lauf: `324 passed, 1 warning`

## Bekannte Einschränkungen (ehrlich)

- **No mouse-drag drawing capture** — the native Plotly toolbar's drawn shapes remain scratch-only (unchanged from before this pass); form-based input is the persistent path. This is a real, structural Streamlit limitation, not a partial implementation of drag-capture.
- **No Trendline tool** — would need two (time, price) points; judged not worth a form-based approximation this pass (see §3)
- **No Redo** (only Undo) — deliberate scope cut (§13)
- **No per-UI toggle for `ALL_TIMEFRAMES` scope** — the store supports it, the UI always saves to the currently-selected timeframe; a checkbox to opt into "show on every timeframe" would be a small follow-up, not built here
- **Editing = unlock, delete, re-add** — there is no in-place "change this line's price" form; given the low friction of delete+re-add for a single number, this was judged sufficient rather than building a separate edit form per drawing type

## Langfristige Plotly-Eignung

**Plotly/Streamlit remains sufficient** for BitcoinElliot's chart needs, re-confirmed by this pass: candles, zoom/pan/crosshair/log-scale, decision-zone/invalidation/target rendering, event markers, and now persistent form-based drawings/Fibonacci are all delivered without a migration or even a prototype component. The one durable gap is **native mouse-drag shape capture** — if genuine click-and-drag trendline/rectangle drawing (TradingView-style) becomes a hard product requirement later, that specific capability (not the whole chart) would need a custom Streamlit component; everything else this pass touched did not need one. This narrows, rather than widens, the case for any future migration.

## Files changed

**Modified**: `dashboard/app.py` (drawing rendering + toolbar UI), `tests/test_pro_terminal_ui.py` (+1 regression test)
**Created**: `src/bitcoin_cycle_analyzer/drawing_state.py`, `tests/test_drawing_state.py`, this report
**Runtime data**: `runtime/drawings/` (gitignored, like other `runtime/` subdirectories — not committed)

No engine file, `decision_intelligence/`, `event_evidence.py`/`event_intelligence.py`, navigation, or information-hierarchy code was modified. Frozen hashes unchanged. Execution remains `DISABLED`.
