const { useState, useEffect, useMemo, useCallback } = React;

const __DEV__ = typeof process !== 'undefined' && process?.env && process.env.NODE_ENV !== 'production';

const toNumber = (value, fallback = 0) => {
    if (value === null || value === undefined) return fallback;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
};

const readConfidence = (movement) => {
    const raw = movement?.matching_confidence ?? movement?.confidence_score ?? movement?.auto_match_confidence ?? movement?.confidence;
    if (raw === null || raw === undefined) return 0;
    const value = typeof raw === 'string' ? parseFloat(raw) : raw;
    if (!Number.isFinite(value)) return 0;
    if (value > 1) {
        return Math.max(0, Math.min(1, value / 100));
    }
    return Math.max(0, Math.min(1, value));
};

const isConciliated = (movement) => {
    const state = String(movement?.state || '').toLowerCase();
    if (state === 'conciliado') {
        return true;
    }
    const status = String(movement?.processing_status || movement?.conciliation_status || movement?.status || movement?.reconciliation_status || '').toLowerCase();
    return ['processed', 'conciliated', 'reconciled', 'conciliado', 'finalized', 'completed'].includes(status);
};

const hasCfdi = (movement) => {
    return Boolean(movement?.cfdi_uuid || movement?.matched_cfdi_uuid || movement?.invoice_uuid || movement?.matched_invoice_uuid || movement?.invoice?.uuid);
};

const isPPD = (movement) => {
    const paymentMethod = String(movement?.payment_method || movement?.invoice?.payment_method || movement?.metadata?.payment_method || '').toUpperCase();
    if (paymentMethod.includes('PPD')) return true;
    const badges = movement?.badges || movement?.metadata?.badges || [];
    return badges.some((badge) => /PPD/i.test(badge.label || badge));
};

const intlRegex = /(META ADS|FACEBOOK|GOOGLE|AWS|AMAZON\.COM|ADOBE|MICROSOFT|APPLE\.COM|SHOPIFY|STRIPE|PAYPAL|AIRBNB|UBER BV|UBER TRIP|META\s+PLATFORMS|SPOTIFY|OPENAI|CLOUDFLARE|DIGITALOCEAN|ATLASSIAN|FIVERR|UPWORK)/i;

const isIntlWithoutCfdi = (movement) => {
    if (hasCfdi(movement)) return false;
    const currency = String(movement?.currency || movement?.moneda || '').toUpperCase();
    if (currency && currency !== 'MXN') return true;
    const description = String(movement?.description || movement?.descripcion || '').toUpperCase();
    if (intlRegex.test(description)) return true;
    const badges = movement?.badges || [];
    return badges.some((badge) => /INTL|Internacional/i.test(badge.label || badge));
};

const incomeHints = /(dep[oó]sito|abono|pago recibido|transferencia recibida|venta|ingreso|mercadopago|clip|stripe payout|paypal payout)/i;
const expenseHints = /(comisi[oó]n|pago|servicio|compra|cargo|retiro|spei a|transferencia a|traspaso a)/i;

const classifyFlow = (movement) => {
    const flow = String(movement?.flow || movement?.movement_flow || movement?.tipo_movimiento || '').toLowerCase();
    if (flow === 'ingreso' || flow === 'egreso') return flow;
    const amount = toNumber(movement?.amount ?? movement?.monto, 0);
    if (amount > 0 && flow.includes('ing')) return 'ingreso';
    if (amount < 0 && flow.includes('egr')) return 'egreso';
    const description = String(movement?.description || movement?.descripcion || '').toLowerCase();
    if (incomeHints.test(description)) return 'ingreso';
    if (expenseHints.test(description)) return 'egreso';
    return amount >= 0 ? 'ingreso' : 'egreso';
};

const computePPDInfo = (row) => {
    const total = toNumber(row?.invoice?.total, 0);
    const complements = Array.isArray(row?.ppd?.complementos) ? row.ppd.complementos : [];
    const paid = complements.reduce((sum, item) => sum + toNumber(item.amountPaid || item.importe_pagado || item.monto_pagado, 0), 0);
    const percent = total > 0 ? Math.min(100, Math.round((paid / total) * 100)) : 0;
    const remaining = Math.max(0, total - paid);
    const currentPaymentPercent = total > 0 ? Math.round((toNumber(row.amount, 0) / total) * 100) : 0;
    return {
        total,
        complements,
        paid,
        percent,
        nextParcialidad: complements.length + 1,
        remaining,
        currentPaymentPercent,
    };
};

const formatCurrency = (value, currency = 'MXN') => {
    const numeric = toNumber(value, 0);
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency }).format(numeric);
};

const formatDate = (value) => {
    if (!value) return '—';
    try {
        return new Date(value).toLocaleDateString('es-MX');
    } catch (error) {
        return value;
    }
};

const formatPeriodLabel = (period) => {
    if (!period) return 'Sin periodo';
    const date = new Date(`${period}-01T00:00:00`);
    if (Number.isNaN(date.getTime())) return period;
    return date.toLocaleDateString('es-MX', { month: 'long', year: 'numeric' });
};

const normalizeToKey = (value) => {
    if (!value || typeof value !== 'string') return null;
    let working = value.trim().toLowerCase();
    if (!working) return null;
    try {
        working = working.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    } catch (error) {
        // noop: normalize can throw on unsupported environments
    }
    const sanitized = working.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return sanitized || null;
};

const resolveAccountMetadata = (movement) => {
    const idCandidates = [
        movement?.bank_account_id,
        movement?.metadata?.payment_account_id,
        movement?.account_id,
        movement?.account,
        movement?.metadata?.account_id,
        movement?.metadata?.account_number,
        movement?.metadata?.account_identifier,
        movement?.metadata?.clabe,
    ];

    let accountId = null;
    for (const candidate of idCandidates) {
        if (candidate === null || candidate === undefined) continue;
        const value = String(candidate).trim();
        if (value) {
            accountId = value;
            break;
        }
    }

    const labelCandidates = [
        movement?.metadata?.account_label,
        movement?.account_label,
        movement?.metadata?.account_name,
        movement?.metadata?.bank_name,
        movement?.metadata?.bank,
        movement?.bank,
        movement?.display_name,
    ];

    const label = labelCandidates.find((candidate) => typeof candidate === 'string' && candidate.trim())?.trim() || null;

    if (!accountId) {
        const normalized = label ? normalizeToKey(label) : null;
        accountId = normalized ? `label:${normalized}` : 'sin-cuenta';
    }

    const accountLabel = label
        || (!accountId.startsWith('label:') && accountId !== 'sin-cuenta' ? `Cuenta ${accountId}` : 'Cuenta sin etiqueta');

    return { accountId, accountLabel };
};

const getActiveCompanyId = () => {
    try {
        const stored = localStorage.getItem('mcp_company_id');
        if (stored && stored.trim()) {
            return stored;
        }
    } catch (error) {
        console.warn('No se pudo leer mcp_company_id de localStorage:', error);
    }
    return 'default';
};

const showToast = (message, type = 'info') => {
    if (window?.mcpHeader?.showNotification) {
        window.mcpHeader.showNotification(message, type);
        return;
    }
    if (window?.Toast?.show) {
        const intentMap = { success: 'success', warning: 'warning', error: 'danger', info: 'info' };
        window.Toast.show({ message, intent: intentMap[type] || 'info' });
        return;
    }
    console.log(`[toast:${type}]`, message);
};

const mapSuggestion = (suggestion) => {
    if (!suggestion) return null;
    const scoreRaw = suggestion.score ?? suggestion.confidence ?? suggestion.match_confidence ?? suggestion.similarity;
    const scoreNormalized = Number.isFinite(scoreRaw) ? (scoreRaw > 1 ? scoreRaw : scoreRaw * 100) : 0;
    return {
        title: suggestion.title || suggestion.label || suggestion.uuid || 'Sugerencia',
        score: Math.round(scoreNormalized),
        detail: suggestion.detail || suggestion.description || suggestion.reason || '',
        raw: suggestion,
    };
};

const mapInvoice = (movement) => {
    const invoice = movement?.invoice || movement?.matched_invoice || movement?.cfdi_details || null;
    if (!invoice) return null;
    const taxes = invoice.taxes || invoice.impuestos || {};
    return {
        uuid: invoice.uuid || invoice.timbre_fiscal_uuid || invoice.cfdi_uuid || null,
        supplierName: invoice.supplierName || invoice.razon_social || invoice.proveedor || invoice.emisor || null,
        subtotal: toNumber(invoice.subtotal ?? taxes.subtotal, 0),
        total: toNumber(invoice.total, 0),
        paymentMethod: invoice.paymentMethod || invoice.forma_pago || invoice.metodo_pago || null,
        taxes: {
            iva: toNumber(taxes.iva ?? taxes.iva_16 ?? taxes.impuesto_iva, 0),
            ieps: toNumber(taxes.ieps ?? taxes.impuesto_ieps, 0),
            retenciones: toNumber(taxes.retenciones ?? taxes.isr ?? taxes.retenciones_isr, 0),
        },
    };
};

const detectBadges = (movement, flow) => {
    const badges = [];
    if (isConciliated(movement)) {
        badges.push({ label: 'Conciliado', tone: 'success' });
    }
    if (!hasCfdi(movement)) {
        badges.push({ label: 'Sin CFDI', tone: 'danger' });
    } else {
        badges.push({ label: 'CFDI', tone: 'info' });
    }
    if (flow === 'ingreso') {
        badges.push({ label: 'Ingreso', tone: 'success' });
    } else if (flow === 'egreso') {
        badges.push({ label: 'Egreso', tone: 'danger' });
    }
    if (isPPD(movement)) {
        badges.push({ label: 'PPD', tone: 'warning' });
    }
    if (isIntlWithoutCfdi(movement)) {
        badges.push({ label: 'Internacional', tone: 'info' });
    }
    const tags = movement?.badges || movement?.tags || movement?.metadata?.tags || [];
    tags.forEach((tag) => {
        const label = tag?.label || tag;
        if (!label) return;
        if (/propias|transferencia interna/i.test(label)) {
            badges.push({ label: 'Propias', tone: 'success' });
        }
        if (/comision|comisión/i.test(label)) {
            badges.push({ label: 'Comisión', tone: 'info' });
        }
    });
    return badges;
};

const mapMovementToRow = (movement) => {
    const id = movement?.movement_id || movement?.id || movement?.uuid || movement?.transaction_id || `mov-${Math.random().toString(36).slice(2)}`;
    const amount = toNumber(movement?.amount ?? movement?.monto, 0);
    const currency = String(movement?.currency || movement?.moneda || 'MXN').toUpperCase();
    const date = movement?.movement_date || movement?.fecha || movement?.date || movement?.fecha_movimiento || null;
    const description = movement?.bank_description || movement?.description || movement?.descripcion || 'Movimiento bancario';
    const suggestionText = movement?.suggestion || movement?.ai_summary || movement?.best_match_description || movement?.matched_expense_description || '';
    const flow = classifyFlow(movement);
    const confidence = readConfidence(movement);

    const rawSuggestions = movement?.ai_suggestions || movement?.suggestions || movement?.candidates || [];
    const suggestions = rawSuggestions
        .map(mapSuggestion)
        .filter(Boolean);

    if (movement?.ai_top_match) {
        const topMatch = mapSuggestion(movement.ai_top_match);
        if (topMatch) suggestions.unshift(topMatch);
    }

    const invoice = mapInvoice(movement);
    const ppd = movement?.ppd || movement?.ppd_metadata || null;
    const bankLongDescription = movement?.long_description || movement?.descripcion_larga || movement?.bank_long_description || description;
    const state = String(movement?.state || 'PENDIENTE').toUpperCase();
    const conciliated = state === 'CONCILIADO';

    const { accountId, accountLabel } = resolveAccountMetadata(movement);

    return {
        id,
        raw: movement,
        date,
        period: date ? String(date).slice(0, 7) : null,
        description,
        bankLongDescription,
        amount,
        currency,
        accountId,
        accountLabel,
        suggestion: suggestionText || suggestions?.[0]?.title || '',
        confidence: Math.round(confidence * 100),
        badges: detectBadges(movement, flow),
        conciliated,
        hasCfdi: hasCfdi(movement),
        flow,
        invoice,
        ppd,
        suggestions,
        metadata: movement?.metadata || {},
        reconciliationStatus: movement?.reconciliation_status || null,
        state,
        onGotoStatement: movement?.goto_statement ? () => movement.goto_statement(movement) : movement?.onGotoStatement,
    };
};

const Badge = ({ children, tone = 'neutral' }) => (
    <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border ${
            tone === 'success'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : tone === 'warning'
                ? 'bg-amber-50 text-amber-700 border-amber-200'
                : tone === 'danger'
                ? 'bg-red-50 text-red-700 border-red-200'
                : tone === 'info'
                ? 'bg-blue-50 text-blue-700 border-blue-200'
                : 'bg-slate-50 text-slate-700 border-slate-200'
        }`}
    >
        {children}
    </span>
);

const Kpi = ({ label, value, hint, tone = 'neutral' }) => (
    <div
        className={`flex flex-col gap-1 rounded-2xl p-4 border shadow-sm bg-white ${
            tone === 'success' ? 'border-emerald-200' : tone === 'danger' ? 'border-red-200' : 'border-slate-200'
        }`}
    >
        <div className="text-slate-500 text-xs uppercase tracking-wide">{label}</div>
        <div className="text-2xl font-semibold">{value}</div>
        {hint && <div className="text-slate-400 text-xs">{hint}</div>}
    </div>
);

const FlowFilter = ({ value, onChange }) => (
    <div className="inline-flex items-center gap-1 border rounded-xl p-1 bg-white">
        {[
            { key: 'all', label: 'Todo' },
            { key: 'ingreso', label: 'Ingresos' },
            { key: 'egreso', label: 'Egresos' },
        ].map((opt) => (
            <button
                key={opt.key}
                onClick={() => onChange(opt.key)}
                className={`px-3 py-1.5 text-sm rounded-lg ${value === opt.key ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'}`}
            >
                {opt.label}
            </button>
        ))}
    </div>
);

const StatusFilter = ({ value, onChange }) => (
    <div className="inline-flex items-center gap-1 border rounded-xl p-1 bg-white">
        {[
            { key: 'all', label: 'Todos' },
            { key: 'conciliated', label: 'Conciliados' },
            { key: 'pending', label: 'Por conciliar' },
        ].map((opt) => (
            <button
                key={opt.key}
                onClick={() => onChange(opt.key)}
                className={`px-3 py-1.5 text-sm rounded-lg ${value === opt.key ? 'bg-emerald-600 text-white' : 'hover:bg-slate-50'}`}
            >
                {opt.label}
            </button>
        ))}
    </div>
);

const Toolbar = ({
    flowFilter,
    setFlowFilter,
    onAutoConciliate,
    autoConciliating,
    onUploadMovements,
    onOpenSatModal,
    onExport,
}) => (
    <div className="flex flex-wrap items-center gap-2">
        <button
            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 text-white px-3.5 py-2 text-sm shadow hover:bg-black disabled:opacity-60"
            onClick={onAutoConciliate}
            disabled={autoConciliating}
        >
            <i className="fas fa-bolt w-4"></i>
            {autoConciliating ? 'Auto-conciliando…' : 'Auto-Conciliar'}
        </button>
        <button
            className="inline-flex items-center gap-2 rounded-xl bg-white border px-3 py-2 text-sm hover:bg-slate-50"
            onClick={onUploadMovements}
        >
            <i className="fas fa-upload w-4"></i> Subir Movimientos
        </button>
        <button
            className="inline-flex items-center gap-2 rounded-xl bg-white border px-3 py-2 text-sm hover:bg-slate-50"
            onClick={onOpenSatModal}
        >
            <i className="fas fa-file-import w-4"></i> Importar CFDI SAT
        </button>
        <button
            className="inline-flex items-center gap-2 rounded-xl bg-white border px-3 py-2 text-sm hover:bg-slate-50"
            onClick={onExport}
        >
            <i className="fas fa-file-export w-4"></i> Exportar
        </button>
        <div className="ml-auto flex items-center gap-2">
            <FlowFilter value={flowFilter} onChange={setFlowFilter} />
            <div className="relative">
                <i className="fas fa-search w-4 h-4 text-slate-400 absolute left-3 top-2.5"></i>
                <input
                    placeholder="Buscar (RFC, UUID, descripción)"
                    className="pl-9 pr-3 py-2 border rounded-xl text-sm w-72 focus:ring-2 focus:ring-slate-300 outline-none"
                    onChange={(event) => {
                        const value = event.target.value.toLowerCase();
                        const customEvent = new CustomEvent('bank-search', { detail: { value } });
                        window.dispatchEvent(customEvent);
                    }}
                />
            </div>
            <button className="inline-flex items-center gap-2 rounded-xl bg-white border px-3 py-2 text-sm hover:bg-slate-50">
                <i className="fas fa-filter w-4"></i> Filtros
            </button>
        </div>
    </div>
);

const ColumnHeader = ({ iconClass, title, subtitle, cta, tone = 'neutral' }) => (
    <div
        className={`flex items-center justify-between px-3 py-2 border-b ${
            tone === 'success'
                ? 'bg-emerald-50 border-emerald-200'
                : tone === 'warning'
                ? 'bg-amber-50 border-amber-200'
                : tone === 'danger'
                ? 'bg-red-50 border-red-200'
                : 'bg-slate-50 border-slate-200'
        }`}
    >
        <div className="flex items-center gap-2">
            <i className={`${iconClass} w-4 h-4`}></i>
            <div className="font-medium">{title}</div>
            {subtitle && <div className="text-slate-500 text-xs">{subtitle}</div>}
        </div>
        {cta}
    </div>
);

const SmartTableHeader = () => (
    <div className="grid grid-cols-[28px_110px_1fr_140px_220px_110px_200px_110px] gap-3 px-3 py-2 text-xs text-slate-500 border-b bg-slate-50">
        <div />
        <div>Fecha</div>
        <div>Descripción banco</div>
        <div className="text-right pr-4">Monto</div>
        <div>Sugerencia</div>
        <div>Confianza</div>
        <div>Badges</div>
        <div className="text-right">Acción</div>
    </div>
);

const Row = ({ row, onOpenDrawer, expandedId, setExpandedId }) => {
    const isOpen = expandedId === row.id;
    const ppdInfo = row.ppd ? computePPDInfo(row) : null;
    const isIntl = isIntlWithoutCfdi(row.raw);

    return (
        <div className="border-b">
            <div className="grid grid-cols-[28px_110px_1fr_140px_220px_110px_200px_110px] items-center gap-3 px-3 py-3 hover:bg-slate-50">
                <button
                    aria-label={isOpen ? 'Contraer' : 'Expandir'}
                    className="inline-flex items-center justify-center w-6 h-6 rounded hover:bg-slate-100 border"
                    onClick={() => setExpandedId(isOpen ? null : row.id)}
                >
                    <span className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}>⌄</span>
                </button>
                <div className="text-sm text-slate-600">{formatDate(row.date)}</div>
                <div className="text-sm font-medium text-slate-800 truncate" title={row.description}>
                    {row.description}
                </div>
                <div className="text-sm tabular-nums font-semibold text-slate-900 text-right pr-4">
                    {formatCurrency(row.amount, row.currency)}
                </div>
                <div className="text-sm text-slate-700 truncate" title={row.suggestion}>
                    {row.suggestion || 'Sin sugerencia'}
                </div>
                <div className="text-sm text-slate-700">{row.confidence}%</div>
                <div className="flex items-center gap-1 flex-wrap">
                    {row.badges.map((badge, index) => (
                        <Badge key={`${row.id}-badge-${index}`} tone={badge.tone}>
                            {badge.label}
                        </Badge>
                    ))}
                </div>
                <div className="flex justify-end">
                    <button
                        className="inline-flex items-center gap-1 rounded-lg bg-slate-900 text-white px-3 py-1.5 text-xs hover:bg-black"
                        onClick={(event) => {
                            event.stopPropagation();
                            onOpenDrawer?.(row);
                        }}
                    >
                        Conciliar <i className="fas fa-chevron-right w-3 h-3"></i>
                    </button>
                </div>
            </div>

            {isOpen && (
                <div className="px-10 pb-4 bg-slate-50/60">
                    <div className="flex items-start justify-between gap-6">
                        <div className="flex-1">
                            <div className="text-xs uppercase text-slate-500">Descripción del banco</div>
                            <div className="text-sm text-slate-800 whitespace-pre-wrap">
                                {row.bankLongDescription || row.description}
                            </div>
                        </div>
                        {row.onGotoStatement && (
                            <div>
                                <button
                                    className="text-xs underline text-slate-700 hover:text-slate-900"
                                    onClick={() => row.onGotoStatement(row)}
                                >
                                    Ir al renglón en el extracto →
                                </button>
                            </div>
                        )}
                    </div>

                    {row.ppd && ppdInfo && (
                        <div className="mt-4 rounded-xl border bg-white overflow-hidden">
                            <div className="px-3 py-2 border-b bg-amber-50 text-xs text-amber-700 uppercase flex items-center gap-2">
                                <i className="fas fa-badge-percent"></i>
                                Pago PPD · Progreso {ppdInfo.percent}% · Saldo: {formatCurrency(ppdInfo.remaining, row.currency)} · Parcialidad prevista #{ppdInfo.nextParcialidad}
                            </div>
                            <div className="p-3 space-y-3 text-sm">
                                <div>
                                    <div className="h-2 bg-slate-200 rounded">
                                        <div className="h-2 rounded bg-slate-900" style={{ width: `${ppdInfo.percent}%` }} />
                                    </div>
                                    <div className="mt-1 text-slate-500">
                                        Pagado {formatCurrency(ppdInfo.paid, row.currency)} de {formatCurrency(ppdInfo.total, row.currency)} ({ppdInfo.percent}%) · Este movimiento: {ppdInfo.currentPaymentPercent}%
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs uppercase text-slate-500 mb-1">Complementos de pago registrados</div>
                                    {ppdInfo.complements.length ? (
                                        <table className="w-full text-xs">
                                            <thead className="bg-slate-50">
                                                <tr>
                                                    <th className="text-left p-2">Fecha</th>
                                                    <th className="text-left p-2">UUID</th>
                                                    <th className="text-right p-2">Parcialidad</th>
                                                    <th className="text-right p-2">Imp. Pagado</th>
                                                    <th className="text-right p-2">Saldo posterior</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {ppdInfo.complements.map((item, index) => (
                                                    <tr key={index} className="border-t">
                                                        <td className="p-2">{item.date || item.fecha || '—'}</td>
                                                        <td className="p-2 truncate" title={item.uuid}>{item.uuid || '—'}</td>
                                                        <td className="p-2 text-right">{item.numParcialidad || item.parcialidad || '—'}</td>
                                                        <td className="p-2 text-right tabular-nums">{formatCurrency(item.amountPaid || item.amount_paid || item.importe_pagado, row.currency)}</td>
                                                        <td className="p-2 text-right tabular-nums">{formatCurrency(item.remainingBalance || item.saldo_posterior, row.currency)}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    ) : (
                                        <div className="text-slate-500">Aún no se registran complementos de pago para este CFDI.</div>
                                    )}
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Registrar complemento</button>
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Conciliar provisional</button>
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Ver en SAT</button>
                                </div>
                            </div>
                        </div>
                    )}

                    {isIntl && (
                        <div className="mt-4 rounded-xl border bg-white overflow-hidden">
                            <div className="px-3 py-2 border-b bg-blue-50 text-xs text-blue-700 uppercase flex items-center gap-2">
                                <i className="fas fa-globe"></i>
                                Servicio/Producto Internacional (sin CFDI)
                            </div>
                            <div className="p-3 space-y-3 text-sm">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div>
                                        <div className="text-slate-500 text-xs uppercase">Detección</div>
                                        <ul className="list-disc ml-4 text-slate-700">
                                            {row.currency && <li>Moneda detectada: <strong>{row.currency}</strong></li>}
                                            <li>Merchant: <strong>{row.description}</strong></li>
                                            <li>Heurística: Moneda≠MXN o merchant internacional</li>
                                        </ul>
                                    </div>
                                    <div>
                                        <div className="text-slate-500 text-xs uppercase">Acciones recomendadas</div>
                                        <ul className="list-disc ml-4 text-slate-700">
                                            <li>Adjuntar <strong>factura extranjera</strong> o recibo</li>
                                            <li>Registrar <strong>IVA de importación</strong> si aplica</li>
                                            <li>Marcar como <strong>no deducible</strong> si no hay soporte válido</li>
                                        </ul>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Adjuntar factura extranjera</button>
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Crear póliza internacional</button>
                                    <button className="rounded-lg border px-3 py-1.5 text-xs">Marcar como no deducible</button>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="rounded-xl border bg-white overflow-hidden">
                            <div className="px-3 py-2 border-b bg-slate-50 text-xs text-slate-500 uppercase">CFDI sugerido</div>
                            <div className="p-3 space-y-2">
                                <div className="text-sm font-medium text-slate-800">{row.invoice?.supplierName || row.suggestion || 'Sin CFDI'}</div>
                                {row.invoice && (
                                    <table className="w-full text-sm">
                                        <tbody>
                                            <tr className="border-t">
                                                <td className="p-1 text-slate-500">UUID</td>
                                                <td className="p-1 text-right font-medium">{row.invoice.uuid || '—'}</td>
                                            </tr>
                                            {row.invoice.paymentMethod && (
                                                <tr className="border-t">
                                                    <td className="p-1 text-slate-500">Método de pago</td>
                                                    <td className="p-1 text-right font-medium">{row.invoice.paymentMethod}</td>
                                                </tr>
                                            )}
                                            <tr className="border-t">
                                                <td className="p-1 text-slate-500">Subtotal</td>
                                                <td className="p-1 text-right tabular-nums">{formatCurrency(row.invoice.subtotal, row.currency)}</td>
                                            </tr>
                                            <tr className="border-t">
                                                <td className="p-1 text-slate-500">IVA</td>
                                                <td className="p-1 text-right tabular-nums">{formatCurrency(row.invoice.taxes.iva, row.currency)}</td>
                                            </tr>
                                            <tr className="border-t">
                                                <td className="p-1 text-slate-500">IEPS</td>
                                                <td className="p-1 text-right tabular-nums">{formatCurrency(row.invoice.taxes.ieps, row.currency)}</td>
                                            </tr>
                                            <tr className="border-t">
                                                <td className="p-1 text-slate-500">Retenciones</td>
                                                <td className="p-1 text-right tabular-nums">{formatCurrency(row.invoice.taxes.retenciones, row.currency)}</td>
                                            </tr>
                                            <tr className="border-t bg-slate-50 font-semibold">
                                                <td className="p-1">Total CFDI</td>
                                                <td className="p-1 text-right tabular-nums">{formatCurrency(row.invoice.total, row.currency)}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                )}
                            </div>
                        </div>
                        <div className="rounded-xl border bg-white overflow-hidden">
                            <div className="px-3 py-2 border-b bg-slate-50 text-xs text-slate-500 uppercase">Contraste vs banco</div>
                            <div className="p-3 space-y-1 text-sm">
                                {row.ppd ? (
                                    <>
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Monto en banco (este pago)</span>
                                            <span className="font-semibold tabular-nums">{formatCurrency(row.amount, row.currency)}</span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Complemento estimado a conciliar</span>
                                            <span className="font-semibold tabular-nums">{formatCurrency(row.amount, row.currency)}</span>
                                        </div>
                                        <div className="flex items-center justify-between border-t pt-2 mt-2">
                                            <span className="text-slate-500">Saldo insoluto tras este pago</span>
                                            <span className="font-semibold tabular-nums">{formatCurrency(Math.max(0, ppdInfo.remaining - row.amount), row.currency)}</span>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Monto en banco</span>
                                            <span className="font-semibold tabular-nums">{formatCurrency(row.amount, row.currency)}</span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Total CFDI</span>
                                            <span className="font-semibold tabular-nums">{formatCurrency(row.invoice?.total || 0, row.currency)}</span>
                                        </div>
                                        <div className="flex items-center justify-between border-t pt-2 mt-2">
                                            <span className="text-slate-500">Diferencia</span>
                                            <span className={`font-semibold tabular-nums ${((row.invoice?.total || 0) - row.amount) === 0 ? 'text-emerald-700' : 'text-amber-700'}`}>
                                                {formatCurrency((row.invoice?.total || 0) - row.amount, row.currency)}
                                            </span>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="mt-4 rounded-xl border bg-white overflow-hidden">
                        <div className="px-3 py-2 border-b bg-slate-50 text-xs text-slate-500 uppercase">Póliza contable (previa)</div>
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50">
                                <tr>
                                    <th className="text-left p-2 font-medium text-slate-600">Cuenta</th>
                                    <th className="text-left p-2 font-medium text-slate-600">Concepto</th>
                                    <th className="text-right p-2 font-medium text-slate-600">Debe</th>
                                    <th className="text-right p-2 font-medium text-slate-600">Haber</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(row.policyPreview || [
                                    { account: '572-01 Comisiones Bancarias', concept: 'Cargo automático banco', debit: Math.abs(row.amount), credit: 0 },
                                    { account: '102 Bancos', concept: 'Salida de fondos', debit: 0, credit: Math.abs(row.amount) },
                                ]).map((line, index) => (
                                    <tr key={index} className="border-t">
                                        <td className="p-2">{line.account || '—'}</td>
                                        <td className="p-2">{line.concept || '—'}</td>
                                        <td className="p-2 text-right tabular-nums">{formatCurrency(line.debit, row.currency)}</td>
                                        <td className="p-2 text-right tabular-nums">{formatCurrency(line.credit, row.currency)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

const Drawer = ({ open, onClose, row, onConciliate, conciliateLoading }) => {
    if (!open || !row) return null;
    return (
        <div className="fixed inset-0 z-40">
            <div className="absolute inset-0 bg-black/30" onClick={onClose} />
            <div className="absolute right-0 top-0 h-full w-full max-w-[520px] bg-white shadow-2xl p-6 overflow-y-auto">
                <div className="flex items-start justify-between">
                    <div>
                        <div className="text-xs uppercase text-slate-500">Revisión de movimiento</div>
                        <div className="text-lg font-semibold text-slate-900 mt-1">
                            {formatCurrency(row.amount, row.currency)} · {formatDate(row.date)}
                        </div>
                        <div className="text-slate-600 mt-1">{row.description}</div>
                    </div>
                    <button className="text-slate-500 hover:text-slate-800" onClick={onClose}>
                        ✕
                    </button>
                </div>

                <div className="mt-6 space-y-3">
                    <div className="text-xs font-medium text-slate-500">Mejores coincidencias</div>
                    {row.suggestions.length === 0 && (
                        <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                            Sin sugerencias disponibles para este movimiento.
                        </div>
                    )}
                    {row.suggestions.map((suggestion, index) => (
                        <div key={index} className="rounded-xl border p-3 hover:bg-slate-50">
                            <div className="flex items-center justify-between">
                                <div className="font-medium text-slate-800 truncate">{suggestion.title}</div>
                                <Badge tone={index === 0 ? 'success' : 'neutral'}>{suggestion.score}%</Badge>
                            </div>
                            <div className="text-sm text-slate-600 mt-1">{suggestion.detail || 'Sin detalle adicional'}</div>
                            <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                                <span className="inline-flex items-center gap-1">
                                    <i className="fas fa-scale-unbalanced"></i> Monto
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <i className="fas fa-calendar"></i> Fecha
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <i className="fas fa-link"></i> Referencia
                                </span>
                            </div>
                            <div className="mt-3 flex gap-2">
                                <button
                                    className="rounded-lg bg-slate-900 text-white px-3 py-1.5 text-xs disabled:opacity-60"
                                    onClick={() => onConciliate(row, suggestion)}
                                    disabled={conciliateLoading}
                                >
                                    {conciliateLoading ? 'Conciliando…' : 'Conciliar con esta'}
                                </button>
                                <button className="rounded-lg border px-3 py-1.5 text-xs">Ver CFDI</button>
                            </div>
                        </div>
                    ))}
                </div>

                <div className="mt-6 space-y-2">
                    <div className="text-xs font-medium text-slate-500">Acciones rápidas</div>
                    <div className="flex flex-wrap gap-2">
                        <button className="rounded-lg border px-3 py-1.5 text-xs">Dividir / Prorratear</button>
                        <button className="rounded-lg border px-3 py-1.5 text-xs">Vincular CFDI manual</button>
                        <button className="rounded-lg border px-3 py-1.5 text-xs">Marcar excepción</button>
                        <button className="rounded-lg border px-3 py-1.5 text-xs">Crear póliza sugerida</button>
                    </div>
                </div>

                <div className="mt-6">
                    <div className="text-xs font-medium text-slate-500">Póliza simulada</div>
                    <div className="mt-2 rounded-xl border overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50">
                                <tr>
                                    <th className="text-left p-2 font-medium text-slate-600">Cuenta</th>
                                    <th className="text-left p-2 font-medium text-slate-600">Descripción</th>
                                    <th className="text-right p-2 font-medium text-slate-600">Debe</th>
                                    <th className="text-right p-2 font-medium text-slate-600">Haber</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr className="border-t">
                                    <td className="p-2">572-01 Comisiones Bancarias</td>
                                    <td className="p-2">Cargo automático banco</td>
                                    <td className="p-2 text-right tabular-nums">{formatCurrency(Math.abs(row.amount), row.currency)}</td>
                                    <td className="p-2 text-right tabular-nums">0.00</td>
                                </tr>
                                <tr className="border-t">
                                    <td className="p-2">102 Bancos</td>
                                    <td className="p-2">Salida de fondos</td>
                                    <td className="p-2 text-right tabular-nums">0.00</td>
                                    <td className="p-2 text-right tabular-nums">{formatCurrency(Math.abs(row.amount), row.currency)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div className="mt-6 flex items-center gap-2">
                    <button
                        className="inline-flex items-center gap-2 rounded-xl bg-slate-900 text-white px-4 py-2 text-sm disabled:opacity-60"
                        onClick={() => onConciliate(row, row.suggestions[0] || null)}
                        disabled={conciliateLoading}
                    >
                        <i className="fas fa-check-circle"></i>
                        {conciliateLoading ? 'Conciliando…' : 'Conciliar'}
                    </button>
                    <button className="inline-flex items-center gap-2 rounded-xl bg-white border px-4 py-2 text-sm">
                        <i className="fas fa-xmark-circle"></i> Reabrir / Descartar
                    </button>
                </div>
            </div>
        </div>
    );
};

const SatImportModal = ({ isOpen, onClose, onProcessed }) => {
    const [files, setFiles] = useState([]);
    const [processing, setProcessing] = useState(false);
    const [results, setResults] = useState([]);
    const [summary, setSummary] = useState(null);
    const [error, setError] = useState(null);
    const totalSizeMb = files.reduce((sum, file) => sum + file.size, 0) / (1024 * 1024);

    useEffect(() => {
        if (!isOpen) {
            setFiles([]);
            setProcessing(false);
            setResults([]);
            setSummary(null);
            setError(null);
        }
    }, [isOpen]);

    const handleFileChange = (event) => {
        const selected = Array.from(event.target.files || []);
        setFiles(selected);
        setResults([]);
        setSummary(null);
        setError(null);
    };

    const clearSelection = () => {
        setFiles([]);
        setResults([]);
        setSummary(null);
        setError(null);
    };

    const processFiles = async () => {
        if (processing || files.length === 0) return;
        setProcessing(true);
        setError(null);

        const companyId = getActiveCompanyId();
        const invoicesPayload = [];
        const partialResults = [];

        try {
            for (const file of files) {
                const extension = (file.name.split('.').pop() || '').toLowerCase();
                if (extension !== 'xml') {
                    partialResults.push({ filename: file.name, status: 'unsupported', message: 'Solo se admiten archivos XML.' });
                    continue;
                }

                const rawXml = await file.text();
                const formData = new FormData();
                formData.append('file', file, file.name);

                let parsed;
                try {
                    const response = await fetch('/invoices/parse', { method: 'POST', body: formData });
                    if (!response.ok) {
                        const text = await response.text();
                        partialResults.push({ filename: file.name, status: 'error', message: `Error interpretando CFDI: ${text || response.status}` });
                        continue;
                    }
                    parsed = await response.json();
                } catch (parseError) {
                    console.error('Error parsing CFDI', parseError);
                    partialResults.push({ filename: file.name, status: 'error', message: 'Error interno al procesar el CFDI.' });
                    continue;
                }

                const metadata = parsed?.metadata || {};
                invoicesPayload.push({
                    filename: file.name,
                    uuid: metadata.uuid || parsed.uuid || null,
                    total: toNumber(parsed.total, 0),
                    issued_at: metadata.fecha_emision || metadata.fecha || parsed.fecha_emision || parsed.issued_at || null,
                    rfc_emisor: metadata?.emisor?.rfc || parsed.rfc_emisor || null,
                    raw_xml: rawXml,
                    metadata,
                });
            }

            let matchResults = [];
            if (invoicesPayload.length > 0) {
                try {
                    const response = await fetch('/invoices/bulk-match', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            company_id: companyId,
                            invoices: invoicesPayload,
                            auto_mark_invoiced: true,
                        }),
                    });
                    if (!response.ok) {
                        const text = await response.text();
                        partialResults.push({ filename: undefined, status: 'error', message: `Error conciliando facturas: ${text || response.status}` });
                    } else {
                        const payload = await response.json();
                        matchResults = Array.isArray(payload?.results) ? payload.results : [];
                    }
                } catch (matchError) {
                    console.error('Error matching invoices', matchError);
                        partialResults.push({ filename: undefined, status: 'error', message: 'Error interno al conciliar las facturas.' });
                }
            }

            const combinedResults = [...matchResults, ...partialResults];
            setResults(combinedResults);
            setSummary({
                total: files.length,
                sent_to_match: invoicesPayload.length,
                linked: combinedResults.filter((item) => item.status === 'linked').length,
                needs_review: combinedResults.filter((item) => item.status === 'needs_review').length,
                errors: combinedResults.filter((item) => item.status === 'error').length,
                unsupported: combinedResults.filter((item) => item.status === 'unsupported').length,
            });
            if (onProcessed) onProcessed();
        } catch (err) {
            console.error('SAT import error', err);
            setError('Ocurrió un error procesando los CFDI. Intenta nuevamente.');
        } finally {
            setProcessing(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
                <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                    <div>
                        <div className="text-xs uppercase text-slate-500">Carga de CFDI</div>
                        <h3 className="text-lg font-semibold text-slate-900">Importar CFDI desde SAT</h3>
                        <p className="text-sm text-slate-500">Analiza archivos XML y concílialos en lote contra tus gastos.</p>
                    </div>
                    <button className="text-slate-400 hover:text-slate-600" onClick={onClose}>
                        <i className="fas fa-times text-xl"></i>
                    </button>
                </div>

                <div className="px-6 py-6 space-y-5">
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 text-sm text-emerald-800">
                        <p className="font-medium">📤 Carga masiva o individual</p>
                        <p className="mt-1">Aceptamos CFDI XML (PDF se ignoran). Al finalizar verás cuántas facturas quedaron conciliadas, pendientes o con error.</p>
                    </div>

                    <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center">
                        <input
                            type="file"
                            multiple
                            accept=".xml"
                            className="hidden"
                            id="sat-invoice-input"
                            onChange={handleFileChange}
                        />
                        <label htmlFor="sat-invoice-input" className="cursor-pointer block">
                            <i className="fas fa-cloud-upload-alt text-4xl text-slate-400 mb-4"></i>
                            <p className="text-lg font-semibold text-slate-700">Arrastra o haz clic para seleccionar tus CFDI</p>
                            <p className="text-sm text-slate-500">Formato soportado: XML</p>
                        </label>
                        {files.length > 0 && (
                            <div className="mt-6 text-left space-y-2">
                                <div className="flex items-center justify-between text-sm text-slate-600">
                                    <span className="font-semibold">Archivos seleccionados ({files.length})</span>
                                    <span>{totalSizeMb.toFixed(2)} MB totales</span>
                                </div>
                                <div className="space-y-2">
                                    {files.map((file) => (
                                        <div
                                            key={file.name}
                                            className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                                        >
                                            <span className="font-medium text-slate-700 truncate">{file.name}</span>
                                            <span className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm">{error}</div>
                    )}

                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <button
                            type="button"
                            className="px-4 py-2 text-sm text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-40"
                            onClick={clearSelection}
                            disabled={processing || files.length === 0}
                        >
                            <i className="fas fa-eraser mr-2"></i>
                            Limpiar selección
                        </button>
                        <button
                            type="button"
                            className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                            onClick={processFiles}
                            disabled={processing || files.length === 0}
                        >
                            <i className={`fas ${processing ? 'fa-spinner fa-spin' : 'fa-play'} mr-2`}></i>
                            {processing ? 'Procesando facturas...' : 'Procesar facturas seleccionadas'}
                        </button>
                    </div>

                    {summary && (
                        <div className="border border-emerald-200 bg-emerald-50 rounded-lg p-4 text-sm text-emerald-800 space-y-1">
                            <p className="font-semibold">Resumen</p>
                            <p>Seleccionados: {summary.total}</p>
                            <p>Conciliados automáticamente: {summary.linked}</p>
                            <p>Revisar manualmente: {summary.needs_review}</p>
                            <p>Errores: {summary.errors}</p>
                            <p>No soportados: {summary.unsupported}</p>
                        </div>
                    )}

                    {results.length > 0 && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <h4 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                                    <i className="fas fa-clipboard-list text-slate-600"></i>
                                    Resultados del procesamiento
                                </h4>
                                <button
                                    type="button"
                                    className="inline-flex items-center gap-2 px-3 py-2 text-sm text-white bg-slate-900 rounded-lg hover:bg-black"
                                    onClick={() => {
                                        const headers = ['Archivo', 'Estado', 'Mensaje'];
                                        const rows = results.map((item) => [item.filename || '—', item.status || '—', item.message || '—']);
                                        const csv = [headers.join(','), ...rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))].join('\n');
                                        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                                        const url = URL.createObjectURL(blob);
                                        const link = document.createElement('a');
                                        link.href = url;
                                        link.setAttribute('download', `resultados-cfdi-${Date.now()}.csv`);
                                        document.body.appendChild(link);
                                        link.click();
                                        document.body.removeChild(link);
                                        URL.revokeObjectURL(url);
                                    }}
                                >
                                    <i className="fas fa-download"></i>
                                    Descargar reporte
                                </button>
                            </div>

                            <div className="border border-slate-200 rounded-lg">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50">
                                        <tr>
                                            <th className="text-left p-2">Archivo</th>
                                            <th className="text-left p-2">Estado</th>
                                            <th className="text-left p-2">Mensaje</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {results.map((item, index) => (
                                            <tr key={index} className="border-t">
                                                <td className="p-2 text-slate-700">{item.filename || '—'}</td>
                                                <td className="p-2 text-slate-600 uppercase text-xs">{item.status || '—'}</td>
                                                <td className="p-2 text-slate-500">{item.message || item.note || '—'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};


const buildGroups = (rows) => {
    return {
        aiReady: rows.filter((row) => !row.conciliated && row.confidence >= 85 && row.hasCfdi),
        manual: rows.filter((row) => !row.conciliated && row.confidence < 85 && row.hasCfdi && !row.badges.some((b) => b.label === 'Sin CFDI')),
        ppd: rows.filter((row) => isPPD(row.raw)),
        intl: rows.filter((row) => isIntlWithoutCfdi(row.raw)),
        missingCfdi: rows.filter((row) => row.badges.some((badge) => badge.label === 'Sin CFDI') && !isIntlWithoutCfdi(row.raw)),
        transfers: rows.filter((row) => row.badges.some((badge) => /Propias/i.test(badge.label))),
    };
};

const BankReconciliationApp = () => {
    const [rows, setRows] = useState([]);
    const [availableAccounts, setAvailableAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [flowFilter, setFlowFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [selectedPeriod, setSelectedPeriod] = useState('all');
    const [selectedAccount, setSelectedAccount] = useState('all');
    const [expandedId, setExpandedId] = useState(null);
    const [drawerRow, setDrawerRow] = useState(null);
    const [autoConciliating, setAutoConciliating] = useState(false);
    const [satModalOpen, setSatModalOpen] = useState(false);
    const [conciliateLoading, setConciliateLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [summary, setSummary] = useState(null);

    const loadMovements = useCallback(async () => {
        const companyId = getActiveCompanyId();
        setLoading(true);
        setError(null);

        const buildParams = (overrideCompanyId) => {
            const params = new URLSearchParams({
                include_summary: 'true',
                limit: '500',
            });
            const effectiveCompany = overrideCompanyId ?? companyId;
            if (effectiveCompany && !['', 'default', 'all'].includes(effectiveCompany)) {
                params.set('company_id', effectiveCompany);
            } else if (effectiveCompany === 'all') {
                params.set('company_id', 'all');
            }
            return params;
        };

        const fetchMovements = async (params) => {
            const response = await fetch(`/bank_reconciliation/movements?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`Error ${response.status}`);
            }
            return response.json();
        };

        try {
            const payload = await fetchMovements(buildParams());
            const movementsResponse = Array.isArray(payload) ? payload : Array.isArray(payload?.movements) ? payload.movements : [];
            const accountsPayload = Array.isArray(payload?.accounts)
                ? payload.accounts
                    .map((account) => {
                        if (!account) return null;
                        const rawId = account.id ?? account.value ?? account.account_id;
                        if (rawId === undefined || rawId === null) return null;
                        return {
                            ...account,
                            id: String(rawId),
                            has_movements: Boolean(account.has_movements),
                        };
                    })
                    .filter(Boolean)
                : [];

            setAvailableAccounts(accountsPayload);

            if (movementsResponse.length === 0) {
                setRows([]);
            } else {
                const normalized = movementsResponse.map(mapMovementToRow);
                setRows(normalized);
            }
            setSummary(payload?.summary || null);
        } catch (err) {
            console.error('Error loading movements', err);
            setError('No se pudieron cargar los movimientos bancarios.');
            setRows([]);
            setAvailableAccounts([]);
            setSummary(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadMovements();
    }, [loadMovements]);

    useEffect(() => {
        const handler = (event) => {
            setSearchTerm(event.detail.value);
        };
        window.addEventListener('bank-search', handler);
        return () => window.removeEventListener('bank-search', handler);
    }, []);

    const periodOptions = useMemo(() => {
        const unique = new Set();
        rows.forEach((row) => {
            if (row.period) {
                unique.add(row.period);
            }
        });
        return Array.from(unique).sort().reverse();
    }, [rows]);

    const periodRows = useMemo(() => {
        if (!selectedPeriod || selectedPeriod === 'all') return rows;
        return rows.filter((row) => row.period === selectedPeriod);
    }, [rows, selectedPeriod]);

    const accountOptions = useMemo(() => {
        const map = new Map();

        availableAccounts.forEach((account) => {
            if (!account || account.id === undefined || account.id === null) return;
            const value = String(account.id);
            const baseLabel = (account.label || account.name || `Cuenta ${value}`).trim();
            const label = account.has_movements ? baseLabel : `${baseLabel} (Sin movimientos)`;
            map.set(value, {
                value,
                label,
                baseLabel,
                hasMovements: Boolean(account.has_movements),
            });
        });

        rows.forEach((row) => {
            if (!row.accountId) return;
            const value = String(row.accountId);
            if (map.has(value)) return;
            const baseLabel = (row.accountLabel || `Cuenta ${value}`).trim();
            map.set(value, {
                value,
                label: baseLabel,
                baseLabel,
                hasMovements: true,
            });
        });

        return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label));
    }, [rows, availableAccounts]);

    const accountOptionMap = useMemo(() => {
        const map = new Map();
        accountOptions.forEach((option) => map.set(option.value, option));
        return map;
    }, [accountOptions]);
    const selectedAccountMeta = selectedAccount === 'all' ? null : accountOptionMap.get(selectedAccount);
    const headerAccount = selectedAccountMeta?.baseLabel ?? 'Todas las cuentas';
    const headerPeriod = selectedPeriod === 'all' ? 'Todos los periodos' : formatPeriodLabel(selectedPeriod);

    useEffect(() => {
        if (selectedAccount !== 'all' && !accountOptionMap.has(selectedAccount)) {
            setSelectedAccount('all');
        }
    }, [selectedAccount, accountOptionMap]);
    const filteredRows = useMemo(() => {
        return periodRows.filter((row) => {
            if (flowFilter !== 'all' && row.flow !== flowFilter) {
                return false;
            }
            if (statusFilter === 'conciliated' && !row.conciliated) {
                return false;
            }
            if (statusFilter === 'pending' && row.conciliated) {
                return false;
            }
            if (selectedAccount !== 'all' && row.accountId !== selectedAccount) {
                return false;
            }
            if (searchTerm) {
                const target = `${row.description} ${row.suggestion} ${row.invoice?.uuid || ''}`.toLowerCase();
                if (!target.includes(searchTerm)) {
                    return false;
                }
            }
            return true;
        });
    }, [periodRows, flowFilter, statusFilter, selectedAccount, searchTerm]);

    const groups = useMemo(() => buildGroups(filteredRows), [filteredRows]);

    const kpi = useMemo(() => {
        const usePeriod = selectedPeriod !== 'all';
        const baseRows = usePeriod ? periodRows : rows;
        const total = usePeriod ? baseRows.length : summary?.total ?? baseRows.length;
        const conciliated = usePeriod
            ? baseRows.filter((row) => row.conciliated).length
            : summary?.conciliated ?? baseRows.filter((row) => row.conciliated).length;
        const pending = total - conciliated;
        const autoMatch = total > 0
            ? Math.round((baseRows.filter((row) => row.confidence >= 85).length / total) * 100)
            : 0;

        const periodTotal = periodRows.length;
        const periodConciliated = periodRows.filter((row) => row.conciliated).length;
        let periodStatus = 'Sin datos';
        let periodTone = 'neutral';
        let periodHint = 'Sin movimientos en este periodo';

        if (periodTotal > 0) {
            if (periodConciliated === periodTotal) {
                periodStatus = 'Conciliado';
                periodTone = 'success';
                periodHint = 'Todo cuadrado este mes';
            } else if (periodConciliated === 0) {
                periodStatus = 'Pendiente';
                periodTone = 'danger';
                periodHint = 'Aún no hay conciliaciones registradas';
            } else {
                periodStatus = 'En progreso';
                periodTone = 'warning';
                periodHint = `${periodConciliated} de ${periodTotal} conciliados`;
            }
        }

        return {
            conciliated,
            pending,
            autoMatch,
            periodStatus,
            periodTone,
            periodHint,
        };
    }, [rows, periodRows, summary, selectedPeriod]);

    const handleAutoConciliate = async () => {
        setAutoConciliating(true);
        try {
            const response = await fetch('/bank_reconciliation/auto-reconcile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!response.ok) {
                throw new Error('Auto reconcile failed');
            }
            const result = await response.json();
            showToast(`Auto-conciliación completada: ${result.matched || 0} movimientos`, 'success');
            await loadMovements();
        } catch (err) {
            console.error('Auto reconcile error', err);
            showToast('Error en auto-conciliación', 'error');
        } finally {
            setAutoConciliating(false);
        }
    };

    const handleUploadMovements = () => {
        showToast('Feature en construcción: subida de movimientos', 'info');
    };

    const handleExport = () => {
        const headers = ['ID', 'Fecha', 'Descripción', 'Monto', 'Confianza', 'Estado'];
        const rowsCsv = rows.map((row) => [row.id, row.date, row.description, row.amount, `${row.confidence}%`, row.conciliated ? 'Conciliado' : 'Pendiente']);
        const csv = [headers.join(','), ...rowsCsv.map((cells) => cells.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `conciliacion-${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const handleConciliate = async (row, suggestion) => {
        if (conciliateLoading) return;
        setConciliateLoading(true);
        try {
            const movementId = row.raw?.movement_id || row.raw?.id || row.id;
            if (!movementId) throw new Error('movement_id missing');
            await fetch('/bank_reconciliation/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    movement_id: movementId,
                    decision: 'accepted',
                    score: suggestion?.score ?? row.confidence,
                    metadata: suggestion?.raw || {},
                }),
            });
            showToast('Movimiento conciliado correctamente', 'success');
            setDrawerRow(null);
            await loadMovements();
        } catch (err) {
            console.error('Conciliate error', err);
            showToast('No se pudo conciliar el movimiento', 'error');
        } finally {
            setConciliateLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-24">
                <div className="flex flex-col items-center gap-3 text-slate-600">
                    <i className="fas fa-spinner fa-spin text-2xl"></i>
                    Cargando conciliación bancaria...
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center py-24">
                <div className="bg-red-50 border border-red-200 text-red-600 px-6 py-4 rounded-lg">
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-100">
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <header className="page-header">
                    <div className="page-header__content">
                        <div className="page-header__meta">
                            <h1 className="page-header__title"><span aria-hidden="true">🔄</span> Conciliación Bancaria Inteligente</h1>
                            <p className="page-header__subtitle">Relaciona movimientos bancarios con CFDI y gastos para cerrar el ciclo financiero.</p>
                        </div>
                        <div className="page-header__actions">
                            <span className="badge-secondary">Banco → CFDI → Gasto</span>
                        </div>
                    </div>
                </header>
            </section>

            <div className="sticky top-0 z-30 border-b bg-white/90 backdrop-blur">
                <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
                    <div className="flex items-center gap-3">
                        <div>
                            <div className="text-xs text-slate-500 uppercase">Cuenta · Periodo</div>
                            <div className="text-lg font-semibold">{headerAccount} · {headerPeriod}</div>
                        </div>
                        <div className="h-8 w-px bg-slate-200" />
                        <div className="text-xs text-slate-500">Última ejecución: {new Date().toLocaleString('es-MX')}</div>
                    </div>
                    <Toolbar
                        flowFilter={flowFilter}
                        setFlowFilter={setFlowFilter}
                        onAutoConciliate={handleAutoConciliate}
                        autoConciliating={autoConciliating}
                        onUploadMovements={handleUploadMovements}
                        onOpenSatModal={() => setSatModalOpen(true)}
                        onExport={handleExport}
                    />
                    <div className="flex flex-wrap items-center gap-4">
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Periodo</label>
                            <select
                                value={selectedPeriod}
                                onChange={(event) => setSelectedPeriod(event.target.value)}
                                className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
                                disabled={!periodOptions.length}
                            >
                                <option value="all">Todos los periodos</option>
                                {periodOptions.map((period) => (
                                    <option key={period} value={period}>{formatPeriodLabel(period)}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Cuenta</label>
                            <select
                                value={selectedAccount}
                                onChange={(event) => setSelectedAccount(event.target.value)}
                                className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
                                disabled={!accountOptions.length}
                            >
                                <option value="all">Todas</option>
                                {accountOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex flex-col gap-1">
                            <span className="block text-xs font-semibold text-slate-500 uppercase">Estado</span>
                            <StatusFilter value={statusFilter} onChange={setStatusFilter} />
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-600">
                            <Badge tone={kpi.periodTone}>{kpi.periodStatus}</Badge>
                            <span>{kpi.periodHint}</span>
                        </div>
                    </div>
                </div>
            </div>

            {selectedAccount !== 'all' && accountOptionMap.has(selectedAccount) && filteredRows.length === 0 && (
                <div className="max-w-7xl mx-auto px-4 pt-3">
                    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        Sin movimientos este mes para {accountOptionMap.get(selectedAccount)?.baseLabel || 'esta cuenta'}.
                    </div>
                </div>
            )}
            <div className="max-w-7xl mx-auto px-4 py-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                <Kpi label="Conciliados" value={kpi.conciliated} hint="" tone="success" />
                <Kpi label="Pendientes" value={kpi.pending} hint="" />
                <Kpi label="Auto-Match %" value={`${kpi.autoMatch}%`} />
                <Kpi label="Estado del periodo" value={kpi.periodStatus} hint={kpi.periodHint} tone={kpi.periodTone} />
            </div>

            <div className="max-w-7xl mx-auto px-4 pb-10 space-y-6">
                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-bolt text-emerald-600"
                        title="Listas para aprobar (IA ≥85%)"
                        subtitle="Revisa y concilia en 1 clic"
                        tone="success"
                        cta={
                            <button className="inline-flex items-center gap-2 rounded-xl bg-slate-900 text-white px-3 py-1.5 text-sm">
                                <i className="fas fa-check-circle"></i> Conciliar ( {groups.aiReady.length} )
                            </button>
                        }
                    />
                    <SmartTableHeader />
                    {groups.aiReady.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.aiReady.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">No hay movimientos listos para aprobar.</div>
                    )}
                </div>

                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-circle-question text-amber-600"
                        title="Revisión manual"
                        subtitle="Te mostramos 3 mejores coincidencias"
                        tone="warning"
                    />
                    <SmartTableHeader />
                    {groups.manual.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.manual.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">Sin movimientos en revisión manual.</div>
                    )}
                </div>

                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-badge-percent text-amber-600"
                        title="PPD / Complementos de pago"
                        subtitle="Gestiona parcialidades, complementos y conciliación provisional"
                        tone="warning"
                        cta={
                            <div className="flex items-center gap-2">
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Registrar complemento</button>
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Conciliar provisional (visibles)</button>
                            </div>
                        }
                    />
                    <SmartTableHeader />
                    {groups.ppd.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.ppd.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">No hay pagos PPD pendientes.</div>
                    )}
                </div>

                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-globe text-blue-600"
                        title="Servicios/Productos Internacionales (sin CFDI)"
                        subtitle="Pagos al extranjero sin CFDI: adjunta factura extranjera o marca excepción"
                        tone="warning"
                        cta={
                            <div className="flex items-center gap-2">
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Adjuntar factura extranjera</button>
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Marcar no deducible</button>
                            </div>
                        }
                    />
                    <SmartTableHeader />
                    {groups.intl.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.intl.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">No se detectaron movimientos internacionales sin CFDI.</div>
                    )}
                </div>

                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-receipt text-red-600"
                        title="Falta CFDI"
                        subtitle="Crea gasto o busca CFDI para cerrar"
                        tone="danger"
                        cta={
                            <div className="flex items-center gap-2">
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Crear gasto</button>
                                <button className="rounded-xl border px-3 py-1.5 text-sm">Buscar CFDI</button>
                            </div>
                        }
                    />
                    <SmartTableHeader />
                    {groups.missingCfdi.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.missingCfdi.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">No hay movimientos sin CFDI.</div>
                    )}
                </div>

                <div className="rounded-2xl border bg-white shadow-sm overflow-hidden">
                    <ColumnHeader
                        iconClass="fas fa-link text-slate-600"
                        title="Transferencias / Propias"
                        subtitle="Detectamos CLABE/Titular para proponer traspaso"
                    />
                    <SmartTableHeader />
                    {groups.transfers.map((row) => (
                        <Row
                            key={row.id}
                            row={row}
                            onOpenDrawer={setDrawerRow}
                            expandedId={expandedId}
                            setExpandedId={setExpandedId}
                        />
                    ))}
                    {groups.transfers.length === 0 && (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">No hay transferencias internas detectadas.</div>
                    )}
                </div>
            </div>

            <Drawer
                open={Boolean(drawerRow)}
                onClose={() => setDrawerRow(null)}
                row={drawerRow}
                onConciliate={handleConciliate}
                conciliateLoading={conciliateLoading}
            />

            <SatImportModal
                isOpen={satModalOpen}
                onClose={() => setSatModalOpen(false)}
                onProcessed={loadMovements}
            />
        </div>
    );
};

const rootElement = document.getElementById('bank-reconciliation-root');
if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(<BankReconciliationApp />);
}
