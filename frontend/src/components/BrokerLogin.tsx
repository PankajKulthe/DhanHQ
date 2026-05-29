import { useState } from "react";
import { KeyRound, LogIn } from "lucide-react";
import { api } from "../api/client";
import { useTradingStore } from "../store/useTradingStore";

export function BrokerLogin() {
  const refresh = useTradingStore((s) => s.refresh);
  const [form, setForm] = useState({ api_key: "", client_code: "", password: "", totp: "", totp_secret: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    if (!/^\d{4}$/.test(form.password.trim())) {
      setError("Enter your 4-digit Angel One MPIN in the MPIN field.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/broker/login", form);
      await refresh();
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      setError(maybeAxios.response?.data?.detail || maybeAxios.response?.data?.message || maybeAxios.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="border-b border-line bg-panel px-6 py-5">
      <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <KeyRound size={18} /> Angel One SmartAPI
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {(["api_key", "client_code", "password", "totp", "totp_secret"] as const).map((key) => (
              <input
                key={key}
                className="h-10 border border-line bg-white px-3 text-sm outline-none focus:border-ink"
                type={key.includes("password") || key.includes("secret") ? "password" : "text"}
                inputMode={key === "password" || key === "totp" ? "numeric" : "text"}
                maxLength={key === "password" ? 4 : key === "totp" ? 6 : undefined}
                placeholder={key === "password" ? "4 DIGIT MPIN" : key.replace("_", " ").toUpperCase()}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            ))}
          </div>
          {error && <div className="mt-3 border border-loss bg-red-50 px-3 py-2 text-sm font-medium text-loss">{error}</div>}
        </div>
        <button onClick={submit} disabled={busy} className="inline-flex h-10 items-center justify-center gap-2 bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60">
          <LogIn size={16} /> {busy ? "Connecting" : "Connect"}
        </button>
      </div>
    </section>
  );
}
