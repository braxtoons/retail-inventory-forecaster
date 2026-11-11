import { Area, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from 'recharts'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import type { ForecastRun, HistoricalPoint, Remote } from '@/api/types'
import { configLabel, fmtDate } from '@/lib/format'

const chartConfig = {
  actual: { label: 'Actual sales', color: 'var(--chart-2)' },
  forecast: { label: 'Forecast', color: 'var(--chart-1)' },
  band: { label: '95% interval', color: 'var(--chart-1)' },
  seasonalNaive: { label: 'Seasonal-naive (last week repeated)', color: 'var(--muted-foreground)' },
} satisfies ChartConfig

interface Point {
  date: string
  actual?: number
  forecast?: number
  band?: [number, number]
  seasonalNaive?: number
}

export function buildChartData(history: HistoricalPoint[], run: ForecastRun | null, horizon: number): Point[] {
  const points: Point[] = history.map((d) => ({ date: d.sale_date, actual: d.quantity_sold }))
  if (run) {
    for (const d of run.forecast.slice(0, horizon)) {
      points.push({
        date: d.forecast_date,
        forecast: d.predicted_quantity,
        band: [d.lower_bound, d.upper_bound],
        seasonalNaive: d.seasonal_naive ?? undefined,
      })
    }
  }
  return points
}

interface ForecastChartProps {
  history: HistoricalPoint[]
  run: Remote<ForecastRun>
  horizon: number
  generating: boolean
  onRegenerate: () => void
}

export function ForecastChart({ history, run, horizon, generating, onRegenerate }: ForecastChartProps) {
  const data = run.status === 'ready' ? run.data : null
  const points = buildChartData(history, data, horizon)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sales forecast</CardTitle>
        <CardDescription>
          {data ? (
            <span className="flex flex-wrap items-center gap-2">
              <span>
                As of <strong data-testid="as-of-date">{fmtDate(data.as_of_date)}</strong> (last day of history)
              </span>
              <Badge variant="outline" data-testid="config-source">
                {data.config_source === 'selected' ? 'Selected configuration' : 'Default configuration'}:{' '}
                {configLabel(data.config)}
              </Badge>
            </span>
          ) : (
            'Product demand across all stores, with a 95% prediction interval.'
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {run.status === 'error' && (
          <Alert variant="destructive">
            <AlertTitle>Could not load the forecast</AlertTitle>
            <AlertDescription>{run.message}</AlertDescription>
          </Alert>
        )}

        {data?.stale && (
          <Alert data-testid="stale-banner">
            <AlertTitle>This forecast is out of date</AlertTitle>
            <AlertDescription className="flex flex-wrap items-center gap-3">
              <span>{data.stale_reason ?? 'The configuration or data changed since it was generated.'}</span>
              <Button size="sm" onClick={onRegenerate} disabled={generating}>
                {generating ? 'Regenerating…' : 'Regenerate'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {run.status === 'loading' && <Skeleton className="h-[360px] w-full" data-testid="chart-skeleton" />}

        {run.status === 'missing' && (
          <Alert data-testid="no-forecast">
            <AlertTitle>No forecast yet</AlertTitle>
            <AlertDescription>{'Select a product and click "Generate forecast" to see predictions.'}</AlertDescription>
          </Alert>
        )}

        {points.length > 0 && run.status !== 'loading' && (
          <ChartContainer config={chartConfig} className="h-[360px] w-full">
            <ComposedChart data={points} margin={{ left: 8, right: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={48} tickLine={false} />
              <YAxis width={56} tickLine={false} axisLine={false} />
              <ChartTooltip content={<ChartTooltipContent labelFormatter={(v) => fmtDate(String(v))} />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Area dataKey="band" stroke="none" fill="var(--color-band)" fillOpacity={0.2} isAnimationActive={false} />
              <Line
                dataKey="seasonalNaive"
                stroke="var(--color-seasonalNaive)"
                strokeOpacity={0.6}
                strokeWidth={1}
                dot={false}
                isAnimationActive={false}
              />
              <Line dataKey="actual" stroke="var(--color-actual)" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line
                dataKey="forecast"
                stroke="var(--color-forecast)"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ChartContainer>
        )}

        {data && (
          <p className="text-muted-foreground text-xs" data-testid="promo-note">
            {data.promo_known_through
              ? `Planned promotions are known through ${fmtDate(data.promo_known_through)}. After that date the forecast assumes no promotions and is likely to under-predict on promotion days.`
              : 'No planned promotions are on record, so the forecast assumes none and is likely to under-predict on promotion days.'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
