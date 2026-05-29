type Props = { label: string; value: string | number; tone?: "gain" | "loss" | "neutral" };

export function MetricTile({ label, value, tone = "neutral" }: Props) {
  const toneClass = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-ink";
  return (
    <div className="border border-line bg-white p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}
