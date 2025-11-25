"""Utilities to parse Mexican CFDI XML invoices and extract tax data."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional


CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "pago20": "http://www.sat.gob.mx/Pagos20",
}

TAX_CODE_MAP = {
    "001": "ISR",
    "002": "IVA",
    "003": "IEPS",
}


class InvoiceParseError(ValueError):
    """Raised when CFDI XML cannot be parsed correctly."""


def _parse_float(value: Optional[str]) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _extract_payment_complement(complemento_node: ET.Element) -> Optional[Dict[str, object]]:
    """Extract payment complement data (Complemento de Pago) from CFDI XML.

    Args:
        complemento_node: The cfdi:Complemento XML node.

    Returns:
        Dict with payment details, or None if no payment complement found.
    """
    if complemento_node is None:
        return None

    # Find pago20:Pagos node
    pagos_node = complemento_node.find("pago20:Pagos", CFDI_NS)
    if pagos_node is None:
        return None

    # Extract totals
    totales_node = pagos_node.find("pago20:Totales", CFDI_NS)
    totales = {}
    if totales_node is not None:
        totales = {
            "total_traslados_iva16": _parse_float(totales_node.attrib.get("TotalTrasladosImpuestoIVA16")),
            "total_traslados_base_iva16": _parse_float(totales_node.attrib.get("TotalTrasladosBaseIVA16")),
            "monto_total_pagos": _parse_float(totales_node.attrib.get("MontoTotalPagos")),
        }

    # Extract individual payments
    pagos_list = []
    for pago_node in pagos_node.findall("pago20:Pago", CFDI_NS):
        pago = {
            "monto": _parse_float(pago_node.attrib.get("Monto")),
            "moneda": pago_node.attrib.get("MonedaP", "MXN"),
            "forma_pago": pago_node.attrib.get("FormaDePagoP"),
            "fecha_pago": pago_node.attrib.get("FechaPago"),
            "tipo_cambio": _parse_float(pago_node.attrib.get("TipoCambioP")) or 1.0,
        }

        # Extract related documents (facturas relacionadas)
        documentos_relacionados = []
        for docto_node in pago_node.findall("pago20:DoctoRelacionado", CFDI_NS):
            docto = {
                "id_documento": docto_node.attrib.get("IdDocumento"),  # UUID de la factura relacionada
                "serie": docto_node.attrib.get("Serie"),
                "folio": docto_node.attrib.get("Folio"),
                "moneda": docto_node.attrib.get("MonedaDR"),
                "num_parcialidad": int(docto_node.attrib.get("NumParcialidad", "0") or "0"),
                "imp_saldo_anterior": _parse_float(docto_node.attrib.get("ImpSaldoAnt")),
                "imp_pagado": _parse_float(docto_node.attrib.get("ImpPagado")),
                "imp_saldo_insoluto": _parse_float(docto_node.attrib.get("ImpSaldoInsoluto")),
                "equivalencia": _parse_float(docto_node.attrib.get("EquivalenciaDR")) or 1.0,
            }
            documentos_relacionados.append(docto)

        pago["documentos_relacionados"] = documentos_relacionados
        pagos_list.append(pago)

    return {
        "version": pagos_node.attrib.get("Version", "2.0"),
        "totales": totales,
        "pagos": pagos_list,
    }


def parse_cfdi_xml(content: bytes) -> Dict[str, object]:
    """Parse CFDI XML bytes and return tax/metadata information.

    Args:
        content: Raw XML content.

    Returns:
        Dict with subtotal, total, taxes, emitter/receiver data, UUID, currency.

    Raises:
        InvoiceParseError: If XML is invalid or missing key nodes.
    """

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:  # pragma: no cover - XML parsing
        raise InvoiceParseError(f"CFDI inválido: {exc}")

    if root.tag.endswith("Comprobante") is False:
        # Accept namespace or without
        if root.find("cfdi:Comprobante", CFDI_NS) is not None:
            root = root.find("cfdi:Comprobante", CFDI_NS)
        else:
            raise InvoiceParseError("No se encontró el nodo cfdi:Comprobante")

    subtotal = _parse_float(root.attrib.get("SubTotal"))
    total = _parse_float(root.attrib.get("Total", root.attrib.get("total")))
    currency = root.attrib.get("Moneda", "MXN")

    emitter_node = root.find("cfdi:Emisor", CFDI_NS)
    receiver_node = root.find("cfdi:Receptor", CFDI_NS)
    impuestos_node = root.find("cfdi:Impuestos", CFDI_NS)
    complemento_node = root.find("cfdi:Complemento", CFDI_NS)

    taxes: List[Dict[str, object]] = []

    if impuestos_node is not None:
        traslados_parent = impuestos_node.find("cfdi:Traslados", CFDI_NS)
        if traslados_parent is not None:
            for traslado in traslados_parent.findall("cfdi:Traslado", CFDI_NS):
                code = traslado.attrib.get("Impuesto") or traslado.attrib.get("impuesto", "")
                taxes.append(
                    {
                        "type": TAX_CODE_MAP.get(code, code or "OTRO"),
                        "code": code,
                        "kind": "traslado",
                        "factor": traslado.attrib.get("TipoFactor") or traslado.attrib.get("tipoFactor"),
                        "rate": _parse_float(traslado.attrib.get("TasaOCuota")),
                        "amount": _parse_float(traslado.attrib.get("Importe")),
                    }
                )

        retenciones_parent = impuestos_node.find("cfdi:Retenciones", CFDI_NS)
        if retenciones_parent is not None:
            for ret in retenciones_parent.findall("cfdi:Retencion", CFDI_NS):
                code = ret.attrib.get("Impuesto") or ret.attrib.get("impuesto", "")
                taxes.append(
                    {
                        "type": TAX_CODE_MAP.get(code, code or "OTRO"),
                        "code": code,
                        "kind": "retencion",
                        "factor": ret.attrib.get("TipoFactor") or ret.attrib.get("tipoFactor"),
                        "rate": _parse_float(ret.attrib.get("TasaOCuota")),
                        "amount": _parse_float(ret.attrib.get("Importe")),
                    }
                )

    uuid = None
    payment_complement = None
    if complemento_node is not None:
        timbre = complemento_node.find("tfd:TimbreFiscalDigital", CFDI_NS)
        if timbre is not None:
            uuid = timbre.attrib.get("UUID")

        # Extract payment complement data (Complemento de Pago)
        payment_complement = _extract_payment_complement(complemento_node)

    # Extract conceptos (line items)
    conceptos_list = []
    conceptos_node = root.find("cfdi:Conceptos", CFDI_NS)
    if conceptos_node is not None:
        for concepto_node in conceptos_node.findall("cfdi:Concepto", CFDI_NS):
            concepto = {
                "clave_prod_serv": concepto_node.attrib.get("ClaveProdServ"),  # SAT product/service code
                "clave_unidad": concepto_node.attrib.get("ClaveUnidad"),
                "cantidad": _parse_float(concepto_node.attrib.get("Cantidad")),
                "unidad": concepto_node.attrib.get("Unidad"),
                "no_identificacion": concepto_node.attrib.get("NoIdentificacion"),
                "descripcion": concepto_node.attrib.get("Descripcion"),
                "valor_unitario": _parse_float(concepto_node.attrib.get("ValorUnitario")),
                "importe": _parse_float(concepto_node.attrib.get("Importe")),
                "objeto_imp": concepto_node.attrib.get("ObjetoImp"),
            }
            conceptos_list.append(concepto)

    iva_amount = sum(tax["amount"] for tax in taxes if tax["type"] == "IVA" and tax["kind"] == "traslado")
    other_taxes_total = sum(tax["amount"] for tax in taxes if not (tax["type"] == "IVA" and tax["kind"] == "traslado"))

    # Extract payment method fields from root (Comprobante) attributes
    metodo_pago = root.attrib.get("MetodoPago")  # PUE (Una exhibición) or PPD (Parcialidades)
    forma_pago = root.attrib.get("FormaPago")    # 01-99 (payment form code)
    condiciones_pago = root.attrib.get("CondicionesDePago")  # Payment conditions text

    result = {
        "subtotal": subtotal,
        "total": total,
        "currency": currency,
        "taxes": taxes,
        "iva_amount": round(iva_amount, 2),
        "other_taxes": round(other_taxes_total, 2),
        "emisor": {k.lower(): v for k, v in emitter_node.attrib.items()} if emitter_node is not None else {},
        "receptor": {k.lower(): v for k, v in receiver_node.attrib.items()} if receiver_node is not None else {},
        "uuid": uuid,
        "conceptos": conceptos_list,  # Add conceptos to result
        "metodo_pago": metodo_pago,  # PUE/PPD - critical for classification
        "forma_pago": forma_pago,    # Payment form code
        "condiciones_pago": condiciones_pago,  # Payment conditions
    }

    # Add payment complement data if present (tipo P invoices)
    if payment_complement is not None:
        result["payment_complement"] = payment_complement

    return result


__all__ = ["parse_cfdi_xml", "InvoiceParseError"]

