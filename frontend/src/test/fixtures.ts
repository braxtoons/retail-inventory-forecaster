import type {
  Accuracy,
  AccuracyBucket,
  BucketLabel,
  ForecastRun,
  InventoryRecommendation,
  Metrics,
  Verdict,
} from '@/api/types'

const metrics = (wape: number, coverage: number | null = null): Metrics => ({
  mae: wape * 100,
  rmse: wape * 130,
  wape,
  mape: wape * 110,
  mape_excluded: 0,
  coverage,
  n: 270,
})

export const bucket = (verdict: Verdict, prophetWape = 0.1, snaiveWape = 0.2): AccuracyBucket => ({
  models: {
    prophet: metrics(prophetWape, 0.88),
    naive: metrics(snaiveWape * 1.1),
    seasonal_naive: metrics(snaiveWape),
  },
  per_fold: ['2017-01-10', '2017-03-11', '2017-05-10'].map((fold_cutoff) => ({
    fold_cutoff,
    prophet: metrics(prophetWape, 0.88),
    naive: metrics(snaiveWape * 1.1),
    seasonal_naive: metrics(snaiveWape),
  })),
  skill: 1 - prophetWape / snaiveWape,
  fold_wins: verdict === 'worse' ? 0 : 3,
  fold_losses: verdict === 'worse' ? 3 : 0,
  n_folds: 3,
  verdict,
})

export const accuracy = (verdicts: Partial<Record<BucketLabel, Verdict>> = {}): Accuracy => {
  const v = (label: BucketLabel): Verdict => verdicts[label] ?? 'beats'
  const make = (label: BucketLabel) =>
    v(label) === 'worse' ? bucket('worse', 0.3, 0.2) : v(label) === 'comparable' ? bucket('comparable', 0.2, 0.205) : bucket('beats')
  return {
    product_id: 1,
    evaluated_at: '2026-11-11T12:00:00',
    training_start: '2014-04-01',
    selected_config: { holidays: true, promo: true, oil: false },
    selected_arm: 'holidays+promo',
    data_changed: false,
    test_folds: { '1-7': make('1-7'), '8-30': make('8-30'), '31-90': make('31-90'), all: make('all') },
    ablation: {
      label: 'selection folds',
      arms: [
        { arm: 'holidays', config: { holidays: true, promo: false, oil: false }, selected: false, wape: 0.2, mae: 20, per_fold_wape: [] },
        { arm: 'holidays+promo', config: { holidays: true, promo: true, oil: false }, selected: true, wape: 0.1, mae: 10, per_fold_wape: [] },
      ],
    },
    service_level: { target: 0.95, lead_time: 7, achieved: 0.67, folds: 3, hits: 2, per_fold: [] },
  }
}

export const forecastRun = (overrides: Partial<ForecastRun> = {}): ForecastRun => ({
  product_id: 1,
  run_id: 7,
  created_at: '2026-11-11T12:00:00',
  as_of_date: '2017-08-15',
  config: { holidays: true, promo: false, oil: false },
  config_source: 'default',
  promo_known_through: '2017-08-31',
  stale: false,
  stale_reason: null,
  forecast_days: 3,
  forecast: [0, 1, 2].map((i) => ({
    forecast_date: `2017-08-${16 + i}`,
    predicted_quantity: 100 + i,
    lower_bound: 80,
    upper_bound: 120,
    seasonal_naive: 95,
  })),
  ...overrides,
})

export const inventory = (overrides: Partial<InventoryRecommendation> = {}): InventoryRecommendation => ({
  product_id: 1,
  run_id: 7,
  as_of_date: '2017-08-15',
  stale: false,
  stale_reason: null,
  lead_time: 7,
  service_level: 0.95,
  mean_lead_time_demand: 700,
  reorder_point: 820,
  safety_stock: 120,
  assumptions: ['Inventory position equals on-hand stock: stock already on order is not counted.'],
  verdict_1_7: 'beats',
  ...overrides,
})
