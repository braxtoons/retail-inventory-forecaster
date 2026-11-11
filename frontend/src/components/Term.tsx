import type { ReactNode } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

// Definitions come from CONTEXT.md so UI copy matches the domain glossary.
export const GLOSSARY: Record<string, string> = {
  WAPE: 'Weighted absolute percentage error: total absolute error divided by total actual sales. Lower is better, and it stays defined on days with zero sales.',
  MAE: 'Mean absolute error: the average miss per day, in units.',
  RMSE: 'Root mean squared error: like MAE but punishes large misses more, in units.',
  MAPE: 'Mean absolute percentage error. Days with zero sales are excluded (their count is shown in brackets).',
  Coverage: 'Share of actual days that fell inside the forecast 95% interval. About 95% means the interval is well calibrated.',
  Skill: 'Skill vs. seasonal-naive = 1 − WAPE(Prophet) ÷ WAPE(seasonal-naive). Positive means Prophet beats simply repeating last week.',
  'Service level': 'Cycle service level: the target probability of not running out of stock during one lead time. Not the same as fill rate.',
  'Reorder point': 'The service-level quantile of lead-time demand. Place an order when stock falls to this level.',
  'Safety stock': 'Reorder point minus mean lead-time demand: the buffer held against forecast uncertainty.',
  'Lead time': 'Days between placing a replenishment order and receiving it.',
  'On-hand': 'Quantity currently in stock at the distribution centre.',
  'Stock-out probability': 'Share of simulated demand paths whose cumulative demand over the lead time exceeds on-hand.',
}

export function Term({ name, children }: { name: keyof typeof GLOSSARY | string; children?: ReactNode }) {
  const text = GLOSSARY[name]
  if (!text) return <>{children ?? name}</>
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="cursor-help underline decoration-dotted underline-offset-4" />}>
        {children ?? name}
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{text}</TooltipContent>
    </Tooltip>
  )
}
