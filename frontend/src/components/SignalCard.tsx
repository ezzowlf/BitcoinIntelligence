import {
  clockTime,
  conflictText,
  evidenceText,
  horizon,
  noSignalHeadline,
  reasonText,
  stateText,
  tone,
  usd,
} from "../lib/language";
import type { LiveState } from "../lib/types";

/**
 * "What should I be watching right now?" — the single most important surface.
 *
 * Every value rendered here comes from the engine's own shadow-signal record.
 * Where the engine reports nothing (confidence is `null` until calibration),
 * the field is omitted rather than filled with a plausible-looking number.
 */
export function SignalCard({ state }: { state: LiveState }) {
  const shadow = state.shadow_signal;
  const signal = shadow?.signal ?? null;
  const live = signal !== null && signal.state_to === "LIVE";
  const direction = signal?.direction ?? null;

  const missing = signal?.missing_evidence ?? [];
  const reasons = signal?.reasons ?? [];

  return (
    <section className={`signal ${live ? `signal-${direction?.toLowerCase()}` : "signal-none"}`}>
      <div className="signal-top">
        <span className="signal-label">TAKEOFF SIGNAL</span>
        <span className="signal-symbol">{state.price.symbol}</span>
      </div>

      <div className="signal-verdict">
        {live ? (
          <span className={`verdict verdict-${direction?.toLowerCase()}`}>{direction}</span>
        ) : (
          <span className="verdict verdict-none">KEIN SIGNAL</span>
        )}
        <span className="signal-price">{usd(state.price.mid)}</span>
      </div>

      {live && signal ? <LiveSignalBody signal={signal} /> : <NoSignalBody state={state} reasons={reasons} missing={missing} />}

      {signal?.conflicts?.length ? (
        <p className="signal-conflict">
          Konflikt: {signal.conflicts.map(conflictText).join(" · ")}
        </p>
      ) : null}

      {shadow?.paused ? <p className="signal-paused">Signalbewertung pausiert.</p> : null}
    </section>
  );
}

function LiveSignalBody({ signal }: { signal: NonNullable<NonNullable<LiveState["shadow_signal"]>["signal"]> }) {
  const [low, high] = signal.entry_zone ?? [null, null];
  return (
    <>
      <dl className="facts">
        <Fact label="Entry-Zone" value={`${usd(low)} – ${usd(high)}`} />
        <Fact label="Invalidierung" value={usd(signal.invalidation)} />
        <Fact label="Zielklasse" value={signal.expected_move_class ? `$${signal.expected_move_class}` : "—"} />
        <Fact label="Zeithorizont" value={horizon(signal.expected_horizon)} />
        <Fact label="Ausführbare Seite" value={signal.vantage_executable_side ?? "—"} />
        <Fact label="Signalzeit" value={clockTime(signal.timestamp)} />
        <Fact label="Gültig bis" value={clockTime(signal.expires_at)} />
        <Fact label="Kalibrierung" value={signal.calibration_status ?? "—"} />
      </dl>
      {signal.reasons?.length ? (
        <p className="signal-why">{signal.reasons.map(reasonText).join(" · ")}</p>
      ) : null}
      <p className="signal-id">Signal-ID {signal.setup_id.slice(0, 12)}</p>
    </>
  );
}

function NoSignalBody({
  state,
  reasons,
  missing,
}: {
  state: LiveState;
  reasons: string[];
  missing: string[];
}) {
  const market = state.market_state;
  const shadow = state.shadow_signal;
  const signal = shadow?.signal ?? null;

  return (
    <>
      <p className="signal-headline">{noSignalHeadline(reasons, missing)}</p>

      {missing.length > 0 && (
        <p className="signal-missing">
          Fehlt: {missing.map(evidenceText).join(" · ")}
        </p>
      )}

      <dl className="facts">
        <Fact label="Marktlage" value={market.direction_bias || "—"} />
        {signal?.direction ? (
          <Fact label="Nächste mögliche Richtung" value={signal.direction} />
        ) : null}
        <Fact label="Flussübereinstimmung" value={flowText(market.flow_agreement)} />
        <Fact
          label="Datenqualität"
          value={stateText(state.health?.components?.binance_spot?.state)}
          tone={tone(state.health?.components?.binance_spot?.state)}
        />
      </dl>

      {signal && (
        <details className="signal-tech">
          <summary>Technischer Grund</summary>
          <p className="mono">
            {reasons.length ? reasons.join(" · ") : "—"}
            {missing.length ? ` · missing_evidence: ${missing.join(", ")}` : ""}
          </p>
          <p className="mono dim">
            {signal.state_to} · {signal.signal_version}
          </p>
        </details>
      )}
    </>
  );
}

function flowText(value: string): string {
  if (value === "CONFIRMED") return "Bestätigt";
  if (value === "DIVERGENT") return "Divergent";
  if (value === "NEUTRAL") return "Neutral";
  return value || "—";
}

function Fact({ label, value, tone: factTone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd className={factTone ? `tone-${factTone}` : undefined}>{value}</dd>
    </div>
  );
}
