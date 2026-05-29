import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

const port = Number(process.env.ANGEL_API_PORT || 8000);
const ANGEL_BASE = "https://apiconnect.angelone.in";
const SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json";
const DATA_DIR = path.resolve("data");
const NIFTY_50 = [
  "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
  "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
  "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
  "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
  "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE",
  "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
  "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
];

let scripMaster = {
  loadedAt: null,
  rows: [],
  byToken: new Map(),
  nseEquityByName: new Map(),
  nfoOptionsByName: new Map()
};

let session = {
  connected: false,
  clientCode: null,
  apiKey: null,
  jwtToken: null,
  refreshToken: null,
  feedToken: null,
  loginAt: null,
  lastMessage: "Disconnected"
};

const cprCache = new Map();

function json(res, status, body) {
  res.writeHead(status, {
    "content-type": "application/json",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization"
  });
  res.end(JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
      if (data.length > 1_000_000) req.destroy();
    });
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function base32Decode(input) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.toUpperCase().replace(/=+$/g, "").replace(/\s+/g, "");
  let bits = "";
  for (const char of clean) {
    const value = alphabet.indexOf(char);
    if (value === -1) throw new Error("Invalid TOTP secret");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let index = 0; index + 8 <= bits.length; index += 8) {
    bytes.push(Number.parseInt(bits.slice(index, index + 8), 2));
  }
  return Buffer.from(bytes);
}

function generateTotp(secret) {
  const key = base32Decode(secret);
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30)));
  const hmac = crypto.createHmac("sha1", key).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const code = (hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(code).padStart(6, "0");
}

function statusPayload() {
  return {
    broker: "ANGEL_ONE",
    connected: session.connected,
    client_code: session.clientCode,
    feed_connected: Boolean(session.feedToken),
    message: session.lastMessage
  };
}

function requireSession() {
  if (!session.connected || !session.jwtToken || !session.apiKey) {
    throw new Error("Angel One is not connected");
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function angelRequest(path, { method = "GET", body = null, auth = true } = {}) {
  requireSession();
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 25_000);
      const response = await fetch(`${ANGEL_BASE}${path}`, {
        method,
        signal: controller.signal,
        headers: {
          "content-type": "application/json",
          accept: "application/json",
          "X-UserType": "USER",
          "X-SourceID": "WEB",
          "X-ClientLocalIP": "127.0.0.1",
          "X-ClientPublicIP": "127.0.0.1",
          "X-MACAddress": "00:00:00:00:00:00",
          "X-PrivateKey": session.apiKey,
          ...(auth ? { Authorization: `Bearer ${session.jwtToken}` } : {})
        },
        body: body ? JSON.stringify(body) : undefined
      }).finally(() => clearTimeout(timeout));
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.status === false || data.status === "false") {
        throw new Error(data.message || data.errorcode || `Angel One request failed with HTTP ${response.status}`);
      }
      return data;
    } catch (error) {
      lastError = error;
      if (attempt < 3) await sleep(350 * attempt);
    }
  }
  throw lastError;
}

function numeric(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function chunk(list, size) {
  const chunks = [];
  for (let index = 0; index < list.length; index += size) {
    chunks.push(list.slice(index, index + size));
  }
  return chunks;
}

async function mapLimit(items, limit, worker) {
  const results = new Array(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await worker(items[index], index);
    }
  });
  await Promise.all(workers);
  return results;
}

function parseExpiry(value) {
  if (!value) return null;
  const raw = String(value).trim().toUpperCase();
  const direct = new Date(raw);
  if (!Number.isNaN(direct.getTime())) return direct;
  const match = raw.match(/^(\d{1,2})([A-Z]{3})(\d{2,4})$/);
  if (!match) return null;
  const months = { JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5, JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11 };
  const year = match[3].length === 2 ? 2000 + Number(match[3]) : Number(match[3]);
  return new Date(Date.UTC(year, months[match[2]], Number(match[1])));
}

function strikeValue(row) {
  const strike = numeric(row.strike);
  return strike > 10000 ? strike / 100 : strike;
}

function formatDate(date) {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function addDays(dateText, days) {
  const date = new Date(`${dateText}T00:00:00`);
  date.setDate(date.getDate() + days);
  return formatDate(date);
}

function previousTradingDay() {
  const date = new Date();
  date.setDate(date.getDate() - 1);
  while (date.getDay() === 0 || date.getDay() === 6) {
    date.setDate(date.getDate() - 1);
  }
  return formatDate(date);
}

function cprFromOhlc({ date, high, low, close, source }) {
  if (high <= 0 || low <= 0 || close <= 0) return null;
  const pivot = (high + low + close) / 3;
  const bcRaw = (high + low) / 2;
  const tcRaw = (pivot - bcRaw) + pivot;
  const bc = Math.min(bcRaw, tcRaw);
  const tc = Math.max(bcRaw, tcRaw);
  return {
    date,
    source,
    high: Number(high.toFixed(2)),
    low: Number(low.toFixed(2)),
    close: Number(close.toFixed(2)),
    pivot: Number(pivot.toFixed(2)),
    bc: Number(bc.toFixed(2)),
    tc: Number(tc.toFixed(2))
  };
}

function cprFromDailyCandle(candle, source = "ONE_DAY") {
  if (!Array.isArray(candle) || candle.length < 5) return null;
  const high = numeric(candle[2]);
  const low = numeric(candle[3]);
  const close = numeric(candle[4]);
  return cprFromOhlc({
    date: String(candle[0]).slice(0, 10),
    high,
    low,
    close,
    source
  });
}

function cprFromIntradayCandles(candles, source = "ONE_MINUTE") {
  if (!Array.isArray(candles) || !candles.length) return null;
  const high = Math.max(...candles.map((candle) => numeric(candle[2])));
  const low = Math.min(...candles.map((candle) => numeric(candle[3])).filter((value) => value > 0));
  const close = numeric(candles.at(-1)?.[4]);
  return cprFromOhlc({
    date: String(candles.at(-1)?.[0] || "").slice(0, 10),
    high,
    low,
    close,
    source
  });
}

async function optionCpr(token, tradeDate = previousTradingDay()) {
  const cacheKey = `${token}:${tradeDate}`;
  if (cprCache.has(cacheKey)) return cprCache.get(cacheKey);
  const attempts = [];
  const historicalRequest = async (interval, fromdate, todate) => {
    const response = await angelRequest("/rest/secure/angelbroking/historical/v1/getCandleData", {
      method: "POST",
      body: {
        exchange: "NFO",
        symboltoken: String(token),
        interval,
        fromdate,
        todate
      }
    });
    attempts.push({ interval, fromdate, todate, count: Array.isArray(response?.data) ? response.data.length : 0 });
    return response;
  };

  const dayStart = `${tradeDate} 00:00`;
  const dayEnd = `${addDays(tradeDate, 1)} 00:00`;
  const marketStart = `${tradeDate} 09:15`;
  const marketEnd = `${tradeDate} 15:30`;

  let data = await historicalRequest("ONE_DAY", dayStart, dayEnd);
  let candle = Array.isArray(data?.data) ? data.data.at(-1) : null;
  let cpr = cprFromDailyCandle(candle, "ONE_DAY_00_00_RANGE");
  if (cpr) {
    const result = { ...cpr, attempts };
    cprCache.set(cacheKey, result);
    return result;
  }

  data = await historicalRequest("ONE_DAY", marketStart, marketEnd);
  candle = Array.isArray(data?.data) ? data.data.at(-1) : null;
  cpr = cprFromDailyCandle(candle, "ONE_DAY_MARKET_RANGE");
  if (cpr) {
    const result = { ...cpr, attempts };
    cprCache.set(cacheKey, result);
    return result;
  }

  data = await historicalRequest("ONE_MINUTE", marketStart, marketEnd);
  cpr = cprFromIntradayCandles(data?.data, "ONE_MINUTE_AGGREGATED");
  if (cpr) {
    const result = { ...cpr, attempts };
    cprCache.set(cacheKey, result);
    return result;
  }

  const result = { error: "No yesterday candle data returned", attempts };
  cprCache.set(cacheKey, result);
  return result;
}

async function historicalDebug(token, tradeDate = previousTradingDay()) {
  const calls = [];
  const configs = [
    ["ONE_DAY", `${tradeDate} 00:00`, `${addDays(tradeDate, 1)} 00:00`],
    ["ONE_DAY", `${tradeDate} 09:15`, `${tradeDate} 15:30`],
    ["ONE_MINUTE", `${tradeDate} 09:15`, `${tradeDate} 15:30`],
    ["FIVE_MINUTE", `${tradeDate} 09:15`, `${tradeDate} 15:30`]
  ];
  for (const [interval, fromdate, todate] of configs) {
    try {
      const response = await angelRequest("/rest/secure/angelbroking/historical/v1/getCandleData", {
        method: "POST",
        body: { exchange: "NFO", symboltoken: String(token), interval, fromdate, todate }
      });
      calls.push({ interval, fromdate, todate, status: response.status, message: response.message, count: response.data?.length || 0, first: response.data?.[0] || null, last: response.data?.at?.(-1) || null });
    } catch (error) {
      calls.push({ interval, fromdate, todate, error: error.message || "Historical request failed" });
    }
  }
  return { token: String(token), tradeDate, calls };
}

function buildScripIndexes(rows) {
  const byToken = new Map();
  const nseEquityByName = new Map();
  const nfoOptionsByName = new Map();

  for (const row of rows) {
    if (row.token) byToken.set(String(row.token), row);
    const name = String(row.name || "").toUpperCase();
    const symbol = String(row.symbol || "").toUpperCase();
    const exchange = String(row.exch_seg || "").toUpperCase();
    const type = String(row.instrumenttype || "").toUpperCase();

    if (exchange === "NSE" && symbol.endsWith("-EQ") && name) {
      nseEquityByName.set(name, row);
    }

    if (exchange === "NFO" && (type === "OPTSTK" || type === "OPTIDX") && name) {
      if (!nfoOptionsByName.has(name)) nfoOptionsByName.set(name, []);
      nfoOptionsByName.get(name).push(row);
    }
  }

  scripMaster = { loadedAt: new Date().toISOString(), rows, byToken, nseEquityByName, nfoOptionsByName };
}

async function loadScripMaster() {
  if (scripMaster.rows.length) return scripMaster;
  const response = await fetch(SCRIP_MASTER_URL);
  if (!response.ok) throw new Error(`Scrip master download failed with HTTP ${response.status}`);
  const rows = await response.json();
  buildScripIndexes(rows);
  return scripMaster;
}

async function quote(exchange, tokens, mode = "FULL") {
  if (!tokens.length) return [];
  const all = [];
  for (const tokenBatch of chunk(tokens.map(String), 45)) {
    const data = await angelRequest("/rest/secure/angelbroking/market/v1/quote/", {
      method: "POST",
      body: { mode, exchangeTokens: { [exchange]: tokenBatch } }
    });
    const fetched = data?.data?.fetched || data?.data || [];
    all.push(...(Array.isArray(fetched) ? fetched : []));
    await sleep(120);
  }
  return all;
}

function normalizeQuote(item) {
  const token = String(item.symbolToken || item.symboltoken || item.token || "");
  const ltp = numeric(item.ltp || item.LTP || item.lastPrice);
  const close = numeric(item.close || item.previousClose || item.prevClose);
  const percentChange = Number.isFinite(Number(item.percentChange))
    ? Number(item.percentChange)
    : close > 0
      ? ((ltp - close) / close) * 100
      : 0;
  const buyDepth = item.depth?.buy || item.depth?.bids || [];
  const sellDepth = item.depth?.sell || item.depth?.asks || [];
  const bid = numeric(buyDepth[0]?.price || buyDepth[0]?.rate);
  const ask = numeric(sellDepth[0]?.price || sellDepth[0]?.rate);
  const spreadPct = bid > 0 && ask > 0 && ltp > 0 ? ((ask - bid) / ltp) * 100 : null;

  return {
    token,
    exchange: item.exchange,
    trading_symbol: item.tradingSymbol || item.tradingsymbol || item.symbol || "",
    ltp,
    close,
    percent_change: Number(percentChange.toFixed(2)),
    volume: numeric(item.tradeVolume || item.volume || item.totalTradedVolume),
    oi: numeric(item.opnInterest || item.openInterest || item.oi),
    avg_price: numeric(item.avgPrice || item.averagePrice),
    bid,
    ask,
    spread_pct: spreadPct === null ? null : Number(spreadPct.toFixed(2))
  };
}

function nearestOptionPair(underlying, spot) {
  const rows = scripMaster.nfoOptionsByName.get(underlying) || [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dated = rows
    .map((row) => ({ row, expiryDate: parseExpiry(row.expiry), strike: strikeValue(row), symbol: String(row.symbol || "").toUpperCase() }))
    .filter((item) => item.expiryDate && item.expiryDate >= today && item.strike > 0 && (item.symbol.endsWith("CE") || item.symbol.endsWith("PE")));

  if (!dated.length) return null;
  const nearestExpiry = dated.reduce((best, item) => (item.expiryDate < best ? item.expiryDate : best), dated[0].expiryDate);
  const expiryRows = dated.filter((item) => item.expiryDate.getTime() === nearestExpiry.getTime());
  const nearestStrike = expiryRows.reduce((best, item) => Math.abs(item.strike - spot) < Math.abs(best - spot) ? item.strike : best, expiryRows[0].strike);
  const ce = expiryRows.find((item) => item.strike === nearestStrike && item.symbol.endsWith("CE"))?.row;
  const pe = expiryRows.find((item) => item.strike === nearestStrike && item.symbol.endsWith("PE"))?.row;
  return { ce, pe, expiry: nearestExpiry.toISOString().slice(0, 10), strike: nearestStrike };
}

function optionDescriptor(stock, pair, option, type, preference = "ALLOWED") {
  return {
    stock,
    pair,
    option,
    type,
    preference,
    option_token: String(option?.token || ""),
    option_symbol: option?.symbol || "",
    expiry: pair?.expiry,
    strike: pair?.strike
  };
}

async function intradayCandles(token, interval = "ONE_MINUTE") {
  const today = formatDate(new Date());
  const response = await angelRequest("/rest/secure/angelbroking/historical/v1/getCandleData", {
    method: "POST",
    body: {
      exchange: "NFO",
      symboltoken: String(token),
      interval,
      fromdate: `${today} 09:15`,
      todate: `${today} 15:30`
    }
  });
  return Array.isArray(response?.data) ? response.data : [];
}

function vwapFromCandles(candles) {
  if (!Array.isArray(candles) || !candles.length) return 0;
  let turnover = 0;
  let volume = 0;
  for (const candle of candles) {
    const typical = (numeric(candle[1]) + numeric(candle[2]) + numeric(candle[3]) + numeric(candle[4])) / 4;
    const candleVolume = numeric(candle[5]);
    turnover += typical * candleVolume;
    volume += candleVolume;
  }
  return volume > 0 ? Number((turnover / volume).toFixed(2)) : 0;
}

function momentumScore(candles, lookback = 3) {
  if (!Array.isArray(candles) || candles.length < lookback) return 0;
  const recent = candles.slice(-lookback);
  let score = 0;
  for (const candle of recent) {
    if (numeric(candle[4]) > numeric(candle[1])) score += 1;
  }
  for (let index = 1; index < recent.length; index += 1) {
    if (numeric(recent[index][4]) > numeric(recent[index - 1][4])) score += 1;
  }
  return score;
}

function optionMomentum(candles1m, candles5m, premium, vwap, cprBottom) {
  const source = Array.isArray(candles5m) && candles5m.length ? candles5m : candles1m;
  if (!Array.isArray(source) || !source.length || premium <= 0) {
    return {
      score: 0,
      label: "NO_CANDLES",
      session_move_pct: 0,
      last_candle_move_pct: 0,
      near_day_high: false,
      details: ["no_intraday_candles"]
    };
  }

  const firstOpen = numeric(source[0]?.[1]);
  const dayHigh = Math.max(...source.map((candle) => numeric(candle[2])));
  const last = source.at(-1);
  const lastOpen = numeric(last?.[1]);
  const lastHigh = numeric(last?.[2]);
  const lastClose = numeric(last?.[4]) || premium;
  const sessionMovePct = firstOpen > 0 ? ((premium - firstOpen) / firstOpen) * 100 : 0;
  const lastCandleMovePct = lastOpen > 0 ? ((lastClose - lastOpen) / lastOpen) * 100 : 0;
  const nearDayHigh = dayHigh > 0 && premium >= dayHigh * 0.95;
  const closesAboveStart = firstOpen > 0 && premium > firstOpen;
  const aboveVwap = vwap > 0 && premium > vwap;
  const aboveCpr = cprBottom > 0 && premium > cprBottom;
  const lastCandleStrong = lastClose > lastOpen && lastHigh > 0 && lastClose >= lastHigh * 0.85;

  let score = 0;
  const details = [];
  if (aboveVwap) {
    score += 20;
    details.push("above_vwap");
  }
  if (aboveCpr) {
    score += 20;
    details.push("above_cpr_bottom");
  }
  if (closesAboveStart) {
    score += 15;
    details.push("above_session_open");
  }
  if (sessionMovePct >= 5) {
    score += 20;
    details.push("session_move_gt_5pct");
  } else if (sessionMovePct >= 2) {
    score += 10;
    details.push("session_move_gt_2pct");
  }
  if (lastCandleStrong || lastCandleMovePct >= 1) {
    score += 15;
    details.push("latest_5m_strength");
  }
  if (nearDayHigh) {
    score += 10;
    details.push("near_day_high");
  }

  const boundedScore = Math.min(score, 100);
  return {
    score: boundedScore,
    label: boundedScore >= 70 ? "STRONG" : boundedScore >= 50 ? "MEDIUM" : "WEAK",
    session_move_pct: Number(sessionMovePct.toFixed(2)),
    last_candle_move_pct: Number(lastCandleMovePct.toFixed(2)),
    near_day_high: nearDayHigh,
    details
  };
}

function spreadPct(quoteItem) {
  if (!quoteItem || !quoteItem.bid || !quoteItem.ask || !quoteItem.ltp) return null;
  return Number((((quoteItem.ask - quoteItem.bid) / quoteItem.ltp) * 100).toFixed(2));
}

function persistScanResult(result) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const timestamp = result.generated_at;
  fs.appendFileSync(path.join(DATA_DIR, "market_sentiment.jsonl"), `${JSON.stringify({
    timestamp,
    bullish_count: result.bullish_count,
    bearish_count: result.bearish_count,
    neutral_count: result.neutral_count,
    final_sentiment: result.nifty_sentiment
  })}\n`);
  for (const row of result.stock_sentiments) {
    fs.appendFileSync(path.join(DATA_DIR, "stock_sentiment.jsonl"), `${JSON.stringify({
      stock_symbol: row.stock_symbol,
      stock_move_percent: row.stock_move_percent,
      ce_price: row.ce_price,
      pe_price: row.pe_price,
      ce_cpr_bottom: row.ce_cpr_bottom,
      pe_cpr_bottom: row.pe_cpr_bottom,
      stock_sentiment: row.stock_sentiment,
      timestamp
    })}\n`);
  }
  for (const row of result.final_option_watchlist) {
    fs.appendFileSync(path.join(DATA_DIR, "option_watchlist.jsonl"), `${JSON.stringify({
      stock_symbol: row.stock_symbol,
      option_symbol: row.option_symbol,
      option_type: row.option_type,
      premium: row.premium,
      volume: row.volume,
      spread: row.spread,
      vwap: row.vwap,
      cpr_status: row.cpr_status,
      momentum_score: row.momentum_score,
      final_rank: row.final_rank,
      timestamp
    })}\n`);
  }
}

async function runScanner(config = {}) {
  requireSession();
  await loadScripMaster();
  const minMove = numeric(config.min_underlying_move_pct, 2);
  const minPremium = numeric(config.min_premium, 10);
  const minVolume = numeric(config.min_volume, 100000);
  const minTurnover = numeric(config.min_turnover, 2000000);
  const maxSpreadPct = numeric(config.max_spread_pct, 2.5);
  const minMomentumScore = numeric(config.min_momentum_score, 60);
  const sentimentTolerance = numeric(config.sentiment_tolerance, 0);
  const symbols = NIFTY_50.map((name) => scripMaster.nseEquityByName.get(name)).filter(Boolean);
  if (!symbols.length) throw new Error("No Nifty 50 NSE equity symbols found in scrip master");

  const stockQuotes = (await quote("NSE", symbols.map((row) => row.token), "FULL")).map(normalizeQuote);
  const quoteByToken = new Map(stockQuotes.map((item) => [item.token, item]));
  const stocks = symbols.map((row) => {
    const q = quoteByToken.get(String(row.token));
    return q ? { name: row.name, token: row.token, trading_symbol: row.symbol, quote: q } : null;
  }).filter(Boolean);

  const atmPairs = [];
  const sentimentOptionDescriptors = [];
  for (const stock of stocks) {
    const pair = nearestOptionPair(String(stock.name).toUpperCase(), stock.quote.ltp);
    if (!pair) continue;
    atmPairs.push({ stock, pair });
    if (pair.ce) sentimentOptionDescriptors.push(optionDescriptor(stock, pair, pair.ce, "CE"));
    if (pair.pe) sentimentOptionDescriptors.push(optionDescriptor(stock, pair, pair.pe, "PE"));
  }

  const optionQuotes = (await quote("NFO", sentimentOptionDescriptors.map((item) => item.option.token), "FULL")).map(normalizeQuote);
  const optionQuoteByToken = new Map(optionQuotes.map((item) => [item.token, item]));

  const cprDate = previousTradingDay();
  const cprResults = await mapLimit(sentimentOptionDescriptors, 4, async (item) => {
    try {
      return await optionCpr(item.option.token, cprDate);
    } catch (error) {
      return { error: error.message || "CPR fetch failed" };
    }
  });
  const cprByToken = new Map(sentimentOptionDescriptors.map((item, index) => [String(item.option.token), cprResults[index]]));

  let bullishCount = 0;
  let bearishCount = 0;
  let neutralCount = 0;
  const bullishStockList = [];
  const bearishStockList = [];
  const stockSentiments = atmPairs.map(({ stock, pair }) => {
    const ceQuote = pair.ce ? optionQuoteByToken.get(String(pair.ce.token)) : null;
    const peQuote = pair.pe ? optionQuoteByToken.get(String(pair.pe.token)) : null;
    const ceCpr = pair.ce ? cprByToken.get(String(pair.ce.token)) : null;
    const peCpr = pair.pe ? cprByToken.get(String(pair.pe.token)) : null;
    const cePrice = numeric(ceQuote?.ltp);
    const pePrice = numeric(peQuote?.ltp);
    const ceCprBottom = numeric(ceCpr?.bc);
    const peCprBottom = numeric(peCpr?.bc);
    const isBullish = ceCprBottom > 0 && cePrice > ceCprBottom;
    const isBearish = peCprBottom > 0 && pePrice > peCprBottom;
    if (isBullish) {
      bullishCount += 1;
      bullishStockList.push(stock.name);
    }
    if (isBearish) {
      bearishCount += 1;
      bearishStockList.push(stock.name);
    }
    if (!isBullish && !isBearish) neutralCount += 1;
    return {
      stock_symbol: stock.name,
      stock_move_percent: stock.quote.percent_change,
      ce_symbol: pair.ce?.symbol || "",
      pe_symbol: pair.pe?.symbol || "",
      ce_token: pair.ce ? String(pair.ce.token) : "",
      pe_token: pair.pe ? String(pair.pe.token) : "",
      ce_price: cePrice,
      pe_price: pePrice,
      ce_cpr_bottom: ceCprBottom,
      pe_cpr_bottom: peCprBottom,
      ce_cpr_available: ceCprBottom > 0,
      pe_cpr_available: peCprBottom > 0,
      ce_above_cpr_bottom: isBullish,
      pe_above_cpr_bottom: isBearish,
      stock_sentiment: isBullish && isBearish ? "BULLISH_AND_BEARISH" : isBullish ? "BULLISH" : isBearish ? "BEARISH" : "NEUTRAL",
      timestamp: new Date().toISOString()
    };
  });

  const niftySentiment = bullishCount > bearishCount + sentimentTolerance
    ? "POSITIVE"
    : bearishCount > bullishCount + sentimentTolerance
      ? "NEGATIVE"
      : "SIDEWAYS";

  const topGainers = [...stocks].sort((a, b) => b.quote.percent_change - a.quote.percent_change);
  const topLosers = [...stocks].sort((a, b) => a.quote.percent_change - b.quote.percent_change);
  const strongStocks = stocks
    .filter((item) => Math.abs(item.quote.percent_change) >= minMove)
    .map((item) => ({
      stock_symbol: item.name,
      trading_symbol: item.trading_symbol,
      token: String(item.token),
      ltp: item.quote.ltp,
      previous_close: item.quote.close,
      stock_move_percent: item.quote.percent_change,
      stock_bias: item.quote.percent_change >= 0 ? "BULLISH" : "BEARISH"
    }));

  const selectedOptionDescriptors = [];
  if (niftySentiment !== "SIDEWAYS") {
    for (const strong of strongStocks) {
      const pairRecord = atmPairs.find((item) => item.stock.name === strong.stock_symbol);
      if (!pairRecord) continue;
      if (niftySentiment === "POSITIVE") {
        if (pairRecord.pair.ce) {
          selectedOptionDescriptors.push(optionDescriptor(pairRecord.stock, pairRecord.pair, pairRecord.pair.ce, "CE", strong.stock_bias === "BULLISH" ? "PREFERRED" : "ALLOWED"));
        }
        if (pairRecord.pair.pe) {
          selectedOptionDescriptors.push(optionDescriptor(pairRecord.stock, pairRecord.pair, pairRecord.pair.pe, "PE", strong.stock_bias === "BEARISH" ? "PREFERRED" : "ALLOWED"));
        }
      }
      if (niftySentiment === "NEGATIVE" && pairRecord.pair.pe) {
        selectedOptionDescriptors.push(optionDescriptor(pairRecord.stock, pairRecord.pair, pairRecord.pair.pe, "PE", "ALLOWED"));
      }
    }
  }

  const selectedOptions = await mapLimit(selectedOptionDescriptors, 3, async (item) => {
    const oq = optionQuoteByToken.get(String(item.option.token)) || normalizeQuote({});
    const cpr = cprByToken.get(String(item.option.token)) || {};
    const cprBottom = numeric(cpr?.bc);
    const premium = numeric(oq.ltp);
    let candles = [];
    let candles5m = [];
    try {
      candles = await intradayCandles(item.option.token, "ONE_MINUTE");
    } catch {
      candles = [];
    }
    try {
      candles5m = await intradayCandles(item.option.token, "FIVE_MINUTE");
    } catch {
      candles5m = [];
    }
    const candleVwap = vwapFromCandles(candles);
    const vwap = candleVwap || numeric(oq.avg_price);
    const momentum = optionMomentum(candles, candles5m, premium, vwap, cprBottom);
    const spread = spreadPct(oq);
    const turnover = premium * numeric(oq.volume);
    const cprStatus = cprBottom > 0 && premium > cprBottom ? "ABOVE_BOTTOM" : cprBottom > 0 ? "BELOW_BOTTOM" : "CPR_UNAVAILABLE";
    const filters = {
      high_volume: numeric(oq.volume) >= minVolume || turnover >= minTurnover,
      tight_spread: spread !== null && spread <= maxSpreadPct,
      above_min_premium: premium >= minPremium,
      above_cpr_bottom: cprStatus === "ABOVE_BOTTOM",
      above_vwap: vwap > 0 && premium > vwap,
      strong_momentum: momentum.score >= minMomentumScore
    };
    const passed = Object.values(filters).every(Boolean);
    return {
      stock_symbol: item.stock.name,
      symbol: item.stock.name,
      underlying: item.stock.name,
      underlying_token: String(item.stock.token),
      underlying_ltp: item.stock.quote.ltp,
      underlying_change_pct: item.stock.quote.percent_change,
      bias: item.stock.quote.percent_change >= 0 ? "BULLISH" : "BEARISH",
      stock_bias: item.stock.quote.percent_change >= 0 ? "BULLISH" : "BEARISH",
      option_type: item.type,
      option_symbol: item.option.symbol,
      trading_symbol: item.option.symbol,
      option_token: String(item.option.token),
      expiry: item.pair.expiry,
      strike: item.pair.strike,
      premium,
      volume: numeric(oq.volume),
      turnover: Number(turnover.toFixed(2)),
      oi: numeric(oq.oi),
      vwap,
      bid: numeric(oq.bid),
      ask: numeric(oq.ask),
      spread,
      spread_pct: spread,
      cpr_date: cprDate,
      cpr_pivot: cpr?.pivot || 0,
      cpr_bottom: cprBottom,
      cpr_bc: cprBottom,
      cpr_tc: cpr?.tc || 0,
      cpr_status: cprStatus,
      cpr_available: cprBottom > 0,
      cpr_confirmed: cprStatus === "ABOVE_BOTTOM",
      momentum_score: momentum.score,
      momentum_label: momentum.label,
      momentum_details: momentum.details,
      session_move_pct: momentum.session_move_pct,
      last_candle_move_pct: momentum.last_candle_move_pct,
      preference: item.preference,
      filters,
      eligible: passed,
      rejection_reasons: Object.entries(filters).filter(([, value]) => !value).map(([key]) => key)
    };
  });

  const finalOptionWatchlist = selectedOptions
    .filter((item) => item.eligible)
    .sort((a, b) => {
      const aLiquidity = a.spread ? a.volume / Math.max(a.spread, 0.01) : a.volume;
      const bLiquidity = b.spread ? b.volume / Math.max(b.spread, 0.01) : b.volume;
      const aCprPosition = a.cpr_bottom ? (a.premium - a.cpr_bottom) / a.cpr_bottom : 0;
      const bCprPosition = b.cpr_bottom ? (b.premium - b.cpr_bottom) / b.cpr_bottom : 0;
      return (
        b.volume - a.volume ||
        b.momentum_score - a.momentum_score ||
        numeric(a.spread, 999) - numeric(b.spread, 999) ||
        bLiquidity - aLiquidity ||
        Math.abs(b.underlying_change_pct) - Math.abs(a.underlying_change_pct) ||
        bCprPosition - aCprPosition
      );
    })
    .map((item, index) => ({ ...item, final_rank: index + 1 }));

  const result = {
    generated_at: new Date().toISOString(),
    nifty_sentiment: niftySentiment,
    sentiment: niftySentiment,
    bullish_count: bullishCount,
    bearish_count: bearishCount,
    neutral_count: neutralCount,
    breadth_score: bullishCount - bearishCount,
    scanned_symbols: symbols.length,
    moved_count: strongStocks.length,
    scrip_master_loaded_at: scripMaster.loadedAt,
    bullish_stock_list: bullishStockList,
    bearish_stock_list: bearishStockList,
    stock_sentiments: stockSentiments,
    top_gainers: topGainers.slice(0, 10).map((item) => ({ stock_symbol: item.name, stock_move_percent: item.quote.percent_change, ltp: item.quote.ltp })),
    top_losers: topLosers.slice(0, 10).map((item) => ({ stock_symbol: item.name, stock_move_percent: item.quote.percent_change, ltp: item.quote.ltp })),
    strong_stocks: strongStocks,
    selected_atm_options: selectedOptions,
    final_option_watchlist: finalOptionWatchlist,
    candidates: finalOptionWatchlist,
    low_confidence: niftySentiment === "SIDEWAYS",
    no_trade_reason: niftySentiment === "SIDEWAYS" ? "Nifty sentiment is SIDEWAYS" : ""
  };

  persistScanResult(result);
  return result;
}

async function angelLogin(payload) {
  const apiKey = String(payload.api_key || "").trim();
  const clientCode = String(payload.client_code || "").trim();
  const password = String(payload.password || "").trim();
  const totp = String(payload.totp || "").trim() || generateTotp(String(payload.totp_secret || ""));

  if (!apiKey || !clientCode || !password || !totp) {
    throw new Error("API key, client code, 4-digit MPIN, and TOTP are required");
  }
  if (!/^\d{4}$/.test(password)) {
    throw new Error("Enter your 4-digit Angel One MPIN, not your account password");
  }
  if (!/^\d{6}$/.test(totp)) {
    throw new Error("TOTP must be exactly 6 digits");
  }

  session.lastMessage = "Connecting to Angel One...";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  const response = await fetch(`${ANGEL_BASE}/rest/auth/angelbroking/user/v1/loginByPassword`, {
    method: "POST",
    signal: controller.signal,
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      "X-UserType": "USER",
      "X-SourceID": "WEB",
      "X-ClientLocalIP": "127.0.0.1",
      "X-ClientPublicIP": "127.0.0.1",
      "X-MACAddress": "00:00:00:00:00:00",
      "X-PrivateKey": apiKey
    },
    body: JSON.stringify({
      clientcode: clientCode,
      password,
      totp
    })
  }).catch((error) => {
    if (error?.name === "AbortError") {
      throw new Error("Angel One login timed out after 20 seconds");
    }
    throw error;
  }).finally(() => clearTimeout(timeout));

  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.status === false || data.status === "false") {
    throw new Error(data.message || data.errorcode || `Angel One login failed with HTTP ${response.status}`);
  }

  const tokens = data.data || {};
  session = {
    connected: true,
    clientCode,
    apiKey,
    jwtToken: tokens.jwtToken,
    refreshToken: tokens.refreshToken,
    feedToken: tokens.feedToken,
    loginAt: new Date().toISOString(),
    lastMessage: "Angel One connected"
  };

  return statusPayload();
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "OPTIONS") {
      json(res, 204, {});
      return;
    }

    if (req.url === "/health") {
      json(res, 200, { status: "ok", mode: "angel-node-bridge", connected: session.connected });
      return;
    }

    if (req.url === "/api/v1/auth/broker/status") {
      json(res, 200, statusPayload());
      return;
    }

    if (req.url === "/api/v1/auth/broker/profile") {
      const data = await angelRequest("/rest/secure/angelbroking/user/v1/getProfile");
      json(res, 200, data);
      return;
    }

    if (req.url === "/api/v1/auth/broker/rms") {
      const data = await angelRequest("/rest/secure/angelbroking/user/v1/getRMS");
      json(res, 200, data);
      return;
    }

    if (req.url === "/api/v1/market/scrip-master/status") {
      await loadScripMaster();
      json(res, 200, {
        loaded_at: scripMaster.loadedAt,
        total: scripMaster.rows.length,
        nse_equities: scripMaster.nseEquityByName.size,
        nfo_underlyings: scripMaster.nfoOptionsByName.size
      });
      return;
    }

    if (req.url?.startsWith("/api/v1/market/historical-debug")) {
      const url = new URL(req.url, `http://127.0.0.1:${port}`);
      const token = url.searchParams.get("token");
      const tradeDate = url.searchParams.get("date") || previousTradingDay();
      if (!token) throw new Error("token query parameter is required");
      json(res, 200, await historicalDebug(token, tradeDate));
      return;
    }

    if (req.url === "/api/v1/auth/broker/login" && req.method === "POST") {
      const payload = await readBody(req);
      const result = await angelLogin(payload);
      json(res, 200, result);
      return;
    }

    if (req.url?.startsWith("/api/v1/analytics/daily")) {
      json(res, 200, {
        trade_date: new Date().toISOString().slice(0, 10),
        stocks_moved_gt_2pct: 0,
        nifty_breadth_score: 0,
        sentiment: session.connected ? "CONNECTED" : "UNKNOWN",
        trades_executed: 0,
        daily_pnl: 0,
        wins: 0,
        losses: 0
      });
      return;
    }

    if (req.url === "/api/v1/market/scan" && req.method === "POST") {
      const config = await readBody(req);
      json(res, 200, await runScanner(config));
      return;
    }

    json(res, 404, { detail: "Route not found" });
  } catch (error) {
    session.lastMessage = error.message || "Request failed";
    json(res, 400, { detail: session.lastMessage, ...statusPayload() });
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Angel One local bridge listening on http://127.0.0.1:${port}`);
});
