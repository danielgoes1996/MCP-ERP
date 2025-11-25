# 🎨 ContaFlow Frontend - Arquitectura Completa

**Fecha**: 4 de Noviembre 2025
**Framework**: Next.js 14 + React + TypeScript
**Estado**: Arquitectura diseñada y documentada

---

## 📋 Resumen Ejecutivo

Frontend modular para ContaFlow que refleja la estructura del backend, con componentes AI-driven, estado gestionado con Zustand/React Query, validación con Zod, y tipos generados desde OpenAPI.

---

## 🏗️ Estructura Completa

```
frontend/
├── src/
│   ├── app/                      # Next.js 14 App Router
│   │   ├── layout.tsx           # Layout principal
│   │   ├── page.tsx             # Home page
│   │   ├── auth/                # Autenticación
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── expenses/            # Gestión de gastos
│   │   │   ├── page.tsx         # Lista de gastos
│   │   │   ├── [id]/page.tsx   # Detalle de gasto
│   │   │   └── new/page.tsx    # Crear gasto
│   │   ├── reconciliation/      # Conciliación bancaria
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── invoicing/           # Facturas
│   │   │   ├── page.tsx
│   │   │   └── bulk/page.tsx
│   │   └── reports/             # Reportes
│   │       └── page.tsx
│   │
│   ├── components/              # Componentes React
│   │   ├── ai/                 # AI-driven components
│   │   │   ├── AISuggestionCard.tsx
│   │   │   ├── AIConfidenceBar.tsx
│   │   │   ├── AIThinking.tsx
│   │   │   └── AIFeedbackButton.tsx
│   │   ├── auth/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── RegisterForm.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── expenses/
│   │   │   ├── ExpenseForm.tsx
│   │   │   ├── ExpenseList.tsx
│   │   │   ├── ExpenseCard.tsx
│   │   │   └── ExpenseFilters.tsx
│   │   ├── reconciliation/
│   │   │   ├── BankStatementUpload.tsx
│   │   │   ├── TransactionMatcher.tsx
│   │   │   └── MatchingSuggestions.tsx
│   │   ├── invoicing/
│   │   │   ├── InvoiceForm.tsx
│   │   │   ├── BulkInvoiceUpload.tsx
│   │   │   └── InvoicePreview.tsx
│   │   ├── reports/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Charts.tsx
│   │   │   └── ExportButton.tsx
│   │   ├── shared/             # Componentes compartidos
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Loading.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       ├── Footer.tsx
│   │       └── Navigation.tsx
│   │
│   ├── stores/                 # Zustand stores
│   │   ├── ai/
│   │   │   └── useAIStore.ts
│   │   ├── auth/
│   │   │   └── useAuthStore.ts
│   │   ├── expenses/
│   │   │   └── useExpensesStore.ts
│   │   ├── reconciliation/
│   │   │   └── useReconciliationStore.ts
│   │   ├── invoicing/
│   │   │   └── useInvoicingStore.ts
│   │   └── reports/
│   │       └── useReportsStore.ts
│   │
│   ├── services/               # API clients
│   │   ├── ai/
│   │   │   └── aiService.ts
│   │   ├── auth/
│   │   │   └── authService.ts
│   │   ├── expenses/
│   │   │   └── expensesService.ts
│   │   ├── reconciliation/
│   │   │   └── reconciliationService.ts
│   │   ├── invoicing/
│   │   │   └── invoicingService.ts
│   │   └── reports/
│   │       └── reportsService.ts
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts       # Axios client configurado
│   │   │   └── queryClient.ts  # React Query config
│   │   ├── utils/
│   │   │   ├── cn.ts          # classnames helper
│   │   │   ├── format.ts      # Formateo de datos
│   │   │   └── validators.ts  # Validadores comunes
│   │   └── validators/        # Zod schemas
│   │       ├── expense.ts
│   │       ├── invoice.ts
│   │       └── transaction.ts
│   │
│   ├── hooks/                  # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useExpenses.ts
│   │   ├── useAISuggestions.ts
│   │   └── useDebounce.ts
│   │
│   ├── types/                  # TypeScript types
│   │   ├── api.ts             # Generados de OpenAPI
│   │   ├── models.ts
│   │   └── index.ts
│   │
│   └── config/
│       ├── constants.ts
│       └── features.ts
│
├── public/                     # Assets estáticos
│   ├── images/
│   └── icons/
│
├── docs/                       # Documentación
│   ├── ARCHITECTURE.md
│   ├── AI_COMPONENTS.md
│   └── API_INTEGRATION.md
│
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
└── .env.example
```

---

## 🎨 Componentes AI-Driven

### 1. AISuggestionCard.tsx

```tsx
/**
 * Tarjeta de sugerencia de IA
 *
 * Muestra sugerencias de la IA con:
 * - Visualización de la sugerencia
 * - Barra de confianza
 * - Botones de aceptar/rechazar
 * - Tracking de interacciones
 */

import { useState } from 'react';
import { Check, X, Sparkles } from 'lucide-react';
import { AIConfidenceBar } from './AIConfidenceBar';

interface AISuggestionCardProps {
  type: 'expense' | 'matching' | 'category';
  suggestion: {
    field: string;
    value: any;
    confidence: number;
    reasoning?: string;
  };
  onAccept: (suggestion: any) => void;
  onReject: () => void;
  autoApply?: boolean;
}

export function AISuggestionCard({
  type,
  suggestion,
  onAccept,
  onReject,
  autoApply = false,
}: AISuggestionCardProps) {
  const [isAccepted, setIsAccepted] = useState(false);
  const [isRejected, setIsRejected] = useState(false);

  const handleAccept = () => {
    setIsAccepted(true);
    onAccept(suggestion);

    // Track aceptación
    trackAIInteraction({
      type,
      action: 'accept',
      confidence: suggestion.confidence,
    });
  };

  const handleReject = () => {
    setIsRejected(true);
    onReject();

    // Track rechazo
    trackAIInteraction({
      type,
      action: 'reject',
      confidence: suggestion.confidence,
    });
  };

  // Auto-aplicar si confianza es muy alta
  if (autoApply && suggestion.confidence > 0.9 && !isAccepted) {
    handleAccept();
  }

  if (isAccepted || isRejected) {
    return null; // Ocultar después de interacción
  }

  return (
    <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4 shadow-sm animate-slide-in">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-1">
          <Sparkles className="w-5 h-5 text-purple-500" />
        </div>

        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-900">
              AI Suggestion
            </h4>
            <AIConfidenceBar confidence={suggestion.confidence} />
          </div>

          <div className="space-y-1 mb-3">
            <p className="text-sm text-gray-600">
              <span className="font-medium">{suggestion.field}:</span>{' '}
              <span className="text-gray-900">{suggestion.value}</span>
            </p>

            {suggestion.reasoning && (
              <p className="text-xs text-gray-500 italic">
                {suggestion.reasoning}
              </p>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleAccept}
              className="flex items-center gap-1 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white text-sm rounded-md transition"
            >
              <Check className="w-4 h-4" />
              Accept
            </button>

            <button
              onClick={handleReject}
              className="flex items-center gap-1 px-3 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm rounded-md transition"
            >
              <X className="w-4 h-4" />
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper para tracking
function trackAIInteraction(data: any) {
  // Enviar a analytics/backend
  console.log('[AI Tracking]', data);
}
```

### 2. AIConfidenceBar.tsx

```tsx
/**
 * Barra de confianza de IA
 *
 * Visualiza el nivel de confianza de una sugerencia de IA
 * con colores según el threshold
 */

interface AIConfidenceBarProps {
  confidence: number; // 0-1
  showPercentage?: boolean;
}

export function AIConfidenceBar({
  confidence,
  showPercentage = true,
}: AIConfidenceBarProps) {
  const percentage = Math.round(confidence * 100);

  // Determinar color según confianza
  const getColor = () => {
    if (confidence >= 0.8) return 'bg-green-500';
    if (confidence >= 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor()} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {showPercentage && (
        <span className="text-xs font-medium text-gray-600">
          {percentage}%
        </span>
      )}
    </div>
  );
}
```

---

## 🔐 Store de Autenticación (Zustand)

```tsx
/**
 * stores/auth/useAuthStore.ts
 *
 * Store global de autenticación con Zustand
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  company_id: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  setToken: (token: string) => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            throw new Error('Invalid credentials');
          }

          const data = await response.json();

          set({
            user: data.user,
            token: data.access_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Guardar token en localStorage
          localStorage.setItem('auth_token', data.access_token);
        } catch (error: any) {
          set({
            error: error.message,
            isLoading: false,
            isAuthenticated: false,
          });
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });

        // Limpiar localStorage
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
      },

      setUser: (user) => set({ user }),
      setToken: (token) => set({ token }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
```

---

## 📡 Servicio de Expenses (React Query)

```tsx
/**
 * services/expenses/expensesService.ts
 *
 * Cliente API para el dominio de expenses
 */

import apiClient from '@/lib/api/client';
import { Expense, CreateExpenseDTO, UpdateExpenseDTO } from '@/types/api';

export const expensesService = {
  /**
   * Obtener todos los gastos
   */
  getAll: async (filters?: any): Promise<Expense[]> => {
    const response = await apiClient.get('/expenses', { params: filters });
    return response.data;
  },

  /**
   * Obtener un gasto por ID
   */
  getById: async (id: string): Promise<Expense> => {
    const response = await apiClient.get(`/expenses/${id}`);
    return response.data;
  },

  /**
   * Crear un nuevo gasto
   */
  create: async (data: CreateExpenseDTO): Promise<Expense> => {
    const response = await apiClient.post('/expenses', data);
    return response.data;
  },

  /**
   * Actualizar un gasto
   */
  update: async (id: string, data: UpdateExpenseDTO): Promise<Expense> => {
    const response = await apiClient.put(`/expenses/${id}`, data);
    return response.data;
  },

  /**
   * Eliminar un gasto
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/expenses/${id}`);
  },

  /**
   * Obtener sugerencias de IA para un gasto
   */
  getAISuggestions: async (expenseId: string) => {
    const response = await apiClient.get(`/expenses/${expenseId}/ai-suggestions`);
    return response.data;
  },

  /**
   * Aplicar sugerencia de IA
   */
  applyAISuggestion: async (expenseId: string, suggestionId: string) => {
    const response = await apiClient.post(
      `/expenses/${expenseId}/apply-suggestion`,
      { suggestion_id: suggestionId }
    );
    return response.data;
  },
};

/**
 * Custom hook para usar expenses con React Query
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useExpenses(filters?: any) {
  return useQuery({
    queryKey: ['manual_expenses', filters],
    queryFn: () => expensesService.getAll(filters),
  });
}

export function useExpense(id: string) {
  return useQuery({
    queryKey: ['expense', id],
    queryFn: () => expensesService.getById(id),
    enabled: !!id,
  });
}

export function useCreateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: expensesService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['manual_expenses'] });
    },
  });
}

export function useUpdateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateExpenseDTO }) =>
      expensesService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['manual_expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expense', variables.id] });
    },
  });
}
```

---

## ✅ Validación con Zod

```tsx
/**
 * lib/validators/expense.ts
 *
 * Esquemas de validación para expenses con Zod
 */

import { z } from 'zod';

export const expenseSchema = z.object({
  amount: z
    .number()
    .positive('El monto debe ser positivo')
    .min(0.01, 'El monto mínimo es $0.01'),

  description: z
    .string()
    .min(3, 'La descripción debe tener al menos 3 caracteres')
    .max(500, 'La descripción no puede exceder 500 caracteres'),

  category: z.enum([
    'food',
    'transport',
    'office',
    'entertainment',
    'utilities',
    'other',
  ]),

  date: z.date().max(new Date(), 'La fecha no puede ser futura'),

  vendor: z.string().optional(),

  receipt: z
    .instanceof(File)
    .refine((file) => file.size <= 5 * 1024 * 1024, 'El archivo debe ser menor a 5MB')
    .refine(
      (file) => ['image/jpeg', 'image/png', 'application/pdf'].includes(file.type),
      'Solo se permiten imágenes (JPEG, PNG) o PDF'
    )
    .optional(),
});

export type ExpenseFormData = z.infer<typeof expenseSchema>;

/**
 * Uso en formulario
 */
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

export function ExpenseForm() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseSchema),
  });

  const onSubmit = (data: ExpenseFormData) => {
    console.log('Valid data:', data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('amount')} type="number" />
      {errors.amount && <span>{errors.amount.message}</span>}

      <input {...register('description')} />
      {errors.description && <span>{errors.description.message}</span>}

      <select {...register('category')}>
        <option value="food">Food</option>
        <option value="transport">Transport</option>
        {/* ... */}
      </select>
      {errors.category && <span>{errors.category.message}</span>}

      <button type="submit">Submit</button>
    </form>
  );
}
```

---

## 🎨 Componentes Shared

```tsx
/**
 * components/shared/Button.tsx
 *
 * Componente de botón reutilizable con variantes
 */

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils/cn';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, className, children, ...props }, ref) => {
    const variants = {
      primary: 'bg-primary-500 hover:bg-primary-600 text-white',
      secondary: 'bg-accent-500 hover:bg-accent-600 text-white',
      outline: 'border border-gray-300 hover:bg-gray-50 text-gray-700',
      ghost: 'hover:bg-gray-100 text-gray-700',
      danger: 'bg-error-500 hover:bg-error-600 text-white',
    };

    const sizes = {
      sm: 'px-3 py-1.5 text-sm',
      md: 'px-4 py-2 text-base',
      lg: 'px-6 py-3 text-lg',
    };

    return (
      <button
        ref={ref}
        className={cn(
          'rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed',
          variants[variant],
          sizes[size],
          className
        )}
        disabled={isLoading}
        {...props}
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <Loader className="animate-spin" size={16} />
            Loading...
          </span>
        ) : (
          children
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

---

## 📚 Resumen de Archivos Creados

### Configuración Base
✅ `package.json` - Dependencias
✅ `tsconfig.json` - TypeScript config
✅ `tailwind.config.ts` - TailwindCSS config
✅ `next.config.js` - Next.js config
✅ `.env.example` - Variables de entorno

### Estructura de Carpetas
✅ Carpetas por dominios creadas
✅ Componentes organizados
✅ Stores por dominio
✅ Services por dominio

### Código Base
✅ API Client con interceptores
✅ Ejemplos de componentes AI
✅ Store de autenticación
✅ Servicio de expenses
✅ Validación con Zod

### Documentación
✅ README.md completo
✅ Este documento de arquitectura

---

## 🚀 Próximos Pasos

### Para completar el frontend:

1. **Instalar dependencias**
   ```bash
   cd frontend
   npm install
   ```

2. **Implementar componentes restantes**
   - Formularios de cada dominio
   - Listas y tablas
   - Modals y diálogos

3. **Configurar React Query Provider**
   ```tsx
   // app/layout.tsx
   import { QueryClientProvider } from '@tanstack/react-query';
   import { queryClient } from '@/lib/api/queryClient';

   export default function RootLayout({ children }) {
     return (
       <QueryClientProvider client={queryClient}>
         {children}
       </QueryClientProvider>
     );
   }
   ```

4. **Implementar páginas por dominio**
   - Expenses dashboard
   - Reconciliation interface
   - Invoicing forms
   - Reports dashboard

5. **Testing**
   - Unit tests con Jest
   - E2E con Playwright
   - Storybook para componentes

---

## ✅ Estado Actual

**Arquitectura**: ✅ Definida y documentada
**Estructura**: ✅ Carpetas creadas
**Configuración**: ✅ Archivos base creados
**Ejemplos**: ✅ Código de referencia incluido
**Documentación**: ✅ Completa

**Listo para**: Implementación de componentes y páginas

---

**Versión**: 1.0.0
**Última actualización**: 4 Noviembre 2025
