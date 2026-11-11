import { Badge } from '@/components/ui/badge'
import type { RiskLevel, Verdict } from '@/api/types'
import { cn } from '@/lib/utils'

const GOOD = 'bg-emerald-600/15 text-emerald-700 dark:text-emerald-400'
const WARN = 'bg-amber-500/20 text-amber-700 dark:text-amber-400'

export function VerdictBadge({ verdict, className }: { verdict: Verdict; className?: string }) {
  const label = { beats: 'Beats baseline', comparable: 'Comparable to baseline', worse: 'Worse than baseline' }[verdict]
  const variant = verdict === 'worse' ? 'destructive' : verdict === 'comparable' ? 'secondary' : 'default'
  return (
    <Badge variant={variant} className={cn(verdict === 'beats' && GOOD, className)} data-verdict={verdict}>
      {label}
    </Badge>
  )
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  const label = { ok: 'Risk: OK', elevated: 'Risk: elevated', high: 'Risk: high' }[risk]
  const variant = risk === 'high' ? 'destructive' : 'secondary'
  return (
    <Badge variant={variant} className={risk === 'ok' ? GOOD : risk === 'elevated' ? WARN : undefined} data-risk={risk}>
      {label}
    </Badge>
  )
}
