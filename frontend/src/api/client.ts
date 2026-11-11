import type {
  Accuracy,
  ForecastRun,
  HistoricalPoint,
  InventoryRecommendation,
  Product,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the backend running?')
  }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // non-JSON body; fall through to the status check
  }
  if (!response.ok) {
    const message =
      body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
        ? body.error
        : `Request failed (${response.status})`
    throw new ApiError(response.status, message)
  }
  return body as T
}

const qs = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  products: () => request<Product[]>('/api/products'),

  historical: (productId: number, daysBack: number) =>
    request<HistoricalPoint[]>(`/api/historical${qs({ product_id: productId, days_back: daysBack })}`),

  /** Latest stored run (never trains). 404 when no run exists. */
  forecast: (productId: number, forecastDays = 90) =>
    request<ForecastRun>(`/api/forecast/${productId}${qs({ forecast_days: forecastDays })}`),

  generateForecast: (productId: number, forecastDays = 90) =>
    request<ForecastRun>('/api/forecast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, forecast_days: forecastDays }),
    }),

  /** Stored evaluation. 404 when the product has not been evaluated. */
  accuracy: (productId: number) => request<Accuracy>(`/api/accuracy/${productId}`),

  inventory: (
    productId: number,
    params: { leadTime: number; serviceLevel: number; onHand?: number },
  ) =>
    request<InventoryRecommendation>(
      `/api/inventory/${productId}${qs({
        lead_time: params.leadTime,
        service_level: params.serviceLevel,
        on_hand: params.onHand,
      })}`,
    ),
}
