/**
 * Presentation-only translation of engine codes into plain language.
 *
 * The engine's own vocabulary (REQUIRED_EVIDENCE_UNAVAILABLE, feed keys,
 * component states) is deliberately left untouched everywhere else: this module
 * is the single place that decides how a code is *shown*. Every function falls
 * back to the raw code, so a code this table has never seen still surfaces
 * verbatim instead of disappearing behind a generic message.
 */

/** Why the engine is not emitting a signal, in the user's words. */
const REASON_TEXT: Record<string, string> = {
  REQUIRED_EVIDENCE_UNAVAILABLE: "Erforderliche Marktdaten fehlen",
  SETUP_EXPIRED: "Setup ist abgelaufen",
  SETUP_INVALIDATED: "Setup wurde invalidiert",
  FLOW_CANDIDATE: "Richtungsfluss erkannt",
  DIRECTIONAL_FLOW_PERSISTS: "Richtungsfluss hält an",
  FLOW_AND_DEPTH_CONFIRM: "Fluss und Orderbuchtiefe bestätigen",
  CAUSAL_RECLAIM: "Preis bestätigt die Richtung",
  EXECUTABLE_SPREAD_VALID: "Spread ist handelbar",
};

/** Feed / evidence keys as the engine names them. */
const EVIDENCE_TEXT: Record<string, string> = {
  spot: "Binance Spot",
  futures: "Binance Futures",
  l2: "Orderbuch (L2)",
  vantage: "Vantage Kurs",
  outcomes: "Outcome-Auswertung",
  storage: "Persistenz",
  executable_quote: "Handelbarer Kurs",
};

// The engine's conflict rule compares signed ORDER-FLOW imbalance
// ((buy-sell)/(buy+sell)) on spot vs futures and fires when the two have
// opposite signs. It never compares prices, so the wording must not suggest a
// price divergence.
const CONFLICT_TEXT: Record<string, string> = {
  SPOT_FUTURES_DIVERGENCE:
    "Orderflow-Konflikt: Spot und Futures zeigen gegenläufigen Kauf-/Verkaufsdruck.",
};

/** Component keys as they appear in health.components. */
const COMPONENT_TEXT: Record<string, string> = {
  vantage: "Vantage",
  binance_spot: "Binance Spot",
  binance_futures: "Binance Futures",
  l2: "Orderbuch (L2)",
  decision_pipeline: "Decision-Pipeline",
  feature_pipeline: "Feature-Pipeline",
  candidate_pipeline: "Candidate-Pipeline",
  prediction_persistence: "Prognose-Speicher",
  outcome_scheduler: "Outcome-Scheduler",
  market_event_pipeline: "Markt-Events",
  consumer_backpressure: "Verarbeitungslast",
  storage: "Speicher",
  disk: "Festplatte",
};

export const reasonText = (code: string): string => REASON_TEXT[code] ?? code;
export const evidenceText = (key: string): string => EVIDENCE_TEXT[key] ?? key;
export const conflictText = (code: string): string => CONFLICT_TEXT[code] ?? code;
export const componentText = (key: string): string => COMPONENT_TEXT[key] ?? key;

/**
 * The one-line headline for "no signal", derived from what the engine actually
 * reported. Never invents a cause: if the engine gave no reason, this says so.
 */
export function noSignalHeadline(
  reasons: string[] | undefined,
  missingEvidence: string[] | undefined,
): string {
  if (missingEvidence && missingEvidence.length > 0) {
    return "Kein Signal – erforderliche Marktdaten fehlen.";
  }
  if (reasons?.includes("SETUP_INVALIDATED")) {
    return "Kein Signal – das Setup wurde invalidiert.";
  }
  if (reasons?.includes("SETUP_EXPIRED")) {
    return "Kein Signal – das Setup ist abgelaufen.";
  }
  return "Kein Signal – die aktuellen Bedingungen erfüllen die Entry-Regeln nicht.";
}

/** Health state -> traffic-light class. Grey means "unknown", never "fine". */
export type Tone = "ok" | "warn" | "bad" | "idle";

export function tone(state: string | undefined | null): Tone {
  const value = (state ?? "").toUpperCase();
  if (["HEALTHY", "LIVE", "CONNECTED", "ONLINE", "AVAILABLE", "RUNNING", "FULL_LIVE"].includes(value)) {
    return "ok";
  }
  if (["DEGRADED", "RECONNECTING", "CONNECTING", "STALE", "STARTING", "RECOVERING", "DEGRADED_LIVE"].includes(value)) {
    return "warn";
  }
  if (["OFFLINE", "CRITICAL", "ERROR", "FAILED"].includes(value)) return "bad";
  return "idle";
}

const STATE_TEXT: Record<string, string> = {
  HEALTHY: "LIVE",
  CONNECTED: "LIVE",
  AVAILABLE: "LIVE",
  ONLINE: "LIVE",
  RUNNING: "LIVE",
  LIVE: "LIVE",
  FULL_LIVE: "LIVE",
  DEGRADED: "DEGRADIERT",
  DEGRADED_LIVE: "DEGRADIERT",
  RECONNECTING: "VERBINDET NEU",
  CONNECTING: "VERBINDET",
  RECOVERING: "RECOVERY",
  STALE: "VERZÖGERT",
  STARTING: "STARTET",
  OFFLINE: "OFFLINE",
  CRITICAL: "KRITISCH",
  UNKNOWN: "UNBEKANNT",
};

export const stateText = (state: string | undefined | null): string =>
  STATE_TEXT[(state ?? "").toUpperCase()] ?? (state ?? "—");

/** System-level banner wording for the header pill. */
export function systemHeadline(connection: string): { label: string; tone: Tone } {
  const value = (connection ?? "").toUpperCase();
  if (value === "LIVE" || value === "FULL_LIVE") return { label: "SYSTEM LIVE", tone: "ok" };
  if (value === "CRITICAL" || value === "OFFLINE") return { label: "SYSTEM KRITISCH", tone: "bad" };
  return { label: `SYSTEM ${stateText(value)}`, tone: "warn" };
}

// ------------------------------------------------------------------ formatting

export function usd(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `$${value.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function age(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds < 1) return "jetzt";
  if (seconds < 60) return `vor ${Math.round(seconds)}s`;
  if (seconds < 3600) return `vor ${Math.round(seconds / 60)} min`;
  return `vor ${Math.round(seconds / 3600)} h`;
}

export function clockTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function horizon(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

/**
 * The engine's own evaluation-time vocabulary, kept deliberately separate from
 * the live-health wording above: a transition records HEALTHY / UNAVAILABLE at
 * the instant it was evaluated, which is not the same statement as a feed being
 * LIVE right now.
 */
const EVIDENCE_STATE_TEXT: Record<string, string> = {
  HEALTHY: "HEALTHY",
  UNAVAILABLE: "UNAVAILABLE",
};

export const evidenceStateText = (state: string | undefined | null): string =>
  EVIDENCE_STATE_TEXT[(state ?? "").toUpperCase()] ?? (state ?? "—");

export function evidenceTone(state: string | undefined | null): Tone {
  const value = (state ?? "").toUpperCase();
  if (value === "HEALTHY") return "ok";
  if (value === "UNAVAILABLE") return "bad";
  return "idle";
}

/** Engine keys as they appear in a transition's feed_health, in setup order. */
export const EVIDENCE_SOURCES = ["spot", "futures", "l2", "vantage"] as const;

/**
 * The Vantage freshness requirement the engine applies, for display only.
 * Mirrors waverun_live.py (`0 <= quote_age <= 3`). Shown so the user can see
 * what "not fresh enough" means; nothing here is used in any decision.
 */
export const VANTAGE_MAX_QUOTE_AGE_S = 3;

/** Signed order-flow imbalance -> direction word. Range is [-1, +1]. */
export function flowPressureText(delta: number | null | undefined): string {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return "—";
  if (delta > 0) return "Kaufdruck";
  if (delta < 0) return "Verkaufsdruck";
  return "neutral";
}

/** Order-flow delta formatted with an explicit sign, e.g. "+0.238". */
export function flowValue(delta: number | null | undefined): string {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return "—";
  return `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}`;
}

/** Seconds with a German decimal comma, e.g. "3,000 s". */
export function seconds(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits })} s`;
}
