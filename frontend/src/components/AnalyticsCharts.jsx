import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDecimal, formatNumber, formatPercent } from '../format.js'

const TYPE_ORDER = ['L', 'M', 'H']
const axisStyle = { fill: '#728291', fontSize: 11 }
const tooltipStyle = {
  border: '1px solid #dce5e9',
  borderRadius: 10,
  boxShadow: '0 8px 24px rgb(15 23 42 / 8%)',
  fontSize: 12,
}

function ordered(rows) {
  return [...rows].sort((a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type))
}

export default function AnalyticsCharts({ data, loading, error, onRetry }) {
  const distribution = ordered(data?.type_distribution ?? [])
  const failureRates = ordered(data?.failure_rates_by_type ?? []).map((row) => ({
    ...row,
    failure_rate_percent: row.failure_rate * 100,
  }))
  const empty = distribution.length === 0 && failureRates.length === 0

  return (
    <section className="panel analytics-panel" id="analytics" aria-labelledby="analytics-title">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Dataset exploration</p>
          <h2 className="panel-title" id="analytics-title">Dataset overview</h2>
          <p className="panel-description">Operating observations by product-quality variant.</p>
        </div>
        <span className="badge badge-neutral">L / M / H</span>
      </div>

      {loading ? (
        <div className="charts-grid" role="status" aria-label="Loading dataset charts">
          {[0, 1].map((index) => (
            <div className="chart-block" key={index}>
              <div className="skeleton chart-skeleton" aria-hidden="true" />
            </div>
          ))}
          <span className="sr-only">Loading charts</span>
        </div>
      ) : error ? (
        <div className="state-message error-message" role="alert">
          <p>{typeof error === 'string' ? error : error.message || 'Charts are unavailable.'}</p>
          <button className="button button-secondary" type="button" onClick={onRetry}>Retry charts</button>
        </div>
      ) : empty ? (
        <div className="state-message">
          <p>No observations are available to chart.</p>
          <button className="button button-secondary" type="button" onClick={onRetry}>Refresh charts</button>
        </div>
      ) : (
        <>
          <div className="charts-grid">
            <div className="chart-block">
              <h3 className="chart-title">Observation distribution</h3>
              <p className="chart-description">Number of observations</p>
              <div className="chart-frame" style={{ height: 190, minWidth: 0 }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <BarChart data={distribution} margin={{ top: 25, right: 12, bottom: 0, left: 0 }} accessibilityLayer>
                    <CartesianGrid stroke="#eaf0f3" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="type" axisLine={false} tickLine={false} tick={axisStyle} tickMargin={10} />
                    <YAxis axisLine={false} tickLine={false} tick={axisStyle} tickFormatter={formatNumber} width={46} allowDecimals={false} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      cursor={{ fill: '#f0f6f5' }}
                      labelFormatter={(label) => `Quality variant ${label}`}
                      formatter={(value) => [formatNumber(value), 'Observations']}
                    />
                    <Bar dataKey="count" name="Observations" fill="#0f8b7e" radius={[5, 5, 0, 0]} maxBarSize={38} isAnimationActive={false}>
                      <LabelList dataKey="count" position="top" formatter={formatNumber} fill="#435967" fontSize={11} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <table className="sr-only">
                <caption>Observation counts by product-quality variant</caption>
                <thead><tr><th scope="col">Type</th><th scope="col">Observations</th></tr></thead>
                <tbody>{distribution.map((row) => <tr key={row.type}><th scope="row">{row.type}</th><td>{formatNumber(row.count)}</td></tr>)}</tbody>
              </table>
            </div>

            <div className="chart-block">
              <h3 className="chart-title">Failure rate by type</h3>
              <p className="chart-description">Share labeled failure · %</p>
              <div className="chart-frame" style={{ height: 190, minWidth: 0 }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <BarChart data={failureRates} margin={{ top: 25, right: 12, bottom: 0, left: 0 }} accessibilityLayer>
                    <CartesianGrid stroke="#eaf0f3" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="type" axisLine={false} tickLine={false} tick={axisStyle} tickMargin={10} />
                    <YAxis axisLine={false} tickLine={false} tick={axisStyle} tickFormatter={(value) => `${formatDecimal(value, 0)}%`} width={46} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      cursor={{ fill: '#f0f6f5' }}
                      labelFormatter={(label) => `Quality variant ${label}`}
                      formatter={(value) => [`${formatDecimal(value, 2)}%`, 'Failure rate']}
                    />
                    <Bar dataKey="failure_rate_percent" name="Failure rate" fill="#71b8ad" radius={[5, 5, 0, 0]} maxBarSize={38} isAnimationActive={false}>
                      <LabelList dataKey="failure_rate_percent" position="top" formatter={(value) => `${formatDecimal(value, 2)}%`} fill="#435967" fontSize={11} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <table className="sr-only">
                <caption>Actual labeled failures by product-quality variant</caption>
                <thead><tr><th scope="col">Type</th><th scope="col">Labeled failures</th><th scope="col">Failure rate</th></tr></thead>
                <tbody>{failureRates.map((row) => <tr key={row.type}><th scope="row">{row.type}</th><td>{formatNumber(row.failure_count)}</td><td>{formatPercent(row.failure_rate)}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
          <p className="chart-footnote">Type describes product quality. Rows are observations, not unique machines.</p>
        </>
      )}
    </section>
  )
}
