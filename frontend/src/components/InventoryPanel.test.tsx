import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { inventory } from '@/test/fixtures'
import { InventoryPanel } from './InventoryPanel'

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

const renderPanel = (productId: number | null = 1, runId: number | null = 7) =>
  render(
    <TooltipProvider>
      <InventoryPanel productId={productId} runId={runId} debounceMs={0} />
    </TooltipProvider>,
  )

afterEach(() => vi.unstubAllGlobals())

describe('InventoryPanel', () => {
  it('shows reorder point, safety stock and assumptions for a loaded recommendation', async () => {
    const fetchMock = vi.fn(() => json(inventory()))
    vi.stubGlobal('fetch', fetchMock)
    renderPanel()
    expect(await screen.findByTestId('reorder-point')).toHaveTextContent('820')
    expect(screen.getByTestId('safety-stock')).toHaveTextContent('120')
    expect(screen.getByTestId('assumptions')).toHaveTextContent('stock already on order is not counted')
    expect(screen.queryByTestId('risk-section')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/inventory/1?lead_time=7&service_level=0.95', undefined)
    expect(screen.queryByTestId('baseline-warning')).not.toBeInTheDocument()
  })

  it('requests risk once on-hand is entered and shows risk level, reorder-now and stock-out dates', async () => {
    const fetchMock = vi.fn((url: string) =>
      json(
        url.includes('on_hand=300')
          ? inventory({
              on_hand: 300,
              stock_out_probability: 0.99,
              risk_level: 'high',
              reorder_now: true,
              projected_stock_out_date: '2017-08-18',
              earliest_likely_stock_out_date: '2017-08-17',
              beyond_horizon: false,
            })
          : inventory(),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderPanel()
    await screen.findByTestId('reorder-point')
    await userEvent.type(screen.getByLabelText(/On-hand/), '300')
    expect(await screen.findByTestId('risk-section')).toHaveTextContent('Risk: high')
    expect(screen.getByTestId('reorder-now')).toHaveTextContent('Reorder now')
    expect(screen.getByTestId('projected-date')).toHaveTextContent('2017-08-18')
    expect(screen.getByTestId('earliest-date')).toHaveTextContent('2017-08-17')
  })

  it('shows "beyond horizon" when stock outlasts the forecast', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        json(inventory({ on_hand: 1e9, stock_out_probability: 0, risk_level: 'ok', reorder_now: false, projected_stock_out_date: null, earliest_likely_stock_out_date: null, beyond_horizon: true })),
      ),
    )
    renderPanel()
    expect(await screen.findByTestId('projected-date')).toHaveTextContent('Beyond the 90-day horizon')
  })

  it('warns when the 1-7 day verdict is worse but still shows the recommendation', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json(inventory({ verdict_1_7: 'worse' }))))
    renderPanel()
    expect(await screen.findByTestId('baseline-warning')).toHaveTextContent('worse than simply repeating last week')
    expect(screen.getByTestId('reorder-point')).toHaveTextContent('820')
  })

  it('flags a recommendation based on a stale forecast', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json(inventory({ stale: true, stale_reason: 'data changed since this forecast was generated' }))))
    renderPanel()
    expect(await screen.findByTestId('inventory-stale')).toHaveTextContent('data changed')
  })

  it('shows the generate-first state without a forecast run, without calling the API', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderPanel(1, null)
    expect(screen.getByTestId('generate-first')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows generate-first when the API answers 404', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ error: 'No forecast has been generated yet. Generate a forecast first.' }, 404)))
    renderPanel()
    expect(await screen.findByTestId('generate-first')).toHaveTextContent('Generate a forecast first')
  })

  it('shows an error state when the API fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ error: 'Internal server error' }, 500)))
    renderPanel()
    expect(await screen.findByTestId('inventory-error')).toHaveTextContent('Internal server error')
  })

  it('reports a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('failed'))))
    renderPanel()
    expect(await screen.findByTestId('inventory-error')).toHaveTextContent('Could not reach the server')
  })
})
