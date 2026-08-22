import { useEffect, useState } from "react";
import { api } from "./services/api";
import {
  AlertRow,
  HistoryChart,
  Icon,
  MetricCard,
  NavigationItem,
  Sensor,
  StatusPill,
  ZoneRow,
} from "./components/DashboardComponents";
import {
  AlertsPage,
  AnalyticsPage,
  ChambersPage,
  FarmersPage,
  NotificationsPage,
  TelemetryPage,
} from "./pages/SectionPages";
import "./App.css";

const emptySummary = {
  total_zones: 0,
  total_produce_stored_kg: 0,
  active_alerts: 0,
  critical_alerts: 0,
  zone_breakdown: {},
};
const sensorDefinitions = [
  {
    icon: "°",
    label: "Temperature",
    key: "temperature",
    unit: "°C",
    range: "Target 21—24°C",
  },
  {
    icon: "◌",
    label: "Humidity",
    key: "humidity",
    unit: "%",
    range: "Target 80—95%",
  },
  {
    icon: "≋",
    label: "CO₂ level",
    key: "co2",
    unit: " ppm",
    range: "Max 380 ppm",
  },
  {
    icon: "☼",
    label: "Light level",
    key: "light",
    unit: " lux",
    range: "Max 20 lux",
  },
];

function formatNumber(value, suffix = "") {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value || 0)}${suffix}`;
}

function App() {
  const [summary, setSummary] = useState(emptySummary);
  const [health, setHealth] = useState(null);
  const [zones, setZones] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [farmers, setFarmers] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [riskByZone, setRiskByZone] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [live, setLive] = useState(null);
  const [history, setHistory] = useState(null);
  const [liveZoneId, setLiveZoneId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeView, setActiveView] = useState("overview");

  useEffect(() => {
    Promise.allSettled([
      api.health(),
      api.summary(),
      api.zones(),
      api.activeAlerts(),
    ])
      .then((results) => {
        const [healthResult, summaryResult, zonesResult, alertsResult] =
          results;
        if (healthResult.status === "fulfilled") setHealth(healthResult.value);
        if (summaryResult.status === "fulfilled")
          setSummary(summaryResult.value);
        if (zonesResult.status === "fulfilled") {
          setZones(zonesResult.value);
          setSelectedId(zonesResult.value[0]?.zone_id || null);
        }
        if (alertsResult.status === "fulfilled") setAlerts(alertsResult.value);
        if (results.some((result) => result.status === "rejected"))
          setError(
            "Some facility data is unavailable. The dashboard will show available API responses.",
          );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([api.liveZone(selectedId), api.zoneHistory(selectedId)])
      .then(([nextLive, nextHistory]) => {
        setLive(nextLive);
        setHistory(nextHistory);
        setLiveZoneId(selectedId);
      })
      .catch(() => setLiveZoneId(null));
  }, [selectedId]);

  useEffect(() => {
    if (activeView === "farmers")
      api
        .farmers()
        .then(setFarmers)
        .catch(() => setFarmers([]));
    if (activeView === "notifications")
      api
        .notifications()
        .then(setNotifications)
        .catch(() => setNotifications([]));
    if (activeView === "analytics" && zones.length) {
      Promise.all(
        zones.map((zone) =>
          api
            .zoneRisk(zone.zone_id)
            .then((risk) => [zone.zone_id, risk])
            .catch(() => [zone.zone_id, null]),
        ),
      ).then((results) => setRiskByZone(Object.fromEntries(results)));
    }
  }, [activeView, zones]);

  const activeZone = zones.find((zone) => zone.zone_id === selectedId);
  const displayLive =
    liveZoneId === selectedId && live
      ? live
      : {
          zone_name: activeZone?.zone_name || "Select a chamber",
          crop_type: activeZone?.current_crop_type,
          overall_status: activeZone?.status || "UNKNOWN",
          risk_score: null,
          spoilage_risk: "Unavailable",
          temperature: null,
          humidity: null,
          co2: null,
          light: null,
        };
  const navigation = [
    { id: "overview", label: "Overview", icon: "◈" },
    {
      id: "chambers",
      label: "Chambers",
      icon: "◫",
      count: zones.length || "—",
    },
    { id: "telemetry", label: "Telemetry", icon: "⌁" },
    { id: "farmers", label: "Farmers", icon: "◌" },
    {
      id: "alerts",
      label: "Alerts",
      icon: "◎",
      count: summary.active_alerts || "—",
      alert: true,
    },
    { id: "analytics", label: "Analytics", icon: "◒" },
  ];
  const metrics = [
    {
      label: "Produce in storage",
      value: loading
        ? "—"
        : formatNumber(summary.total_produce_stored_kg, " kg"),
      note: "Across all active batches",
      tone: "lime",
    },
    {
      label: "Chambers online",
      value: loading ? "—" : summary.total_zones,
      note: `${summary.zone_breakdown?.optimal || 0} optimal zones`,
    },
    {
      label: "Active alerts",
      value: loading ? "—" : summary.active_alerts,
      note: loading
        ? "Waiting for alert data"
        : `${summary.critical_alerts || 0} critical require attention`,
      tone: summary.active_alerts ? "orange" : "neutral",
    },
    {
      label: "Backend status",
      value: health?.status || "—",
      note: health?.version
        ? `API version ${health.version}`
        : "Waiting for API response",
      tone: "blue",
    },
  ];
  const summaryTime = summary.timestamp
    ? new Date(summary.timestamp).toLocaleString("en-IN", {
        dateStyle: "full",
        timeStyle: "medium",
        timeZone: "Asia/Kolkata",
      })
    : "Waiting for facility timestamp";
  const navigate = (item) => setActiveView(item.id);

  function OverviewPage() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">{summaryTime}</p>
            <h1>Facility overview</h1>
            <p className="subtitle">
              Here is what is happening across your cold chain today.
            </p>
          </div>
          <button className="refresh" onClick={() => window.location.reload()}>
            <Icon>↻</Icon> Refresh data
          </button>
        </section>
        {error && (
          <div className="error-banner">
            <strong>Connection issue</strong>
            {error}
          </div>
        )}
        <section className="metrics-grid">
          {metrics.map((metric) => (
            <MetricCard key={metric.label} {...metric} />
          ))}
        </section>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Live monitoring</p>
            <h2>Chamber status</h2>
          </div>
          <button
            className="text-button"
            onClick={() => navigate(navigation[1])}
          >
            View all chambers <span>→</span>
          </button>
        </div>
        <section className="monitor-grid">
          <div className="panel zones-panel">
            <div className="panel-head">
              <div>
                <h3>All chambers</h3>
                <small>Current sensor readings</small>
              </div>
              <StatusPill status={summary.system_status || "UNKNOWN"} />
            </div>
            <div className="zone-list">
              {loading ? (
                <div className="empty-state">Loading chambers...</div>
              ) : zones.length ? (
                zones.map((zone) => (
                  <ZoneRow
                    key={zone.zone_id}
                    zone={zone}
                    selected={selectedId === zone.zone_id}
                    onSelect={setSelectedId}
                    formatNumber={formatNumber}
                  />
                ))
              ) : (
                <div className="empty-state">
                  No zones returned by the backend.
                </div>
              )}
            </div>
          </div>
          <div className="panel detail-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Selected chamber</p>
                <h3>{displayLive.zone_name}</h3>
                <small>{displayLive.crop_type || "No crop assigned"}</small>
              </div>
              <StatusPill status={displayLive.overall_status} />
            </div>
            <div className="risk-block">
              <div>
                <span>Spoilage risk</span>
                <strong>
                  {displayLive.risk_score == null
                    ? "—"
                    : Math.round(displayLive.risk_score)}
                  <em>{displayLive.risk_score == null ? "" : "%"}</em>
                </strong>
                <small>{displayLive.spoilage_risk} quality forecast</small>
              </div>
              <div
                className="risk-ring"
                style={{ "--risk": `${displayLive.risk_score || 0}%` }}
              >
                <span>
                  {displayLive.risk_score == null
                    ? "—"
                    : `${Math.round(displayLive.risk_score)}%`}
                </span>
              </div>
            </div>
            <div className="sensor-grid">
              {sensorDefinitions.map((sensor) => (
                <Sensor
                  key={sensor.key}
                  {...sensor}
                  value={displayLive[sensor.key]}
                />
              ))}
            </div>
          </div>
        </section>
        <section className="lower-grid">
          <div className="panel chart-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Sensor history</p>
                <h3>Temperature trend</h3>
              </div>
              <span className="chart-key">
                <i /> Temperature <b>24 hours</b>
              </span>
            </div>
            <HistoryChart history={history} />
          </div>
          <div className="panel alerts-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Needs attention</p>
                <h3>Recent alerts</h3>
              </div>
              <button
                className="text-button"
                onClick={() => navigate(navigation[4])}
              >
                View all <span>→</span>
              </button>
            </div>
            {alerts.length ? (
              alerts
                .slice(0, 3)
                .map((alert) => <AlertRow key={alert.alert_id} alert={alert} />)
            ) : (
              <div className="empty-state">
                No active alerts. Your facility is calm.
              </div>
            )}
          </div>
        </section>
      </>
    );
  }

  function renderPage() {
    if (activeView === "chambers")
      return (
        <ChambersPage
          zones={zones}
          selectedId={selectedId}
          onSelect={setSelectedId}
          summary={summary}
          formatNumber={formatNumber}
          loading={loading}
        />
      );
    if (activeView === "telemetry")
      return (
        <TelemetryPage
          live={displayLive}
          history={history}
          zoneName={displayLive.zone_name}
          sensors={sensorDefinitions}
        />
      );
    if (activeView === "alerts")
      return <AlertsPage alerts={alerts} loading={loading} />;
    if (activeView === "notifications")
      return (
        <NotificationsPage notifications={notifications} loading={loading} />
      );
    if (activeView === "farmers")
      return <FarmersPage farmers={farmers} loading={loading} />;
    if (activeView === "analytics")
      return (
        <AnalyticsPage
          zones={zones}
          riskByZone={riskByZone}
          loading={loading}
        />
      );
    return <OverviewPage />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">N</span>
          <div>
            <strong>NAVAMSA</strong>
            <small>cold chain intelligence</small>
          </div>
        </div>
        <nav>
          <p className="nav-label">Workspace</p>
          {navigation.slice(0, 4).map((item) => (
            <NavigationItem
              key={item.id}
              item={item}
              active={activeView === item.id}
              onNavigate={navigate}
            />
          ))}
          <p className="nav-label nav-gap">Manage</p>
          {navigation.slice(4).map((item) => (
            <NavigationItem
              key={item.id}
              item={item}
              active={activeView === item.id}
              onNavigate={navigate}
            />
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="operator">
            <span>NX</span>
            <div>
              <strong>NodeX</strong>
              <small>Operations lead</small>
            </div>
          </div>
          <div
            className={`connection ${health?.status === "HEALTHY" ? "" : "offline"}`}
          >
            <span /> API{" "}
            {health?.status === "HEALTHY" ? "connection" : "unavailable"}{" "}
            <strong>●</strong>
          </div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div className="mobile-brand">
            <span className="brand-mark">N</span>
            <strong>NAVAMSA</strong>
          </div>
          <div className="breadcrumbs">
            Operations <span>/</span> {activeView}
          </div>
          <div className="top-actions">
            <span
              className={`live-dot ${health?.status === "HEALTHY" ? "" : "offline"}`}
            />
            {health?.status || "Connecting"}
            <button
              aria-label="Notifications"
              onClick={() => setActiveView("notifications")}
            >
              ♧<i>{summary.active_alerts || 0}</i>
            </button>
            <button className="avatar">NX</button>
          </div>
        </header>
        <div className="content-wrap">
          {activeView !== "overview" && (
            <button
              className="back-button"
              onClick={() => setActiveView("overview")}
            >
              ← Back to overview
            </button>
          )}
          {renderPage()}
        </div>
        <footer>
          <span>NAVAMSA OS v1.0</span>
          <span>
            Data refreshes automatically <i className="live-dot" />
          </span>
        </footer>
      </main>
      <div className="mobile-nav">
        {navigation.map((item) => (
          <NavigationItem
            key={item.id}
            item={item}
            active={activeView === item.id}
            onNavigate={navigate}
            mobile
          />
        ))}
      </div>
    </div>
  );
}

export default App;
