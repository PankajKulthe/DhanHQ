import { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, CheckCircle2, Database, History, Play, ShieldAlert, Wifi } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BrokerLogin } from "../components/BrokerLogin";
import { MetricTile } from "../components/MetricTile";
import { TradingViewPanel } from "../components/TradingViewPanel";
import { useTradingStore } from "../store/useTradingStore";

function num(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function text(value: unknown, fallback = "-") {
  return value == null || value === "" ? fallback : String(value);
}

function money(value: unknown) {
  return `Rs ${num(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function optionName(item: Record<string, unknown> | null | undefined) {
  return text(item?.option_symbol ?? item?.trading_symbol ?? item?.symbol, "No candidate");
}

function today(daysBack = 0) {
  const date = new Date();
  date.setDate(date.getDate() - daysBack);
  return date.toISOString().slice(0, 10);
}

export function Dashboard() {
  const { status, analytics, scan, backtest, error, loading, backtestLoading, refresh, runScan, runBacktest } = useTradingStore();
  const [backtestRange, setBacktestRange] = useState({ from_date: today(10), to_date: today() });

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectedOptions = scan?.selected_atm_options ?? analytics?.recent_scanned_options ?? [];
  const candidates = scan?.candidates ?? [];
  const bestCandidate = candidates[0] ?? analytics?.best_candidate ?? null;
  const allScannedOptions = selectedOptions.length ? selectedOptions : analytics?.recent_scanned_options ?? [];
  const strongStocks = scan?.strong_stocks ?? [];
  const storage = analytics?.storage ?? {};
  const dataPlanInactive = Boolean(status?.connected && status.data_plan && status.data_plan.toUpperCase() !== "ACTIVE");

  const chartData = [
    { name: "Wins", value: analytics?.wins ?? 0 },
    { name: "Losses", value: analytics?.losses ?? 0 },
    { name: "Trades", value: analytics?.trades_executed ?? 0 }
  ];

  const equityData = useMemo(() => {
    const curve = (backtest?.metrics?.equity_curve as unknown[]) ?? [];
    return curve.map((value, index) => ({ name: String(index + 1), equity: num(value) }));
  }, [backtest]);

  async function runLatestCandidateBacktest() {
    await runBacktest({
      ...backtestRange,
      use_latest_candidate: true,
      config: {
        max_trades_per_day: 2,
        risk_per_trade: 6000,
        max_daily_loss: 12000,
        min_premium: 20,
        min_volume: 50000,
        max_spread_pct: 2.5,
        range_start: "09:15",
        range_end: "09:25",
        square_off_time: "15:15",
        sl_mode: "RISK",
        target_mode: "FIXED_RR",
        rr: 2,
        volume_confirmation_multiplier: 1.2,
        vwap_exit_enabled: true,
        min_trade_score: 75
      }
    });
  }

  return (
    <main className="min-h-screen bg-[#f7f8f5] text-ink">
      <header className="border-b border-line bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">Options Trading Desk</h1>
            <p className="text-sm text-neutral-500">Dhan scanner, stored analytics, backtests, and controlled execution</p>
          </div>
          <div className={`inline-flex items-center gap-2 text-sm font-semibold ${status?.connected ? "text-gain" : "text-loss"}`}>
            <Wifi size={17} /> {status?.message ?? "Checking"}
          </div>
        </div>
      </header>

      <BrokerLogin />

      <section className="mx-auto grid max-w-7xl gap-4 px-6 py-6 md:grid-cols-5">
        <MetricTile label="Daily PnL" value={money(analytics?.daily_pnl ?? 0)} tone={(analytics?.daily_pnl ?? 0) >= 0 ? "gain" : "loss"} />
        <MetricTile label="Realized" value={money(analytics?.realized_pnl ?? 0)} tone={(analytics?.realized_pnl ?? 0) >= 0 ? "gain" : "loss"} />
        <MetricTile label="Breadth" value={scan?.breadth_score ?? analytics?.nifty_breadth_score ?? 0} />
        <MetricTile label="Sentiment" value={scan?.nifty_sentiment ?? scan?.sentiment ?? analytics?.sentiment ?? "UNKNOWN"} />
        <MetricTile label="Trades Today" value={`${analytics?.trades_executed ?? 0} / 2`} />
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 pb-8 xl:grid-cols-[1fr_0.9fr]">
        <div className="space-y-5">
          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold"><Activity size={17} /> Strategy Scanner</div>
              <button onClick={runScan} disabled={loading || dataPlanInactive} className="inline-flex h-9 items-center gap-2 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">
                <Play size={15} /> {loading ? "Scanning" : "Run Scan"}
              </button>
            </div>
            {error && <div className="mb-3 border border-loss bg-red-50 px-3 py-2 text-sm font-medium text-loss">{error}</div>}
            {dataPlanInactive && (
              <div className="mb-3 border border-amber bg-yellow-50 px-3 py-2 text-sm font-medium text-amber">
                Dhan Data API is {status?.data_plan}. Scanner needs active Dhan market quote access. Data validity: {status?.data_validity ?? "NA"}.
              </div>
            )}
            <div className="grid gap-3 text-sm text-neutral-600 md:grid-cols-4">
              <div>Watchlist <span className="font-semibold text-ink">{candidates.length}</span></div>
              <div>Scanned <span className="font-semibold text-ink">{scan?.scanned_symbols ?? (analytics?.storage?.stock_sentiment_rows_today ? 49 : 0)}</span></div>
              <div>Bullish <span className="font-semibold text-gain">{scan?.bullish_count ?? analytics?.bullish_count ?? 0}</span></div>
              <div>Bearish <span className="font-semibold text-loss">{scan?.bearish_count ?? analytics?.bearish_count ?? 0}</span></div>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-neutral-600 md:grid-cols-3">
              <div>Score <span className="font-semibold text-ink">{Number(scan?.sentiment_score ?? 0).toFixed(1)}</span></div>
              <div>Confidence <span className="font-semibold text-ink">{Number(scan?.confidence_score ?? 0).toFixed(1)}</span></div>
              <div>Regime <span className="font-semibold text-ink">{scan?.market_regime ?? "-"}</span></div>
            </div>
          </div>

          <div className="border border-line bg-white p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><CheckCircle2 size={17} /> Perfect Candidate</div>
            {bestCandidate ? (
              <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <div className="text-lg font-semibold">{optionName(bestCandidate)}</div>
                  <div className="mt-1 text-sm text-neutral-600">
                    {text(bestCandidate.underlying)} {num(bestCandidate.underlying_change_pct).toFixed(2)}% · {text(bestCandidate.option_type)} · {money(bestCandidate.premium)}
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-neutral-600 md:grid-cols-4">
                    <span>Vol {num(bestCandidate.volume).toLocaleString("en-IN")}</span>
                    <span>Spread {bestCandidate.spread_pct == null ? "-" : `${num(bestCandidate.spread_pct).toFixed(2)}%`}</span>
                    <span>Momentum {num(bestCandidate.momentum_score)}</span>
                    <span>Smart {num(bestCandidate.smart_money_score)}</span>
                    <span>Trade {num(bestCandidate.final_trade_score)}</span>
                    <span>VWAP {money(bestCandidate.vwap)}</span>
                    <span>CPR {text(bestCandidate.cpr_status)}</span>
                    <span>Rank {text(bestCandidate.final_rank, bestCandidate.eligible ? "1" : "-")}</span>
                  </div>
                </div>
                <div className="border border-line bg-[#fbfaf7] p-3 text-sm">
                  <div className="font-semibold">Entry Plan</div>
                  <div className="mt-2 text-neutral-600">5m close above 9:15-9:25 option range high, volume confirmation, VWAP hold, CPR already confirmed.</div>
                  <div className="mt-3 font-semibold">Risk Rule</div>
                  <div className="mt-2 text-neutral-600">Max 2 trades/day, Rs 6,000 risk/trade, SL trigger from risk engine, Dhan SL limit below trigger.</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-neutral-600">No eligible candidate yet. Run the scanner after Dhan is connected.</div>
            )}
          </div>

          <div className="border border-line bg-white p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><BarChart3 size={17} /> All Scanned Options</div>
            <div className="max-h-[420px] overflow-auto border border-line">
              <table className="w-full min-w-[920px] border-collapse text-left text-xs">
                <thead className="sticky top-0 bg-[#eef2ef] text-neutral-600">
                  <tr>
                    <th className="px-3 py-2">Option</th>
                    <th className="px-3 py-2">Stock</th>
                    <th className="px-3 py-2">Premium</th>
                    <th className="px-3 py-2">Volume</th>
                    <th className="px-3 py-2">Spread</th>
                    <th className="px-3 py-2">Momentum</th>
                    <th className="px-3 py-2">Smart</th>
                    <th className="px-3 py-2">Trade</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {allScannedOptions.map((item, index) => (
                    <tr key={`${optionName(item)}-${index}`} className="border-t border-line">
                      <td className="px-3 py-2 font-semibold">{optionName(item)}</td>
                      <td className="px-3 py-2">{text(item.underlying ?? item.stock_symbol)} {num(item.underlying_change_pct).toFixed(2)}%</td>
                      <td className="px-3 py-2">{money(item.premium)}</td>
                      <td className="px-3 py-2">{num(item.volume).toLocaleString("en-IN")}</td>
                      <td className="px-3 py-2">{item.spread_pct == null ? "-" : `${num(item.spread_pct).toFixed(2)}%`}</td>
                      <td className="px-3 py-2">{num(item.momentum_score)}</td>
                      <td className="px-3 py-2">{num(item.smart_money_score)}</td>
                      <td className="px-3 py-2">{num(item.final_trade_score)}</td>
                      <td className="px-3 py-2">
                        <span className={item.eligible ? "font-semibold text-gain" : "font-semibold text-loss"}>{item.eligible ? "Perfect" : "Rejected"}</span>
                        {!item.eligible && Array.isArray(item.rejection_reasons) && item.rejection_reasons.length > 0 && (
                          <div className="mt-1 text-[11px] text-neutral-500">{item.rejection_reasons.join(", ")}</div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!allScannedOptions.length && (
                    <tr><td colSpan={9} className="px-3 py-4 text-neutral-600">No scanned options stored yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <TradingViewPanel />

          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><History size={17} /> Backtest Latest Candidate</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <label className="grid gap-1">
                <span className="text-xs font-medium uppercase text-neutral-500">From</span>
                <input className="h-9 border border-line px-2" type="date" value={backtestRange.from_date} onChange={(event) => setBacktestRange({ ...backtestRange, from_date: event.target.value })} />
              </label>
              <label className="grid gap-1">
                <span className="text-xs font-medium uppercase text-neutral-500">To</span>
                <input className="h-9 border border-line px-2" type="date" value={backtestRange.to_date} onChange={(event) => setBacktestRange({ ...backtestRange, to_date: event.target.value })} />
              </label>
            </div>
            <button onClick={runLatestCandidateBacktest} disabled={backtestLoading || !status?.connected} className="mt-3 inline-flex h-9 items-center gap-2 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">
              <Play size={15} /> {backtestLoading ? "Running" : "Run Backtest"}
            </button>
            {backtest && (
              <div className="mt-4 space-y-3">
                <div className="text-sm font-semibold">{text(backtest.source?.option_symbol, "Latest candidate")}</div>
                <div className="grid grid-cols-2 gap-2 text-xs text-neutral-600">
                  <span>Trades {text(backtest.metrics.trades)}</span>
                  <span>Win {text(backtest.metrics.win_rate)}%</span>
                  <span>PF {text(backtest.metrics.profit_factor)}</span>
                  <span>Expectancy {money(backtest.metrics.expectancy)}</span>
                  <span>Max DD {text(backtest.metrics.max_drawdown)}</span>
                  <span>Sharpe {text(backtest.metrics.sharpe_ratio)}</span>
                </div>
                <div className="h-40 border border-line p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={equityData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" hide />
                      <YAxis width={52} />
                      <Tooltip />
                      <Line type="monotone" dataKey="equity" stroke="#147d4c" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><Database size={17} /> Data Storage Health</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>Latest scan</div><div className="font-semibold">{analytics?.latest_scan_at ? new Date(analytics.latest_scan_at).toLocaleTimeString("en-IN") : "-"}</div>
              <div>Market rows</div><div className="font-semibold">{storage.market_sentiment_rows ?? 0}</div>
              <div>Stock rows today</div><div className="font-semibold">{storage.stock_sentiment_rows_today ?? 0}</div>
              <div>Options today</div><div className="font-semibold">{storage.scanned_option_rows_today ?? 0}</div>
              <div>Filter lifecycle</div><div className="font-semibold">{storage.filtered_stock_rows_today ?? 0}</div>
              <div>Watchlist rows</div><div className="font-semibold">{storage.option_watchlist_rows_today ?? 0}</div>
            </div>
          </div>

          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><ShieldAlert size={17} /> Risk State</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>Mode</div><div className="font-semibold">Paper by default</div>
              <div>Max trades/day</div><div className="font-semibold">2</div>
              <div>Live trading</div><div className="font-semibold text-loss">Disabled unless env enabled</div>
              <div>SL order</div><div className="font-semibold">Dhan STOP_LOSS</div>
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
