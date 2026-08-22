export function Icon({ children }) {
  return (
    <span className="icon" aria-hidden="true">
      {children}
    </span>
  );
}

export function StatusPill({ status = "UNKNOWN" }) {
  return (
    <span className={`status-pill status-${status.toLowerCase()}`}>
      <span />
      {status}
    </span>
  );
}

export function MetricCard({ label, value, note, tone = "neutral" }) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

export function NavigationItem({ item, active, onNavigate, mobile = false }) {
  return (
    <button
      className={`${mobile ? "mobile-nav-item" : "nav-link"} ${active ? "active" : ""}`}
      onClick={() => onNavigate(item)}
    >
      <Icon>{item.icon}</Icon>
      <span>{item.label}</span>
      {!mobile && item.count && (
        <span className={`nav-count ${item.alert ? "alert-count" : ""}`}>
          {item.count}
        </span>
      )}
    </button>
  );
}

export function ZoneRow({ zone, selected, onSelect, formatNumber }) {
  return (
    <button
      className={`zone-row ${selected ? "selected" : ""}`}
      onClick={() => onSelect(zone.zone_id)}
    >
      <span className="zone-icon">
        {zone.current_crop_type?.slice(0, 1) || "C"}
      </span>
      <span className="zone-info">
        <strong>{zone.zone_name}</strong>
        <small>
          {zone.current_crop_type} · {formatNumber(zone.capacity_kg, " kg")}{" "}
          capacity
        </small>
      </span>
      <StatusPill status={zone.status} />
      <span className="chevron">›</span>
    </button>
  );
}

export function Sensor({ icon, label, value, unit, range }) {
  return (
    <div className="sensor">
      <Icon>{icon}</Icon>
      <div>
        <span>{label}</span>
        <strong>
          {value ?? "--"}
          <em>{unit}</em>
        </strong>
        <small>{range}</small>
      </div>
    </div>
  );
}

export function AlertRow({ alert }) {
  return (
    <div className="alert-row">
      <span className={`alert-icon ${alert.severity?.toLowerCase()}`}>!</span>
      <div>
        <strong>{alert.title}</strong>
        <small>{alert.message}</small>
      </div>
      <time>
        {new Date(alert.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </time>
    </div>
  );
}

export function HistoryChart({ history }) {
  const values = history?.data?.map((item) => item.value) || [];
  if (!values.length) {
    return (
      <div className="empty-state chart-empty">
        No telemetry history available for this chamber.
      </div>
    );
  }

  const points = values
    .map(
      (value, index) =>
        `${(index / (values.length - 1 || 1)) * 100},${100 - ((value - Math.min(...values)) / (Math.max(...values) - Math.min(...values) || 1)) * 78 - 10}`,
    )
    .join(" ");

  return (
    <div className="chart-wrap">
      <div className="chart-y">
        <span>24°C</span>
        <span>22°C</span>
        <span>20°C</span>
      </div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="chart"
        role="img"
        aria-label="Temperature over the last 24 hours"
      >
        <defs>
          <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#b8ed48" stopOpacity=".28" />
            <stop offset="1" stopColor="#b8ed48" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`0,100 ${points} 100,100`} fill="url(#area)" />
        <polyline
          points={points}
          fill="none"
          stroke="#b8ed48"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="chart-x">
        <span>24h ago</span>
        <span>12h ago</span>
        <span>Now</span>
      </div>
    </div>
  );
}
