import { CandlestickChart } from "lucide-react";

export function TradingViewPanel() {
  return (
    <div className="h-[420px] border border-line bg-white">
      <div className="flex h-10 items-center gap-2 border-b border-line px-4 text-sm font-semibold">
        <CandlestickChart size={17} /> NIFTY Option Chart
      </div>
      <iframe
        title="TradingView NIFTY"
        className="h-[378px] w-full"
        src="https://s.tradingview.com/widgetembed/?symbol=NSE%3ANIFTY&interval=5&theme=light&style=1&hide_side_toolbar=true"
      />
    </div>
  );
}
