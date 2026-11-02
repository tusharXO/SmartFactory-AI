import { lazy, Suspense, useEffect, useState } from 'react'
import { getCharts, getHealth, getModelMetrics, getOverview } from './api.js'
import { formatNumber, formatPercent } from './format.js'
import MetricCard from './components/MetricCard.jsx'
import PredictionForm from './components/PredictionForm.jsx'
import ObservationsTable from './components/ObservationsTable.jsx'
import ModelMetrics from './components/ModelMetrics.jsx'

const AnalyticsCharts = lazy(() => import('./components/AnalyticsCharts.jsx'))

function Icon({ name, size = 20 }) {
  const paths = {
    factory: (
      <>
        <path d="M3 21V9l6 3V6l6 3V3h6v18H3Z" />
        <path d="M7 17h1m4 0h1m4 0h1" />
      </>
    ),
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    prediction: <path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z" />,
    observations: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M8 9v11m-5-6h18" />
      </>
    ),
    model: <path d="M5 20V10m7 10V4m7 16v-7M2 20h20" />,
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5" />
        <path d="M6.1 6.1A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.9" />
      </>
    ),
    alert: (
      <>
        <path d="m12 3 10 18H2L12 3Z" />
        <path d="M12 9v5m0 3v.1" />
      </>
    ),
    layers: <path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5" />,
    percent: (
      <>
        <path d="m5 19 14-14" />
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="18" r="3" />
      </>
    ),
    arrow: <path d="M7 17 17 7M7 7h10v10" />,
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.layers}
    </svg>
  )
}

function useResource(load, refreshKey) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setState({ data: null, loading: true, error: null })
    load({ signal: controller.signal }).then(
      (data) => {
        if (active) setState({ data, loading: false, error: null })
      },
      (error) => {
        if (active && error.name !== 'AbortError') {
          setState({ data: null, loading: false, error })
        }
      },
    )
    return () => {
      active = false
      controller.abort()
    }
  }, [load, refreshKey])
  return state
}

const NAV_ITEMS = [
  ['overview', 'Overview'],
  ['prediction', 'Prediction'],
  ['observations', 'Observations'],
  ['model', 'Model evaluation'],
]

function sectionFromHash() {
  const section = window.location.hash.slice(1)
  return NAV_ITEMS.some(([id]) => id === section) ? section : 'overview'
}

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [activeSection, setActiveSection] = useState(sectionFromHash)

  useEffect(() => {
    const syncSection = () => setActiveSection(sectionFromHash())
    window.addEventListener('hashchange', syncSection)
    return () => window.removeEventListener('hashchange', syncSection)
  }, [])

  const health = useResource(getHealth, refreshKey)
  const overview = useResource(getOverview, refreshKey)
  const charts = useResource(getCharts, refreshKey)
  const model = useResource(getModelMetrics, refreshKey)
  const refreshing = [health, overview, charts, model].some((resource) => resource.loading)
  const refresh = () => setRefreshKey((value) => value + 1)
  const status = health.loading ? 'checking' : health.error ? 'offline' : health.data.status
  const statusText = {
    checking: 'Checking API',
    offline: 'API unavailable',
    ok: 'API connected',
    degraded: 'API needs attention',
  }[status]

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to dashboard
      </a>
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="SmartFactory AI overview">
          <span className="brand-mark"><Icon name="factory" size={23} /></span>
          <span>SmartFactory<span className="brand-ai">AI</span></span>
        </a>
        <p className="sidebar-caption">ANALYTICS WORKSPACE</p>
        <nav className="sidebar-nav" aria-label="Dashboard navigation">
          {NAV_ITEMS.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className={activeSection === id ? 'nav-link active' : 'nav-link'}
              aria-current={activeSection === id ? 'location' : undefined}
            >
              <Icon name={id} size={19} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-source">
          <span className="source-mark"><Icon name="layers" /></span>
          <p>Built on synthetic data</p>
          <span>UCI AI4I 2020 dataset</span>
          <a
            href="https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"
            target="_blank"
            rel="noreferrer"
          >
            Explore the source <Icon name="arrow" size={14} />
          </a>
        </div>
        <div className="sidebar-bottom">
          <span className="sidebar-dot" />Synthetic dataset demo
        </div>
      </aside>

      <main className="main-content" id="main-content">
        <div className="topbar">
          <p className="breadcrumb">Workspace <span>/</span> <strong>Equipment analytics</strong></p>
          <span className="connection-status" data-state={status} role="status">
            <span />{statusText}
          </span>
        </div>
        <header className="page-header" id="overview">
          <div>
            <p className="eyebrow">SMARTFACTORY AI</p>
            <h1>Predictive Maintenance Analytics</h1>
            <p className="page-description">Explore operating conditions. Understand failure patterns.</p>
          </div>
          <button
            type="button"
            className="button button-secondary refresh-button"
            onClick={refresh}
            disabled={refreshing}
          >
            <Icon name="refresh" size={16} />
            {refreshing ? 'Refreshing…' : 'Refresh data'}
          </button>
        </header>

        {health.error && (
          <div className="connection-error" role="alert">
            <Icon name="alert" />
            <div>
              <strong>Backend connection unavailable</strong>
              <p>The dashboard could not reach the data service. Use Refresh data to reconnect.</p>
            </div>
          </div>
        )}
        {overview.error && !health.error && (
          <div className="connection-error" role="alert">
            <Icon name="alert" />
            <p>{overview.error.message}</p>
          </div>
        )}

        <section className="kpi-grid" aria-label="Dataset summary">
          <MetricCard
            label="Total observations"
            value={formatNumber(overview.data?.total_observations)}
            description="Operating measurement snapshots"
            icon={<Icon name="observations" />}
            loading={overview.loading}
          />
          <MetricCard
            label="Labeled failures"
            value={formatNumber(overview.data?.failure_count)}
            description="Actual failure class in the dataset"
            icon={<Icon name="alert" />}
            loading={overview.loading}
          />
          <MetricCard
            label="Failure rate"
            value={formatPercent(overview.data?.failure_rate)}
            description="Share of observations labeled failure"
            icon={<Icon name="percent" />}
            loading={overview.loading}
          />
          <MetricCard
            label="Quality variants"
            value={formatNumber(overview.data?.type_count)}
            description="Product quality types L, M, and H"
            icon={<Icon name="layers" />}
            loading={overview.loading}
          />
        </section>

        <div className="section-heading">
          <div>
            <p className="eyebrow">EXPLORE & ESTIMATE</p>
            <h2>From observations to insight</h2>
          </div>
          <span className="badge badge-neutral">Synthetic dataset demo</span>
        </div>
        <div className="analysis-layout">
          <Suspense
            fallback={
              <section className="panel state-message" role="status">Loading chart tools…</section>
            }
          >
            <AnalyticsCharts {...charts} onRetry={refresh} />
          </Suspense>
          <PredictionForm modelReady={health.data?.model_ready ?? null} />
        </div>
        <ObservationsTable refreshKey={refreshKey} />
        <ModelMetrics {...model} onRetry={refresh} />

        <footer className="dashboard-footer">
          <div>
            <strong>SmartFactory AI</strong>
            <p>Snapshot classification using synthetic equipment data.</p>
          </div>
          <div className="footer-links">
            <a
              href="https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"
              target="_blank"
              rel="noreferrer"
            >
              AI4I 2020 · UCI
            </a>
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">
              CC BY 4.0
            </a>
            <a href="https://github.com/tusharXO/SmartFactory-AI" target="_blank" rel="noreferrer">
              GitHub <Icon name="arrow" size={13} />
            </a>
          </div>
        </footer>
      </main>
    </div>
  )
}
