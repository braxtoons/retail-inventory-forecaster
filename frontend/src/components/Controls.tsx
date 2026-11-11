import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import type { Product } from '@/api/types'

interface ControlsProps {
  products: Product[]
  productId: number | null
  historicalDays: number
  forecastDays: number
  generating: boolean
  onProductChange: (id: number) => void
  onHistoricalDaysChange: (days: number) => void
  onForecastDaysChange: (days: number) => void
  onGenerate: () => void
}

export function Controls(props: ControlsProps) {
  const { products, productId, historicalDays, forecastDays, generating } = props
  const items = products.map((p) => ({ value: String(p.product_id), label: p.product_name }))
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)_minmax(0,1.2fr)_auto] md:items-end">
      <div className="grid gap-1.5">
        <Label htmlFor="product-select">Product</Label>
        <Select
          items={items}
          value={productId === null ? null : String(productId)}
          onValueChange={(value) => value && props.onProductChange(Number(value))}
        >
          <SelectTrigger id="product-select" className="w-full" aria-label="Product">
            <SelectValue placeholder="Select a product..." />
          </SelectTrigger>
          <SelectContent>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="historical-days">Historical days</Label>
        <Input
          id="historical-days"
          type="number"
          min={30}
          max={730}
          value={historicalDays}
          onChange={(e) => props.onHistoricalDaysChange(Math.min(730, Math.max(30, Number(e.target.value) || 30)))}
        />
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="forecast-days">Forecast horizon: {forecastDays} days</Label>
        <Slider
          id="forecast-days"
          aria-label="Forecast horizon in days"
          min={1}
          max={90}
          step={1}
          value={[forecastDays]}
          onValueChange={(v) => props.onForecastDaysChange(Array.isArray(v) ? v[0] : v)}
        />
      </div>

      <Button onClick={props.onGenerate} disabled={productId === null || generating}>
        {generating ? 'Generating…' : 'Generate forecast'}
      </Button>
    </div>
  )
}
