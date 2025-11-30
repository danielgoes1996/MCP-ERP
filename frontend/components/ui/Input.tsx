/**
 * Input Component - ContaFlow Enterprise Design System
 *
 * Reusable input component matching login/register design
 */

import { InputHTMLAttributes, forwardRef, ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  icon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      label,
      error,
      helperText,
      icon,
      type = 'text',
      ...props
    },
    ref
  ) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-semibold text-gray-900 mb-2">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
              {icon}
            </span>
          )}
          <input
            type={type}
            className={cn(
              'w-full bg-white border rounded-xl text-sm text-gray-900 placeholder-gray-400 transition-all',
              'focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10',
              icon ? 'pl-12 pr-4 py-3' : 'px-4 py-3',
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500/10'
                : 'border-gray-300',
              className
            )}
            ref={ref}
            {...props}
          />
        </div>
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}
        {helperText && !error && (
          <p className="mt-2 text-sm text-gray-500">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
