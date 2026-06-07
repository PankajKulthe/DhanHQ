import { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, CheckCircle2, Database, History, KeyRound, LogIn, Play, ShieldAlert, Wifi } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { BrokerLogin } from "../components/BrokerLogin";
import { MetricTile } from "../components/MetricTile";
import { OptionCandlestickChart } from "../components/OptionCandlestickChart";
import { TradingViewPanel } from "../components/TradingViewPanel";
import { useTradingStore } from "../store/useTradingStore";
import type { HistoricalOptionResponse, LatestCandidate } from "../types";

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
  const { status, analytics, scan, scans, backtest, error, loading, backtestLoading, refresh, runScan, runBacktest } = useTradingStore();
  const [backtestRange, setBacktestRange] = useState({ from_date: today(10), to_date: today() });
  const [activeUniverse, setActiveUniverse] = useState<"NIFTY_50" | "NIFTY_NEXT_50">("NIFTY_50");
  const [workspaceTab, setWorkspaceTab] = useState<"SCANNER" | "CHARTS">("SCANNER");
  const [chartCandidate, setChartCandidate] = useState<LatestCandidate | null>(null);
  const [chartDataState, setChartDataState] = useState<HistoricalOptionResponse | null>(null);
  const [chartBusy, setChartBusy] = useState(false);
  const [chartError, setChartError] = useState("");
  const [chartMode, setChartMode] = useState<"HISTORICAL" | "LIVE">("HISTORICAL");
  const [chartForm, setChartForm] = useState({ security_id: "", option_symbol: "", from_date: today(7), to_date: today(), interval: "5" });
  const [appAccess, setAppAccess] = useState({ checking: true, enabled: false, unlocked: false });
  const [appPassword, setAppPassword] = useState("");
  const [appBusy, setAppBusy] = useState(false);
  const [appError, setAppError] = useState("");

  useEffect(() => {
    let alive = true;
    async function checkAppAccess() {
      try {
        const response = await api.get<{ enabled: boolean; unlocked: boolean }>("/auth/app/status");
        if (!alive) return;
        setAppAccess({ checking: false, enabled: response.data.enabled, unlocked: response.data.unlocked });
        if (response.data.unlocked) {
          await refresh();
        }
      } catch {
        if (alive) {
          setAppAccess({ checking: false, enabled: true, unlocked: false });
        }
      }
    }
    checkAppAccess();
    return () => {
      alive = false;
    };
  }, [refresh]);

  useEffect(() => {
    if (!appAccess.unlocked) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/api/v1/ws/dashboard`);
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === "dashboard") {
          useTradingStore.setState({ analytics: payload.data });
        }
      } catch {
        // Ignore malformed websocket frames; HTTP refresh still works.
      }
    };
    return () => {
      socket.close();
    };
  }, [appAccess.unlocked]);

  useEffect(() => {
    if (chartMode !== "LIVE" || !chartForm.security_id || workspaceTab !== "CHARTS") return;
    const timer = window.setInterval(() => {
      loadChart(false, true);
    }, 12000);
    return () => window.clearInterval(timer);
  }, [chartMode, chartForm.security_id, chartForm.from_date, chartForm.to_date, chartForm.interval, workspaceTab]);

  async function unlockApp() {
    setAppError("");
    if (!appPassword.trim()) {
      setAppError("Enter your private dashboard password.");
      return;
    }
    setAppBusy(true);
    try {
      const response = await api.post<{ enabled: boolean; unlocked: boolean }>("/auth/app/login", { password: appPassword });
      setAppAccess({ checking: false, enabled: response.data.enabled, unlocked: response.data.unlocked });
      setAppPassword("");
      await refresh();
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      setAppError(maybeAxios.response?.data?.detail || maybeAxios.message || "Unlock failed");
    } finally {
      setAppBusy(false);
    }
  }

  const activeScan = scans[activeUniverse] ?? (scan?.universe === activeUniverse ? scan : null);
  const selectedOptions = activeScan?.selected_atm_options ?? (activeUniverse === "NIFTY_50" ? analytics?.recent_scanned_options : []) ?? [];
  const candidates = activeScan?.candidates ?? [];
  const bestCandidate = candidates[0] ?? (activeUniverse === "NIFTY_50" ? analytics?.best_candidate : null) ?? null;
  const allScannedOptions = selectedOptions.length ? selectedOptions : activeUniverse === "NIFTY_50" ? analytics?.recent_scanned_options ?? [] : [];
  const strongStocks = activeScan?.strong_stocks ?? [];
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

  async function loadLatestChartCandidate() {
    setChartError("");
    setChartBusy(true);
    try {
      const response = await api.get<LatestCandidate>("/historical/latest-candidate", { params: { universe: activeUniverse } });
      const candidate = response.data;
      setChartCandidate(candidate);
      setChartForm((current) => ({
        ...current,
        security_id: candidate.security_id,
        option_symbol: candidate.option_symbol
      }));
      await loadChart(true, chartMode === "LIVE", candidate.security_id);
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      setChartError(maybeAxios.response?.data?.detail || maybeAxios.message || "Candidate load failed");
    } finally {
      setChartBusy(false);
    }
  }

  async function loadChart(useCurrentForm = true, live = chartMode === "LIVE", overrideSecurityId?: string) {
    const securityId = overrideSecurityId || chartForm.security_id.trim();
    if (!securityId) {
      setChartError("Select a candidate or enter a Dhan security id.");
      return;
    }
    setChartError("");
    if (useCurrentForm) setChartBusy(true);
    try {
      const response = await api.get<HistoricalOptionResponse>("/historical/options", {
        params: {
          security_id: securityId,
          from_date: chartForm.from_date,
          to_date: chartForm.to_date,
          interval: chartForm.interval,
          exchange_segment: "NSE_FNO",
          instrument: chartCandidate?.instrument || "OPTSTK",
          live
        }
      });
      setChartDataState(response.data);
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      setChartError(maybeAxios.response?.data?.detail || maybeAxios.message || "Chart load failed");
    } finally {
      if (useCurrentForm) setChartBusy(false);
    }
  }

  if (appAccess.checking) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f7f8f5] px-6 text-ink">
        <div className="border border-line bg-white px-5 py-4 text-sm font-semibold">Checking dashboard access...</div>
      </main>
    );
  }

  if (appAccess.enabled && !appAccess.unlocked) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f7f8f5] px-6 text-ink">
        <section className="w-full max-w-md border border-line bg-white p-5">
          <div className="flex items-center gap-2 text-base font-semibold">
            <KeyRound size={19} /> Private Trading Desk
          </div>
          <p className="mt-2 text-sm text-neutral-600">Enter the dashboard password before broker access or scanner data is shown.</p>
          <input
            className="mt-4 h-11 w-full border border-line px-3 text-sm outline-none focus:border-ink"
            type="password"
            value={appPassword}
            placeholder="Dashboard password"
            onChange={(event) => setAppPassword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") unlockApp();
            }}
          />
          {appError && <div className="mt-3 border border-loss bg-red-50 px-3 py-2 text-sm font-medium text-loss">{appError}</div>}
          <button onClick={unlockApp} disabled={appBusy} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60">
            <LogIn size={16} /> {appBusy ? "Unlocking" : "Unlock Dashboard"}
          </button>
        </section>
      </main>
    );
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
        <MetricTile label="Breadth" value={activeScan?.breadth_score ?? (activeUniverse === "NIFTY_50" ? analytics?.nifty_breadth_score : 0) ?? 0} />
        <MetricTile label="Sentiment" value={activeScan?.nifty_sentiment ?? activeScan?.sentiment ?? (activeUniverse === "NIFTY_50" ? analytics?.sentiment : "NOT SCANNED") ?? "UNKNOWN"} />
        <MetricTile label="Trades Today" value={`${analytics?.trades_executed ?? 0} / 2`} />
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-5">
        <div className="grid max-w-md grid-cols-2 gap-2 border border-line bg-white p-2">
          {[
            { key: "SCANNER", label: "Scanner" },
            { key: "CHARTS", label: "Charts" }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setWorkspaceTab(tab.key as "SCANNER" | "CHARTS")}
              className={`h-10 border border-line text-sm font-semibold ${workspaceTab === tab.key ? "bg-ink text-white" : "bg-[#f7f8f5] text-ink"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {workspaceTab === "CHARTS" ? (
        <section className="mx-auto grid max-w-7xl gap-5 px-6 pb-8 xl:grid-cols-[1fr_0.36fr]">
          <div className="space-y-4">
            <div className="border border-line bg-white p-4">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold"><BarChart3 size={17} /> Option Candlestick Chart</div>
                <div className="flex gap-2">
                  {(["HISTORICAL", "LIVE"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setChartMode(mode)}
                      className={`h-9 border border-line px-3 text-xs font-semibold ${chartMode === mode ? "bg-ink text-white" : "bg-[#f7f8f5] text-ink"}`}
                    >
                      {mode === "LIVE" ? "Live Poll" : "Historical"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-3 text-sm md:grid-cols-[1.1fr_0.9fr_0.9fr_0.6fr_auto_auto]">
                <input className="h-10 border border-line px-3" value={chartForm.security_id} placeholder="Dhan security id" onChange={(event) => setChartForm({ ...chartForm, security_id: event.target.value })} />
                <input className="h-10 border border-line px-3" type="date" value={chartForm.from_date} onChange={(event) => setChartForm({ ...chartForm, from_date: event.target.value })} />
                <input className="h-10 border border-line px-3" type="date" value={chartForm.to_date} onChange={(event) => setChartForm({ ...chartForm, to_date: event.target.value })} />
                <select className="h-10 border border-line px-2" value={chartForm.interval} onChange={(event) => setChartForm({ ...chartForm, interval: event.target.value })}>
                  <option value="1">1m</option>
                  <option value="5">5m</option>
                  <option value="15">15m</option>
                  <option value="25">25m</option>
                  <option value="60">60m</option>
                  <option value="1D">Daily</option>
                </select>
                <button onClick={loadLatestChartCandidate} disabled={chartBusy || !status?.connected} className="h-10 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">Latest</button>
                <button onClick={() => loadChart()} disabled={chartBusy || !status?.connected} className="h-10 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">{chartBusy ? "Loading" : "Load"}</button>
              </div>
              <div className="mt-3 text-xs text-neutral-600">
                {chartForm.option_symbol || chartCandidate?.option_symbol || "Load latest candidate or enter a security id"} | {chartDataState ? `${chartDataState.candles.length} candles | cache ${chartDataState.cache}` : "No data loaded"}
              </div>
              {chartError && <div className="mt-3 border border-loss bg-red-50 px-3 py-2 text-sm font-medium text-loss">{chartError}</div>}
            </div>
            <OptionCandlestickChart data={chartDataState} />
          </div>
          <aside className="space-y-4">
            <div className="border border-line bg-white p-4 text-sm">
              <div className="font-semibold">Chart Levels</div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <span className="text-neutral-600">CPR date</span><span className="font-semibold">{chartDataState?.cpr.date ?? "-"}</span>
                <span className="text-neutral-600">TC</span><span className="font-semibold">{chartDataState?.cpr.tc ? money(chartDataState.cpr.tc) : "-"}</span>
                <span className="text-neutral-600">Pivot</span><span className="font-semibold">{chartDataState?.cpr.pivot ? money(chartDataState.cpr.pivot) : "-"}</span>
                <span className="text-neutral-600">BC</span><span className="font-semibold">{chartDataState?.cpr.bc ? money(chartDataState.cpr.bc) : "-"}</span>
                <span className="text-neutral-600">Source</span><span className="font-semibold">{chartDataState?.cpr.source ?? "-"}</span>
                <span className="text-neutral-600">Mode</span><span className="font-semibold">{chartMode === "LIVE" ? "Polling" : "Historical"}</span>
              </div>
            </div>
            <div className="border border-line bg-white p-4 text-sm">
              <div className="font-semibold">Candidate</div>
              <div className="mt-3 space-y-2 text-neutral-600">
                <div>{chartCandidate?.option_symbol ?? "-"}</div>
                <div>Stock: <span className="font-semibold text-ink">{chartCandidate?.stock_symbol ?? "-"}</span></div>
                <div>Eligible: <span className="font-semibold text-ink">{chartCandidate ? String(chartCandidate.eligible) : "-"}</span></div>
                <div>Token: <span className="font-semibold text-ink">{chartCandidate?.security_id ?? chartForm.security_id || "-"}</span></div>
              </div>
            </div>
          </aside>
        </section>
      ) : (
      <section className="mx-auto grid max-w-7xl gap-5 px-6 pb-8 xl:grid-cols-[1fr_0.9fr]">
        <div className="space-y-5">
          <div className="border border-line bg-white p-2">
            <div className="grid grid-cols-2 gap-2">
              {[
                { key: "NIFTY_50", label: "Nifty 50" },
                { key: "NIFTY_NEXT_50", label: "Nifty Next 50" }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveUniverse(tab.key as "NIFTY_50" | "NIFTY_NEXT_50")}
                  className={`h-10 border border-line text-sm font-semibold ${activeUniverse === tab.key ? "bg-ink text-white" : "bg-[#f7f8f5] text-ink"}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="border border-line bg-white p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold"><Activity size={17} /> {activeUniverse === "NIFTY_NEXT_50" ? "Nifty Next 50 Scanner" : "Nifty 50 Scanner"}</div>
              <button onClick={() => runScan(activeUniverse)} disabled={loading || dataPlanInactive} className="inline-flex h-9 items-center gap-2 bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60">
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
              <div>Scanned <span className="font-semibold text-ink">{activeScan?.scanned_symbols ?? (activeUniverse === "NIFTY_50" && analytics?.storage?.stock_sentiment_rows_today ? 49 : 0)}</span></div>
              <div>Bullish <span className="font-semibold text-gain">{activeScan?.bullish_count ?? (activeUniverse === "NIFTY_50" ? analytics?.bullish_count : 0) ?? 0}</span></div>
              <div>Bearish <span className="font-semibold text-loss">{activeScan?.bearish_count ?? (activeUniverse === "NIFTY_50" ? analytics?.bearish_count : 0) ?? 0}</span></div>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-neutral-600 md:grid-cols-3">
              <div>Score <span className="font-semibold text-ink">{Number(activeScan?.sentiment_score ?? 0).toFixed(1)}</span></div>
              <div>Confidence <span className="font-semibold text-ink">{Number(activeScan?.confidence_score ?? 0).toFixed(1)}</span></div>
              <div>Regime <span className="font-semibold text-ink">{activeScan?.market_regime ?? "-"}</span></div>
            </div>
            {activeUniverse === "NIFTY_NEXT_50" && !activeScan && (
              <div className="mt-3 border border-line bg-[#fbfaf7] px-3 py-2 text-xs text-neutral-600">
                This tab runs the same CPR/VWAP/momentum option scan on the official Nifty Next 50 constituent list.
              </div>
            )}
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
              <div className="text-sm text-neutral-600">No eligible candidate yet. Run the {activeUniverse === "NIFTY_NEXT_50" ? "Nifty Next 50" : "Nifty 50"} scanner after Dhan is connected.</div>
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
      )}
    </main>
  );
}
