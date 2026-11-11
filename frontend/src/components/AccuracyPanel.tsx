import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Accuracy, AccuracyBucket, BucketLabel, ModelName, Remote } from '@/api/types'
import { configLabel, fmtDate, fmtNumber, fmtPercent } from '@/lib/format'
import { Term } from './Term'
import { VerdictBadge } from './badges'

const BUCKET_TITLES: Record<BucketLabel, string> = {
  '1-7': 'Days 1–7',
  '8-30': 'Days 8–30',
  '31-90': 'Days 31–90',
  all: 'Overall (1–90)',
}

const MODEL_TITLES: Record<ModelName, string> = {
  prophet: 'Prophet (selected configuration)',
  naive: 'Naive (last value)',
  seasonal_naive: 'Seasonal-naive (last week)',
}

const foldChartConfig = {
  prophet: { label: 'Prophet', color: 'var(--chart-1)' },
  seasonal_naive: { label: 'Seasonal-naive', color: 'var(--chart-3)' },
} satisfies ChartConfig

/** Buckets shown for a requested horizon: every bucket that starts within it, plus the overall view. */
export function coveredBuckets(horizon: number): BucketLabel[] {
  const out: BucketLabel[] = ['1-7']
  if (horizon >= 8) out.push('8-30')
  if (horizon >= 31) out.push('31-90')
  out.push('all')
  return out
}

function ModelTable({ bucket }: { bucket: AccuracyBucket }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead className="text-right"><Term name="WAPE" /></TableHead>
          <TableHead className="text-right"><Term name="MAE" /></TableHead>
          <TableHead className="text-right"><Term name="RMSE" /></TableHead>
          <TableHead className="text-right"><Term name="MAPE" /></TableHead>
          <TableHead className="text-right"><Term name="Coverage" /></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {(Object.keys(MODEL_TITLES) as ModelName[]).map((model) => {
          const m = bucket.models[model]
          if (!m) return null
          return (
            <TableRow key={model} data-testid={`row-${model}`}>
              <TableCell className="font-medium">{MODEL_TITLES[model]}</TableCell>
              <TableCell className="text-right">{fmtPercent(m.wape)}</TableCell>
              <TableCell className="text-right">{fmtNumber(m.mae, 1)}</TableCell>
              <TableCell className="text-right">{fmtNumber(m.rmse, 1)}</TableCell>
              <TableCell className="text-right">
                {m.mape === null ? 'n/a' : `${fmtNumber(m.mape, 1)}%`}
                {m.mape_excluded ? <span className="text-muted-foreground"> ({m.mape_excluded} excl.)</span> : null}
              </TableCell>
              <TableCell className="text-right">{m.coverage === null ? '–' : fmtPercent(m.coverage, 0)}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function BucketView({ label, bucket }: { label: BucketLabel; bucket: AccuracyBucket }) {
  const folds = bucket.per_fold.map((f) => ({
    fold: fmtDate(f.fold_cutoff),
    prophet: f.prophet?.wape ?? null,
    seasonal_naive: f.seasonal_naive?.wape ?? null,
  }))
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <VerdictBadge verdict={bucket.verdict} />
        <span data-testid={`skill-${label}`}>
          <Term name="Skill">Skill</Term> vs. seasonal-naive:{' '}
          <strong>{bucket.skill === null ? 'n/a' : `${bucket.skill >= 0 ? '+' : ''}${(bucket.skill * 100).toFixed(1)}%`}</strong>
        </span>
        <span className="text-muted-foreground">
          Prophet won {bucket.fold_wins} of {bucket.n_folds} test folds
        </span>
      </div>

      {bucket.verdict === 'worse' && (
        <Alert variant="destructive" data-testid="worse-alert">
          <AlertTitle>Forecast is worse than repeating last week</AlertTitle>
          <AlertDescription>
            For {BUCKET_TITLES[label].toLowerCase()}, this product's Prophet forecast has higher error than simply
            repeating the last observed week. Treat it with caution, and prefer the baseline for decisions in this range.
          </AlertDescription>
        </Alert>
      )}

      <ModelTable bucket={bucket} />

      <div>
        <h4 className="mb-1 text-sm font-medium">Error by test fold (WAPE, lower is better)</h4>
        <ChartContainer config={foldChartConfig} className="h-[200px] w-full">
          <BarChart data={folds} margin={{ left: 4, right: 4 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="fold" tickLine={false} />
            <YAxis width={44} tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Bar dataKey="prophet" fill="var(--color-prophet)" radius={3} isAnimationActive={false} />
            <Bar dataKey="seasonal_naive" fill="var(--color-seasonal_naive)" radius={3} isAnimationActive={false} />
          </BarChart>
        </ChartContainer>
      </div>
    </div>
  )
}

function Ablation({ accuracy }: { accuracy: Accuracy }) {
  return (
    <div className="grid gap-2">
      <h4 className="text-sm font-medium">Regressor ablation ({accuracy.ablation.label})</h4>
      <p className="text-muted-foreground text-xs">
        Used only to choose the configuration, so these scores are optimistic for the chosen arm. The headline numbers above come from
        held-out test folds.
      </p>
      <Table data-testid="ablation-table">
        <TableHeader>
          <TableRow>
            <TableHead>Configuration</TableHead>
            <TableHead className="text-right"><Term name="WAPE" /> (selection folds)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {accuracy.ablation.arms.map((arm) => (
            <TableRow key={arm.arm}>
              <TableCell>
                {configLabel(arm.config)}{' '}
                {arm.selected && <Badge variant="secondary">selected</Badge>}
              </TableCell>
              <TableCell className="text-right">{fmtPercent(arm.wape)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function ServiceLevelNote({ accuracy }: { accuracy: Accuracy }) {
  const sl = accuracy.service_level
  if (sl.achieved === null) return null
  return (
    <p className="text-sm" data-testid="service-level">
      Achieved <Term name="Service level">service level</Term>: <strong>{fmtPercent(sl.achieved, 0)}</strong> ({sl.hits} of{' '}
      {sl.folds} test folds had {sl.lead_time}-day demand at or below the reorder point) vs. a target of{' '}
      <strong>{fmtPercent(sl.target, 0)}</strong>.{' '}
      {sl.achieved < (sl.target ?? 0) - 0.1 && (
        <span className="text-muted-foreground">
          The forecast intervals look too narrow, so reorder points may understate risk.
        </span>
      )}
    </p>
  )
}

export function AccuracyPanel({ state, horizon }: { state: Remote<Accuracy>; horizon: number }) {
  const [selected, setSelected] = useState<BucketLabel>('1-7')
  const buckets = coveredBuckets(horizon)
  const active = buckets.includes(selected) ? selected : buckets[0]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Forecast accuracy</CardTitle>
        <CardDescription>
          Rolling cross-validation on held-out test folds, compared with simple baselines. Accuracy at day 3 and day 80 are
          different numbers, so they are shown per horizon range.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {(state.status === 'loading' || state.status === 'idle') && (
          <div className="grid gap-2" data-testid="accuracy-skeleton">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        )}

        {state.status === 'missing' && (
          <Alert data-testid="not-evaluated">
            <AlertTitle>Not evaluated yet</AlertTitle>
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}

        {state.status === 'error' && (
          <Alert variant="destructive" data-testid="accuracy-error">
            <AlertTitle>Could not load accuracy</AlertTitle>
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}

        {state.status === 'ready' && (
          <>
            <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
              <span>Evaluated {fmtDate(state.data.evaluated_at)}</span>
              <span>·</span>
              <span>Selected configuration: {configLabel(state.data.selected_config)}</span>
              {state.data.data_changed && (
                <Badge variant="destructive">data changed since evaluation, re-run the evaluation</Badge>
              )}
            </div>

            <Tabs value={active} onValueChange={(v) => setSelected(v as BucketLabel)}>
              <TabsList>
                {buckets.map((label) => (
                  <TabsTrigger key={label} value={label}>
                    {BUCKET_TITLES[label]}
                  </TabsTrigger>
                ))}
              </TabsList>
              {buckets.map((label) => (
                <TabsContent key={label} value={label} className="pt-3">
                  <BucketView label={label} bucket={state.data.test_folds[label]} />
                </TabsContent>
              ))}
            </Tabs>

            <p className="text-muted-foreground text-xs">
              How to read this: a lower <Term name="WAPE" /> is better. A verdict of &quot;beats&quot; needs at least 5% lower error
              than repeating last week <em>and</em> a win in at least two of the three test folds; otherwise the result is
              &quot;comparable&quot; or &quot;worse&quot;.
            </p>

            <ServiceLevelNote accuracy={state.data} />
            <Ablation accuracy={state.data} />
          </>
        )}
      </CardContent>
    </Card>
  )
}
