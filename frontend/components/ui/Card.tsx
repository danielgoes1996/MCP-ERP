/**
 * Card Component
 *
 * Reusable card container component
 */

import { HTMLAttributes, ReactNode, forwardRef } from 'react';
import { cn } from '@/lib/utils/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  noPadding?: boolean;
  action?: ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    { className, title, subtitle, noPadding = false, action, children, ...props },
    ref
  ) => {
    return (
      <div
        ref={ref}
        className={cn(
          'bg-white rounded-xl border border-gray-200 shadow-sm',
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
