export type BrokerStatus = {
  broker: string;
  connected: boolean;
  client_code?: string;
  feed_connected: boolean;
  message: string;
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
  final_option_watchlist?: Record<string, unknown>[];
  selected_atm_options?: Record<string, unknown>[];
  strong_stocks?: Record<string, unknown>[];
  candidates: Record<string, unknown>[];
};

export type DailyAnalytics = {
  trade_date: string;
  stocks_moved_gt_2pct: number;
  nifty_breadth_score: number;
  sentiment: string;
  trades_executed: number;
  daily_pnl: number;
  wins: number;
  losses: number;
};
