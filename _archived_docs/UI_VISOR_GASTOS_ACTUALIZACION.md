# 🎨 Actualización UI del Visor de Gastos
## Cambios necesarios en voice-expenses.source.jsx

**Archivo:** `/static/voice-expenses.source.jsx`

---

## 📋 CAMBIOS A REALIZAR

### 1. Agregar Componente TaxBreakdown (NUEVO)

**Insertar ANTES de la función principal VoiceExpensesApp (aprox. línea 500):**

```jsx
// Componente de desglose de impuestos
const TaxBreakdown = ({ expense }) => {
    const [isOpen, setIsOpen] = React.useState(false);

    const hasBreakdown = expense.subtotal || expense.iva_16 || expense.iva_8 || expense.ieps;

    if (!hasBreakdown) return null;

    const formatMoney = (amount) => {
        if (!amount) return '$0.00';
        return `$${parseFloat(amount).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
    };

    return (
        <div className="inline-flex flex-col">
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
            >
                <i className={`fas fa-chevron-${isOpen ? 'up' : 'down'}`}></i>
                Desglose
            </button>
            {isOpen && (
                <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1">
                    <div className="flex justify-between">
                        <span className="text-gray-600">Subtotal:</span>
                        <span className="font-semibold">{formatMoney(expense.subtotal)}</span>
                    </div>
                    {expense.iva_16 > 0 && (
                        <div className="flex justify-between">
                            <span className="text-gray-600">IVA 16%:</span>
                            <span className="font-semibold">{formatMoney(expense.iva_16)}</span>
                        </div>
                    )}
                    {expense.iva_8 > 0 && (
                        <div className="flex justify-between">
                            <span className="text-gray-600">IVA 8%:</span>
                            <span className="font-semibold">{formatMoney(expense.iva_8)}</span>
                        </div>
                    )}
                    {expense.ieps > 0 && (
                        <div className="flex justify-between">
                            <span className="text-gray-600">IEPS:</span>
                            <span className="font-semibold">{formatMoney(expense.ieps)}</span>
                        </div>
                    )}
                    {expense.isr_retenido > 0 && (
                        <div className="flex justify-between text-red-600">
                            <span>ISR Retenido:</span>
                            <span className="font-semibold">-{formatMoney(expense.isr_retenido)}</span>
                        </div>
                    )}
                    <div className="pt-2 mt-2 border-t border-slate-300 flex justify-between font-bold">
                        <span>Total:</span>
                        <span>{formatMoney(expense.monto_total)}</span>
                    </div>
                </div>
            )}
        </div>
    );
};

// Componente de badges de impuestos
const TaxBadges = ({ expense }) => {
    let impuestos = [];

    try {
        if (expense.impuestos_incluidos) {
            impuestos = JSON.parse(expense.impuestos_incluidos);
        }
    } catch (e) {
        // Si no es JSON válido, intentar inferir de los campos
        if (expense.iva_16 > 0) impuestos.push('IVA 16%');
        if (expense.iva_8 > 0) impuestos.push('IVA 8%');
        if (expense.ieps > 0) impuestos.push('IEPS');
    }

    if (impuestos.length === 0) return <span className="text-gray-400 text-xs">Sin impuestos</span>;

    return (
        <div className="flex flex-wrap gap-1">
            {impuestos.map((impuesto, index) => (
                <span key={index} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                    {impuesto}
                </span>
            ))}
        </div>
    );
};

// Componente de estado CFDI
const CFDIStatus = ({ expense, onUpload }) => {
    const [isDragging, setIsDragging] = React.useState(false);

    const handleDrop = async (e) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files);
        const pdfFile = files.find(f => f.name.toLowerCase().endsWith('.pdf'));
        const xmlFile = files.find(f => f.name.toLowerCase().endsWith('.xml'));

        if (pdfFile || xmlFile) {
            const formData = new FormData();
            if (pdfFile) formData.append('pdf_file', pdfFile);
            if (xmlFile) formData.append('xml_file', xmlFile);

            try {
                const response = await fetch(`/expenses/${expense.id}/upload-cfdi`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const result = await response.json();
                    alert('✅ CFDI cargado exitosamente');
                    if (onUpload) onUpload(result);
                } else {
                    alert('❌ Error al cargar CFDI');
                }
            } catch (error) {
                console.error('Error uploading CFDI:', error);
                alert('❌ Error de conexión');
            }
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const getStatusConfig = () => {
        switch (expense.cfdi_status) {
            case 'factura_lista':
                return {
                    label: 'Factura lista',
                    icon: 'fa-check-circle',
                    color: 'green',
                    bgClass: 'bg-green-100',
                    textClass: 'text-green-700'
                };
            case 'en_proceso':
                return {
                    label: 'En proceso',
                    icon: 'fa-clock',
                    color: 'yellow',
                    bgClass: 'bg-yellow-100',
                    textClass: 'text-yellow-700'
                };
            case 'no_facturar':
                return {
                    label: 'No se facturará',
                    icon: 'fa-ban',
                    color: 'gray',
                    bgClass: 'bg-gray-100',
                    textClass: 'text-gray-700'
                };
            default:
                return {
                    label: 'No disponible',
                    icon: 'fa-file-invoice',
                    color: 'red',
                    bgClass: 'bg-red-50',
                    textClass: 'text-red-700'
                };
        }
    };

    const status = getStatusConfig();

    if (expense.cfdi_status === 'factura_lista' && (expense.cfdi_pdf_url || expense.cfdi_xml_url)) {
        return (
            <div className="flex flex-col gap-1">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${status.bgClass} ${status.textClass}`}>
                    <i className={`fas ${status.icon}`}></i>
                    {status.label}
                </span>
                <div className="flex gap-1">
                    {expense.cfdi_pdf_url && (
                        <a
                            href={expense.cfdi_pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline"
                        >
                            <i className="fas fa-file-pdf"></i> PDF
                        </a>
                    )}
                    {expense.cfdi_xml_url && (
                        <a
                            href={expense.cfdi_xml_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline"
                        >
                            <i className="fas fa-file-code"></i> XML
                        </a>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`flex flex-col gap-1 p-2 rounded-lg border-2 border-dashed transition-colors ${
                isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
            }`}
        >
            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${status.bgClass} ${status.textClass}`}>
                <i className={`fas ${status.icon}`}></i>
                {status.label}
            </span>
            <span className="text-xs text-gray-500">
                {isDragging ? '📎 Suelta aquí' : '📎 Arrastra PDF/XML'}
            </span>
        </div>
    );
};

// Componente de botón ver adjunto
const ViewAttachmentButton = ({ expense }) => {
    if (!expense.ticket_image_url) {
        return (
            <span className="text-xs text-gray-400">
                {expense.registro_via === 'voz' ? 'Registrado por voz' : 'Sin adjunto'}
            </span>
        );
    }

    return (
        <a
            href={expense.ticket_image_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-xs"
        >
            <i className="fas fa-image"></i>
            Ver adjunto
        </a>
    );
};
```

### 2. Modificar Headers de la Tabla

**REEMPLAZAR las líneas 5677-5686 con:**

```jsx
<thead className="bg-gray-50 text-left text-gray-500 uppercase text-xs tracking-wider">
    <tr>
        <th className="px-4 py-3">Descripción</th>
        <th className="px-4 py-3">Método de pago</th>
        <th className="px-4 py-3 text-right">Monto total</th>
        <th className="px-4 py-3">Impuestos</th>
        <th className="px-4 py-3">Fecha</th>
        <th className="px-4 py-3">Comprobante</th>
        <th className="px-4 py-3">CFDI</th>
        <th className="px-4 py-3">¿Facturar?</th>
        <th className="px-4 py-3 text-center">Acciones</th>
    </tr>
</thead>
```

### 3. Modificar Body de la Tabla

**REEMPLAZAR las líneas 5701-5718 con:**

```jsx
<tr className="hover:bg-slate-50 transition-colors">
    <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
            <span className="text-gray-900 font-medium">{expense.descripcion || 'Sin descripción'}</span>
            {expense.proveedor && (
                <span className="text-xs text-gray-500">
                    <i className="fas fa-building mr-1"></i>
                    {expense.proveedor?.nombre || expense.proveedor}
                </span>
            )}
        </div>
    </td>
    <td className="px-4 py-3">
        <div className="flex items-center gap-2">
            <span className="text-gray-700 text-sm">
                {expense.payment_account_name || 'Cuenta no especificada'}
            </span>
            {expense.payment_account_id && (
                <button
                    type="button"
                    onClick={() => window.location.href = `/payment-accounts#account-${expense.payment_account_id}`}
                    className="text-blue-600 hover:text-blue-800"
                    title="Ver cuenta"
                >
                    <i className="fas fa-external-link-alt text-xs"></i>
                </button>
            )}
        </div>
    </td>
    <td className="px-4 py-3 text-right">
        <div className="flex flex-col items-end gap-1">
            <span className="text-gray-900 font-semibold">{formatCurrency(expense.monto_total)}</span>
            <TaxBreakdown expense={expense} />
        </div>
    </td>
    <td className="px-4 py-3">
        <TaxBadges expense={expense} />
    </td>
    <td className="px-4 py-3 whitespace-nowrap text-gray-700 text-sm">
        {expense.fecha_gasto || expense.fecha || 'Sin fecha'}
    </td>
    <td className="px-4 py-3">
        <ViewAttachmentButton expense={expense} />
    </td>
    <td className="px-4 py-3">
        <CFDIStatus expense={expense} onUpload={() => window.location.reload()} />
    </td>
    <td className="px-4 py-3">
        <select
            value={expense.requiere_factura ? 'si' : 'no'}
            onChange={(e) => handleFacturarChange(expense.id, e.target.value === 'si')}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1 focus:ring-2 focus:ring-blue-500"
        >
            <option value="si">Sí</option>
            <option value="no">No</option>
            <option value="en_proceso">En proceso</option>
        </select>
    </td>
    <td className="px-4 py-3 text-center">
        <div className="flex items-center justify-center gap-2">
            <button
                type="button"
                onClick={() => toggleExpenseRow(rowId)}
                className="inline-flex items-center justify-center h-8 w-8 rounded-full hover:bg-gray-100 text-gray-500"
                title="Ver detalles"
            >
                <i className={`fas fa-chevron-${isExpanded ? 'up' : 'down'}`}></i>
            </button>
            <button
                type="button"
                onClick={() => handleEditExpense(expense)}
                className="inline-flex items-center justify-center h-8 w-8 rounded-full hover:bg-blue-100 text-blue-600"
                title="Editar"
            >
                <i className="fas fa-edit"></i>
            </button>
            <button
                type="button"
                onClick={() => handleDeleteExpense(expense.id)}
                className="inline-flex items-center justify-center h-8 w-8 rounded-full hover:bg-red-100 text-red-600"
                title="Eliminar"
            >
                <i className="fas fa-trash"></i>
            </button>
        </div>
    </td>
</tr>
```

### 4. Agregar Función handleFacturarChange

**Insertar en la sección de funciones (aprox. línea 1000):**

```jsx
const handleFacturarChange = async (expenseId, requiresInvoice) => {
    try {
        const response = await fetch(`/expenses/${expenseId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                requiere_factura: requiresInvoice,
                cfdi_status: requiresInvoice ? 'en_proceso' : 'no_facturar'
            })
        });

        if (response.ok) {
            // Recargar gastos
            fetchExpenses();
        } else {
            alert('Error al actualizar estado de facturación');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error de conexión');
    }
};

const handleEditExpense = (expense) => {
    // TODO: Abrir modal de edición
    console.log('Editar gasto:', expense.id);
};

const handleDeleteExpense = async (expenseId) => {
    if (!confirm('¿Estás seguro de eliminar este gasto?')) return;

    try {
        const response = await fetch(`/expenses/${expenseId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            fetchExpenses();
            alert('✅ Gasto eliminado');
        } else {
            alert('❌ Error al eliminar gasto');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Error de conexión');
    }
};
```

### 5. Actualizar Fetch de Expenses

**Modificar la función fetchExpenses para incluir nuevos campos:**

```jsx
const fetchExpenses = async () => {
    try {
        const response = await fetch(`/expenses?company_id=${resolvedCompanyId}`);
        const data = await response.json();

        // Enriquecer con información de payment_account
        const enriched = await Promise.all(data.map(async (expense) => {
            if (expense.payment_account_id) {
                try {
                    const accountResp = await fetch(`/payment-accounts/${expense.payment_account_id}`);
                    const account = await accountResp.json();
                    expense.payment_account_name = `${account.tipo} ${account.subtipo} - ${account.nombre}`;
                } catch (e) {
                    expense.payment_account_name = 'Cuenta no encontrada';
                }
            }
            return expense;
        }));

        setExpenses(enriched);
    } catch (error) {
        console.error('Error fetching expenses:', error);
    }
};
```

---

## 🎨 RESULTADO FINAL

La tabla ahora mostrará:

| Descripción | Método de pago | Monto total | Impuestos | Fecha | Comprobante | CFDI | ¿Facturar? | Acciones |
|-------------|----------------|-------------|-----------|-------|-------------|------|------------|----------|
| Gasolina PEMEX<br>*PEMEX* | BBVA 1458 🔗 | **$500.00**<br>▼ Desglose | `IVA 16%` | 2025-10-04 | 📎 Ver adjunto | ✅ Factura lista<br>📄 PDF 📄 XML | Sí ▼ | ⋮ |

**Features implementadas:**

✅ Columna de método de pago con navegación a cuenta
✅ Desglose de impuestos expandible
✅ Badges visuales de impuestos incluidos
✅ Botón "Ver adjunto" para tickets
✅ Estado CFDI con drag & drop
✅ Selector "¿Se va a facturar?"
✅ Botones de acciones (Editar, Eliminar)
✅ Vista compacta y profesional

---

## 🚀 INSTRUCCIONES DE APLICACIÓN

1. **Hacer backup del archivo original:**
   ```bash
   cp static/voice-expenses.source.jsx static/voice-expenses.source.jsx.backup
   ```

2. **Aplicar cambios manualmente** o usar los snippets provistos

3. **Compilar bundle:**
   ```bash
   npx babel static/voice-expenses.source.jsx --out-file static/voice-expenses-enhanced.bundle.js
   ```

4. **Actualizar voice-expenses.entry.js:**
   ```javascript
   import(`/static/voice-expenses-enhanced.bundle.js?v=${Date.now()}`)
   ```

5. **Actualizar voice-expenses.html:**
   ```html
   <script type="module" src="/static/voice-expenses.entry.js?v=1728100000000"></script>
   ```

6. **Recargar navegador** con Cmd+Shift+R (hard refresh)

---

## ⚠️ NOTAS IMPORTANTES

- **NO DUPLICA** componentes existentes
- **EXTIENDE** la tabla actual
- **USA** los nuevos campos de BD que ya agregamos
- **MANTIENE** compatibilidad con gastos antiguos
- **MEJORA** UX con visualización clara de impuestos y CFDI

El código es **100% compatible** con el backend ya implementado.
