import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { api, ApiError } from '@/api/client'
import type { InventoryRecommendation, Remote } from '@/api/types'
import { fmtDate, fmtNumber, fmtPercent } from '@/lib/format'
import { Term } from './Term'
import { RiskBadge } from './badges'

interface InventoryPanelProps {
  productId: number | null
  /** Changes whenever a new forecast run is stored, which triggers a refetch. */
  runId: number | null
  debounceMs?: number
}

export function InventoryPanel({ productId, runId, debounceMs = 250 }: InventoryPanelProps) {
  const [leadTime, setLeadTime] = useState(7)
  const [serviceLevel, setServiceLevel] = useState(0.95)
  const [onHand, setOnHand] = useState('')
  const [state, setState] = useState<Remote<InventoryRecommendation>>({ status: 'idle' })

  useEffect(() => {
    if (productId === null || runId === null) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setState((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }))
      try {
        const onHandValue = onHand.trim() === '' ? undefined : Number(onHand)
        const data = await api.inventory(productId, { leadTime, serviceLevel, onHand: onHandValue })
        if (!cancelled) setState({ status: 'ready', data })
      } catch (err) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Unexpected error'
        setState(err instanceof ApiError && err.status === 404 ? { status: 'missing', message } : { status: 'error', message })
      }
    }, debounceMs)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [productId, runId, leadTime, serviceLevel, onHand, debounceMs])

  const noForecast = productId === null || runId === null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Inventory recommendation</CardTitle>
        <CardDescription>
          Stock held at the distribution centre, from simulated demand paths of the latest forecast.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="lead-time"><Term name="Lead time" /> (days)</Label>
            <Input
              id="lead-time"
              type="number"
              min={1}
              max={90}
              value={leadTime}
              onChange={(e) => setLeadTime(Math.min(90, Math.max(1, Math.round(Number(e.target.value)) || 1)))}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="service-level"><Term name="Service level" />: {fmtPercent(serviceLevel, 0)}</Label>
            <Slider
              id="service-level"
              aria-label="Service level"
              min={0.8}
              max={0.99}
              step={0.01}
              value={[serviceLevel]}
              onValueChange={(v) => setServiceLevel(Array.isArray(v) ? v[0] : v)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="on-hand"><Term name="On-hand" /> (units)</Label>
            <Input
              id="on-hand"
              type="number"
              min={0}
              placeholder="e.g. 5000"
              value={onHand}
              onChange={(e) => setOnHand(e.target.value)}
            />
          </div>
        </div>

        {noForecast && (
          <Alert data-testid="generate-first">
            <AlertTitle>Generate a forecast first</AlertTitle>
            <AlertDescription>Recommendations are computed from a stored forecast run for the selected product.</AlertDescription>
          </Alert>
        )}

        {!noForecast && (state.status === 'loading' || state.status === 'idle') && (
          <div className="grid gap-2" data-testid="inventory-skeleton">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {!noForecast && state.status === 'missing' && (
          <Alert data-testid="generate-first">
            <AlertTitle>Generate a forecast first</AlertTitle>
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}

        {!noForecast && state.status === 'error' && (
          <Alert variant="destructive" data-testid="inventory-error">
            <AlertTitle>Could not compute the recommendation</AlertTitle>
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}

        {!noForecast && state.status === 'ready' && <Recommendation rec={state.data} />}
      </CardContent>
    </Card>
  )
}

function Recommendation({ rec }: { rec: InventoryRecommendation }) {
  return (
    <div className="grid gap-4">
      {rec.verdict_1_7 === 'worse' && (
        <Alert variant="destructive" data-testid="baseline-warning">
          <AlertTitle>Low confidence in this reorder point</AlertTitle>
          <AlertDescription>
            Over the next 7 days this product&apos;s forecast was worse than simply repeating last week in cross-validation.
            The recommendation is still shown, but verify it before ordering.
          </AlertDescription>
        </Alert>
      )}
      {rec.stale && (
        <Alert data-testid="inventory-stale">
          <AlertTitle>Based on an out-of-date forecast</AlertTitle>
          <AlertDescription>{rec.stale_reason}. Regenerate the forecast to refresh this recommendation.</AlertDescription>
        </Alert>
      )}

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label={<Term name="Reorder point" />} value={fmtNumber(rec.reorder_point)} testId="reorder-point" />
        <Stat label={<Term name="Safety stock" />} value={fmtNumber(rec.safety_stock)} testId="safety-stock" />
        <Stat label="Mean lead-time demand" value={fmtNumber(rec.mean_lead_time_demand)} />
      </dl>

      {rec.risk_level === undefined ? (
        <p className="text-muted-foreground text-sm">Enter your on-hand stock to see stock-out risk and dates.</p>
      ) : (
        <div className="grid gap-3" data-testid="risk-section">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge risk={rec.risk_level} />
            <Badge variant={rec.reorder_now ? 'destructive' : 'secondary'} data-testid="reorder-now">
              {rec.reorder_now ? 'Reorder now' : 'No reorder needed yet'}
            </Badge>
            <span className="text-sm">
              <Term name="Stock-out probability" />: <strong>{fmtPercent(rec.stock_out_probability, 1)}</strong> within{' '}
              {rec.lead_time} days
            </span>
          </div>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Projected stock-out date (median demand)</dt>
              <dd data-testid="projected-date">
                {rec.beyond_horizon ? 'Beyond the 90-day horizon' : rec.projected_stock_out_date ? fmtDate(rec.projected_stock_out_date) : 'Beyond the 90-day horizon'}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Earliest likely stock-out (high-demand case)</dt>
              <dd data-testid="earliest-date">
                {rec.earliest_likely_stock_out_date ? fmtDate(rec.earliest_likely_stock_out_date) : 'Beyond the 90-day horizon'}
              </dd>
            </div>
          </dl>
        </div>
      )}

      <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-xs" data-testid="assumptions">
        {rec.assumptions.map((a) => (
          <li key={a}>{a}</li>
        ))}
        <li>On-hand is interpreted as stock at the forecast as-of date ({fmtDate(rec.as_of_date)}).</li>
      </ul>
    </div>
  )
}

function Stat({ label, value, testId }: { label: React.ReactNode; value: string; testId?: string }) {
  return (
    <div>
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="text-2xl font-semibold" data-testid={testId}>
        {value}
      </dd>
    </div>
  )
}
