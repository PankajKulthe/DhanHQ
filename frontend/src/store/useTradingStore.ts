import { create } from "zustand";
import { api } from "../api/client";
import type { BacktestResult, BrokerStatus, DailyAnalytics, ScanResult } from "../types";

type State = {
  status: BrokerStatus | null;
  scan: ScanResult | null;
  scans: Record<string, ScanResult | null>;
  analytics: DailyAnalytics | null;
  backtest: BacktestResult | null;
  error: string;
  loading: boolean;
  backtestLoading: boolean;
  refresh: () => Promise<void>;
  runScan: (universe?: "NIFTY_50" | "NIFTY_NEXT_50") => Promise<void>;
  runBacktest: (payload: Record<string, unknown>) => Promise<void>;
};

export const useTradingStore = create<State>((set) => ({
  status: null,
  scan: null,
  scans: {},
  analytics: null,
  backtest: null,
  error: "",
  loading: false,
  backtestLoading: false,
  refresh: async () => {
    set({ loading: true, error: "" });
    try {
      const [status, analytics] = await Promise.all([
        api.get<BrokerStatus>("/auth/broker/status"),
        api.get<DailyAnalytics>("/analytics/daily")
      ]);
      set({ status: status.data, analytics: analytics.data, loading: false });
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      set({ error: maybeAxios.response?.data?.detail || maybeAxios.message || "Refresh failed", loading: false });
    }
  },
  runScan: async (universe = "NIFTY_50") => {
    set({ loading: true, error: "" });
    try {
      const response = await api.post<ScanResult>("/market/scan", { universe });
      const analytics = await api.get<DailyAnalytics>("/analytics/daily");
      set((state) => ({ scan: response.data, scans: { ...state.scans, [universe]: response.data }, analytics: analytics.data, loading: false }));
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      set({ error: maybeAxios.response?.data?.detail || maybeAxios.message || "Scanner failed", loading: false });
    }
  },
  runBacktest: async (payload: Record<string, unknown>) => {
    set({ backtestLoading: true, error: "" });
    try {
      const response = await api.post<BacktestResult>("/backtests/run", payload);
      set({ backtest: response.data, backtestLoading: false });
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      set({ error: maybeAxios.response?.data?.detail || maybeAxios.message || "Backtest failed", backtestLoading: false });
    }
  }
}));
