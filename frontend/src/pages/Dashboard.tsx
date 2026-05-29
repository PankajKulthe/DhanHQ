import { useEffect } from "react";
import { Activity, Play, ShieldAlert, Wifi } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BrokerLogin } from "../components/BrokerLogin";
import { MetricTile } from "../components/MetricTile";
import { TradingViewPanel } from "../components/TradingViewPanel";
import { useTradingStore } from "../store/useTradingStore";

export function Dashboard() {
  const { status, analytics, scan, error, loading, refresh, runScan } = useTradingStore();

  useEffect(() => {
    refresh();
  }, [refresh]);

  const chartData = [
    { name: "Wins", value: analytics?.wins ?? 0 },
    { name: "Losses", value: analytics?.losses ?? 0 },
    { name: "Trades", value: analytics?.trades_executed ?? 0 }
  ];

  return (
    <main className="min-h-screen bg-[#fbfaf7] text-ink">
      <header className="border-b border-line bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Options Trading Desk</h1>
            <p className="text-sm text-neutral-500">Nifty breadth, option breakout execution, backtests, and risk controls</p>
          </div>
          <div className={`inline-flex items-center gap-2 text-sm font-semibold ${status?.connected ? "text-gain" : "text-loss"}`}>
            <Wifi size={17} /> {status?.message ?? "Checking"}
          </div>
        </div>
      </header>

      <BrokerLogin />

      <section className="mx-auto grid max-w-7xl gap-4 px-6 py-6 md:grid-cols-4">
        <MetricTile label="Daily PnL" value={`Rs ${analytics?.daily_pnl ?? 0}`} tone={(analytics?.daily_pnl ?? 0) >= 0 ? "gain" : "loss"} />
        <MetricTile label="Breadth Score" value={scan?.breadth_score ?? analytics?.nifty_breadth_score ?? 0} />
        <MetricTile label="Sentiment" value={scan?.sentiment ?? analytics?.sentiment ?? "UNKNOWN"} />
        <MetricTile label="Moved >2%" value={scan?.moved_count ?? analytics?.stocks_moved_gt_2pct ?? 0} />
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 pb-8 lg:grid-cols-[1.4fr_0.8fr]">
        <TradingViewPanel />
        <div className="space-y-5">
          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold"><Activity size={17} /> Strategy Scanner</div>
              <button onClick={runScan} disabled={loading} className="inline-flex h-9 items-center gap-2 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">
                <Play size={15} /> {loading ? "Scanning" : "Run"}
              </button>
            </div>
            {error && <div className="mb-3 border border-loss bg-red-50 px-3 py-2 text-sm font-medium text-loss">{error}</div>}
            <div className="text-sm text-neutral-600">
              Watchlist: {scan?.candidates.length ?? 0}
              {scan?.scanned_symbols ? ` / Scanned: ${scan.scanned_symbols}` : ""}
              {scan?.bullish_count != null ? ` / Bullish: ${scan.bullish_count}` : ""}
              {scan?.bearish_count != null ? ` / Bearish: ${scan.bearish_count}` : ""}
              {scan?.neutral_count != null ? ` / Neutral: ${scan.neutral_count}` : ""}
            </div>
            {scan?.nifty_sentiment === "SIDEWAYS" && <div className="mt-2 border border-amber bg-yellow-50 px-3 py-2 text-sm font-medium text-amber">Nifty sentiment is sideways, so final trade watchlist is disabled by rule.</div>}
            <div className="mt-3 h-60 overflow-auto border border-line">
              {((scan?.candidates?.length ? scan.candidates : scan?.selected_atm_options) ?? []).map((item, index) => (
                <div key={index} className="border-b border-line px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">{String(item.option_symbol ?? item.trading_symbol ?? item.symbol ?? "Candidate")}</span>
                    <span className={item.eligible ? "text-gain" : "text-amber"}>{item.eligible ? "Eligible" : "Watch"}</span>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-neutral-600">
                    <span>{String(item.underlying)} {Number(item.underlying_change_pct ?? 0).toFixed(2)}%</span>
                    <span>{String(item.option_type)} @ Rs {Number(item.premium ?? 0).toFixed(2)}</span>
                    <span>Vol {Number(item.volume ?? 0).toLocaleString("en-IN")}</span>
                    <span>OI {Number(item.oi ?? 0).toLocaleString("en-IN")}</span>
                    <span>Turnover Rs {Number(item.turnover ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
                    <span>Momentum {String(item.momentum_label ?? "-")} {Number(item.momentum_score ?? 0)}</span>
                    <span>Strike {String(item.strike ?? "-")}</span>
                    <span>Spread {item.spread_pct == null ? "-" : `${Number(item.spread_pct).toFixed(2)}%`}</span>
                    <span>Session {Number(item.session_move_pct ?? 0).toFixed(2)}%</span>
                    <span>Last 5m {Number(item.last_candle_move_pct ?? 0).toFixed(2)}%</span>
                    <span>CPR Bottom {item.cpr_available ? Number(item.cpr_bottom ?? item.cpr_bc ?? 0).toFixed(2) : "-"}</span>
                    <span className={item.cpr_confirmed ? "text-gain" : "text-loss"}>{item.cpr_confirmed ? "Above CPR" : item.cpr_available ? "Below CPR" : "CPR unavailable"}</span>
                  </div>
                  {!item.eligible && Array.isArray(item.rejection_reasons) && item.rejection_reasons.length > 0 && (
                    <div className="mt-2 text-xs font-medium text-loss">Reject: {item.rejection_reasons.join(", ")}</div>
                  )}
                </div>
              ))}
              {scan && scan.candidates.length === 0 && (
                <div className="px-3 py-3 text-sm text-neutral-600">
                  No final watchlist entries. Showing selected options with rejection reasons. Selected options: {scan.selected_atm_options?.length ?? 0}; strong stocks: {scan.strong_stocks?.length ?? 0}.
                </div>
              )}
            </div>
          </div>
          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><ShieldAlert size={17} /> Risk State</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>Mode</div><div className="font-semibold">Paper by default</div>
              <div>Live trading</div><div className="font-semibold text-loss">Disabled unless env enabled</div>
              <div>Duplicate trades</div><div className="font-semibold">Idempotency protected</div>
            </div>
          </div>
          <div className="h-56 border border-line bg-white p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#147d4c" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </main>
  );
}
