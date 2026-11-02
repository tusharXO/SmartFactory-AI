export default function MetricCard({ label, value, description, icon, loading }) {
  return (
    <article className="metric-card" aria-busy={loading || undefined}>
      <div className="metric-card-top">
        <p className="metric-label">{label}</p>
        {icon && <span className="metric-icon" aria-hidden="true">{icon}</span>}
      </div>
      <p className="metric-value">
        {loading ? (
          <>
            <span className="skeleton metric-skeleton" aria-hidden="true" />
            <span className="sr-only">Loading {label.toLowerCase()}</span>
          </>
        ) : value}
      </p>
      <p className="metric-description">{description}</p>
    </article>
  )
}
