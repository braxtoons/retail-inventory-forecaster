import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { accuracy } from '@/test/fixtures'
import { AccuracyPanel, coveredBuckets } from './AccuracyPanel'

const renderPanel = (ui: React.ReactElement) => render(<TooltipProvider>{ui}</TooltipProvider>)

describe('AccuracyPanel', () => {
  it('shows model vs. baselines, verdict, ablation labelled as selection folds, and achieved service level', () => {
    renderPanel(<AccuracyPanel state={{ status: 'ready', data: accuracy() }} horizon={90} />)
    expect(screen.getByTestId('row-prophet')).toBeInTheDocument()
    expect(screen.getByTestId('row-naive')).toBeInTheDocument()
    expect(screen.getByTestId('row-seasonal_naive')).toBeInTheDocument()
    expect(screen.getAllByText('Beats baseline').length).toBeGreaterThan(0)
    expect(screen.getByTestId('skill-1-7')).toHaveTextContent('+50.0%')
    expect(screen.getByText(/Regressor ablation \(selection folds\)/)).toBeInTheDocument()
    const sl = screen.getByTestId('service-level')
    expect(sl).toHaveTextContent('67%')
    expect(sl).toHaveTextContent('95%')
    expect(sl).toHaveTextContent('2 of 3 test folds')
  })

  it('shows only the buckets covered by the requested horizon', () => {
    expect(coveredBuckets(7)).toEqual(['1-7', 'all'])
    expect(coveredBuckets(30)).toEqual(['1-7', '8-30', 'all'])
    expect(coveredBuckets(90)).toEqual(['1-7', '8-30', '31-90', 'all'])
    renderPanel(<AccuracyPanel state={{ status: 'ready', data: accuracy() }} horizon={7} />)
    expect(screen.queryByRole('tab', { name: 'Days 31–90' })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Days 1–7' })).toBeInTheDocument()
  })

  it('shows the not-evaluated empty state with the command to run', () => {
    renderPanel(
      <AccuracyPanel
        state={{ status: 'missing', message: 'This product has not been evaluated yet. Run `python -m evaluate --product 3`.' }}
        horizon={30}
      />,
    )
    const alert = screen.getByTestId('not-evaluated')
    expect(within(alert).getByText('Not evaluated yet')).toBeInTheDocument()
    expect(alert).toHaveTextContent('python -m evaluate --product 3')
    expect(screen.queryByTestId('row-prophet')).not.toBeInTheDocument()
  })

  it('shows an error state', () => {
    renderPanel(<AccuracyPanel state={{ status: 'error', message: 'Internal server error' }} horizon={30} />)
    expect(screen.getByTestId('accuracy-error')).toHaveTextContent('Internal server error')
  })

  it('shows a skeleton while loading', () => {
    renderPanel(<AccuracyPanel state={{ status: 'loading' }} horizon={30} />)
    expect(screen.getByTestId('accuracy-skeleton')).toBeInTheDocument()
  })

  it('explains a "worse" verdict in plain language', () => {
    renderPanel(<AccuracyPanel state={{ status: 'ready', data: accuracy({ '1-7': 'worse' }) }} horizon={30} />)
    const alert = screen.getByTestId('worse-alert')
    expect(alert).toHaveTextContent('worse than repeating last week')
    expect(screen.getAllByText('Worse than baseline').length).toBeGreaterThan(0)
  })

  it('switches buckets', async () => {
    renderPanel(<AccuracyPanel state={{ status: 'ready', data: accuracy({ '8-30': 'comparable' }) }} horizon={90} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Days 8–30' }))
    expect(await screen.findByText('Comparable to baseline')).toBeInTheDocument()
  })

  it('flags evaluation results older than the data', () => {
    renderPanel(<AccuracyPanel state={{ status: 'ready', data: { ...accuracy(), data_changed: true } }} horizon={30} />)
    expect(screen.getByText(/data changed since evaluation/)).toBeInTheDocument()
  })
})
