import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
const SESSION_STORAGE_KEY = "devintel_session_history";

const tabs = [
  { id: "ingest", label: "Ingest Repo", icon: "01" },
  { id: "query", label: "Ask AI", icon: "02" },
  { id: "debug", label: "Debug Help", icon: "03" },
];

function extractErrorMessage(error, fallbackMessage) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (typeof first?.msg === "string") return first.msg;
  }
  if (typeof error?.response?.data?.error === "string" && error.response.data.error.trim()) {
    return error.response.data.error;
  }
  return fallbackMessage;
}

function safeParseHistory(raw) {
  try {
    const parsed = JSON.parse(raw || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function createSessionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const values = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(values);
  } else {
    values.forEach((_, index) => {
      values[index] = Math.floor(Math.random() * 256);
    });
  }
  values[6] = (values[6] & 0x0f) | 0x40;
  values[8] = (values[8] & 0x3f) | 0x80;
  const hex = Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function ScoreSparkline({ scores }) {
  if (!scores.length) return null;
  const width = 320;
  const height = 86;
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const spread = max - min || 1;
  const points = scores
    .map((score, index) => {
      const x = (index / Math.max(scores.length - 1, 1)) * width;
      const y = height - ((score - min) / spread) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="sparkline-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" preserveAspectRatio="none">
        <polyline points={points} />
      </svg>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("ingest");
  const [theme, setTheme] = useState(() => localStorage.getItem("devintel_theme") || "dark");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [sessionId] = useState(createSessionId);
  const [repoUrl, setRepoUrl] = useState("");
  const [currentRepo, setCurrentRepo] = useState("");
  const [question, setQuestion] = useState("");
  const [errorText, setErrorText] = useState("");
  const [codeSnippet, setCodeSnippet] = useState("");
  const [loading, setLoading] = useState({ ingest: false, query: false, debug: false });
  const [statusCard, setStatusCard] = useState({
    kind: "info",
    message: "Connect your backend and start exploring code intelligence.",
  });
  const [queryResult, setQueryResult] = useState(null);
  const [debugResult, setDebugResult] = useState("");
  const [history, setHistory] = useState(() =>
    safeParseHistory(localStorage.getItem(SESSION_STORAGE_KEY))
  );

  const canUseGemini = useMemo(() => Boolean(geminiApiKey.trim()), [geminiApiKey]);
  const hasIndexedRepo = useMemo(() => Boolean(currentRepo), [currentRepo]);
  const canQuery = useMemo(
    () => Boolean(question.trim() && canUseGemini && hasIndexedRepo),
    [question, canUseGemini, hasIndexedRepo]
  );
  const canDebug = useMemo(
    () => Boolean(errorText.trim() && canUseGemini && hasIndexedRepo),
    [errorText, canUseGemini, hasIndexedRepo]
  );
  const canIngest = useMemo(() => Boolean(repoUrl.trim()), [repoUrl]);
  const filteredHistory = useMemo(
    () => history.filter((entry) => (currentRepo ? entry.repoUrl === currentRepo : true)).slice(0, 10),
    [currentRepo, history]
  );
  const averageScore = useMemo(() => {
    if (!filteredHistory.length) return 0;
    return filteredHistory.reduce((sum, item) => sum + (Number(item.score) || 0), 0) / filteredHistory.length;
  }, [filteredHistory]);
  const scoreSeries = useMemo(
    () => filteredHistory.slice().reverse().map((entry) => Number(entry.score) || 0),
    [filteredHistory]
  );

  const setTabLoading = (tab, value) => {
    setLoading((prev) => ({ ...prev, [tab]: value }));
  };

  const setSuccess = (message) => setStatusCard({ kind: "success", message });
  const setFailure = (message) => setStatusCard({ kind: "error", message });
  const sessionHeaders = { "X-DevIntel-Session-ID": sessionId };
  const geminiHeaders = {
    ...sessionHeaders,
    "X-Gemini-API-Key": geminiApiKey.trim(),
  };
  const appendHistory = (entry) => {
    setHistory((prev) => [entry, ...prev].slice(0, 50));
  };

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("devintel_theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    const checkBackendConnection = async () => {
      try {
        const response = await axios.get(`${API_BASE}/`);
        setStatusCard({
          kind: "success",
          message: response.data?.message || "Backend connected successfully.",
        });
      } catch {
        setStatusCard({
          kind: "error",
          message: "Backend is not reachable. Start backend server on the configured API URL.",
        });
      }
    };

    checkBackendConnection();
  }, []);

  const handleIngest = async (event) => {
    event.preventDefault();
    if (!canIngest) return;

    setTabLoading("ingest", true);
    setQueryResult(null);
    setDebugResult("");
    try {
      const normalizedRepoUrl = repoUrl.trim();
      const response = await axios.post(`${API_BASE}/ingest`, { repo_url: normalizedRepoUrl }, {
        headers: sessionHeaders,
      });
      setSuccess(response.data?.message || "Repository indexed successfully.");
      setCurrentRepo(normalizedRepoUrl);
      setRepoUrl("");
      setActiveTab("query");
    } catch (error) {
      setFailure(extractErrorMessage(error, "Could not index repository. Check backend logs."));
    } finally {
      setTabLoading("ingest", false);
    }
  };

  const handleQuery = async (event) => {
    event.preventDefault();
    if (!canQuery) return;

    setTabLoading("query", true);
    try {
      const normalizedQuestion = question.trim();
      const response = await axios.post(`${API_BASE}/query`, { q: normalizedQuestion }, {
        headers: geminiHeaders,
      });
      if (response.data?.error) {
        setFailure(response.data.error);
        return;
      }
      const resultScore = Number(response.data?.score) || 0;
      setQueryResult(response.data);
      appendHistory({
        id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        repoUrl: currentRepo || "unspecified",
        question: normalizedQuestion,
        score: resultScore,
        createdAt: new Date().toISOString(),
      });
      setSuccess("AI response generated with relevance score.");
    } catch (error) {
      setFailure(extractErrorMessage(error, "Query failed. Please check backend status and API quota."));
    } finally {
      setTabLoading("query", false);
    }
  };

  const handleDebug = async (event) => {
    event.preventDefault();
    if (!canDebug) return;

    setTabLoading("debug", true);
    try {
      const response = await axios.post(`${API_BASE}/debug`, {
        error: errorText.trim(),
        code: codeSnippet,
      }, {
        headers: geminiHeaders,
      });
      setDebugResult(response.data?.result || "No debug guidance received.");
      setSuccess("Debug intelligence generated.");
    } catch (error) {
      setFailure(extractErrorMessage(error, "Debug request failed. Please check backend status and API quota."));
    } finally {
      setTabLoading("debug", false);
    }
  };

  return (
    <main className="page-shell" data-theme={theme}>
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <div className="ambient ambient-c" />

      <section className="glass-panel">
        <header className="hero">
          <div className="hero-top">
            <p className="badge">DevIntel Studio</p>
            <button
              type="button"
              className="theme-toggle"
              onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </button>
          </div>
          <h1>Modern AI Workspace for Your Backend</h1>
          <p className="subtitle">
            Ingest repositories, ask precise technical questions, and debug faster with a sleek interactive workflow.
          </p>
        </header>

        <nav className="tab-grid">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        <section className="credential-panel" aria-labelledby="gemini-key-heading">
          <div>
            <p className="credential-eyebrow">Bring your own key</p>
            <h2 id="gemini-key-heading">Google Gemini API key</h2>
            <p>
              Used only for this tab&apos;s AI requests. DevIntel does not save it in browser storage,
              a database, or the repository index.
            </p>
          </div>
          <div className="credential-controls">
            <label htmlFor="geminiApiKey">Gemini API key</label>
            <div className="key-input-row">
              <input
                id="geminiApiKey"
                type="password"
                value={geminiApiKey}
                onChange={(event) => setGeminiApiKey(event.target.value)}
                placeholder="Paste your Gemini API key"
                autoComplete="off"
                spellCheck="false"
              />
              <button
                type="button"
                className="secondary-button"
                onClick={() => setGeminiApiKey("")}
                disabled={!geminiApiKey}
              >
                Clear key
              </button>
            </div>
            <p className="key-status">
              {!canUseGemini
                ? "A key is required to ask or debug."
                : hasIndexedRepo
                  ? "Key ready for this tab."
                  : "Key ready — index a repository to begin."}
            </p>
          </div>
        </section>

        <article className="content-grid">
          <section className="input-panel">
            {activeTab === "ingest" && (
              <form onSubmit={handleIngest} className="form">
                <label htmlFor="repoUrl">Repository URL</label>
                <input
                  id="repoUrl"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/org/repo"
                  maxLength={500}
                />
                <button disabled={!canIngest || loading.ingest}>
                  {loading.ingest ? "Indexing..." : "Index Repository"}
                </button>
              </form>
            )}

            {activeTab === "query" && (
              <form onSubmit={handleQuery} className="form">
                <label htmlFor="question">Ask your codebase</label>
                <textarea
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="How is user authentication implemented in this repository?"
                  rows={6}
                  maxLength={1200}
                />
                <button disabled={!canQuery || loading.query}>
                  {loading.query ? "Thinking..." : "Generate Answer"}
                </button>
              </form>
            )}

            {activeTab === "debug" && (
              <form onSubmit={handleDebug} className="form">
                <label htmlFor="errorText">Paste error message</label>
                <textarea
                  id="errorText"
                  value={errorText}
                  onChange={(e) => setErrorText(e.target.value)}
                  placeholder="TypeError: Cannot read properties of undefined..."
                  rows={4}
                  maxLength={2000}
                />
                <label htmlFor="codeSnippet">Related code (optional)</label>
                <textarea
                  id="codeSnippet"
                  value={codeSnippet}
                  onChange={(e) => setCodeSnippet(e.target.value)}
                  placeholder="Paste related code block for better diagnostics."
                  rows={7}
                  maxLength={3000}
                />
                <button disabled={!canDebug || loading.debug}>
                  {loading.debug ? "Analyzing..." : "Debug This"}
                </button>
              </form>
            )}
          </section>

          <section className="result-panel">
            <div className={`status ${statusCard.kind}`}>
              <h3>System Status</h3>
              <p>{statusCard.message}</p>
            </div>

            <div className="metrics-grid">
              <div className="card metric-card">
                <p className="metric-label">Current Repo</p>
                <h3>{currentRepo || "Not selected"}</h3>
              </div>
              <div className="card metric-card">
                <p className="metric-label">Avg Score</p>
                <h3>{filteredHistory.length ? averageScore.toFixed(3) : "--"}</h3>
              </div>
              <div className="card metric-card">
                <p className="metric-label">Recent Queries</p>
                <h3>{filteredHistory.length}</h3>
              </div>
            </div>

            {scoreSeries.length > 1 && (
              <div className="card">
                <div className="card-top">
                  <h3>Score Trend</h3>
                  <span className="score">Last {scoreSeries.length} queries</span>
                </div>
                <ScoreSparkline scores={scoreSeries} />
              </div>
            )}

            {queryResult && (
              <div className="card">
                <div className="card-top">
                  <h3>AI Answer</h3>
                  <span className="score">Score: {Number(queryResult.score).toFixed(3)}</span>
                </div>
                <div className="markdown">
                  <ReactMarkdown>{queryResult.answer}</ReactMarkdown>
                </div>
              </div>
            )}

            {debugResult && (
              <div className="card">
                <h3>Debug Guidance</h3>
                <div className="markdown debug-markdown">
                  <ReactMarkdown>{debugResult}</ReactMarkdown>
                </div>
              </div>
            )}

            {filteredHistory.length > 0 && (
              <div className="card">
                <div className="card-top">
                  <h3>Session History</h3>
                  <span className="score">Saved locally</span>
                </div>
                <div className="history-list">
                  {filteredHistory.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="history-item"
                      onClick={() => {
                        setQuestion(item.question);
                        setActiveTab("query");
                      }}
                    >
                      <p>{item.question}</p>
                      <div>
                        <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                        <strong>{Number(item.score).toFixed(3)}</strong>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>
        </article>
      </section>
    </main>
  );
}
