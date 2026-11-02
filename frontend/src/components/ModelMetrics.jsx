import { formatDecimal, formatNumber, formatPercent } from '../format.js'

export default function ModelMetrics({ data, loading, error, onRetry }) {
  const metrics = data?.metrics
  const matrix = metrics?.confusion_matrix
  const hasMatrix = Array.isArray(matrix) && matrix.length === 2 && matrix.every((row) => Array.isArray(row) && row.length === 2)
  const metricItems = metrics ? [
    { label: 'Precision', value: formatPercent(metrics.precision), description: 'Failure predictions that were correct' },
    { label: 'Recall', value: formatPercent(metrics.recall), description: 'Labeled failures detected' },
    { label: 'F1 score', value: formatPercent(metrics.f1), description: 'Balance of precision and recall' },
    { label: 'Average precision', value: formatDecimal(metrics.average_precision, 4), description: 'Across score thresholds' },
  ] : []

  return (
    <section className="panel model-panel" id="model" aria-labelledby="model-title">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Measured performance</p>
          <h2 className="panel-title" id="model-title">Model evaluation</h2>
          <p className="panel-description">Failure is the positive class. Results use held-out observations.</p>
        </div>
        {data && !loading && !error && <span className="badge badge-neutral">{data.model_name.replace(/([a-z])([A-Z])/g, '$1 $2')}</span>}
      </div>

      {loading ? (
        <div className="state-message" role="status">
          <span className="skeleton evaluation-skeleton" aria-hidden="true" />
          <span className="sr-only">Loading model evaluation</span>
        </div>
      ) : error ? (
        <div className="state-message error-message" role="alert">
          <p>{typeof error === 'string' ? error : error.message || 'Model evaluation is unavailable.'}</p>
          <button className="button button-secondary" type="button" onClick={onRetry}>Retry evaluation</button>
        </div>
      ) : !metrics ? (
        <div className="state-message"><p>No evaluation report is available.</p></div>
      ) : (
        <>
          <div className="metrics-grid">
            {metricItems.map((item) => (
              <div className="evaluation-stat" key={item.label}>
                <p className="evaluation-label">{item.label}</p>
                <p className="evaluation-value">{item.value}</p>
                <p className="evaluation-description">{item.description}</p>
              </div>
            ))}
          </div>

          <div className="evaluation-layout">
            <div className="evaluation-context">
              <h3 className="chart-title">A reproducible baseline</h3>
              <p className="panel-description">
                {formatNumber(data.split.train_rows)} training observations · {formatNumber(data.split.test_rows)} test observations
              </p>
              <p className="evaluation-detail">
                Test labels: {formatNumber(data.class_counts.test['0'])} non-failures and {formatNumber(data.class_counts.test['1'])} failures.
              </p>
              {hasMatrix && (
                <p className="evaluation-detail">
                  Detected {formatNumber(matrix[1][1])} of {formatNumber(matrix[1][0] + matrix[1][1])} labeled failures,
                  with {formatNumber(matrix[0][1])} false alarms and {formatNumber(matrix[1][0])} missed failures.
                </p>
              )}
              {hasMatrix && matrix[0][1] > matrix[1][1] && (
                <p className="evaluation-caution">False alarms outnumber detected failures in this baseline.</p>
              )}
            </div>

            {hasMatrix ? (
              <table className="confusion-matrix">
                <caption>Confusion matrix · actual labels in rows</caption>
                <thead>
                  <tr><th scope="col">Actual</th><th scope="col">Predicted 0</th><th scope="col">Predicted 1</th></tr>
                </thead>
                <tbody>
                  <tr><th scope="row">Non-failure (0)</th><td className="matrix-correct">{formatNumber(matrix[0][0])}</td><td className="matrix-error">{formatNumber(matrix[0][1])}</td></tr>
                  <tr><th scope="row">Failure (1)</th><td className="matrix-error">{formatNumber(matrix[1][0])}</td><td className="matrix-correct">{formatNumber(matrix[1][1])}</td></tr>
                </tbody>
              </table>
            ) : <p className="state-message">Confusion matrix unavailable.</p>}
          </div>

          <p className="model-footnote">
            Evaluation uses synthetic observations. Model scores are uncalibrated estimates for a measurement snapshot;
            they do not forecast a breakdown date. Average precision summarizes the precision–recall curve.
          </p>
        </>
      )}
    </section>
  )
}
