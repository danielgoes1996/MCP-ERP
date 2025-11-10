/**
 * Root Layout - Next.js 14
 *
 * Layout principal que envuelve toda la aplicación.
 * Incluye providers de React Query y configuración global.
 */

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'ContaFlow - Gestión Financiera Inteligente',
  description: 'Sistema de gestión financiera con IA integrada',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={inter.className}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
