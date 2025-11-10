/**
 * Logo Component
 *
 * Logo de ContaFlow reutilizable
 */

import Image from 'next/image';
import { cn } from '@/lib/utils/cn';

interface LogoProps {
  variant?: 'full' | 'isotipo';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizes = {
  sm: { width: 120, height: 40 },
  md: { width: 160, height: 53 },
  lg: { width: 200, height: 66 },
};

const isotipoSizes = {
  sm: { width: 32, height: 32 },
  md: { width: 48, height: 48 },
  lg: { width: 64, height: 64 },
};

export function Logo({ variant = 'full', size = 'md', className }: LogoProps) {
  const dimensions = variant === 'full' ? sizes[size] : isotipoSizes[size];
  const src = variant === 'full' ? '/ContaFlow.png' : '/IsotipoContaFlow.png';

  return (
    <Image
      src={src}
      alt="ContaFlow"
      width={dimensions.width}
      height={dimensions.height}
      className={cn('object-contain', className)}
      priority
    />
  );
}
