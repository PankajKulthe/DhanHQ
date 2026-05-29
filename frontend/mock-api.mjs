import http from "node:http";

const port = Number(process.env.MOCK_API_PORT || 8000);

function json(res, status, body) {
  res.writeHead(status, {
    "content-type": "application/json",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization"
  });
  res.end(JSON.stringify(body));
}

const server = http.createServer((req, res) => {
  if (req.method === "OPTIONS") {
    json(res, 204, {});
    return;
  }

  if (req.url === "/health") {
    json(res, 200, { status: "ok", mode: "mock" });
    return;
  }

  if (req.url === "/api/v1/auth/broker/status") {
    json(res, 200, {
      broker: "ANGEL_ONE",
      connected: false,
      client_code: null,
      feed_connected: false,
      message: "Mock API running"
    });
    return;
  }

  if (req.url === "/api/v1/auth/broker/login" && req.method === "POST") {
    json(res, 200, {
      broker: "ANGEL_ONE",
      connected: true,
      client_code: "MOCK",
      feed_connected: false,
      message: "Mock login accepted"
    });
    return;
  }

  if (req.url?.startsWith("/api/v1/analytics/daily")) {
    json(res, 200, {
      trade_date: new Date().toISOString().slice(0, 10),
      stocks_moved_gt_2pct: 0,
      nifty_breadth_score: 0,
      sentiment: "UNKNOWN",
      trades_executed: 0,
      daily_pnl: 0,
      wins: 0,
      losses: 0
    });
    return;
  }

  if (req.url === "/api/v1/market/scan" && req.method === "POST") {
    json(res, 200, {
      generated_at: new Date().toISOString(),
      sentiment: "SIDEWAYS",
      breadth_score: 0,
      candidates: []
    });
    return;
  }

  json(res, 404, { detail: "Mock route not found" });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Mock API listening on http://127.0.0.1:${port}`);
});
