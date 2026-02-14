"use client";

import { useMemo, useState } from "react";
const TOKEN_BUY_URL = "https://nad.fun/tokens/0x7934935754B3f8F435cE7026F4e3e52b22cf7777";
const NFT_MINT_URL = "https://innishan.github.io/dust-protocol-mint/";

type DustItem = {
  symbol: string;
  amount: number;
  mon_value: number | null;
  token: string;
};

type Report = {
  source: string;
  wallet: string;
  dust_count: number;
  notes: string[];
  dust: DustItem[];
};

function shortAddr(a: string) {
  if (!a || a.length < 10) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

export default function Page() {
  const [wallet, setWallet] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showNotes, setShowNotes] = useState(false);

  const dust = report?.dust ?? [];

  // Simple “demo-grade” valuation:
  // - If you have mon_value later, it will show.
  // - For stablecoins, treat amount as USD (good enough for hackathon).
  const stableSymbols = new Set(["USDC", "USDT", "USDT0", "AUSD", "DAI"]);
  const estimatedUsd = useMemo(() => {
    return dust.reduce((acc, d) => (stableSymbols.has(d.symbol) ? acc + (Number(d.amount) || 0) : acc), 0);
  }, [dust]);

  const totalTokens = dust.length;

  async function analyze() {
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const base = process.env.NEXT_PUBLIC_API_BASE;
      const res = await fetch(`${base}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setReport(data);
      setShowNotes(false);
    } catch (e: any) {
      setError(e?.message || "Failed to analyze wallet");
    } finally {
      setLoading(false);
    }
  }

  function copyTokenAddresses() {
    const addrs = dust.map((d) => d.token).join("\n");
    navigator.clipboard.writeText(addrs);
    alert("Copied token addresses");
  }

  function generateInstructions() {
    if (!report) return;
    const lines: string[] = [];
    lines.push("Dust Cleaner Protocol — Non-custodial execution instructions");
    lines.push(`Wallet: ${report.wallet}`);
    lines.push("");
    lines.push("1) Review dust list");
    dust.forEach((d) => lines.push(`- ${d.symbol}: ${d.amount} (${d.token})`));
    lines.push("");
    lines.push("2) User signs transactions (agent never holds keys):");
    lines.push("- Approve DustCleaner contract to spend each token");
    lines.push("- Call DustCleaner contract clean() / swap() with selected tokens");
    lines.push("");
    lines.push("3) Protocol fee is enforced on-chain. NFT holders receive monthly distribution.");
    navigator.clipboard.writeText(lines.join("\n"));
    alert("Copied demo instructions to clipboard");
  }

  return (
    <main style={{ maxWidth: 1040, margin: "36px auto", padding: 18, fontFamily: "ui-sans-serif" }}>
      {/* Header */}
      <div
        style={{
          padding: 18,
          borderRadius: 16,
          border: "1px solid rgba(255,255,255,0.10)",
          background: "rgba(0,0,0,0.65)",
          color: "white",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <img
                src="/logo.png"
                alt="Dust Cleaner"
                style={{ width: 34, height: 34, borderRadius: 10, objectFit: "cover" }}
              />
              <div style={{ fontSize: 28, fontWeight: 900 }}>Dust Cleaner Protocol</div>
            </div>
            <div style={{ marginTop: 6, opacity: 0.85 }}>
              AI-native, on-chain dust aggregation for Monad — public wallet scan (Stage 2)
            </div>
          </div>

          <div style={{ textAlign: "right", opacity: 0.9 }}>
            <div style={{ fontSize: 12 }}>On-chain assets</div>
            <div style={{ marginTop: 6, fontSize: 12 }}>
              <b>NFT CA:</b> 0x053c782Bbf191c2B6e792bF829cFF039D55381fC
            </div>
            <div style={{ fontSize: 12 }}>
              <b>Agent Token CA:</b> 0x7934935754B3f8F435cE7026F4e3e52b22cf7777
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 10, flexWrap: "wrap" }}>
              <a
                href={TOKEN_BUY_URL}
                target="_blank"
                rel="noreferrer"
                style={{
                  padding: "8px 10px",
                  borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.25)",
                  background: "rgba(255,255,255,0.06)",
                  color: "white",
                  fontSize: 12,
                  fontWeight: 800,
                  textDecoration: "none",
                }}
              >
                Buy Token
              </a>

              <a
                href={NFT_MINT_URL}
                target="_blank"
                rel="noreferrer"
                style={{
                  padding: "8px 10px",
                  borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.25)",
                  background: "rgba(255,255,255,0.06)",
                  color: "white",
                  fontSize: 12,
                  fontWeight: 800,
                  textDecoration: "none",
                }}
              >
                Mint NFT
              </a>
            </div>
          </div>
        </div>

        {/* Wallet input */}
        <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          <input
            value={wallet}
            onChange={(e) => setWallet(e.target.value)}
            placeholder="Paste wallet address (0x...)"
            style={{
              flex: 1,
              minWidth: 260,
              padding: 12,
              border: "1px solid rgba(255,255,255,0.25)",
              borderRadius: 12,
              background: "rgba(255,255,255,0.06)",
              color: "white",
              outline: "none",
            }}
          />
          <button
            onClick={analyze}
            disabled={loading || wallet.length < 10}
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid #fff",
              background: "#fff",
              color: "#111",
              fontWeight: 800,
              cursor: loading ? "not-allowed" : "pointer",
              minWidth: 140,
            }}
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: 12, padding: 12, border: "1px solid #ff8b8b", borderRadius: 12, color: "#ffd0d0" }}>
            {error}
          </div>
        )}
      </div>

      {/* Results */}
      {report && (
        <section style={{ marginTop: 18 }}>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            <div style={{ padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
              <div style={{ opacity: 0.7, fontSize: 12 }}>Wallet</div>
              <div style={{ marginTop: 6, fontWeight: 800 }}>{shortAddr(report.wallet)}</div>
              <div style={{ marginTop: 6, opacity: 0.65, fontSize: 12 }}>{report.wallet}</div>
            </div>

            <div style={{ padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
              <div style={{ opacity: 0.7, fontSize: 12 }}>Scan source</div>
              <div style={{ marginTop: 6, fontWeight: 800 }}>{report.source}</div>
              <div style={{ marginTop: 6, opacity: 0.7, fontSize: 12 }}>Registry + on-chain balanceOf fallback</div>
            </div>

            <div style={{ padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
              <div style={{ opacity: 0.7, fontSize: 12 }}>Dust found</div>
              <div style={{ marginTop: 6, fontWeight: 900, fontSize: 22 }}>{report.dust_count}</div>
              <div style={{ marginTop: 6, opacity: 0.7, fontSize: 12 }}>Tokens detected as dust candidates</div>
            </div>

            <div style={{ padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
              <div style={{ opacity: 0.7, fontSize: 12 }}>Est. stable value (demo)</div>
              <div style={{ marginTop: 6, fontWeight: 900, fontSize: 22 }}>${estimatedUsd.toFixed(4)}</div>
              <div style={{ marginTop: 6, opacity: 0.7, fontSize: 12 }}>Sum of USDC/USDT/AUSD amounts</div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
            <button
              onClick={copyTokenAddresses}
              disabled={!dust.length}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #111",
                background: "#fff",
                cursor: !dust.length ? "not-allowed" : "pointer",
                fontWeight: 800,
              }}
            >
              Copy token addresses
            </button>

            <button
              onClick={generateInstructions}
              disabled={!dust.length}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #111",
                background: "#111",
                color: "#fff",
                cursor: !dust.length ? "not-allowed" : "pointer",
                fontWeight: 800,
              }}
            >
              Generate clean instructions (copy)
            </button>

            <button
              onClick={() => setShowNotes((v) => !v)}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #eee",
                background: "#fff",
                cursor: "pointer",
                fontWeight: 800,
              }}
            >
              {showNotes ? "Hide notes" : "Show notes"}
            </button>
          </div>

          {/* Notes */}
          {showNotes && report.notes?.length > 0 && (
            <div style={{ marginTop: 12, padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
              <div style={{ fontWeight: 900 }}>Scan notes</div>
              <ul style={{ marginTop: 8, paddingLeft: 18, opacity: 0.85 }}>
                {report.notes.map((n, i) => (
                  <li key={i} style={{ marginBottom: 4, wordBreak: "break-word" }}>
                    {n}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Dust list */}
          <div style={{ marginTop: 12, padding: 14, border: "1px solid #eee", borderRadius: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              <div style={{ fontWeight: 900, fontSize: 16 }}>Dust tokens</div>
              <div style={{ opacity: 0.7, fontSize: 12 }}>Detected tokens: {totalTokens}</div>
            </div>

            <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
              {dust.map((d, idx) => (
                <div key={idx} style={{ padding: 12, border: "1px solid #eee", borderRadius: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ fontWeight: 900 }}>{d.symbol}</div>
                    <div style={{ opacity: 0.75 }}>
                      {d.mon_value === null ? "—" : `${Number(d.mon_value).toFixed(4)} MON`}
                    </div>
                  </div>
                  <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
                    <div style={{ opacity: 0.9 }}><b>Amount:</b> {d.amount}</div>
                    <div style={{ opacity: 0.75, wordBreak: "break-all" }}>
                      <b>Token:</b> {d.token}
                    </div>
                  </div>
                </div>
              ))}

              {!dust.length && <div style={{ opacity: 0.7 }}>No dust found.</div>}
            </div>
          </div>

          {/* Trust model */}
          <div style={{ marginTop: 12, padding: 14, border: "1px dashed #ddd", borderRadius: 14, opacity: 0.9 }}>
            <b>Trust model:</b> agent is read-only for public wallets. Users sign transactions. Fees are enforced on-chain and shared with NFT holders.
          </div>
        </section>
      )}
    </main>
  );
}
