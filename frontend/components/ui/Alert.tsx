/**
 * Alert Component
 *
 * Alert/notification component for messages
 */

import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils/cn';
import { AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react';

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'success' | 'error' | 'warning' | 'info';
  title?: string;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'info', title, children, ...props }, ref) => {
    const variants = {
      success: {
        container: 'bg-success-50 border-success-200 text-success-800',
        icon: CheckCircle,
        iconColor: 'text-success-600',
      },
      error: {
        container: 'bg-error-50 border-error-200 text-error-800',
        icon: XCircle,
        iconColor: 'text-error-600',
      },
      warning: {
        container: 'bg-warning-50 border-warning-200 text-warning-800',
        icon: AlertCircle,
        iconColor: 'text-warning-600',
      },
      info: {
        container: 'bg-info-50 border-info-200 text-info-800',
        icon: Info,
        iconColor: 'text-info-600',
      },
    };

    const config = variants[variant];
    const Icon = config.icon;

    return (
      <div
        ref={ref}
        className={cn(
          'flex items-start gap-3 p-4 rounded-lg border',
          config.container,
          className
        )}
        {...props}
      >
        <Icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', config.iconColor)} />
        <div className="flex-1">
          {title && <p className="font-semibold mb-1">{title}</p>}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    );
  }
);

Alert.displayName = 'Alert';
