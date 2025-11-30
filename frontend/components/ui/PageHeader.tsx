/**
 * PageHeader Component - ContaFlow Enterprise Design System
 *
 * Consistent page header with title, subtitle, and optional actions
 */

'use client';

import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
  animate?: boolean;
}

export function PageHeader({
  title,
  subtitle,
  actions,
  className,
  animate = true,
}: PageHeaderProps) {
  const content = (
    <div className={cn('flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between', className)}>
      <div>
        <h1 className="text-3xl font-bold text-[#11446e]">{title}</h1>
        {subtitle && (
          <p className="text-gray-600 mt-2">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex gap-3">
          {actions}
        </div>
      )}
    </div>
  );

  if (!animate) {
    return content;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {content}
    </motion.div>
  );
}
