import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { forecastRun } from '@/test/fixtures'
import { buildChartData, ForecastChart } from './ForecastChart'

const history = [{ sale_date: '2017-08-14', quantity_sold: 90, total_amount: null }]

describe('ForecastChart', () => {
  it('shows the as-of date, config source and promotion caveat', () => {
    render(<ForecastChart history={history} run={{ status: 'ready', data: forecastRun() }} horizon={3} generating={false} onRegenerate={() => {}} />)
    expect(screen.getByTestId('as-of-date')).toHaveTextContent('2017-08-15')
    expect(screen.getByTestId('config-source')).toHaveTextContent('Default configuration')
    expect(screen.getByTestId('promo-note')).toHaveTextContent('known through 2017-08-31')
    expect(screen.queryByTestId('stale-banner')).not.toBeInTheDocument()
  })

  it('shows the selected configuration when the product was evaluated', () => {
    const run = forecastRun({ config_source: 'selected', config: { holidays: true, promo: true, oil: false } })
    render(<ForecastChart history={history} run={{ status: 'ready', data: run }} horizon={3} generating={false} onRegenerate={() => {}} />)
    expect(screen.getByTestId('config-source')).toHaveTextContent('Selected configuration: holidays + promotions')
  })

  it('shows a stale banner with a Regenerate button', async () => {
    const onRegenerate = vi.fn()
    const run = forecastRun({ stale: true, stale_reason: 'configuration changed since this forecast was generated' })
    render(<ForecastChart history={history} run={{ status: 'ready', data: run }} horizon={3} generating={false} onRegenerate={onRegenerate} />)
    const banner = screen.getByTestId('stale-banner')
    expect(banner).toHaveTextContent('configuration changed')
    await userEvent.click(screen.getByRole('button', { name: 'Regenerate' }))
    expect(onRegenerate).toHaveBeenCalledTimes(1)
  })

  it('shows the no-forecast state, a skeleton and an error', () => {
    const { rerender } = render(<ForecastChart history={[]} run={{ status: 'missing', message: 'none' }} horizon={30} generating={false} onRegenerate={() => {}} />)
    expect(screen.getByTestId('no-forecast')).toBeInTheDocument()
    rerender(<ForecastChart history={[]} run={{ status: 'loading' }} horizon={30} generating={false} onRegenerate={() => {}} />)
    expect(screen.getByTestId('chart-skeleton')).toBeInTheDocument()
    rerender(<ForecastChart history={[]} run={{ status: 'error', message: 'boom' }} horizon={30} generating={false} onRegenerate={() => {}} />)
    expect(screen.getByText('boom')).toBeInTheDocument()
  })

  it('trims the stored 90-day run to the requested horizon and includes the seasonal-naive series', () => {
    const points = buildChartData(history, forecastRun(), 2)
    expect(points).toHaveLength(3)                       // 1 historical + 2 forecast days
    expect(points[2].seasonalNaive).toBe(95)
    expect(points[1].band).toEqual([80, 120])
  })
})
