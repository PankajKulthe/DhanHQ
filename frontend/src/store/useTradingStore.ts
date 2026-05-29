import { create } from "zustand";
import { api } from "../api/client";
import type { BrokerStatus, DailyAnalytics, ScanResult } from "../types";

type State = {
  status: BrokerStatus | null;
  scan: ScanResult | null;
  analytics: DailyAnalytics | null;
  error: string;
  loading: boolean;
  refresh: () => Promise<void>;
  runScan: () => Promise<void>;
};

export const useTradingStore = create<State>((set) => ({
  status: null,
  scan: null,
  analytics: null,
  error: "",
  loading: false,
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
  runScan: async () => {
    set({ loading: true, error: "" });
    try {
      const response = await api.post<ScanResult>("/market/scan", {});
      set({ scan: response.data, loading: false });
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
      set({ error: maybeAxios.response?.data?.detail || maybeAxios.message || "Scanner failed", loading: false });
    }
  }
}));
