/**
 * Derives what the UI shows about feeds and pipeline from the backend health
 * report. This layer only *selects and labels* — it never upgrades a state.
 * If the backend says OFFLINE, every view here says OFFLINE.
 */
import type { ComponentHealth, LiveState } from "./types";
import { componentText, tone, type Tone } from "./language";

export interface FeedRow {
  key: string;
  label: string;
  state: string;
  tone: Tone;
  ageSeconds: number | null;
  lastEventAt: string | null;
  reconnects: number;
  lastError: string | null;
  recoveryLevel: number;
  detail: string | null;
  /** Optional feeds degrade the system rather than breaking it. */
  optional: boolean;
}

/** Feeds shown in the header, in the order the spec asks for. */
export const HEADER_FEEDS = ["vantage", "binance_spot", "binance_futures", "l2"] as const;

const SHORT_LABEL: Record<string, string> = {
  vantage: "Vantage",
  binance_spot: "Spot",
  binance_futures: "Futures",
  l2: "L2",
};

const OPTIONAL = new Set(["binance_futures", "l2"]);

function toRow(key: string, component: ComponentHealth | undefined, label: string): FeedRow {
  return {
    key,
    label,
    state: component?.state ?? "UNKNOWN",
    tone: tone(component?.state),
    ageSeconds: component?.age_seconds ?? null,
    lastEventAt: component?.last_event_at ?? null,
    reconnects: component?.reconnect_count ?? 0,
    lastError: component?.last_error ?? null,
    recoveryLevel: component?.recovery_level ?? 0,
    detail: component?.detail ?? null,
    optional: OPTIONAL.has(key),
  };
}

/** Compact feed set for the header strip. */
export function headerFeeds(state: LiveState | null): FeedRow[] {
  const components = state?.health?.components ?? {};
  return HEADER_FEEDS.map((key) => toRow(key, components[key], SHORT_LABEL[key] ?? key));
}

/** Feeds plus the decision pipeline, for the DATA HEALTH view. */
export function dataHealthRows(state: LiveState | null): FeedRow[] {
  const components = state?.health?.components ?? {};
  const rows = HEADER_FEEDS.map((key) => toRow(key, components[key], componentText(key)));
  rows.push(toRow("decision_pipeline", components.decision_pipeline, componentText("decision_pipeline")));
  return rows;
}

/** Everything the backend reports, for the SYSTEM page. */
export function allComponents(state: LiveState | null): FeedRow[] {
  const components = state?.health?.components ?? {};
  return Object.keys(components)
    .sort()
    .map((key) => toRow(key, components[key], componentText(key)));
}

export interface ProblemSummary {
  /** True while anything is not fully healthy. */
  degraded: boolean;
  critical: boolean;
  /** Feed/component keys that are not healthy. */
  affected: FeedRow[];
  headline: string;
  body: string;
}

/**
 * The compact alert card's content. Deliberately describes the *effect on the
 * product* ("Signalentscheidung pausiert") rather than restating component
 * states, which stay available under Details.
 */
export function problemSummary(state: LiveState | null): ProblemSummary | null {
  if (!state) return null;
  const connection = (state.connection ?? "").toUpperCase();
  if (connection === "LIVE" || connection === "FULL_LIVE") return null;

  const affected = allComponents(state).filter((row) => row.tone === "warn" || row.tone === "bad");
  const critical = connection === "CRITICAL" || connection === "OFFLINE";
  const feedNames = affected
    .filter((row) => (HEADER_FEEDS as readonly string[]).includes(row.key))
    .map((row) => componentText(row.key));

  const headline = critical ? "Datenfeed gestört" : "System eingeschränkt";
  const parts: string[] = [];
  if (feedNames.length > 0) {
    parts.push(`${feedNames.join(" + ")} ${feedNames.length > 1 ? "werden" : "wird"} neu verbunden.`);
  }
  parts.push(
    critical
      ? "Signalentscheidung vorübergehend pausiert."
      : "Signalentscheidung läuft eingeschränkt weiter.",
  );

  return { degraded: true, critical, affected, headline, body: parts.join(" ") };
}
