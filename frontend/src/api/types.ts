// Hand-written response types. They must track the backend specs (see openspec change
// `improve-forecasting-evaluation-and-inventory`) and CONTEXT.md vocabulary.

export interface Product {
  product_id: number
  product_name: string
  category: string | null
  unit_price: number | null
}

export interface HistoricalPoint {
  sale_date: string
  quantity_sold: number
  total_amount: number | null
}

export interface ModelConfig {
  holidays: boolean
  promo: boolean
  oil: boolean
}

export interface ForecastDay {
  forecast_date: string
  predicted_quantity: number
  lower_bound: number
  upper_bound: number
  /** Seasonal-naive reference (last observed week repeated). */
  seasonal_naive: number | null
}

export interface ForecastRun {
  product_id: number
  run_id: number
  created_at: string
  /** Last date of history; forecasts start the day after. */
  as_of_date: string
  config: ModelConfig
  config_source: 'selected' | 'default'
  /** Last date with planned-promotion data; later dates assume no promotions. */
  promo_known_through: string | null
  stale: boolean
  stale_reason: string | null
  forecast_days: number
  forecast: ForecastDay[]
}

export type BucketLabel = '1-7' | '8-30' | '31-90' | 'all'
export type Verdict = 'beats' | 'comparable' | 'worse'
export type ModelName = 'prophet' | 'naive' | 'seasonal_naive'

export interface Metrics {
  mae: number | null
  rmse: number | null
  wape: number | null
  /** Percent; zero-actual days are excluded (see mape_excluded). */
  mape: number | null
  mape_excluded: number | null
  /** Share of actuals inside the 95% interval (Prophet only). */
  coverage: number | null
  n: number | null
}

export interface FoldMetrics {
  fold_cutoff: string
  prophet: Metrics | null
  naive: Metrics | null
  seasonal_naive: Metrics | null
}

export interface AccuracyBucket {
  models: Partial<Record<ModelName, Metrics>>
  per_fold: FoldMetrics[]
  /** 1 - WAPE_prophet / WAPE_seasonal_naive */
  skill: number | null
  fold_wins: number
  fold_losses: number
  n_folds: number
  verdict: Verdict
}

export interface AblationArm {
  arm: string
  config: ModelConfig
  selected: boolean
  wape: number | null
  mae: number | null
  per_fold_wape: Array<number | null>
}

export interface ServiceLevel {
  target: number | null
  lead_time: number | null
  achieved: number | null
  folds: number
  hits: number
  per_fold: Array<{ fold_cutoff: string; hit: boolean }>
}

export interface Accuracy {
  product_id: number
  evaluated_at: string
  training_start: string | null
  selected_config: ModelConfig
  selected_arm: string
  data_changed: boolean
  test_folds: Record<BucketLabel, AccuracyBucket>
  ablation: { label: string; arms: AblationArm[] }
  service_level: ServiceLevel
}

export type RiskLevel = 'ok' | 'elevated' | 'high'

export interface InventoryRecommendation {
  product_id: number
  run_id: number
  as_of_date: string
  stale: boolean
  stale_reason: string | null
  lead_time: number
  service_level: number
  mean_lead_time_demand: number
  reorder_point: number
  safety_stock: number
  assumptions: string[]
  /** Verdict of the 1-7 day bucket vs. seasonal-naive; null when the product is not evaluated. */
  verdict_1_7: Verdict | null
  // present only when on_hand was supplied
  on_hand?: number
  stock_out_probability?: number
  risk_level?: RiskLevel
  reorder_now?: boolean
  projected_stock_out_date?: string | null
  earliest_likely_stock_out_date?: string | null
  beyond_horizon?: boolean
}

/** Loading state shared by the data panels. */
export type Remote<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'missing'; message: string }
  | { status: 'error'; message: string }
