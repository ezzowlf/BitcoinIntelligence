import type { NotificationPermissionState } from "../lib/api";

/**
 * Push and sound controls with their current state always visible.
 *
 * Restored 2026-09-21: the mobile redesign dropped this row, which left the
 * sound toggle unreachable and made it impossible to grant notification
 * permission at all (the browser only accepts that request from a user
 * gesture). A LIVE signal is visible for ~305s roughly once every 15h, so
 * without these two channels there is effectively no way to learn one fired.
 */
export function AlertControls({
  audio,
  push,
}: {
  audio: { enabled: boolean; toggle: () => void };
  push: { permission: NotificationPermissionState; request: () => Promise<void> };
}) {
  const pushState: Record<NotificationPermissionState, { label: string; tone: string }> = {
    granted: { label: "AN", tone: "ok" },
    denied: { label: "BLOCKIERT", tone: "bad" },
    default: { label: "AUS", tone: "idle" },
    unsupported: { label: "NICHT VERFÜGBAR", tone: "idle" },
  };
  const current = pushState[push.permission];

  return (
    <section className="alerts">
      <span className="alerts-label">ALARME BEI LIVE-SIGNAL</span>

      <div className="alerts-row">
        <span className="alerts-name">Push-Benachrichtigung</span>
        <span className="alerts-action">
          <span className={`tag tag-${current.tone}`}>{current.label}</span>
          {push.permission === "default" ? (
            <button type="button" onClick={() => void push.request()}>
              Aktivieren
            </button>
          ) : null}
        </span>
      </div>
      {push.permission === "denied" ? (
        <p className="alerts-hint">
          Im Browser blockiert – nur in den Website-Einstellungen wieder freigebbar.
        </p>
      ) : null}

      <div className="alerts-row">
        <span className="alerts-name">Signalton</span>
        <span className="alerts-action">
          <span className={`tag tag-${audio.enabled ? "ok" : "idle"}`}>
            {audio.enabled ? "AN" : "AUS"}
          </span>
          <button type="button" aria-pressed={audio.enabled} onClick={audio.toggle}>
            {audio.enabled ? "Ausschalten" : "Einschalten"}
          </button>
        </span>
      </div>
    </section>
  );
}
