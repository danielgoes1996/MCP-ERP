"""Utilities to parse Mexican CFDI XML invoices and extract tax data."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional


CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
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
    if complemento_node is not None:
        timbre = complemento_node.find("tfd:TimbreFiscalDigital", CFDI_NS)
        if timbre is not None:
            uuid = timbre.attrib.get("UUID")

    iva_amount = sum(tax["amount"] for tax in taxes if tax["type"] == "IVA" and tax["kind"] == "traslado")
    other_taxes_total = sum(tax["amount"] for tax in taxes if not (tax["type"] == "IVA" and tax["kind"] == "traslado"))

    return {
        "subtotal": subtotal,
        "total": total,
        "currency": currency,
        "taxes": taxes,
        "iva_amount": round(iva_amount, 2),
        "other_taxes": round(other_taxes_total, 2),
        "emitter": emitter_node.attrib if emitter_node is not None else None,
        "receiver": receiver_node.attrib if receiver_node is not None else None,
        "uuid": uuid,
    }


__all__ = ["parse_cfdi_xml", "InvoiceParseError"]

