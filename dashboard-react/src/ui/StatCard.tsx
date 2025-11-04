import { ReactNode } from 'react'

type Intent = 'neutral' | 'success' | 'warning' | 'danger'

type StatCardProps = {
  label: string
  value: ReactNode
  meta?: ReactNode
  delta?: { value: ReactNode; intent?: Intent }
  icon?: ReactNode
  intent?: Intent
  children?: ReactNode
}

export function StatCard({ label, value, meta, delta, icon, intent = 'neutral', children }: StatCardProps) {
  return (
    <article className="stat-card" data-intent={intent}>
      {icon ? <div className="stat-card__icon" aria-hidden="true">{icon}</div> : null}
      <div className="stat-card__body">
        <p className="stat-card__label">{label}</p>
        <p className="stat-card__value">{value}</p>
        {meta ? <p className="stat-card__meta">{meta}</p> : null}
        {children}
      </div>
      {delta ? (
        <div className="stat-card__delta" data-intent={delta.intent || 'neutral'}>
          {delta.value}
        </div>
      ) : null}
    </article>
  )
}
