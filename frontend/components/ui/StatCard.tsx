/**
 * StatCard Component - ContaFlow Enterprise Design System
 *
 * Reusable statistics card with icon, value, label, and trend indicator
 */

'use client';

import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { Card } from './Card';

export interface StatCardProps {
  name: string;
  value: string | number;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon: LucideIcon;
  iconColor?: string;
  iconBgColor?: string;
  variant?: 'default' | 'gradient-green' | 'gradient-primary' | 'gradient-warning' | 'gradient-danger';
  className?: string;
  delay?: number;
}

export function StatCard({
  name,
  value,
  change,
  trend = 'neutral',
  icon: Icon,
  iconColor = 'text-[#11446e]',
  iconBgColor = 'bg-[#11446e]/5',
  variant = 'default',
  className,
  delay = 0,
}: StatCardProps) {
  const trendColors = {
    up: 'text-[#60b97b]',
    down: 'text-red-500',
    neutral: 'text-gray-500',
  };

  const trendIcons = {
    up: '↑',
    down: '↓',
    neutral: '→',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <Card variant={variant} className={cn('group cursor-default', className)}>
        <div className="flex items-center justify-between">
          <div className={cn('p-3 rounded-xl transition-transform group-hover:scale-110', iconBgColor)}>
            <Icon className={cn('w-6 h-6', iconColor)} />
          </div>
          {change && (
            <div className="flex items-center space-x-1">
              <span className={cn('text-lg font-medium', trendColors[trend])}>
                {trendIcons[trend]}
              </span>
              <span className={cn('text-sm font-medium', trendColors[trend])}>
                {change}
              </span>
            </div>
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-gray-900">
            {value}
          </p>
          <p className="text-sm text-gray-600 mt-1">{name}</p>
        </div>
      </Card>
    </motion.div>
  );
}
