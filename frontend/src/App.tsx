import { useCallback, useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { TooltipProvider } from '@/components/ui/tooltip'
import { api, ApiError } from '@/api/client'
import type { Accuracy, ForecastRun, HistoricalPoint, Product, Remote } from '@/api/types'
import { AccuracyPanel } from '@/components/AccuracyPanel'
import { Controls } from '@/components/Controls'
import { ForecastChart } from '@/components/ForecastChart'
import { InventoryPanel } from '@/components/InventoryPanel'

const MAX_HORIZON = 90

const toRemote = <T,>(err: unknown): Remote<T> => {
  const message = err instanceof Error ? err.message : 'Unexpected error'
  return err instanceof ApiError && err.status === 404 ? { status: 'missing', message } : { status: 'error', message }
}

export default function App() {
  const [products, setProducts] = useState<Product[]>([])
  const [productId, setProductId] = useState<number | null>(null)
  const [historicalDays, setHistoricalDays] = useState(90)
  const [forecastDays, setForecastDays] = useState(30)
  const [history, setHistory] = useState<HistoricalPoint[]>([])
  const [run, setRun] = useState<Remote<ForecastRun>>({ status: 'idle' })
  const [accuracy, setAccuracy] = useState<Remote<Accuracy>>({ status: 'idle' })
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .products()
      .then((list) => {
        setProducts(list)
        if (list.length > 0) setProductId(list[0].product_id)
      })
      .catch((err: Error) => setError(`Failed to fetch products: ${err.message}`))
  }, [])

  // Selecting a product reads what is already stored; nothing is trained.
  useEffect(() => {
    if (productId === null) return
    let cancelled = false
    setRun({ status: 'loading' })
    setAccuracy({ status: 'loading' })
    api
      .forecast(productId, MAX_HORIZON)
      .then((data) => !cancelled && setRun({ status: 'ready', data }))
      .catch((err) => !cancelled && setRun(toRemote(err)))
    api
      .accuracy(productId)
      .then((data) => !cancelled && setAccuracy({ status: 'ready', data }))
      .catch((err) => !cancelled && setAccuracy(toRemote(err)))
    return () => {
      cancelled = true
    }
  }, [productId])

  useEffect(() => {
    if (productId === null) return
    let cancelled = false
    api
      .historical(productId, historicalDays)
      .then((data) => !cancelled && setHistory(data))
      .catch((err: Error) => !cancelled && setError(`Failed to fetch historical data: ${err.message}`))
    return () => {
      cancelled = true
    }
  }, [productId, historicalDays])

  const generate = useCallback(async () => {
    if (productId === null) return
    setGenerating(true)
    setError('')
    try {
      const data = await api.generateForecast(productId, MAX_HORIZON)
      setRun({ status: 'ready', data })
    } catch (err) {
      setError(`Failed to generate forecast: ${err instanceof Error ? err.message : 'unexpected error'}`)
    } finally {
      setGenerating(false)
    }
  }, [productId])

  const runId = run.status === 'ready' ? run.data.run_id : null
  const product = products.find((p) => p.product_id === productId)

  return (
    <TooltipProvider>
      <div className="bg-muted/40 min-h-screen">
        <header className="bg-primary text-primary-foreground">
          <div className="mx-auto max-w-6xl px-4 py-8">
            <h1 className="text-3xl font-semibold">Retail Inventory Forecaster</h1>
            <p className="mt-1 opacity-90">
              Demand forecasts with prediction intervals, honest accuracy against baselines, and reorder recommendations.
            </p>
          </div>
        </header>

        <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6">
          {error && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>Something went wrong</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <section className="bg-card rounded-xl border p-4">
            <Controls
              products={products}
              productId={productId}
              historicalDays={historicalDays}
              forecastDays={forecastDays}
              generating={generating}
              onProductChange={setProductId}
              onHistoricalDaysChange={setHistoricalDays}
              onForecastDaysChange={setForecastDays}
              onGenerate={generate}
            />
            {product && (
              <p className="text-muted-foreground mt-3 text-sm">
                {product.product_name} · {product.category ?? 'uncategorised'}. A product is a product family summed across
                all stores; quantities refer to stock at one distribution centre.
              </p>
            )}
          </section>

          <ForecastChart history={history} run={run} horizon={forecastDays} generating={generating} onRegenerate={generate} />

          <div className="grid gap-6 lg:grid-cols-2">
            <AccuracyPanel state={accuracy} horizon={forecastDays} />
            <InventoryPanel productId={productId} runId={runId} />
          </div>
        </main>
      </div>
    </TooltipProvider>
  )
}
