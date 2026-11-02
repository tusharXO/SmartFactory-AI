import { useEffect, useRef, useState } from 'react'
import { predict } from '../api.js'

const EXAMPLE_INPUT = {
  type: 'M',
  air_temperature_k: '300.0',
  process_temperature_k: '310.0',
  rotational_speed_rpm: '1500',
  torque_nm: '40.0',
  tool_wear_min: '100',
}

const NUMERIC_FIELDS = [
  { name: 'air_temperature_k', label: 'Air temperature', unit: 'K', positive: true },
  { name: 'process_temperature_k', label: 'Process temperature', unit: 'K', positive: true },
  { name: 'rotational_speed_rpm', label: 'Rotational speed', unit: 'rpm', positive: true, integer: true },
  { name: 'torque_nm', label: 'Torque', unit: 'Nm' },
  { name: 'tool_wear_min', label: 'Tool wear', unit: 'min', integer: true },
]

function validate(values) {
  const errors = {}
  const payload = { type: values.type }
  if (!['L', 'M', 'H'].includes(values.type)) {
    errors.type = 'Choose L, M, or H.'
  }
  for (const field of NUMERIC_FIELDS) {
    const value = Number(values[field.name])
    if (values[field.name].trim() === '' || !Number.isFinite(value)) {
      errors[field.name] = 'Enter a finite number.'
    } else if (field.integer && !Number.isSafeInteger(value)) {
      errors[field.name] = 'Enter a whole number within the supported range.'
    } else if (field.positive ? value <= 0 : value < 0) {
      errors[field.name] = field.positive
        ? 'Enter a value greater than zero.'
        : 'Enter zero or a positive value.'
    }
    payload[field.name] = value
  }
  return { errors, payload }
}

export default function PredictionForm({ modelReady = null }) {
  const [values, setValues] = useState({ ...EXAMPLE_INPUT })
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const activeRequest = useRef(null)

  useEffect(() => () => activeRequest.current?.abort(), [])

  function updateValue(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => ({ ...current, [name]: '' }))
    setError('')
    setResult(null)
  }

  function resetExample() {
    setValues({ ...EXAMPLE_INPUT })
    setFieldErrors({})
    setError('')
    setResult(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (activeRequest.current || submitting || modelReady === false) return

    const { errors, payload } = validate(values)
    setFieldErrors(errors)
    setResult(null)
    setError('')
    if (Object.keys(errors).length) {
      setError('Check the highlighted measurements.')
      event.currentTarget.elements.namedItem(Object.keys(errors)[0])?.focus()
      return
    }

    const controller = new AbortController()
    activeRequest.current = controller
    setSubmitting(true)
    try {
      const response = await predict(payload, { signal: controller.signal })
      if (!controller.signal.aborted) setResult(response)
    } catch (requestError) {
      if (controller.signal.aborted) return
      const serverErrors = {}
      for (const detail of requestError.details ?? []) {
        const name = detail.loc?.at(-1)
        if (Object.hasOwn(EXAMPLE_INPUT, name)) serverErrors[name] = detail.msg
      }
      setFieldErrors(serverErrors)
      setError(
        Object.keys(serverErrors).length
          ? 'Check the highlighted measurements.'
          : requestError.message || 'The prediction could not be completed. Please try again.',
      )
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
      if (!controller.signal.aborted) setSubmitting(false)
    }
  }

  return (
    <section className="panel prediction-panel" id="prediction" aria-labelledby="prediction-title">
      <header className="panel-header">
        <div>
          <p className="eyebrow">MODEL INFERENCE</p>
          <h2 className="panel-title" id="prediction-title">Failure classifier</h2>
          <p className="panel-description">Classify a set of operating measurements.</p>
        </div>
        <span className="badge badge-neutral">6 inputs</span>
      </header>

      <form onSubmit={handleSubmit} noValidate aria-busy={submitting}>
        <div className="prediction-example">
          <span className="field-hint">Example inputs, ready to edit</span>
          <button className="button button-ghost" type="button" onClick={resetExample} disabled={submitting}>
            Reset example
          </button>
        </div>

        <fieldset className="prediction-fields" disabled={submitting}>
          <legend className="sr-only">Six equipment measurements</legend>
          <div className="form-grid">
            <div className="field">
              <label className="field-label" htmlFor="prediction-type">Quality variant</label>
              <select
                className="select"
                id="prediction-type"
                name="type"
                value={values.type}
                onChange={updateValue}
                required
                aria-invalid={Boolean(fieldErrors.type)}
                aria-describedby={fieldErrors.type ? 'prediction-type-error' : undefined}
              >
                <option value="L">L · Low</option>
                <option value="M">M · Medium</option>
                <option value="H">H · High</option>
              </select>
              {fieldErrors.type && <p className="field-error" id="prediction-type-error">{fieldErrors.type}</p>}
            </div>

            {NUMERIC_FIELDS.map((field) => {
              const id = `prediction-${field.name}`
              return (
                <div className="field" key={field.name}>
                  <label className="field-label" htmlFor={id}>
                    {field.label} <span className="field-hint">({field.unit})</span>
                  </label>
                  <input
                    className="input"
                    id={id}
                    name={field.name}
                    type="number"
                    inputMode={field.integer ? 'numeric' : 'decimal'}
                    value={values[field.name]}
                    onChange={updateValue}
                    step={field.integer ? 1 : 'any'}
                    min={field.integer && field.positive ? 1 : 0}
                    max={field.integer ? Number.MAX_SAFE_INTEGER : undefined}
                    required
                    aria-invalid={Boolean(fieldErrors[field.name])}
                    aria-describedby={fieldErrors[field.name] ? `${id}-error` : undefined}
                  />
                  {fieldErrors[field.name] && <p className="field-error" id={`${id}-error`}>{fieldErrors[field.name]}</p>}
                </div>
              )
            })}
          </div>
        </fieldset>

        {modelReady === false && (
          <p className="state-message" role="status">Predictions are unavailable until the model is ready.</p>
        )}
        {error && <p className="error-message" role="alert">{error}</p>}

        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={submitting || modelReady === false}>
            <svg className="button-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="m9 5 10 7-10 7V5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
            {submitting ? 'Running prediction…' : 'Run prediction'}
          </button>
        </div>
      </form>

      {result ? (
        <div className="prediction-result" data-failure={result.predicted_failure === 1} role="status" aria-live="polite" aria-atomic="true">
          <p className="result-label">Predicted class</p>
          <p className="result-value">{result.predicted_failure === 1 ? 'Failure (1)' : 'Non-failure (0)'}</p>
          <p className="result-score">Model score (class 1): <strong>{result.model_score.toFixed(4)}</strong></p>
          <p className="field-hint">{result.model_name} · score range 0–1</p>
        </div>
      ) : (
        <div className="prediction-empty">
          <p className="state-message">Run a prediction to see the model output.</p>
        </div>
      )}
      <p className="model-footnote">
        Synthetic snapshot classification. Scores are uncalibrated and do not estimate time until failure.
      </p>
    </section>
  )
}
