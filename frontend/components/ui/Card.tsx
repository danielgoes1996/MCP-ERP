/**
 * Card Component - ContaFlow Enterprise Design System
 *
 * Reusable card container component with gradient variants
 */

import { HTMLAttributes, ReactNode, forwardRef } from 'react';
import { cn } from '@/lib/utils/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  noPadding?: boolean;
  action?: ReactNode;
  variant?: 'default' | 'gradient-green' | 'gradient-primary' | 'gradient-warning' | 'gradient-danger';
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      title,
      subtitle,
      noPadding = false,
      action,
      variant = 'default',
      children,
      ...props
    },
    ref
  ) => {
    const variants = {
      default: 'bg-white border border-gray-200',
      'gradient-green': 'bg-gradient-to-br from-[#60b97b]/10 to-white border-2 border-[#60b97b]/20',
      'gradient-primary': 'bg-gradient-to-br from-[#11446e]/10 to-white border-2 border-[#11446e]/20',
      'gradient-warning': 'bg-gradient-to-br from-yellow-50 to-white border-2 border-yellow-200',
      'gradient-danger': 'bg-gradient-to-br from-red-50 to-white border-2 border-red-200',
    };

    return (
      <div
        ref={ref}
        className={cn(
          'rounded-xl shadow-sm transition-shadow hover:shadow-md',
          variants[variant],
          !noPadding && 'p-6',
          className
        )}
        {...props}
      >
        {(title || subtitle || action) && (
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              {title && (
                <h3 className="text-lg font-bold text-gray-900">{title}</h3>
              )}
              {subtitle && (
                <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
              )}
            </div>
            {action && <div className="flex-shrink-0">{action}</div>}
          </div>
        )}
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';
