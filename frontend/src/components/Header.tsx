import { headerFeeds } from "../lib/health";
import { stateText, systemHeadline, usd } from "../lib/language";
import type { LiveState } from "../lib/types";

/**
 * Two-second answer to "is TAKEOFF actually running right now?".
 *
 * Line 1: what we track and what it costs. Line 2: the system verdict plus one
 * dot per feed. When the browser's own stream is down we say so explicitly
 * rather than showing the last known state as if it were current.
 */
export function Header({ state, streamOk }: { state: LiveState | null; streamOk: boolean }) {
  const price = state?.price.mid ?? null;
  const system = streamOk
    ? systemHeadline(state?.connection ?? "OFFLINE")
    : { label: "KEINE VERBINDUNG", tone: "bad" as const };
  const feeds = headerFeeds(state);

  return (
    <header className="hdr">
      <div className="hdr-top">
        <div className="hdr-brand">
          <span className="hdr-mark">TAKEOFF</span>
          <span className="hdr-symbol">{state?.price.symbol ?? "BTC/USD"}</span>
        </div>
        <div className="hdr-price">{usd(price)}</div>
      </div>

      <div className="hdr-bottom">
        <span className={`pill pill-${system.tone}`}>
          <i className={`dot dot-${system.tone}`} aria-hidden="true" />
          {system.label}
        </span>
        <div className="hdr-feeds">
          {feeds.map((feed) => (
            <span
              key={feed.key}
              className="feed-chip"
              title={`${feed.label}: ${stateText(feed.state)}`}
            >
              {feed.label}
              <i className={`dot dot-${feed.tone}`} aria-hidden="true" />
            </span>
          ))}
        </div>
      </div>
    </header>
  );
}
