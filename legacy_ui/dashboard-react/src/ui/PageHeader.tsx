import { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  subtitle?: string
  breadcrumbs?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, breadcrumbs, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__content">
        <div className="page-header__meta">
          {breadcrumbs ? (
            <nav className="page-header__breadcrumbs" aria-label="Breadcrumb">
              {breadcrumbs}
            </nav>
          ) : null}
          <h1 className="page-header__title">{title}</h1>
          {subtitle ? <p className="page-header__subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="page-header__actions">{actions}</div> : null}
      </div>
    </header>
  )
}
