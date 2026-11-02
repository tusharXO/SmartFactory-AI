const numberFormatter = new Intl.NumberFormat('en-US')

export function formatNumber(value) {
  return Number.isFinite(value) ? numberFormatter.format(value) : '—'
}

export function formatPercent(value, digits = 2) {
  return Number.isFinite(value) ? new Intl.NumberFormat('en-US', {
    style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(value) : '—'
}

export function formatDecimal(value, digits = 1) {
  return Number.isFinite(value) ? new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(value) : '—'
}
