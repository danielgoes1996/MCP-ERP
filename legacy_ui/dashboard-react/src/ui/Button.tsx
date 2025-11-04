import { ButtonHTMLAttributes, ReactNode } from 'react'

const baseClasses = 'btn'
const variantClasses: Record<string, string> = {
  primary: 'btn--primary',
  secondary: 'btn--secondary',
  ghost: 'btn--ghost',
  danger: 'btn--danger',
}
const sizeClasses: Record<string, string> = {
  sm: 'btn--sm',
  md: '',
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
  iconStart?: ReactNode
  iconEnd?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  iconStart,
  iconEnd,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  const classes = [
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    loading ? 'btn--loading' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button className={classes} {...rest}>
      {iconStart ? <span aria-hidden="true">{iconStart}</span> : null}
      <span>{children}</span>
      {iconEnd ? <span aria-hidden="true">{iconEnd}</span> : null}
    </button>
  )
}
