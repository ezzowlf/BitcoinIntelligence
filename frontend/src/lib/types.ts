export type ChecklistStatus = "MET" | "MISSING" | "RISK";

export interface ChecklistRow {
  label: string;
  status: ChecklistStatus;
  detail: string;
}

export interface SourceRow {
  key: string;
  label: string;
  state: string;
  online: boolean;
}

export interface LiveState {
  server_time: string;
  connection: "LIVE" | "STALE" | "OFFLINE";
  price: {
    symbol: string;
    mid: number | null;
    bid: number | null;
    ask: number | null;
    spread: number | null;
    age_seconds: number | null;
    timestamp: string | null;
  };
  market_state: {
    setup_state: string;
    direction_bias: string;
    final_decision: string;
    long_pressure_score: number;
    short_pressure_score: number;
    flow_agreement: "CONFIRMED" | "DIVERGENT" | "NEUTRAL";
    spot_flow: string;
    futures_flow: string;
    l2_imbalance: number | null;
    range_expansion: number | null;
    realized_volatility: number | null;
    flow_pressure: number | null;
  };
  assessment: string;
  proximity: {
    score: number;
    components: Record<string, number>;
    label: string;
    is_probability: boolean;
  };
  checklist: ChecklistRow[];
  sources: SourceRow[];
  v5_3: {
    discovery_win_rate: number;
    discovery_label: string;
    forward_resolved: number;
    forward_target: number;
    forward_progress: string;
    forward_wins: number;
    accepted_signals: number;
    veto_blocked_signals: number;
    provisional_rate: number | null;
    verified: boolean;
    status: string;
    hypothesis_sha256: string;
  };
  execution: string;
  tick_count: number;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface CandleResponse {
  symbol: string;
  source: string;
  timeframe: string;
  has_volume: boolean;
  tick_count: number;
  candles: Candle[];
  execution: string;
}

export const TIMEFRAMES = ["30s", "1m", "3m", "5m", "15m", "1h", "4h"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];
