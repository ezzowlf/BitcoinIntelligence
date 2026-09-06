type Signal = { setup_id: string; state_to: string; timestamp: string };
type Store = Pick<Storage, "getItem" | "setItem">;

/** At-most-once per setup/stage; first frame and disabled intervals stay silent. */
export class SignalAnnouncements {
  private seen: Set<string>;
  private initialized = false;
  private storage: Store;
  constructor(storage: Store) {
    this.storage = storage;
    try { this.seen = new Set(JSON.parse(storage.getItem("waverun.signal.seen") ?? "[]")); }
    catch { this.seen = new Set(); }
  }
  accept(signal: Signal | null | undefined, enabled: boolean, now: number): "PREWARNING" | "LIVE" | null {
    if (!signal) return null;
    const key = `${signal.setup_id}:${signal.state_to}`;
    const known = this.seen.has(key);
    const first = !this.initialized;
    this.initialized = true;
    this.seen.add(key);
    this.seen = new Set([...this.seen].slice(-2000));
    try { this.storage.setItem("waverun.signal.seen", JSON.stringify([...this.seen])); }
    catch { return null; } // no durable dedup guarantee, remain silent
    const age = now - Date.parse(signal.timestamp);
    if (first || known || !enabled || !Number.isFinite(age) || age < 0 || age > 10000) return null;
    return signal.state_to === "PREWARNING" || signal.state_to === "LIVE" ? signal.state_to : null;
  }
}
