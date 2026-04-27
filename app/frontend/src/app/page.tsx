"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth, getModelInfo, getReady } from "@/lib/api";
import { useScanHistory } from "@/hooks/useScanHistory";
import { HealthData, ModelInfoData } from "@/lib/types";
import { toFriendlyError, formatPercentScore } from "@/lib/helpers";

export default function DashboardPage(): React.JSX.Element {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [localUptime, setLocalUptime] = useState(0);
  const [uptimeRunning, setUptimeRunning] = useState(true);
  const [model, setModel] = useState<ModelInfoData | null>(null);
  const [ready, setReady] = useState<boolean>(false);
  const [showReminder, setShowReminder] = useState(true);
  const history = useScanHistory();

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const [healthRes, readyRes, modelRes] = await Promise.all([getHealth(), getReady(), getModelInfo()]);
        setHealth(healthRes.data);
        setLocalUptime(healthRes.data?.uptime_seconds || 0);
        setReady(Boolean(readyRes.data.ready));
        setModel(modelRes.data);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(toFriendlyError(err));
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (uptimeRunning) {
      interval = setInterval(() => {
        setLocalUptime(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [uptimeRunning]);

  const formatUptime = (seconds?: number) => {
    if (!seconds) return "00:00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const fakeCount = history.items.filter(i => i.result.decision === "FAKE").length;
  const realCount = history.items.filter(i => i.result.decision === "REAL").length;
  const pendingCount = history.items.filter(i => i.result.decision === "UNCERTAIN").length;

  return (
    <>
      <div className="pageHeader">
        <div className="pageTitle">
          <h1>Dashboard</h1>
          <p>Plan, prioritize, and accomplish your tasks with ease.</p>
        </div>
        <div className="headerActions">
          <Link href="/predict/image" className="primaryButton">
            <span>+</span> New Scan
          </Link>
          <Link href="/reports" className="secondaryButton" style={{ borderColor: "var(--primary)", color: "var(--primary)" }}>Import Data</Link>
        </div>
      </div>

      {error && (
        <div className="errorAlert">
          <strong>Backend Error:</strong> {error}
        </div>
      )}

      {/* Top Stats Grid */}
      <div className="dashboardGrid">
        <div className="statCard primary">
          <p className="statLabel">Total Scans</p>
          <p className="statValue">{history.analytics.totalScans}</p>
          <div className="statTrend">
            <span>↗</span> Analytics up to date
          </div>
          <div className="statIcon">📊</div>
        </div>

        <div className="statCard">
          <p className="statLabel">Fake Detected</p>
          <p className="statValue">{fakeCount}</p>
          <div className="statTrend">
            <span>↗</span> {formatPercentScore(history.analytics.fakeRate)} Rate
          </div>
          <div className="statIcon" style={{ color: "var(--risk-high)", background: "var(--danger-bg)" }}>⚠️</div>
        </div>

        <div className="statCard">
          <p className="statLabel">Real Authenticated</p>
          <p className="statValue">{realCount}</p>
          <div className="statTrend">
            <span>↗</span> System Healthy
          </div>
          <div className="statIcon" style={{ color: "var(--risk-low)", background: "#dcfce7" }}>✅</div>
        </div>

        <div className="statCard">
          <p className="statLabel">Uncertain Review</p>
          <p className="statValue">{pendingCount}</p>
          <div className="statTrend">
            Manual check needed
          </div>
          <div className="statIcon" style={{ color: "var(--risk-uncertain)", background: "#dbeafe" }}>⏳</div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="dashboardMain">
        {/* Left Col */}
        <div className="card">
          <div className="cardTitle">
            <h3>Scan Analytics</h3>
          </div>
          <div className="chartContainer">
            {(() => {
              const counts = [0, 0, 0, 0, 0, 0, 0];
              history.items.forEach(item => {
                const date = new Date(item.timestamp);
                const diffTime = Math.abs(new Date().getTime() - date.getTime());
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                if (diffDays <= 7) {
                  counts[date.getDay()] += 1;
                }
              });
              const maxCount = Math.max(...counts, 1);
              const heights = counts.map(c => Math.round((c / maxCount) * 100));
              
              return heights.map((h, i) => (
                <div key={i} className={`chartBar ${i % 2 === 0 ? "active" : "secondary"}`} style={{ height: `${Math.max(h, 5)}%` }} title={`Scans: ${counts[i]}`}>
                  <span className="chartLabel">{"SMTWTFS"[i]}</span>
                </div>
              ));
            })()}
          </div>
        </div>

        {/* Right Col */}
        <div className="card">
          <div className="cardTitle">
            <h3>Reminders</h3>
          </div>
          {showReminder ? (
            <div style={{ background: "var(--primary-light)", padding: "1.5rem", borderRadius: "16px", color: "var(--primary)" }}>
              <h4 style={{ margin: "0 0 0.5rem" }}>System Maintenance</h4>
              <p style={{ margin: "0 0 1rem", fontSize: "0.85rem", opacity: 0.9 }}>Time: 02:00 pm - 04:00 pm</p>
              <button className="primaryButton" style={{ width: "100%" }} onClick={() => setShowReminder(false)}>Acknowledge</button>
            </div>
          ) : (
            <p style={{ color: "var(--muted)", textAlign: "center", padding: "1rem 0" }}>No pending reminders.</p>
          )}
        </div>
      </div>

      {/* Bottom Grid */}
      <div className="dashboardBottom">
        <div className="card">
          <div className="cardTitle">
            <h3>Recent Scans</h3>
            <Link href="/reports" style={{ fontSize: "0.8rem", fontWeight: 600 }}>+ View All</Link>
          </div>
          
          {history.items.length === 0 ? (
            <p style={{ color: "var(--muted)", textAlign: "center", padding: "2rem 0" }}>No recent scans found.</p>
          ) : (
            <ul className="historyList">
              {history.items.slice(0, 4).map((item) => (
                <li key={item.id} className="historyItem">
                  <div className="historyIcon" style={{ 
                    background: item.result.decision === "FAKE" ? "var(--danger-bg)" : item.result.decision === "REAL" ? "#dcfce7" : "#dbeafe",
                    color: item.result.decision === "FAKE" ? "var(--risk-high)" : item.result.decision === "REAL" ? "var(--risk-low)" : "var(--risk-uncertain)"
                  }}>
                    {item.result.decision === "FAKE" ? "⚠️" : item.result.decision === "REAL" ? "✅" : "❓"}
                  </div>
                  <div className="historyDetails">
                    <p className="historyTitle">Scan ID: {item.id.substring(0, 8)}</p>
                    <p className="historyMeta">{new Date(item.timestamp).toLocaleString()}</p>
                  </div>
                  <div className="historyStats">
                    <span className={`riskBadge risk-${item.result.risk_level.toLowerCase()}`}>
                      {item.result.decision}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <div className="cardTitle">
            <h3>Project Progress</h3>
          </div>
          <div className="donutChart">
            <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%" }}>
              <path stroke="var(--line)" strokeWidth="6" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
              <path stroke="var(--primary)" strokeWidth="6" strokeDasharray={`${Math.round(history.analytics.avgConfidence * 100)}, 100`} fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            </svg>
            <div className="donutCenter">
              <div className="donutValue">{Math.round(history.analytics.avgConfidence * 100)}%</div>
              <div className="donutLabel">Avg Confidence</div>
            </div>
          </div>
          <div className="donutLegend">
            <div className="legendItem"><span className="legendDot primary"></span> Real</div>
            <div className="legendItem"><span className="legendDot secondary"></span> Fake</div>
          </div>
        </div>

        <div className="darkPanel">
          <h3>Time Tracker</h3>
          <div className="darkPanelValue">
            {formatUptime(localUptime)}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: "1rem" }}>
            <button 
              className="iconBtn timerBtn" 
              onClick={() => setUptimeRunning(!uptimeRunning)}
              style={{ background: "white", color: "var(--primary)", border: "none", cursor: "pointer" }}
              title={uptimeRunning ? "Pause Uptime Tracking" : "Resume"}
            >
              {uptimeRunning ? "⏸" : "▶"}
            </button>
            <button 
              className="iconBtn timerBtn" 
              onClick={() => { setUptimeRunning(false); setLocalUptime(0); }}
              style={{ background: "#ef4444", color: "white", border: "none", cursor: "pointer" }}
              title="Reset Uptime"
            >
              ⏹
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
