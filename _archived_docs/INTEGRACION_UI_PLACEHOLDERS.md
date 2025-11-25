# 🚀 Guía de Integración: Placeholders en UI Existente

## ✅ TL;DR - Lo Que Necesitas Hacer

**Solo 3 pasos simples para tener todo funcionando:**

1. Importar los 2 componentes nuevos en `voice-expenses.source.jsx`
2. Agregar el badge en tu navbar (donde está "Facturas pendientes")
3. Agregar el modal en tu renderizado principal

**Tiempo estimado: 10 minutos** ⏱️

---

## 📋 Paso 1: Importar Componentes

Al inicio de tu archivo `static/voice-expenses.source.jsx`, agrega:

```jsx
// ===== NUEVAS IMPORTACIONES PARA PLACEHOLDERS =====
// (Agregar después de tus imports existentes de React)

// Componente del badge con contador
const PlaceholderBadge = ({ onClick }) => {
    const [pendingCount, setPendingCount] = React.useState(0);

    React.useEffect(() => {
        const fetchCount = async () => {
            try {
                const res = await fetch('/api/expenses/placeholder-completion/stats/detailed?company_id=default');
                const data = await res.json();
                setPendingCount(data.total_pending);
            } catch (e) {
                console.error('Error fetching placeholders:', e);
            }
        };

        fetchCount();
        const interval = setInterval(fetchCount, 30000); // Actualizar cada 30s
        return () => clearInterval(interval);
    }, []);

    if (pendingCount === 0) return null;

    return (
        <button
            onClick={onClick}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                background: '#fff3cd',
                border: '2px solid #ffc107',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '500',
                marginLeft: '12px'
            }}
        >
            <span>⚠️</span>
            <span>Completar Gastos</span>
            <span style={{
                background: '#dc3545',
                color: 'white',
                padding: '2px 8px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 'bold'
            }}>
                {pendingCount}
            </span>
        </button>
    );
};

// Modal de completación (versión compacta inline)
const PlaceholderModal = ({ onClose, onComplete }) => {
    const [pending, setPending] = React.useState([]);
    const [current, setCurrent] = React.useState(0);
    const [fields, setFields] = React.useState({});

    React.useEffect(() => {
        fetch('/api/expenses/placeholder-completion/pending?company_id=default')
            .then(r => r.json())
            .then(setPending);
    }, []);

    if (pending.length === 0) {
        return (
            <div style={{
                position: 'fixed',
                top: 0, left: 0, right: 0, bottom: 0,
                background: 'rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 9999
            }} onClick={onClose}>
                <div style={{
                    background: 'white',
                    padding: '32px',
                    borderRadius: '12px',
                    textAlign: 'center'
                }}>
                    <h2>🎉 ¡Todo completo!</h2>
                    <p>No hay gastos pendientes.</p>
                    <button onClick={onClose}>Cerrar</button>
                </div>
            </div>
        );
    }

    const expense = pending[current];

    const handleSubmit = async () => {
        await fetch('/api/expenses/placeholder-completion/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                expense_id: expense.expense_id,
                completed_fields: fields,
                company_id: 'default'
            })
        });

        if (current < pending.length - 1) {
            setCurrent(current + 1);
            setFields({});
        } else {
            onComplete();
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                background: 'white',
                padding: '24px',
                borderRadius: '12px',
                width: '600px',
                maxHeight: '80vh',
                overflow: 'auto'
            }}>
                <h2>Completar Gasto {current + 1} de {pending.length}</h2>
                <p><strong>{expense.descripcion}</strong></p>
                <p>Monto: ${expense.monto_total}</p>

                <div style={{marginTop: '20px'}}>
                    <label>
                        Categoría:
                        <select
                            onChange={(e) => setFields({...fields, categoria: e.target.value})}
                            style={{width: '100%', padding: '8px', marginTop: '4px'}}
                        >
                            <option value="">Selecciona...</option>
                            <option value="servicios">Servicios</option>
                            <option value="materiales">Materiales</option>
                            <option value="nomina">Nómina</option>
                        </select>
                    </label>
                </div>

                <div style={{marginTop: '16px', display: 'flex', gap: '12px'}}>
                    <button onClick={() => setCurrent(current + 1)}>
                        Saltar
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={Object.keys(fields).length === 0}
                        style={{
                            background: '#4caf50',
                            color: 'white',
                            padding: '10px 20px',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer'
                        }}
                    >
                        Guardar y Continuar
                    </button>
                </div>
            </div>
        </div>
    );
};
```

---

## 📋 Paso 2: Agregar State en tu Componente Principal

Busca en `voice-expenses.source.jsx` donde tienes tus estados (useState), y agrega:

```jsx
// Ejemplo: Busca donde tienes algo como esto:
function VoiceExpensesApp() {
    const [expenses, setExpenses] = useState([]);
    const [showInvoiceModal, setShowInvoiceModal] = useState(false);
    // ... tus otros estados ...

    // ===== AGREGAR ESTE ESTADO =====
    const [showPlaceholderModal, setShowPlaceholderModal] = useState(false);

    // ... resto de tu código ...
}
```

---

## 📋 Paso 3: Agregar Badge en el Navbar

Busca donde renderizas tu navbar/header. Probablemente algo como:

```jsx
// ANTES (ejemplo de tu código actual):
<div className="header">
    <h1>Gastos</h1>
    <button onClick={() => setShowInvoiceModal(true)}>
        Facturas Pendientes
    </button>
</div>

// DESPUÉS (con el badge agregado):
<div className="header">
    <h1>Gastos</h1>
    <button onClick={() => setShowInvoiceModal(true)}>
        Facturas Pendientes
    </button>

    {/* ===== NUEVO BADGE ===== */}
    <PlaceholderBadge onClick={() => setShowPlaceholderModal(true)} />
</div>
```

---

## 📋 Paso 4: Agregar Modal en el Render

Al final de tu función de render, antes del cierre del componente principal:

```jsx
return (
    <div className="app">
        {/* ... todo tu contenido existente ... */}

        {/* Modal de facturas (ya existe) */}
        {showInvoiceModal && (
            <InvoiceModal onClose={() => setShowInvoiceModal(false)} />
        )}

        {/* ===== NUEVO MODAL DE PLACEHOLDERS ===== */}
        {showPlaceholderModal && (
            <PlaceholderModal
                onClose={() => setShowPlaceholderModal(false)}
                onComplete={() => {
                    setShowPlaceholderModal(false);
                    // Opcional: Refrescar tu lista de gastos
                    fetchExpenses();
                }}
            />
        )}
    </div>
);
```

---

## 🎯 Ejemplo Completo de Integración

Aquí está cómo quedaría tu archivo con TODO integrado:

```jsx
// ========== voice-expenses.source.jsx ==========

const { useState, useCallback, useRef, useEffect, useMemo } = React;

// ... tus constantes existentes (MISSION_DETAILS, etc.) ...

// ===== COMPONENTES DE PLACEHOLDERS (AGREGAR AQUÍ) =====
const PlaceholderBadge = ({ onClick }) => { /* código del badge */ };
const PlaceholderModal = ({ onClose, onComplete }) => { /* código del modal */ };

// ===== TU COMPONENTE PRINCIPAL =====
function VoiceExpensesApp() {
    // Estados existentes
    const [expenses, setExpenses] = useState([]);
    const [showInvoiceModal, setShowInvoiceModal] = useState(false);

    // ===== NUEVO ESTADO =====
    const [showPlaceholderModal, setShowPlaceholderModal] = useState(false);

    // ... tu código existente ...

    return (
        <div className="app">
            {/* Header */}
            <header className="main-header">
                <h1>Sistema de Gastos</h1>

                <div className="actions">
                    <button onClick={() => setShowInvoiceModal(true)}>
                        Facturas Pendientes
                    </button>

                    {/* ===== NUEVO BADGE ===== */}
                    <PlaceholderBadge onClick={() => setShowPlaceholderModal(true)} />
                </div>
            </header>

            {/* ... resto de tu UI existente ... */}

            {/* Modales */}
            {showInvoiceModal && <InvoiceModal onClose={() => setShowInvoiceModal(false)} />}

            {/* ===== NUEVO MODAL ===== */}
            {showPlaceholderModal && (
                <PlaceholderModal
                    onClose={() => setShowPlaceholderModal(false)}
                    onComplete={() => {
                        setShowPlaceholderModal(false);
                        fetchExpenses(); // Tu función existente
                    }}
                />
            )}
        </div>
    );
}

// Renderizar
ReactDOM.render(<VoiceExpensesApp />, document.getElementById('root'));
```

---

## 🔄 Integración con Flujo de Subida de Facturas

Si ya tienes un endpoint que sube facturas, agrega esto:

```jsx
// En tu función de upload de facturas existente
async function uploadInvoices(files) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const response = await fetch('/api/bulk-invoice/upload', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();

    // ===== AGREGAR ESTA VALIDACIÓN =====
    if (result.placeholders_created > 0) {
        // Mostrar notificación
        alert(`${result.placeholders_created} facturas necesitan información adicional`);

        // Abrir modal automáticamente
        setShowPlaceholderModal(true);
    }
}
```

---

## ✅ Checklist de Integración

```
□ 1. Copiar código de PlaceholderBadge en voice-expenses.source.jsx
□ 2. Copiar código de PlaceholderModal en voice-expenses.source.jsx
□ 3. Agregar estado showPlaceholderModal
□ 4. Agregar <PlaceholderBadge /> en el navbar
□ 5. Agregar {showPlaceholderModal && <PlaceholderModal />} al final del render
□ 6. (Opcional) Integrar con flujo de upload de facturas
□ 7. Probar en el navegador
```

---

## 🧪 Cómo Probar

1. **Crear un placeholder de prueba:**
   ```bash
   curl -X POST http://localhost:8000/api/expenses \
     -H "Content-Type: application/json" \
     -d '{
       "descripcion": "Test Placeholder",
       "monto_total": 100,
       "fecha_gasto": "2025-01-15",
       "workflow_status": "requiere_completar",
       "company_id": "default",
       "metadata": "{\"missing_fields\": [\"categoria\"]}"
     }'
   ```

2. **Refrescar tu UI:**
   - Deberías ver el badge "⚠️ Completar Gastos (1)"
   - Hacer clic debería abrir el modal
   - Completar el campo faltante
   - Guardar → el badge desaparece

---

## 🎨 Personalización (Opcional)

Si quieres que el badge se vea como tu diseño existente:

```jsx
// Modificar los estilos del badge para que coincidan con tus botones
<PlaceholderBadge
    onClick={() => setShowPlaceholderModal(true)}
    className="tu-clase-de-boton-existente" // ← Usar tus clases CSS
/>
```

---

## 🚨 Troubleshooting

**Problema:** No aparece el badge
- Verificar que la API `/stats/detailed` esté funcionando
- Abrir DevTools → Network → buscar el request
- Ver si `total_pending` es > 0

**Problema:** Modal no se abre
- Verificar que el estado `showPlaceholderModal` se actualiza
- Usar React DevTools para inspeccionar el estado

**Problema:** No hay placeholders
- Crear uno de prueba con el curl de arriba
- O esperar a que el sistema automático cree uno

---

## 📊 Resultado Final

Cuando termines, tendrás:

✅ Badge que muestra contador en tiempo real
✅ Modal que se abre al hacer clic
✅ Flujo completo de completar campos faltantes
✅ Actualización automática cuando terminas
✅ 0 líneas de código backend adicional (ya está todo listo)

**Total de código nuevo en tu frontend: ~100 líneas** 🎉

---

¿Necesitas ayuda con algún paso específico? ¡Pregunta!
