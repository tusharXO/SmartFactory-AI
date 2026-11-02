import { expect, test } from '@playwright/test'

const API_URL = 'http://127.0.0.1:8000/api'
const EXAMPLE_INPUT = {
  type: 'M',
  air_temperature_k: 300.0,
  process_temperature_k: 310.0,
  rotational_speed_rpm: 1500,
  torque_nm: 40.0,
  tool_wear_min: 100,
}
const number = (value) => new Intl.NumberFormat('en-US').format(value)
const percent = (value) => `${(value * 100).toFixed(2)}%`

async function getApi(request, path, params) {
  const response = await request.get(`${API_URL}/${path}`, { params })
  expect(response.ok(), `GET ${path} should reach the real backend`).toBeTruthy()
  return response.json()
}

async function getPrediction(request) {
  const response = await request.post(`${API_URL}/predict`, { data: EXAMPLE_INPUT })
  expect(response.ok(), 'The example prediction should use the real saved model').toBeTruthy()
  return response.json()
}

function metricCard(page, label) {
  return page.locator('.metric-card').filter({ has: page.getByText(label, { exact: true }) })
}

function observationIds(page) {
  return page.locator('#observations tbody .observation-id')
}

async function expectPageRows(page, data) {
  await expect(observationIds(page)).toHaveText(data.items.map((row) => `#${number(row.udi)}`))
  await expect(page.locator('#observations .table-footer')).toContainText(`of ${number(data.total)} matching observations`)
}

test('shows API-backed KPI cards, two charts, and held-out model metrics', async ({ page, request }, testInfo) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  const [overview, charts, report] = await Promise.all([
    getApi(request, 'overview'),
    getApi(request, 'charts'),
    getApi(request, 'model-metrics'),
  ])
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Predictive Maintenance Analytics')
  await expect(metricCard(page, 'Total observations').locator('.metric-value')).toHaveText(number(overview.total_observations))
  await expect(metricCard(page, 'Labeled failures').locator('.metric-value')).toHaveText(number(overview.failure_count))
  await expect(metricCard(page, 'Failure rate').locator('.metric-value')).toHaveText(percent(overview.failure_rate))
  await expect(metricCard(page, 'Quality variants').locator('.metric-value')).toHaveText(number(overview.type_count))
  await expect(page.locator('#analytics svg.recharts-surface')).toHaveCount(2)
  for (const row of charts.type_distribution) {
    const chartRow = page.locator('#analytics .chart-block').first().locator('tbody tr')
      .filter({ has: page.getByRole('rowheader', { name: row.type, exact: true }) })
    await expect(chartRow).toContainText(number(row.count))
  }
  for (const [label, value] of [
    ['Precision', percent(report.metrics.precision)],
    ['Recall', percent(report.metrics.recall)],
    ['F1 score', percent(report.metrics.f1)],
    ['Average precision', report.metrics.average_precision.toFixed(4)],
  ]) {
    const statistic = page.locator('.evaluation-stat').filter({ has: page.getByText(label, { exact: true }) })
    await expect(statistic.locator('.evaluation-value')).toHaveText(value)
  }
  await expect(page.locator('.connection-status')).toHaveText('API connected')
  await expect(page.locator('#observations tbody .observation-id')).toHaveCount(10)
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png'), fullPage: true })
  expect(errors).toEqual([])
})

test('runs a real prediction, clears stale output on edit, and rejects invalid RPM', async ({ page, request }) => {
  const expected = await getPrediction(request)
  let submittedRequests = 0
  page.on('request', (outgoing) => {
    if (outgoing.method() === 'POST' && outgoing.url() === `${API_URL}/predict`) submittedRequests += 1
  })
  await page.goto('/')
  const run = page.getByRole('button', { name: 'Run prediction', exact: true })
  await expect(run).toBeEnabled()
  await run.click()

  const result = page.locator('.prediction-result')
  await expect(result.locator('.result-value')).toHaveText(expected.predicted_failure ? 'Failure (1)' : 'Non-failure (0)')
  await expect(result.locator('.result-score strong')).toHaveText(expected.model_score.toFixed(4))
  await expect(result).toContainText(expected.model_name)
  expect(submittedRequests).toBe(1)

  await page.getByLabel('Torque', { exact: false }).fill('41')
  await expect(result).toHaveCount(0)
  await page.getByLabel('Rotational speed', { exact: false }).fill('-1')
  await run.click()
  await expect(page.locator('#prediction-rotational_speed_rpm-error')).toHaveText('Enter a value greater than zero.')
  await expect(result).toHaveCount(0)
  expect(submittedRequests).toBe(1)
})

test('filters and pages actual SQL records and resets pagination when filters change', async ({ page, request }) => {
  const firstPage = await getApi(request, 'observations', { limit: 10, offset: 0, type: 'M', failure: 0 })
  const secondPage = await getApi(request, 'observations', { limit: 10, offset: 10, type: 'M', failure: 0 })
  const highQualityPage = await getApi(request, 'observations', { limit: 10, offset: 0, type: 'H', failure: 0 })
  const allRowsPage = await getApi(request, 'observations', { limit: 10, offset: 0 })
  await page.goto('/')
  const section = page.locator('#observations')
  await page.getByLabel('Quality type', { exact: true }).selectOption('M')
  await page.getByLabel('Actual label', { exact: true }).selectOption('0')
  await expectPageRows(page, firstPage)
  await expect(section.locator('tbody .label-normal')).toHaveCount(firstPage.items.length)
  await expect(section.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled()

  await section.getByRole('button', { name: 'Next', exact: true }).click()
  await expectPageRows(page, secondPage)
  await expect(section.locator('.table-footer')).toContainText('11–20')
  await page.getByLabel('Quality type', { exact: true }).selectOption('H')
  await expectPageRows(page, highQualityPage)
  await expect(section.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled()
  await section.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await expectPageRows(page, allRowsPage)
  await expect(page.getByLabel('Quality type', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('Actual label', { exact: true })).toHaveValue('')
})

test('disables prediction when model health is unavailable while retaining real analytics', async ({ page, request }) => {
  const overview = await getApi(request, 'overview')
  // Simulate only a readiness failure; analytics still use the running backend.
  await page.route('**/api/health', async (route) => {
    const response = await route.fetch()
    const health = await response.json()
    await route.fulfill({ response, json: { ...health, model_ready: false, status: 'degraded' } })
  })
  await page.goto('/')

  await expect(page.getByRole('button', { name: 'Run prediction', exact: true })).toBeDisabled()
  await expect(page.getByText('Predictions are unavailable until the model is ready.', { exact: true })).toBeVisible()
  await expect(page.locator('.connection-status')).toHaveText('API needs attention')
  await expect(metricCard(page, 'Total observations').locator('.metric-value')).toHaveText(number(overview.total_observations))
  await expect(page.locator('#analytics svg.recharts-surface')).toHaveCount(2)
})

test('recovers from a controlled observations error through Retry', async ({ page, request }) => {
  const actualPage = await getApi(request, 'observations', { limit: 10, offset: 0 })
  let unavailable = true
  // Only this endpoint's failure state is simulated, including StrictMode retries.
  await page.route('**/api/observations?*', async (route) => {
    if (unavailable) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Controlled test: observations are temporarily unavailable.' }),
      })
    } else {
      await route.continue()
    }
  })
  await page.goto('/')
  const section = page.locator('#observations')
  await expect(section.getByText('Observations unavailable', { exact: true })).toBeVisible()
  await expect(section.getByRole('button', { name: 'Retry observations', exact: true })).toBeVisible()
  await expect(observationIds(page)).toHaveCount(0)

  unavailable = false
  await section.getByRole('button', { name: 'Retry observations', exact: true }).click()
  await expectPageRows(page, actualPage)
  await expect(section.getByText('Observations unavailable', { exact: true })).toHaveCount(0)
})

test('shows a controlled empty filter state and returns to real records when cleared', async ({ page, request }) => {
  const actualPage = await getApi(request, 'observations', { limit: 10, offset: 0 })
  // The empty response is deliberately synthetic and used only to test this UI state.
  await page.route('**/api/observations?*', async (route) => {
    const params = new URL(route.request().url()).searchParams
    if (params.get('type') === 'H' && params.get('failure') === '1') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, limit: 10, offset: 0 }),
      })
    } else {
      await route.continue()
    }
  })
  await page.goto('/')
  await page.getByLabel('Quality type', { exact: true }).selectOption('H')
  await page.getByLabel('Actual label', { exact: true }).selectOption('1')
  const section = page.locator('#observations')
  await expect(section.getByText('No matching observations', { exact: true })).toBeVisible()
  await expect(section.locator('.table-footer')).toContainText('0 matching observations')
  await section.getByRole('button', { name: 'Show all observations', exact: true }).click()
  await expectPageRows(page, actualPage)
  await expect(section.getByText('No matching observations', { exact: true })).toHaveCount(0)
})

test('works on a narrow viewport with contained table scrolling and real predictions', async ({ page, request }, testInfo) => {
  const overview = await getApi(request, 'overview')
  const prediction = await getPrediction(request)
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(metricCard(page, 'Total observations').locator('.metric-value')).toHaveText(number(overview.total_observations))
  await expect(page.getByRole('navigation', { name: 'Dashboard navigation' })).toBeVisible()
  await expect(page.locator('#analytics svg.recharts-surface')).toHaveCount(2)
  await expect(observationIds(page)).toHaveCount(10)
  const dimensions = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    pageWidth: document.documentElement.scrollWidth,
    tableViewport: document.querySelector('.table-scroll').clientWidth,
    tableWidth: document.querySelector('.table-scroll').scrollWidth,
  }))
  expect(dimensions.pageWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1)
  expect(dimensions.tableWidth).toBeGreaterThan(dimensions.tableViewport)

  await page.getByRole('link', { name: 'Prediction', exact: true }).click()
  await expect(page).toHaveURL(/#prediction$/)
  await page.getByRole('button', { name: 'Run prediction', exact: true }).click()
  await expect(page.locator('.prediction-result .result-score strong')).toHaveText(prediction.model_score.toFixed(4))
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect(page.getByRole('heading', { level: 1 })).toBeInViewport()
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 320, height: 740 })
  const narrowWidth = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(narrowWidth.document).toBeLessThanOrEqual(narrowWidth.viewport + 1)
  await expect(page.getByRole('table', { name: 'Observation counts by product-quality variant' })).toHaveCount(1)
  await expect(page.getByRole('table', { name: 'Actual labeled failures by product-quality variant' })).toHaveCount(1)
  expect(errors).toEqual([])
})

test('keeps section navigation in sync with direct links and browser history', async ({ page }) => {
  const nav = page.getByRole('navigation', { name: 'Dashboard navigation' })
  const model = nav.getByRole('link', { name: 'Model evaluation', exact: true })
  const prediction = nav.getByRole('link', { name: 'Prediction', exact: true })
  const observations = nav.getByRole('link', { name: 'Observations', exact: true })
  await page.goto('/#model')
  await expect(model).toHaveAttribute('aria-current', 'location')
  await prediction.click()
  await expect(page).toHaveURL(/#prediction$/)
  await expect(prediction).toHaveAttribute('aria-current', 'location')
  await observations.click()
  await expect(observations).toHaveAttribute('aria-current', 'location')

  await page.goBack()
  await expect(page).toHaveURL(/#prediction$/)
  await expect(prediction).toHaveAttribute('aria-current', 'location')
  await expect(observations).not.toHaveAttribute('aria-current')
  await page.goBack()
  await expect(model).toHaveAttribute('aria-current', 'location')
  await page.goForward()
  await expect(prediction).toHaveAttribute('aria-current', 'location')
})

test('shows unavailable data honestly and reconnects to the real API through Refresh data', async ({ page, request }) => {
  const overview = await getApi(request, 'overview')
  let offline = true
  // Simulate transport failure only; recovery goes to the real local backend.
  await page.route('**/api/**', async (route) => {
    if (offline) await route.abort('connectionrefused')
    else await route.continue()
  })
  await page.goto('/')
  await expect(page.locator('.connection-status')).toHaveText('API unavailable')
  await expect(page.getByRole('alert').filter({ hasText: 'Backend connection unavailable' })).toBeVisible()
  await expect(metricCard(page, 'Total observations').locator('.metric-value')).toHaveText('—')
  await expect(observationIds(page)).toHaveCount(0)

  offline = false
  await page.getByRole('button', { name: 'Refresh data', exact: true }).click()
  await expect(page.locator('.connection-status')).toHaveText('API connected')
  await expect(metricCard(page, 'Total observations').locator('.metric-value')).toHaveText(number(overview.total_observations))
  await expect(page.locator('#analytics svg.recharts-surface')).toHaveCount(2)
  await expect(observationIds(page)).toHaveCount(10)
  await expect(page.getByRole('alert')).toHaveCount(0)
})
