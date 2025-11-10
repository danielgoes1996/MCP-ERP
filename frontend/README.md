# ContaFlow Frontend

Frontend modular para ContaFlow construido con Next.js 14, React, TypeScript y TailwindCSS.

## 🏗️ Arquitectura

### Estructura por Dominios

El frontend refleja la estructura del backend, organizado en dominios funcionales:

```
src/
├── app/                    # Next.js 14 App Router
│   ├── auth/              # Rutas de autenticación
│   ├── expenses/          # Gestión de gastos
│   ├── reconciliation/    # Conciliación bancaria
│   ├── invoicing/         # Facturas
│   ├── reports/           # Reportes
│   └── layout.tsx         # Layout principal
│
├── components/            # Componentes React
│   ├── ai/               # Componentes AI-driven
│   ├── auth/             # Login, register
│   ├── expenses/         # Gestión de gastos
│   ├── reconciliation/   # Conciliación
│   ├── invoicing/        # Facturas
│   ├── reports/          # Reportes
│   ├── shared/           # Componentes compartidos
│   └── layout/           # Layout components
│
├── stores/               # Zustand stores por dominio
│   ├── ai/              # Estado de IA
│   ├── auth/            # Estado de autenticación
│   ├── expenses/        # Estado de gastos
│   ├── reconciliation/  # Estado de conciliación
│   ├── invoicing/       # Estado de facturas
│   └── reports/         # Estado de reportes
│
├── services/            # API clients por dominio
│   ├── ai/             # Cliente API de IA
│   ├── auth/           # Cliente API de auth
│   ├── expenses/       # Cliente API de gastos
│   ├── reconciliation/ # Cliente API de conciliación
│   ├── invoicing/      # Cliente API de facturas
│   └── reports/        # Cliente API de reportes
│
├── lib/                # Utilidades y configuración
│   ├── api/           # Cliente API base (axios/fetch)
│   ├── utils/         # Funciones utilitarias
│   └── validators/    # Esquemas Zod
│
├── hooks/             # Custom React hooks
├── types/             # TypeScript types (generados de OpenAPI)
└── config/            # Configuración de la app
```

## 🎨 Stack Tecnológico

- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript
- **Styling**: TailwindCSS
- **Estado**: Zustand (global) + React Query (server state)
- **Validación**: Zod
- **Forms**: React Hook Form + Zod
- **API**: Axios + React Query
- **Icons**: Lucide React

## 🚀 Quick Start

```bash
# Instalar dependencias
npm install

# Desarrollo
npm run dev

# Build producción
npm run build

# Iniciar producción
npm start

# Linting
npm run lint

# Type checking
npm run type-check
```

## 🔧 Configuración

### Variables de Entorno

Crear `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=ContaFlow
NEXT_PUBLIC_APP_VERSION=1.0.0
```

### Endpoints de la API

El frontend se conecta al backend en:
- **Development**: `http://localhost:8000`
- **Production**: Configurar en `.env.production`

## 🤖 Características AI-Driven

### Sugerencias Inteligentes

Los componentes AI-driven muestran sugerencias de IA en tiempo real:

```tsx
<AIExpenseSuggestion
  expense={expense}
  onAccept={(suggestion) => applySuggestion(suggestion)}
  onReject={() => trackRejection()}
/>
```

### Aprendizaje Continuo

- **Tracking**: Todas las interacciones se trackean
- **Feedback**: El usuario confirma/rechaza sugerencias
- **Mejora**: La IA aprende de las decisiones

## 📦 Módulos por Dominio

### 1. Auth (Autenticación)
- Login / Register
- Password reset
- Profile management
- JWT handling

### 2. Expenses (Gastos)
- Crear/editar gastos
- Upload de recibos
- Categorización automática
- Validación de campos
- **AI**: Sugerencias de categoría, vendor, monto

### 3. Reconciliation (Conciliación)
- Importar estado de cuenta
- Matching automático
- Revisión manual
- **AI**: Sugerencias de matching

### 4. Invoicing (Facturas)
- Crear facturas
- Procesamiento bulk
- Validación CFDI
- **AI**: Extracción de datos

### 5. Reports (Reportes)
- Dashboards
- Gráficas
- Exports (PDF, Excel)
- Filtros avanzados

## 🧩 Componentes Compartidos

### UI Components

```tsx
// Buttons
<Button variant="primary" size="md">Click me</Button>

// Inputs
<Input label="Amount" type="number" />

// Cards
<Card title="Expense Details">Content</Card>

// Modals
<Modal open={isOpen} onClose={handleClose}>...</Modal>

// Tables
<DataTable data={expenses} columns={columns} />
```

### AI Components

```tsx
// AI Suggestion Card
<AISuggestionCard
  type="expense"
  suggestion={suggestion}
  onAccept={handleAccept}
  onReject={handleReject}
/>

// AI Confidence Indicator
<AIConfidenceBar confidence={0.85} />

// AI Loading State
<AIThinking message="Analyzing expense..." />
```

## 🔐 Autenticación

```tsx
// Protected route
export default function ExpensesPage() {
  const { user } = useAuth();

  if (!user) return <Navigate to="/auth/login" />;

  return <ExpensesDashboard />;
}
```

## 📡 API Integration

### React Query

```tsx
// Fetch expenses
const { data, isLoading } = useQuery({
  queryKey: ['expenses'],
  queryFn: () => expensesService.getAll(),
});

// Create expense
const mutation = useMutation({
  mutationFn: expensesService.create,
  onSuccess: () => {
    queryClient.invalidateQueries(['expenses']);
  },
});
```

### Zustand Store

```tsx
// Global state
const useExpensesStore = create<ExpensesState>((set) => ({
  selectedExpense: null,
  filters: {},
  setSelectedExpense: (expense) => set({ selectedExpense: expense }),
  setFilters: (filters) => set({ filters }),
}));
```

## 🎯 Validación con Zod

```tsx
const expenseSchema = z.object({
  amount: z.number().positive(),
  description: z.string().min(3),
  category: z.enum(['food', 'transport', 'office']),
  date: z.date(),
});

// En formulario
const { register, handleSubmit } = useForm({
  resolver: zodResolver(expenseSchema),
});
```

## 🧪 Testing

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Coverage
npm run test:coverage
```

## 📚 Documentación

- [Arquitectura](./docs/ARCHITECTURE.md)
- [Componentes AI](./docs/AI_COMPONENTS.md)
- [API Integration](./docs/API_INTEGRATION.md)
- [State Management](./docs/STATE_MANAGEMENT.md)
- [Styling Guide](./docs/STYLING_GUIDE.md)

## 🎨 Design System

### Colors

- **Primary**: Blue (#0ea5e9)
- **Accent**: Purple (#d946ef)
- **Success**: Green (#22c55e)
- **Warning**: Yellow (#eab308)
- **Error**: Red (#ef4444)

### Typography

- **Font**: Inter (sans-serif)
- **Mono**: JetBrains Mono

### Spacing

- Base unit: 4px (0.25rem)
- Scale: 4, 8, 12, 16, 24, 32, 48, 64px

## 🚀 Deployment

```bash
# Build
npm run build

# Deploy (Vercel)
vercel deploy

# Deploy (Docker)
docker build -t contaflow-frontend .
docker run -p 3000:3000 contaflow-frontend
```

## 📄 License

Private - ContaFlow

---

**Versión**: 1.0.0
**Última actualización**: Noviembre 2025
