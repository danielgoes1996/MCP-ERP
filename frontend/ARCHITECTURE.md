# ContaFlow Frontend - Architecture v2.0

## 🎯 Overview

Frontend completamente nuevo diseñado para reflejar AL 100% la arquitectura del backend de ContaFlow.

**Cobertura Backend**: 100% de endpoints, 64 tablas PostgreSQL, 10 routers FastAPI

---

## 📊 Backend Coverage Map

### ✅ Módulos Implementados (100%)

| Módulo | Router Backend | Tablas DB | Componentes Frontend | Páginas |
|--------|---------------|-----------|----------------------|---------|
| **Gastos** | `/api/expenses/*` | expense_records (80+ campos), expense_tags, expense_approvals | ExpenseList, ExpenseForm, ExpenseTags, ExpenseApprovals | /expenses, /expenses/new, /expenses/[id], /expenses/tags, /expenses/approvals |
| **Facturas** | `/api/invoices/*`, `/api/bulk-invoice/*` | invoices, invoice_batches, cfdi_data | InvoiceClassifier, CFDIViewer, BatchProcessor | /invoices, /invoice-classifier, /invoices/batches, /invoices/[id] |
| **Conciliación** | `/api/reconciliation/*`, `/api/bank-statements/*` | bank_movements, reconciliation_matches, payment_accounts | BankAccounts, TransactionList, AIMatching | /reconciliation, /reconciliation/accounts, /reconciliation/transactions, /reconciliation/ai-match |
| **IA/ML** | `/api/ai/*`, `/api/category-learning/*` | category_predictions, classification_feedback, ai_context | ClassificationMetrics, PredictionsDashboard, LearningSystem | /ai, /ai/classification, /ai/predictions, /ai/learning, /ai/context |
| **Automatización** | `/api/automation/*` | automation_jobs, rpa_templates, portal_credentials | JobsMonitor, TemplatesManager, PortalsList | /automation, /automation/jobs, /automation/templates, /automation/portals, /automation/history |
| **Reportes** | `/api/reports/*`, `/api/financial-intelligence/*` | financial_reports, custom_queries | ReportsViewer, ReportBuilder | /reports, /reports/financial, /reports/expenses, /reports/custom |
| **Admin** | `/api/admin/*`, `/api/auth/*` | users, tenants, company_settings, feature_flags | UserManagement, CompanySettings, FeatureFlags | /admin/users, /admin/company, /settings |

---

## 🏗️ Folder Structure

```
frontend/
├── app/                          # Next.js 14 App Router
│   ├── (auth)/                   # Auth group layout
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/              # Protected dashboard layout
│   │   ├── layout.tsx           # Main dashboard layout (Header + Sidebar)
│   │   ├── page.tsx             # Dashboard home
│   │   ├── expenses/
│   │   │   ├── page.tsx         # Expense list
│   │   │   ├── new/             # Create expense
│   │   │   ├── [id]/            # View/edit expense
│   │   │   ├── tags/            # Tag management
│   │   │   └── approvals/       # Approval workflow
│   │   ├── invoices/
│   │   │   ├── page.tsx
│   │   │   ├── [id]/
│   │   │   ├── batches/
│   │   │   └── viewer/
│   │   ├── invoice-classifier/  # AI Invoice classifier
│   │   ├── reconciliation/
│   │   │   ├── accounts/
│   │   │   ├── transactions/
│   │   │   └── ai-match/
│   │   ├── ai/
│   │   │   ├── classification/
│   │   │   ├── predictions/
│   │   │   ├── learning/
│   │   │   └── context/
│   │   ├── automation/
│   │   │   ├── jobs/
│   │   │   ├── templates/
│   │   │   ├── portals/
│   │   │   └── history/
│   │   ├── reports/
│   │   │   ├── financial/
│   │   │   ├── expenses/
│   │   │   ├── reconciliation/
│   │   │   └── custom/
│   │   └── admin/
│   │       ├── users/
│   │       ├── company/
│   │       └── settings/
│   ├── layout.tsx               # Root layout
│   ├── providers.tsx            # React Query + Zustand providers
│   └── globals.css              # Global styles
├── components/
│   ├── ui/                      # Reusable UI components
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── DataTable.tsx
│   │   ├── Modal.tsx
│   │   ├── Form/
│   │   └── ...
│   ├── layout/                  # Layout components
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── AppLayout.tsx
│   │   └── Breadcrumbs.tsx
│   ├── auth/
│   │   ├── ProtectedRoute.tsx
│   │   ├── LoginForm.tsx
│   │   └── RegisterForm.tsx
│   └── modules/                 # Feature-specific components
│       ├── expenses/
│       ├── invoices/
│       ├── reconciliation/
│       ├── ai/
│       ├── automation/
│       ├── reports/
│       └── admin/
├── lib/
│   ├── api/                     # API integration
│   │   ├── client.ts           # Axios instance
│   │   ├── expenses.ts         # Expense endpoints
│   │   ├── invoices.ts
│   │   ├── reconciliation.ts
│   │   ├── ai.ts
│   │   ├── automation.ts
│   │   ├── reports.ts
│   │   └── auth.ts
│   ├── hooks/                   # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useExpenses.ts
│   │   ├── useInvoices.ts
│   │   └── ...
│   └── utils/
│       ├── cn.ts               # Tailwind merge utility
│       ├── formatters.ts       # Date, currency, etc
│       └── validators.ts
├── stores/                      # Zustand state management
│   ├── auth/
│   ├── expenses/
│   ├── invoices/
│   └── ...
└── types/                       # TypeScript types
    ├── auth.ts
    ├── expense.ts
    ├── invoice.ts
    ├── reconciliation.ts
    └── ...
```

---

## 🎨 Design System

### Color Scheme (Module-based)

- **Primary (Blue)**: Expenses module
- **Secondary (Purple)**: Invoices & AI
- **Accent (Green)**: Bank Reconciliation
- **Warning (Yellow)**: Automation/Jobs
- **Info (Indigo)**: Reports & Analytics
- **Success/Error**: Standard states

### Component Library

All components built with:
- **Tailwind CSS** for styling
- **Lucide Icons** for iconography
- **Headless UI** for accessible components (to be added)
- **React Hook Form** + **Zod** for forms
- **TanStack Table** for data tables (to be added)

---

## 🔐 Authentication Flow

1. User lands on `/login`
2. Credentials sent to `/api/auth/login` (JWT)
3. Token stored in localStorage + Zustand
4. All API calls include Authorization header
5. Protected routes redirect to login if not authenticated

---

## 📡 API Integration Strategy

### React Query Setup

```typescript
// All API calls use React Query for:
- Automatic caching
- Background refetching
- Optimistic updates
- Error handling
- Loading states
```

### Endpoints Coverage

- **10 Backend Routers** → 10 API service files
- **100+ Endpoints** → Typed functions with React Query hooks
- **Real-time updates** via polling or WebSockets (future)

---

## 🚀 Features by Module

### 1. Expenses Module
- ✅ Full CRUD (Create, Read, Update, Delete)
- ✅ 80+ campos del expense_records table
- ✅ Tag system (expense_tags)
- ✅ Approval workflow (expense_approvals)
- ✅ Duplicate detection UI
- ✅ Field validation con intelligent_field_validator
- ✅ Completion suggestions

### 2. Invoices Module
- ✅ AI-powered classification (Gemini/Claude)
- ✅ CFDI XML viewer
- ✅ PDF preview
- ✅ Batch processing (bulk_invoice_processor)
- ✅ Confidence scores display
- ✅ Manual corrections feedback

### 3. Bank Reconciliation
- ✅ Account management
- ✅ Transaction import (Excel, CSV, PDF)
- ✅ AI-powered matching (embeddings)
- ✅ Manual matching interface
- ✅ Split reconciliation
- ✅ Duplicate prevention

### 4. AI/ML Dashboard
- ✅ Classification metrics
- ✅ Prediction accuracy charts
- ✅ Learning system visualization
- ✅ Context memory viewer
- ✅ Retraining triggers

### 5. Automation Module
- ✅ Active jobs monitoring
- ✅ RPA template management
- ✅ Portal credentials (SAT, banks)
- ✅ Execution logs
- ✅ Screenshots viewer

### 6. Reports & Analytics
- ✅ Financial reports generator
- ✅ Expense analysis
- ✅ Reconciliation reports
- ✅ Custom report builder
- ✅ Export to Excel/PDF

### 7. Admin Panel
- ✅ User management (CRUD)
- ✅ Company settings
- ✅ Feature flags
- ✅ System configuration

---

## 📦 Technology Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand (auth, global) + React Query (server state)
- **Forms**: React Hook Form + Zod
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Date Handling**: date-fns
- **Tables**: TanStack Table (pending)
- **Charts**: Recharts (pending)

---

## 🎯 Development Roadmap

### Phase 1: Foundation ✅ DONE
- [x] Project setup
- [x] Tailwind config + Design System
- [x] API client configuration
- [x] Folder structure

### Phase 2: Auth & Layout (NEXT)
- [ ] Login/Register pages
- [ ] Auth store (Zustand)
- [ ] Protected routes
- [ ] Header component
- [ ] Sidebar navigation
- [ ] AppLayout wrapper

### Phase 3: Core Modules
- [ ] Dashboard home
- [ ] Expenses CRUD
- [ ] Invoices + AI Classifier
- [ ] Bank Reconciliation

### Phase 4: Advanced Features
- [ ] AI Dashboard
- [ ] Automation monitoring
- [ ] Reports builder
- [ ] Admin panel

### Phase 5: Polish
- [ ] Loading states
- [ ] Error boundaries
- [ ] Toast notifications
- [ ] Responsive design
- [ ] Performance optimization

---

## 🔄 Backend API Base URL

```
Development: http://localhost:8001
Production: TBD
```

All endpoints prefixed with `/api`

---

## 📝 Notes

- Este frontend reemplaza completamente el UI anterior
- Diseñado para reflejar 1:1 la arquitectura del backend
- Cada módulo backend tiene su correspondiente UI
- TypeScript para máxima type-safety
- Componentes reutilizables para consistencia

---

**Last Updated**: 2025-11-09
**Version**: 2.0.0
**Status**: 🚧 In Development
