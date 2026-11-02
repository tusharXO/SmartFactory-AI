import { useEffect, useState } from 'react'
import { getObservations } from '../api.js'
import { formatDecimal, formatNumber } from '../format.js'

const PAGE_SIZE = 10
const INITIAL_QUERY = { type: '', failure: '', offset: 0 }

export default function ObservationsTable({ refreshKey = 0 }) {
  const [query, setQuery] = useState(INITIAL_QUERY)
  const [retry, setRetry] = useState(0)
  const [resource, setResource] = useState({ key: '', data: null, loading: true, error: null })
  const { type, failure, offset } = query
  const requestKey = `${type}|${failure}|${offset}|${refreshKey}|${retry}`

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    setResource({ key: requestKey, data: null, loading: true, error: null })

    getObservations({ limit: PAGE_SIZE, offset, type, failure, signal: controller.signal })
      .then((data) => {
        if (!cancelled) {
          setResource({ key: requestKey, data, loading: false, error: null })
        }
      })
      .catch((error) => {
        if (!cancelled && !controller.signal.aborted) {
          setResource({
            key: requestKey,
            data: null,
            loading: false,
            error: error.message || 'The observation records could not be loaded.',
          })
        }
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [type, failure, offset, requestKey])

  // Never show a previous query's rows while React starts the next request.
  const { data, loading, error } = resource.key === requestKey
    ? resource
    : { data: null, loading: true, error: null }
  const items = data?.items ?? []
  const filtersActive = type !== '' || failure !== ''
  const retryRequest = () => setRetry((value) => value + 1)
  const clearFilters = () => setQuery({ ...INITIAL_QUERY })
  const previousDisabled = loading || offset === 0
  const nextDisabled = loading || !data || offset + items.length >= data.total
  const firstRow = items.length ? data.offset + 1 : 0
  const lastRow = items.length ? data.offset + items.length : 0

  return (
    <section className="panel" id="observations" aria-labelledby="observations-heading">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Explore the records</p>
          <h2 className="panel-title" id="observations-heading">Equipment observations</h2>
          <p className="panel-description">Operating measurements and their actual dataset labels.</p>
        </div>
        <span className="badge badge-neutral">Source labels</span>
      </div>

      <div className="table-toolbar">
        <div className="table-filters">
          <div className="field">
            <label className="field-label" htmlFor="observation-type">Quality type</label>
            <select
              className="select"
              id="observation-type"
              value={type}
              onChange={(event) => setQuery((current) => ({
                ...current, type: event.target.value, offset: 0,
              }))}
            >
              <option value="">All types</option>
              <option value="L">L</option>
              <option value="M">M</option>
              <option value="H">H</option>
            </select>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="observation-failure">Actual label</label>
            <select
              className="select"
              id="observation-failure"
              value={failure}
              onChange={(event) => setQuery((current) => ({
                ...current, failure: event.target.value, offset: 0,
              }))}
            >
              <option value="">All labels</option>
              <option value="0">Non-failure (0)</option>
              <option value="1">Failure (1)</option>
            </select>
          </div>
          {filtersActive && (
            <button className="button button-ghost" type="button" onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </div>
        <p className="panel-description">{PAGE_SIZE} observations per page</p>
      </div>

      <div className="table-scroll" tabIndex={0} aria-label="Scrollable equipment observations">
        <table className="observations-table" aria-busy={loading}>
          <caption className="sr-only">
            Synthetic equipment observations. Actual labels come from the dataset, not model predictions.
          </caption>
          <thead>
            <tr>
              <th scope="col">Observation</th>
              <th scope="col">Type</th>
              <th scope="col">Air <span>(K)</span></th>
              <th scope="col">Process <span>(K)</span></th>
              <th scope="col">Speed <span>(rpm)</span></th>
              <th scope="col">Torque <span>(Nm)</span></th>
              <th scope="col">Wear <span>(min)</span></th>
              <th scope="col">Actual label</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8}>
                  <div className="state-message" role="status">Loading observations…</div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={8}>
                  <div className="state-message" role="alert">
                    <strong>Observations unavailable</strong>
                    <p className="error-message">{error}</p>
                    <button className="button button-secondary" type="button" onClick={retryRequest}>
                      Retry observations
                    </button>
                  </div>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <div className="state-message" role="status">
                    <strong>{data.total > 0 ? 'No observations on this page' : 'No matching observations'}</strong>
                    <p>{filtersActive ? 'Try another quality type or actual label.' : 'There are no records to display on this page.'}</p>
                    {filtersActive ? (
                      <button className="button button-secondary" type="button" onClick={clearFilters}>
                        Show all observations
                      </button>
                    ) : offset > 0 ? (
                      <button className="button button-secondary" type="button" onClick={() => setQuery((current) => ({ ...current, offset: 0 }))}>
                        Back to first page
                      </button>
                    ) : (
                      <button className="button button-secondary" type="button" onClick={retryRequest}>
                        Retry observations
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : items.map((row) => (
              <tr key={row.udi}>
                <td>
                  <span className="observation-id">#{formatNumber(row.udi)}</span>
                  <span className="product-id">{row.product_id}</span>
                </td>
                <td><span className="badge badge-type" data-type={row.type}>{row.type}</span></td>
                <td>{formatDecimal(row.air_temperature_k)}</td>
                <td>{formatDecimal(row.process_temperature_k)}</td>
                <td>{formatNumber(row.rotational_speed_rpm)}</td>
                <td>{formatDecimal(row.torque_nm)}</td>
                <td>{formatNumber(row.tool_wear_min)}</td>
                <td>
                  <span className={row.machine_failure === 1 ? 'label-failure' : 'label-normal'}>
                    {row.machine_failure === 1 ? 'Failure' : 'Non-failure'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="table-scroll-hint">Scroll the table horizontally to see all measurements.</p>
      <div className="table-footer">
        <p className="panel-description" aria-live="polite">
          {loading ? 'Loading records…' : error ? 'Record count unavailable' : items.length
            ? `${formatNumber(firstRow)}–${formatNumber(lastRow)} of ${formatNumber(data.total)} matching observations`
            : `${formatNumber(data.total)} matching observations`}
        </p>
        <nav className="pagination" aria-label="Observation pages">
          <button
            className="button button-secondary"
            type="button"
            disabled={previousDisabled}
            onClick={() => setQuery((current) => ({ ...current, offset: Math.max(0, current.offset - PAGE_SIZE) }))}
          >
            Previous
          </button>
          <button
            className="button button-secondary"
            type="button"
            disabled={nextDisabled}
            onClick={() => setQuery((current) => ({ ...current, offset: current.offset + PAGE_SIZE }))}
          >
            Next
          </button>
        </nav>
      </div>
    </section>
  )
}
