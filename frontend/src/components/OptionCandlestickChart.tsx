import type { HistoricalOptionResponse, OptionCandle } from "../types";

function scale(value: number, min: number, max: number, height: number, top = 14) {
  if (max <= min) return top + height / 2;
  return top + ((max - value) / (max - min)) * height;
}

function labelTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(11, 16);
  return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function priceRange(candles: OptionCandle[], data: HistoricalOptionResponse) {
  const prices = candles.flatMap((candle) => [candle.high, candle.low]);
  prices.push(data.cpr.pivot, data.cpr.bc, data.cpr.tc);
  data.vwap.forEach((point) => {
    if (point.value) prices.push(point.value);
  });
  const clean = prices.filter((value) => Number.isFinite(value) && value > 0);
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const pad = Math.max((max - min) * 0.08, 0.5);
  return { min: min - pad, max: max + pad };
}

export function OptionCandlestickChart({ data }: { data: HistoricalOptionResponse | null }) {
  if (!data || !data.candles.length) {
    return <div className="grid h-[420px] place-items-center border border-line bg-[#fbfaf7] text-sm text-neutral-600">No candle data loaded.</div>;
  }

  const candles = data.candles;
  const width = 980;
  const priceHeight = 300;
  const volumeHeight = 78;
  const left = 56;
  const top = 12;
  const plotWidth = width - left - 20;
  const { min, max } = priceRange(candles, data);
  const step = plotWidth / candles.length;
  const bodyWidth = Math.max(4, Math.min(14, step * 0.58));
  const maxVolume = Math.max(...candles.map((candle) => candle.volume), 1);
  const vwapPoints = data.vwap
    .map((point, index) => {
      if (!point.value) return "";
      return `${left + index * step + step / 2},${scale(point.value, min, max, priceHeight, top)}`;
    })
    .filter(Boolean)
    .join(" ");

  const lines = [
    { label: "TC", value: data.cpr.tc, color: "#7c3aed" },
    { label: "Pivot", value: data.cpr.pivot, color: "#ca8a04" },
    { label: "BC", value: data.cpr.bc, color: "#2563eb" }
  ].filter((line) => line.value > 0);

  return (
    <div className="overflow-x-auto border border-line bg-white">
      <svg viewBox={`0 0 ${width} 430`} className="min-w-[760px] text-[11px]">
        <rect x="0" y="0" width={width} height="430" fill="#ffffff" />
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = top + tick * priceHeight;
          const price = max - tick * (max - min);
          return (
            <g key={tick}>
              <line x1={left} x2={width - 20} y1={y} y2={y} stroke="#e5e7eb" />
              <text x="8" y={y + 4} fill="#525252">{price.toFixed(2)}</text>
            </g>
          );
        })}
        {lines.map((line) => {
          const y = scale(line.value, min, max, priceHeight, top);
          return (
            <g key={line.label}>
              <line x1={left} x2={width - 20} y1={y} y2={y} stroke={line.color} strokeDasharray="6 4" />
              <text x={width - 84} y={y - 4} fill={line.color}>{line.label} {line.value.toFixed(2)}</text>
            </g>
          );
        })}
        {vwapPoints && <polyline points={vwapPoints} fill="none" stroke="#0f766e" strokeWidth="2" />}
        {candles.map((candle, index) => {
          const x = left + index * step + step / 2;
          const high = scale(candle.high, min, max, priceHeight, top);
          const low = scale(candle.low, min, max, priceHeight, top);
          const open = scale(candle.open, min, max, priceHeight, top);
          const close = scale(candle.close, min, max, priceHeight, top);
          const up = candle.close >= candle.open;
          const color = up ? "#147d4c" : "#b42318";
          const bodyY = Math.min(open, close);
          const bodyH = Math.max(Math.abs(close - open), 1);
          const volumeY = top + priceHeight + 34 + (1 - candle.volume / maxVolume) * volumeHeight;
          const volumeH = (candle.volume / maxVolume) * volumeHeight;
          return (
            <g key={`${candle.ts}-${index}`}>
              <line x1={x} x2={x} y1={high} y2={low} stroke={color} strokeWidth="1.4" />
              <rect x={x - bodyWidth / 2} y={bodyY} width={bodyWidth} height={bodyH} fill={up ? "#dff3e7" : "#fee4e2"} stroke={color} />
              <rect x={x - bodyWidth / 2} y={volumeY} width={bodyWidth} height={volumeH} fill={color} opacity="0.35" />
            </g>
          );
        })}
        {[0, Math.floor(candles.length / 2), candles.length - 1].filter((value, index, arr) => arr.indexOf(value) === index).map((index) => {
          const x = left + index * step + step / 2;
          return <text key={index} x={x - 24} y="414" fill="#525252">{labelTime(candles[index].ts)}</text>;
        })}
        <text x={left} y="22" fill="#0f766e">VWAP</text>
        <text x={left} y="338" fill="#525252">Volume</text>
      </svg>
    </div>
  );
}
