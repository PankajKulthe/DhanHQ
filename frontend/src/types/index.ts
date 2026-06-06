export type BrokerStatus = {
  broker: string;
  connected: boolean;
  client_code?: string;
  feed_connected: boolean;
  message: string;
  active_segment?: string | null;
  data_plan?: string | null;
  data_validity?: string | null;
};

export type ScanResult = {
  generated_at: string;
  sentiment: "POSITIVE" | "NEGATIVE" | "SIDEWAYS" | "BULLISH" | "BEARISH";
  nifty_sentiment?: "POSITIVE" | "NEGATIVE" | "SIDEWAYS";
  breadth_score: number;
  scanned_symbols?: number;
  moved_count?: number;
  bullish_count?: number;
  bearish_count?: number;
  neutral_count?: number;
  sentiment_score?: number;
  confidence_score?: number;
  market_regime?: string;
  final_option_watchlist?: Record<string, unknown>[];
  selected_atm_options?: Record<string, unknown>[];
  strong_stocks?: Record<string, unknown>[];
  stock_sentiments?: Record<string, unknown>[];
  top_gainers?: Record<string, unknown>[];
  top_losers?: Record<string, unknown>[];
  candidates: Record<string, unknown>[];
};

export type DailyAnalytics = {
  trade_date: string;
  stocks_moved_gt_2pct: number;
  nifty_breadth_score: number;
  sentiment: string;
  trades_executed: number;
  daily_pnl: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  wins: number;
  losses: number;
  latest_scan_at?: string | null;
  bullish_count?: number;
  bearish_count?: number;
  neutral_count?: number;
  storage?: Record<string, number>;
  best_candidate?: Record<string, unknown> | null;
  recent_scanned_options?: Record<string, unknown>[];
  recent_trades?: Record<string, unknown>[];
};

export type BacktestResult = {
  metrics: Record<string, unknown>;
  trades: Record<string, unknown>[];
  rules?: Record<string, unknown>;
  source?: Record<string, unknown>;
};
