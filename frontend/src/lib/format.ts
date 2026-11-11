export const fmtNumber = (value: number | null | undefined, digits = 0): string =>
  value === null || value === undefined || Number.isNaN(value)
    ? 'n/a'
    : value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtPercent = (value: number | null | undefined, digits = 1): string =>
  value === null || value === undefined || Number.isNaN(value) ? 'n/a' : `${(value * 100).toFixed(digits)}%`

export const fmtDate = (iso: string | null | undefined): string => (iso ? iso.split('T')[0] : 'n/a')

export const configLabel = (config: { holidays: boolean; promo: boolean; oil: boolean }): string => {
  const parts = [config.holidays && 'holidays', config.promo && 'promotions', config.oil && 'oil price'].filter(Boolean)
  return parts.length ? parts.join(' + ') : 'no regressors'
}
