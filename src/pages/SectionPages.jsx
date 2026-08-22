import {
  AlertRow,
  HistoryChart,
  MetricCard,
  Sensor,
  StatusPill,
  ZoneRow,
} from "../components/DashboardComponents";

function PageHeader({ eyebrow, title, subtitle }) {
  return (
    <div className="page-heading section-page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
    </div>
  );
}

function EmptyState({ children }) {
  return <div className="empty-state page-empty-state">{children}</div>;
}

export function ChambersPage({
  zones,
  selectedId,
  onSelect,
  summary,
  formatNumber,
  loading,
}) {
  return (
    <>
      <PageHeader
        eyebrow="Live monitoring"
        title="Chambers"
        subtitle="Monitor every cold storage chamber and its current operating state."
      />
      <section className="page-grid">
        {loading ? (
          <EmptyState>Loading chambers...</EmptyState>
        ) : zones.length ? (
          zones.map((zone) => (
            <article className="panel page-card" key={zone.zone_id}>
              <div className="panel-head">
                <div>
                  <h3>{zone.zone_name}</h3>
                  <small>
                    {zone.current_crop_type} ·{" "}
                    {formatNumber(zone.capacity_kg, " kg")} capacity
                  </small>
                </div>
                <StatusPill status={zone.status} />
              </div>
              <ZoneRow
                zone={zone}
                selected={selectedId === zone.zone_id}
                onSelect={onSelect}
                formatNumber={formatNumber}
              />
            </article>
          ))
        ) : (
          <EmptyState>No chambers returned by the backend.</EmptyState>
        )}
      </section>
      <div className="page-summary">
        <MetricCard
          label="Total chambers"
          value={zones.length}
          note={`${summary.zone_breakdown?.optimal || 0} optimal`}
        />
        <MetricCard
          label="Critical chambers"
          value={summary.zone_breakdown?.critical || 0}
          note="Requires attention"
          tone="orange"
        />
      </div>
    </>
  );
}

export function TelemetryPage({ live, history, zoneName, sensors }) {
  return (
    <>
      <PageHeader
        eyebrow="Sensor network"
        title="Telemetry"
        subtitle={`Historical and live readings for ${zoneName}.`}
      />
      <section className="panel telemetry-page-card">
        <div className="panel-head">
          <div>
            <h3>Live sensor readings</h3>
            <small>Current values from the selected chamber</small>
          </div>
          <StatusPill status={live?.overall_status || "UNKNOWN"} />
        </div>
        <div className="sensor-grid page-sensor-grid">
          {sensors.map((sensor) => (
            <Sensor key={sensor.key} {...sensor} value={live?.[sensor.key]} />
          ))}
        </div>
      </section>
      <section className="panel chart-panel full-page-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Last 24 hours</p>
            <h3>Temperature history</h3>
          </div>
        </div>
        <HistoryChart history={history} />
      </section>
    </>
  );
}

export function AlertsPage({ alerts, loading }) {
  return (
    <>
      <PageHeader
        eyebrow="Needs attention"
        title="Alerts"
        subtitle="Review active anomalies reported by the cold storage network."
      />
      <section className="panel full-page-panel">
        {loading ? (
          <EmptyState>Loading alerts...</EmptyState>
        ) : alerts.length ? (
          alerts.map((alert) => <AlertRow key={alert.alert_id} alert={alert} />)
        ) : (
          <EmptyState>No active alerts. Your facility is calm.</EmptyState>
        )}
      </section>
    </>
  );
}

export function NotificationsPage({ notifications, loading }) {
  return (
    <>
      <PageHeader
        eyebrow="Delivery history"
        title="Notifications"
        subtitle="SMS and WhatsApp notifications sent to farmers."
      />
      <section className="panel full-page-panel">
        {loading ? (
          <EmptyState>Loading notifications...</EmptyState>
        ) : notifications.length ? (
          notifications.map((notification) => (
            <div className="alert-row" key={notification.notification_id}>
              <span className="alert-icon">✓</span>
              <div>
                <strong>{notification.channel} notification</strong>
                <small>{notification.content}</small>
              </div>
              <time>
                {new Date(notification.sent_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
            </div>
          ))
        ) : (
          <EmptyState>No notifications returned by the backend.</EmptyState>
        )}
      </section>
    </>
  );
}

export function FarmersPage({ farmers, loading }) {
  return (
    <>
      <PageHeader
        eyebrow="Produce partners"
        title="Farmers"
        subtitle="Registered farmers connected to this cold storage facility."
      />
      <section className="page-grid">
        {loading ? (
          <EmptyState>Loading farmers...</EmptyState>
        ) : farmers.length ? (
          farmers.map((farmer) => (
            <article
              className="panel page-card farmer-card"
              key={farmer.user_id}
            >
              <span className="zone-icon">
                {farmer.name?.slice(0, 1) || "F"}
              </span>
              <div>
                <h3>{farmer.name}</h3>
                <small>
                  {farmer.phone_number || farmer.email || "No contact details"}
                </small>
              </div>
              <StatusPill status="ACTIVE" />
            </article>
          ))
        ) : (
          <EmptyState>No farmers returned by the backend.</EmptyState>
        )}
      </section>
    </>
  );
}

export function AnalyticsPage({ zones, riskByZone, loading }) {
  return (
    <>
      <PageHeader
        eyebrow="AI insights"
        title="Analytics"
        subtitle="Live spoilage risk calculated from each chamber's sensor readings."
      />
      <section className="page-grid">
        {loading ? (
          <EmptyState>Calculating risk scores...</EmptyState>
        ) : (
          zones.map((zone) => {
            const risk = riskByZone[zone.zone_id];
            return (
              <article className="panel page-card" key={zone.zone_id}>
                <div className="panel-head">
                  <div>
                    <h3>{zone.zone_name}</h3>
                    <small>{zone.current_crop_type}</small>
                  </div>
                  <StatusPill status={risk?.risk_level || "UNKNOWN"} />
                </div>
                <div className="analytics-value">
                  {risk ? `${Math.round(risk.spoilage_risk_percentage)}%` : "—"}
                </div>
                <small>
                  {risk
                    ? `${risk.predicted_quality} quality · ${risk.estimated_shelf_life_days} days estimated shelf life`
                    : "Risk data unavailable"}
                </small>
              </article>
            );
          })
        )}
      </section>
    </>
  );
}
