/**
 * Button Component - ContaFlow Enterprise Design System
 *
 * Reusable button component with variants and animations
 */

'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  fullWidth?: boolean;
  disableAnimation?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      fullWidth = false,
      disableAnimation = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center rounded-xl font-semibold transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

    const variants = {
      primary:
        'bg-gradient-to-r from-[#11446e] to-[#0d3454] text-white hover:shadow-md shadow-sm focus:ring-[#11446e]',
      secondary:
        'bg-[#60b97b] text-white hover:shadow-md shadow-sm hover:shadow-[#60b97b]/20 focus:ring-[#60b97b]',
      outline:
        'border-2 border-[#11446e] text-[#11446e] hover:bg-[#11446e]/5 focus:ring-[#11446e]',
      ghost:
        'text-[#11446e] hover:bg-[#11446e]/5 focus:ring-[#11446e]',
      danger:
        'bg-red-500 text-white hover:bg-red-600 hover:shadow-md shadow-sm focus:ring-red-500',
    };

    const sizes = {
      sm: 'px-3 py-2 text-sm',
      md: 'px-4 py-3.5 text-base',
      lg: 'px-6 py-3.5 text-lg',
    };

    const buttonClasses = cn(
      baseStyles,
      variants[variant],
      sizes[size],
      fullWidth && 'w-full',
      className
    );

    if (disableAnimation) {
      return (
        <button
          ref={ref}
          className={buttonClasses}
          disabled={disabled || isLoading}
          {...props}
        >
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {children}
        </button>
      );
    }

    return (
      <motion.button
        ref={ref}
        className={buttonClasses}
        disabled={disabled || isLoading}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        {...(props as any)}
      >
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </motion.button>
    );
  }
);

Button.displayName = 'Button';
