"""Accounting rules engine for expense scenarios.

This module centralises the logic to transform expense records into
accounting journal entries according to the business rules defined for
Mexican accounting flows (gastos, provisiones, PPD, anticipos y activos
fijos).

It returns rich metadata so both backend and UI can reason about the
scenario applied, whether the entries are definitive, and what
additional steps (pagos parciales, depreciación) remain pending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

ROUNDING = Decimal("0.01")


@dataclass
class Movement:
    cuenta: str
    nombre_cuenta: str
    descripcion: str
    tipo: str
    debe: Decimal = Decimal("0")
    haber: Decimal = Decimal("0")

    def serialise(self) -> Dict[str, Any]:
        return {
            "cuenta": self.cuenta,
            "nombre_cuenta": self.nombre_cuenta,
            "descripcion": self.descripcion,
            "tipo": self.tipo,
            "debe": _to_str(self.debe),
            "haber": _to_str(self.haber),
        }


@dataclass
class Poliza:
    contexto: str
    concepto: str
    tipo_poliza: str
    fecha: date
    movimientos: List[Movement] = field(default_factory=list)
    referencia: Optional[str] = None

    def add(self, movement: Movement) -> None:
        self.movimientos.append(movement)

    @property
    def total_debe(self) -> Decimal:
        return sum((mov.debe for mov in self.movimientos), start=Decimal("0"))

    @property
    def total_haber(self) -> Decimal:
        return sum((mov.haber for mov in self.movimientos), start=Decimal("0"))

    def serialise(self, *, folio: str) -> Dict[str, Any]:
        total_debe = self.total_debe
        total_haber = self.total_haber
        balanceado = (total_debe - total_haber).copy_abs() <= Decimal("0.01")
        return {
            "contexto": self.contexto,
            "concepto": self.concepto,
            "tipo_poliza": self.tipo_poliza,
            "fecha_asiento": self.fecha.isoformat(),
            "numero_poliza": folio,
            "movimientos": [mov.serialise() for mov in self.movimientos],
            "total_debe": _to_str(total_debe),
            "total_haber": _to_str(total_haber),
            "balanceado": balanceado,
        }


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(ROUNDING)
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(ROUNDING)
    except Exception:
        return Decimal("0.00")


def _to_str(value: Decimal) -> str:
    return f"{value.quantize(ROUNDING):.2f}"


def _current_date(raw_date: Optional[str]) -> date:
    if raw_date:
        try:
            return datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass
    return datetime.utcnow().date()


ACCOUNT_INFO: Dict[str, Dict[str, str]] = {
    "1100": {"nombre": "Caja chica", "tipo": "activo"},
    "1110": {"nombre": "Bancos", "tipo": "activo"},
    "1185": {"nombre": "Gastos por comprobar", "tipo": "activo"},
    "1140": {"nombre": "Anticipos a proveedores", "tipo": "activo"},
    "1190": {"nombre": "IVA acreditable pendiente", "tipo": "activo"},
    "1195": {"nombre": "IVA acreditable pagado", "tipo": "activo"},
    "2100": {"nombre": "Proveedores", "tipo": "pasivo"},
    "6155": {"nombre": "Gasto por depreciación", "tipo": "gasto"},
    "6190": {"nombre": "Gastos no deducibles", "tipo": "gasto"},
    "1590": {"nombre": "Depreciación acumulada de activos fijos", "tipo": "activo"},
    "1500": {"nombre": "Activo fijo - Maquinaria", "tipo": "activo"},
    "1510": {"nombre": "Activo fijo - Equipo", "tipo": "activo"},
    "1520": {"nombre": "Activo fijo - Cómputo", "tipo": "activo"},
    "1530": {"nombre": "Activo fijo - Mobiliario", "tipo": "activo"},
    "6140": {"nombre": "Combustibles y lubricantes", "tipo": "gasto"},
    "6150": {"nombre": "Gastos de viaje y viáticos", "tipo": "gasto"},
    "6160": {"nombre": "Publicidad y promoción", "tipo": "gasto"},
    "6170": {"nombre": "Servicios tecnológicos", "tipo": "gasto"},
    "6180": {"nombre": "Papelería y misceláneos", "tipo": "gasto"},
    "6110": {"nombre": "Honorarios profesionales", "tipo": "gasto"},
    "6120": {"nombre": "Renta de local u oficina", "tipo": "gasto"},
    "6130": {"nombre": "Servicios básicos", "tipo": "gasto"},
    "6195": {"nombre": "Gastos médicos y bienestar", "tipo": "gasto"},
}

EXPENSE_ACCOUNT_MAP: Dict[str, str] = {
    "combustible": "6140",
    "combustibles": "6140",
    "viajes": "6150",
    "viaticos": "6150",
    "alimentos": "6150",
    "servicios": "6130",
    "oficina": "6180",
    "honorarios": "6110",
    "renta": "6120",
    "publicidad": "6160",
    "marketing": "6160",
    "tecnologia": "6170",
    "tecnología": "6170",
    "salud": "6195",
    "otros": "6180",
}

ASSET_ACCOUNT_MAP: Dict[str, str] = {
    "maquinaria": "1500",
    "equipo": "1510",
    "equipo_general": "1510",
    "computo": "1520",
    "cómputo": "1520",
    "tecnologia": "1520",
    "tecnología": "1520",
    "mobiliario": "1530",
    "vehiculos": "1510",
    "vehículos": "1510",
}

PAYMENT_ACCOUNT_MAP: Dict[str, str] = {
    "company_account": "1110",
    "own_account": "1185",
    "cash": "1100",
    "tarjeta_empresa": "1110",
    "tarjeta_empleado": "1185",
}


def _resolve_account(code: str) -> Dict[str, str]:
    info = ACCOUNT_INFO.get(code)
    if info:
        return {**info, "code": code}
    return {"code": code, "nombre": "Cuenta sin cat", "tipo": "otro"}


def _resolve_expense_account(expense: Dict[str, Any]) -> Dict[str, str]:
    category = (expense.get("category") or "otros").strip().lower()
    code = EXPENSE_ACCOUNT_MAP.get(category, EXPENSE_ACCOUNT_MAP["otros"])
    return _resolve_account(code)


def _resolve_asset_account(asset_class: Optional[str]) -> Dict[str, str]:
    if not asset_class:
        return _resolve_account("1500")
    code = ASSET_ACCOUNT_MAP.get(asset_class.lower(), "1500")
    return _resolve_account(code)


def _resolve_payment_account(expense: Dict[str, Any]) -> Dict[str, str]:
    paid_by = (expense.get("paid_by") or "company_account").lower()
    code = PAYMENT_ACCOUNT_MAP.get(paid_by, "1110")
    return _resolve_account(code)


def _calculate_tax_breakdown(expense: Dict[str, Any]) -> Dict[str, Decimal]:
    tax_meta = expense.get("tax_metadata") or {}
    metadata = expense.get("metadata") or {}
    if isinstance(metadata, dict):
        tax_meta = {**metadata.get("tax_info", {}), **tax_meta}
    subtotal = _to_decimal(tax_meta.get("subtotal"))
    iva = _to_decimal(tax_meta.get("iva_amount") or tax_meta.get("iva"))
    total = _to_decimal(tax_meta.get("total"))

    if total == 0:
        total = _to_decimal(expense.get("amount"))
    if subtotal == 0 and total > 0:
        subtotal = (total / Decimal("1.16")).quantize(ROUNDING)
    if iva == 0 and subtotal > 0:
        iva = (total - subtotal).quantize(ROUNDING)

    return {
        "subtotal": subtotal,
        "iva": iva,
        "total": total if total > 0 else subtotal + iva,
    }


def _folio(expense: Dict[str, Any], suffix: str, sequence: int = 1) -> str:
    expense_id = expense.get("id") or "EXP"
    return f"POL-{expense_id}-{suffix.upper()}-{sequence:02d}"


def generate_accounting_entries(
    expense: Dict[str, Any],
    payments: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate accounting entries and scenario metadata for an expense."""

    payments = list(payments or [])
    amounts = _calculate_tax_breakdown(expense)
    subtotal = amounts["subtotal"]
    iva = amounts["iva"]
    total = amounts["total"]

    total_paid = _to_decimal(expense.get("total_paid"))
    if total_paid == 0:
        total_paid = sum((_to_decimal(payment.get("amount")) for payment in payments), start=Decimal("0"))

    invoice_status = (expense.get("invoice_status") or "").lower()
    bank_status = (expense.get("bank_status") or "").lower()
    will_have_cfdi = bool(expense.get("will_have_cfdi", True))

    expense_date = _current_date(expense.get("expense_date"))
    today = datetime.utcnow().date()

    is_advance = bool(expense.get("is_advance"))
    is_ppd = bool(expense.get("is_ppd"))
    asset_class = expense.get("asset_class")
    payment_terms = (expense.get("payment_terms") or "").lower()

    paid_keyword = "ppd" in payment_terms or "parcial" in payment_terms or "parcialidades" in payment_terms
    is_credit = total_paid < (total - Decimal("0.5"))
    has_invoice = invoice_status in {"facturado", "registrada"}
    bank_paid = bank_status in {"conciliado", "conciliado_banco", "pagado"} or total_paid >= (total - Decimal("0.5"))

    polizas: List[Dict[str, Any]] = []
    scenario = "gasto_factura_pagado"
    scenario_label = "Gasto pagado con factura"
    is_definitive = bank_paid and has_invoice
    notes: List[str] = []

    if asset_class:
        scenario = "activo_fijo"
        scenario_label = "Activo fijo"
        polizas.extend(_build_asset_entries(expense, subtotal, iva, total, total_paid, payments, has_invoice, bank_paid))
        is_definitive = bank_paid and has_invoice
    elif is_advance:
        scenario = "anticipo_proveedor"
        scenario_label = "Anticipo a proveedor"
        polizas.extend(_build_advance_entries(expense, subtotal, iva, total, has_invoice))
        is_definitive = has_invoice
        if not has_invoice:
            notes.append("Pendiente recibir CFDI para re-clasificar anticipo")
    elif is_ppd or paid_keyword:
        scenario = "ppd"
        scenario_label = "Pago en parcialidades"
        polizas.extend(_build_ppd_entries(expense, subtotal, iva, total, payments, has_invoice))
        is_definitive = bank_paid and has_invoice and (total_paid >= (total - Decimal("0.5")))
        if payments:
            notes.append(f"Pagos registrados: {len(payments)} de valor { _to_str(total_paid) }")
        else:
            notes.append("Sin pagos registrados aún")
    elif not has_invoice and will_have_cfdi:
        scenario = "gasto_pendiente_comprobar"
        scenario_label = "Gasto por comprobar"
        polizas.extend(_build_pending_invoice_entries(expense, subtotal, iva, total, bank_paid))
        is_definitive = False
        notes.append("Esperando CFDI para regularizar el gasto")
    elif not will_have_cfdi:
        scenario = "gasto_no_deducible"
        scenario_label = "No deducible"
        polizas.extend(_build_non_deductible_entries(expense, total))
        is_definitive = True
    elif has_invoice and is_credit:
        scenario = "provision_credito"
        scenario_label = "Provisión crédito"
        polizas.extend(_build_credit_entries(expense, subtotal, iva, total, total_paid, bank_paid))
        is_definitive = bank_paid
        if not bank_paid:
            notes.append("Pago al proveedor pendiente")
    else:
        polizas.extend(_build_cash_entries(expense, subtotal, iva, total))
        notes.append("Factura y pago conciliados")

    if not polizas:
        # Guarantee at least one placeholder entry to avoid UI breakage
        placeholder = Poliza(
            contexto="sin_escenario",
            concepto="Gasto sin movimientos",
            tipo_poliza="Pendiente",
            fecha=expense_date,
        )
        placeholder.add(
            Movement(
                cuenta="9999",
                nombre_cuenta="Sin definir",
                descripcion="Registrar detalles contables",
                tipo="memo",
            )
        )
        polizas_serialised = [placeholder.serialise(folio=_folio(expense, "PEND"))]
    else:
        polizas_serialised = [
            poliza.serialise(folio=_folio(expense, scenario, idx + 1))
            for idx, poliza in enumerate(polizas)
        ]

    principal = polizas_serialised[0]
    principal.setdefault("polizas", polizas_serialised)

    result = {
        "scenario": scenario,
        "scenario_label": scenario_label,
        "is_definitive": is_definitive,
        "polizas": polizas_serialised,
        "numero_poliza": principal["numero_poliza"],
        "tipo_poliza": principal["tipo_poliza"],
        "fecha_asiento": principal["fecha_asiento"],
        "concepto": principal["concepto"],
        "movimientos": principal["movimientos"],
        "total_debe": principal["total_debe"],
        "total_haber": principal["total_haber"],
        "balanceado": principal["balanceado"],
        "notas": notes,
        "generado_en": today.isoformat(),
    }
    return result


def _build_cash_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
) -> List[Poliza]:
    poliza = Poliza(
        contexto="pago_contado",
        concepto="Gasto pagado con CFDI",
        tipo_poliza="Egreso",
        fecha=_current_date(expense.get("expense_date")),
    )
    gasto_account = _resolve_expense_account(expense)
    poliza.add(
        Movement(
            cuenta=gasto_account["code"],
            nombre_cuenta=gasto_account["nombre"],
            descripcion="Registro del gasto",
            tipo=gasto_account.get("tipo", "gasto"),
            debe=subtotal,
        )
    )
    if iva > 0:
        iva_account = _resolve_account("1195")
        poliza.add(
            Movement(
                cuenta="1195",
                nombre_cuenta=iva_account["nombre"],
                descripcion="IVA acreditable pagado",
                tipo=iva_account.get("tipo", "activo"),
                debe=iva,
            )
        )
    payment_account = _resolve_payment_account(expense)
    poliza.add(
        Movement(
            cuenta=payment_account["code"],
            nombre_cuenta=payment_account["nombre"],
            descripcion="Salida de fondos",
            tipo=payment_account.get("tipo", "activo"),
            haber=total,
        )
    )
    return [poliza]


def _build_credit_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
    total_paid: Decimal,
    bank_paid: bool,
) -> List[Poliza]:
    entries: List[Poliza] = []
    expense_date = _current_date(expense.get("expense_date"))

    poliza_registro = Poliza(
        contexto="registro_provision",
        concepto="Registro de factura a crédito",
        tipo_poliza="Diario",
        fecha=expense_date,
    )
    gasto_account = _resolve_expense_account(expense)
    poliza_registro.add(
        Movement(
            cuenta=gasto_account["code"],
            nombre_cuenta=gasto_account["nombre"],
            descripcion="Reconocimiento del gasto",
            tipo=gasto_account.get("tipo", "gasto"),
            debe=subtotal,
        )
    )
    if iva > 0:
        poliza_registro.add(
            Movement(
                cuenta="1190",
                nombre_cuenta=_resolve_account("1190")["nombre"],
                descripcion="IVA acreditable pendiente",
                tipo="activo",
                debe=iva,
            )
        )
    poliza_registro.add(
        Movement(
            cuenta="2100",
            nombre_cuenta=_resolve_account("2100")["nombre"],
            descripcion="Cuenta por pagar al proveedor",
            tipo="pasivo",
            haber=total,
        )
    )
    entries.append(poliza_registro)

    if bank_paid and total_paid > Decimal("0"):
        poliza_pago = Poliza(
            contexto="pago_proveedor",
            concepto="Pago de factura a crédito",
            tipo_poliza="Egreso",
            fecha=datetime.utcnow().date(),
        )
        poliza_pago.add(
            Movement(
                cuenta="2100",
                nombre_cuenta=_resolve_account("2100")["nombre"],
                descripcion="Liquidación al proveedor",
                tipo="pasivo",
                debe=total_paid,
            )
        )
        if iva > 0:
            poliza_pago.add(
                Movement(
                    cuenta="1195",
                    nombre_cuenta=_resolve_account("1195")["nombre"],
                    descripcion="IVA acreditable pagado",
                    tipo="activo",
                    debe=iva,
                )
            )
            poliza_pago.add(
                Movement(
                    cuenta="1190",
                    nombre_cuenta=_resolve_account("1190")["nombre"],
                    descripcion="Baja de IVA pendiente",
                    tipo="activo",
                    haber=iva,
                )
            )
        payment_account = _resolve_payment_account(expense)
        poliza_pago.add(
            Movement(
                cuenta=payment_account["code"],
                nombre_cuenta=payment_account["nombre"],
                descripcion="Salida de fondos",
                tipo=payment_account.get("tipo", "activo"),
                haber=total_paid,
            )
        )
        entries.append(poliza_pago)

    return entries


def _build_pending_invoice_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
    bank_paid: bool,
) -> List[Poliza]:
    entries: List[Poliza] = []
    payment_account = _resolve_payment_account(expense)
    expense_date = _current_date(expense.get("expense_date"))

    poliza_pago = Poliza(
        contexto="pago_sin_factura",
        concepto="Pago pendiente de comprobación",
        tipo_poliza="Egreso",
        fecha=expense_date,
    )
    poliza_pago.add(
        Movement(
            cuenta="1185",
            nombre_cuenta=_resolve_account("1185")["nombre"],
            descripcion="Gasto por comprobar",
            tipo="activo",
            debe=total,
        )
    )
    poliza_pago.add(
        Movement(
            cuenta=payment_account["code"],
            nombre_cuenta=payment_account["nombre"],
            descripcion="Pago provisional",
            tipo=payment_account.get("tipo", "activo"),
            haber=total,
        )
    )
    entries.append(poliza_pago)

    if bank_paid and expense.get("invoice_status") == "facturado":
        poliza_reclas = Poliza(
            contexto="reclasificacion_factura",
            concepto="Reclasificación al recibir CFDI",
            tipo_poliza="Diario",
            fecha=datetime.utcnow().date(),
        )
        gasto_account = _resolve_expense_account(expense)
        poliza_reclas.add(
            Movement(
                cuenta=gasto_account["code"],
                nombre_cuenta=gasto_account["nombre"],
                descripcion="Aplicación del gasto",
                tipo=gasto_account.get("tipo", "gasto"),
                debe=subtotal,
            )
        )
        if iva > 0:
            poliza_reclas.add(
                Movement(
                    cuenta="1195",
                    nombre_cuenta=_resolve_account("1195")["nombre"],
                    descripcion="IVA acreditable pagado",
                    tipo="activo",
                    debe=iva,
                )
            )
        poliza_reclas.add(
            Movement(
                cuenta="1185",
                nombre_cuenta=_resolve_account("1185")["nombre"],
                descripcion="Baja de gasto por comprobar",
                tipo="activo",
                haber=total,
            )
        )
        entries.append(poliza_reclas)

    return entries


def _build_non_deductible_entries(
    expense: Dict[str, Any],
    total: Decimal,
) -> List[Poliza]:
    poliza = Poliza(
        contexto="no_deducible",
        concepto="Clasificación a gasto no deducible",
        tipo_poliza="Diario",
        fecha=datetime.utcnow().date(),
    )
    poliza.add(
        Movement(
            cuenta="6190",
            nombre_cuenta=_resolve_account("6190")["nombre"],
            descripcion="Reconocimiento como no deducible",
            tipo="gasto",
            debe=total,
        )
    )
    poliza.add(
        Movement(
            cuenta="1185",
            nombre_cuenta=_resolve_account("1185")["nombre"],
            descripcion="Cancelación de gasto por comprobar",
            tipo="activo",
            haber=total,
        )
    )
    return [poliza]


def _build_ppd_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
    payments: Sequence[Dict[str, Any]],
    has_invoice: bool,
) -> List[Poliza]:
    entries: List[Poliza] = []
    expense_date = _current_date(expense.get("expense_date"))
    poliza_registro = Poliza(
        contexto="registro_ppd",
        concepto="Registro de CFDI PPD",
        tipo_poliza="Diario",
        fecha=expense_date,
    )
    gasto_account = _resolve_expense_account(expense)
    poliza_registro.add(
        Movement(
            cuenta=gasto_account["code"],
            nombre_cuenta=gasto_account["nombre"],
            descripcion="Reconocimiento del gasto",
            tipo=gasto_account.get("tipo", "gasto"),
            debe=subtotal,
        )
    )
    if iva > 0:
        poliza_registro.add(
            Movement(
                cuenta="1190",
                nombre_cuenta=_resolve_account("1190")["nombre"],
                descripcion="IVA acreditable pendiente",
                tipo="activo",
                debe=iva,
            )
        )
    poliza_registro.add(
        Movement(
            cuenta="2100",
            nombre_cuenta=_resolve_account("2100")["nombre"],
            descripcion="Cuenta por pagar al proveedor",
            tipo="pasivo",
            haber=total,
        )
    )
    entries.append(poliza_registro)

    if not has_invoice:
        return entries

    remaining_total = total
    remaining_iva = iva

    for idx, payment in enumerate(payments, start=1):
        amount = _to_decimal(payment.get("amount"))
        if amount <= 0:
            continue
        ratio = Decimal("0")
        if total > 0:
            ratio = (amount / total).quantize(ROUNDING)
        iva_portion = (iva * ratio).quantize(ROUNDING)
        iva_portion = min(iva_portion, remaining_iva)
        payment_account = _resolve_payment_account(expense)

        poliza_pago = Poliza(
            contexto="pago_ppd",
            concepto=f"Pago parcial {idx}",
            tipo_poliza="Egreso",
            fecha=_current_date(payment.get("payment_date")) if payment.get("payment_date") else datetime.utcnow().date(),
        )
        poliza_pago.add(
            Movement(
                cuenta="2100",
                nombre_cuenta=_resolve_account("2100")["nombre"],
                descripcion="Disminución de cuentas por pagar",
                tipo="pasivo",
                debe=amount,
            )
        )
        if iva_portion > 0:
            poliza_pago.add(
                Movement(
                    cuenta="1195",
                    nombre_cuenta=_resolve_account("1195")["nombre"],
                    descripcion="IVA acreditable pagado",
                    tipo="activo",
                    debe=iva_portion,
                )
            )
            poliza_pago.add(
                Movement(
                    cuenta="1190",
                    nombre_cuenta=_resolve_account("1190")["nombre"],
                    descripcion="Baja de IVA pendiente",
                    tipo="activo",
                    haber=iva_portion,
                )
            )
        poliza_pago.add(
            Movement(
                cuenta=payment_account["code"],
                nombre_cuenta=payment_account["nombre"],
                descripcion="Salida de efectivo",
                tipo=payment_account.get("tipo", "activo"),
                haber=amount,
            )
        )
        entries.append(poliza_pago)
        remaining_total -= amount
        remaining_iva -= iva_portion
        if remaining_total <= Decimal("0.01"):
            break

    return entries


def _build_advance_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
    has_invoice: bool,
) -> List[Poliza]:
    entries: List[Poliza] = []
    expense_date = _current_date(expense.get("expense_date"))
    poliza_anticipo = Poliza(
        contexto="anticipo",
        concepto="Entrega de anticipo a proveedor",
        tipo_poliza="Egreso",
        fecha=expense_date,
    )
    payment_account = _resolve_payment_account(expense)
    poliza_anticipo.add(
        Movement(
            cuenta="1140",
            nombre_cuenta=_resolve_account("1140")["nombre"],
            descripcion="Registro del anticipo",
            tipo="activo",
            debe=total,
        )
    )
    poliza_anticipo.add(
        Movement(
            cuenta=payment_account["code"],
            nombre_cuenta=payment_account["nombre"],
            descripcion="Pago del anticipo",
            tipo=payment_account.get("tipo", "activo"),
            haber=total,
        )
    )
    entries.append(poliza_anticipo)

    if has_invoice:
        poliza_factura = Poliza(
            contexto="aplicacion_anticipo",
            concepto="Aplicación del anticipo contra gasto",
            tipo_poliza="Diario",
            fecha=datetime.utcnow().date(),
        )
        gasto_account = _resolve_expense_account(expense)
        poliza_factura.add(
            Movement(
                cuenta=gasto_account["code"],
                nombre_cuenta=gasto_account["nombre"],
                descripcion="Reconocimiento del gasto",
                tipo=gasto_account.get("tipo", "gasto"),
                debe=subtotal,
            )
        )
        if iva > 0:
            poliza_factura.add(
                Movement(
                    cuenta="1195",
                    nombre_cuenta=_resolve_account("1195")["nombre"],
                    descripcion="IVA acreditable pagado",
                    tipo="activo",
                    debe=iva,
                )
            )
        poliza_factura.add(
            Movement(
                cuenta="1140",
                nombre_cuenta=_resolve_account("1140")["nombre"],
                descripcion="Aplicación del anticipo",
                tipo="activo",
                haber=total,
            )
        )
        entries.append(poliza_factura)
    return entries


def _build_asset_entries(
    expense: Dict[str, Any],
    subtotal: Decimal,
    iva: Decimal,
    total: Decimal,
    total_paid: Decimal,
    payments: Sequence[Dict[str, Any]],
    has_invoice: bool,
    bank_paid: bool,
) -> List[Poliza]:
    entries: List[Poliza] = []
    expense_date = _current_date(expense.get("expense_date"))
    asset_account = _resolve_asset_account(expense.get("asset_class"))

    poliza_compra = Poliza(
        contexto="compra_activo",
        concepto="Compra de activo fijo",
        tipo_poliza="Diario",
        fecha=expense_date,
    )
    poliza_compra.add(
        Movement(
            cuenta=asset_account["code"],
            nombre_cuenta=asset_account["nombre"],
            descripcion="Registro del activo fijo",
            tipo="activo",
            debe=subtotal,
        )
    )
    if iva > 0:
        poliza_compra.add(
            Movement(
                cuenta="1190",
                nombre_cuenta=_resolve_account("1190")["nombre"],
                descripcion="IVA acreditable pendiente",
                tipo="activo",
                debe=iva,
            )
        )
    poliza_compra.add(
        Movement(
            cuenta="2100",
            nombre_cuenta=_resolve_account("2100")["nombre"],
            descripcion="Cuenta por pagar al proveedor",
            tipo="pasivo",
            haber=total,
        )
    )
    entries.append(poliza_compra)

    if bank_paid and total_paid > Decimal("0"):
        poliza_pago = Poliza(
            contexto="pago_activo",
            concepto="Pago de activo fijo",
            tipo_poliza="Egreso",
            fecha=datetime.utcnow().date(),
        )
        poliza_pago.add(
            Movement(
                cuenta="2100",
                nombre_cuenta=_resolve_account("2100")["nombre"],
                descripcion="Pago a proveedor",
                tipo="pasivo",
                debe=total_paid,
            )
        )
        if iva > 0:
            poliza_pago.add(
                Movement(
                    cuenta="1195",
                    nombre_cuenta=_resolve_account("1195")["nombre"],
                    descripcion="IVA acreditable pagado",
                    tipo="activo",
                    debe=iva,
                )
            )
            poliza_pago.add(
                Movement(
                    cuenta="1190",
                    nombre_cuenta=_resolve_account("1190")["nombre"],
                    descripcion="Cancelación de IVA pendiente",
                    tipo="activo",
                    haber=iva,
                )
            )
        payment_account = _resolve_payment_account(expense)
        poliza_pago.add(
            Movement(
                cuenta=payment_account["code"],
                nombre_cuenta=payment_account["nombre"],
                descripcion="Salida de efectivo",
                tipo=payment_account.get("tipo", "activo"),
                haber=total_paid,
            )
        )
        entries.append(poliza_pago)
    elif payments:
        entries.extend(_build_ppd_entries(expense, subtotal, iva, total, payments, has_invoice))

    depreciation_months = 12
    metadata = expense.get("metadata") or {}
    if isinstance(metadata, dict):
        depreciation_months = int(metadata.get("depreciation_months") or depreciation_months)
    if depreciation_months < 1:
        depreciation_months = 12

    depreciation_amount = Decimal("0.00")
    if depreciation_months > 0:
        depreciation_amount = (subtotal / Decimal(depreciation_months)).quantize(ROUNDING)

    if depreciation_amount > Decimal("0"):
        poliza_depr = Poliza(
            contexto="depreciacion",
            concepto="Depreciación mensual del activo",
            tipo_poliza="Diario",
            fecha=datetime.utcnow().date(),
        )
        poliza_depr.add(
            Movement(
                cuenta="6155",
                nombre_cuenta=_resolve_account("6155")["nombre"],
                descripcion="Gasto por depreciación",
                tipo="gasto",
                debe=depreciation_amount,
            )
        )
        poliza_depr.add(
            Movement(
                cuenta="1590",
                nombre_cuenta=_resolve_account("1590")["nombre"],
                descripcion="Depreciación acumulada",
                tipo="activo",
                haber=depreciation_amount,
            )
        )
        entries.append(poliza_depr)

    return entries
