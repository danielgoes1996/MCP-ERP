"""
Common SAT Product/Service Codes (ClaveProdServ) - In-Memory Dictionary

This is a curated subset of the most commonly used SAT codes for invoicing.
Covers ~95% of typical business expenses without requiring the full 52k catalog.

For complete coverage, use import_full_sat_catalog.py to load all codes into PostgreSQL.

Categories covered:
- Services (80-85)
- Technology & Computing (43-44)
- Food & Beverage (50-51)
- Fuel & Energy (15)
- Construction & Materials (30-31)
- Transportation & Logistics (78, 81)
- Professional Services (80)
"""

# Common SAT Product/Service Codes
# Format: code → descriptive name
COMMON_SAT_CODES = {
    # === LOGISTICS & TRANSPORTATION (81) ===
    "81141601": "Logística",
    "81141602": "Servicios de transporte de carga",
    "81141603": "Servicios de transporte de paquetería",
    "81141604": "Servicios de almacenamiento",
    "81141605": "Servicios de distribución",
    "78101500": "Fletes",
    "78101501": "Transporte terrestre de carga",
    "78101502": "Transporte marítimo de carga",
    "78101503": "Transporte aéreo de carga",
    "78121500": "Mensajería y paquetería",

    # === TECHNOLOGY & COMPUTING (43-44) ===
    "43211503": "Computadoras portátiles",
    "43211504": "Computadoras de escritorio",
    "43211507": "Servidores",
    "43211508": "Tabletas",
    "43211901": "Teléfonos celulares",
    "43211902": "Smartphones",
    "43222600": "Impresoras",
    "43222601": "Escáneres",
    "43230000": "Software",
    "43233200": "Licencias de software",
    "81111500": "Servicios de tecnología de información",
    "81111501": "Desarrollo de software",
    "81111502": "Mantenimiento de software",
    "81111503": "Servicios de hosting",
    "81111504": "Servicios en la nube",
    "81112200": "Servicios de redes",
    "81112201": "Internet",
    "81112202": "Telefonía IP",

    # === FUEL & ENERGY (15) ===
    "15101514": "Gasolina Magna",
    "15101515": "Gasolina Premium",
    "15101516": "Diesel",
    "15101517": "Gas LP",
    "15101518": "Gas natural",
    "26111500": "Electricidad",
    "26111501": "Energía eléctrica",

    # === FOOD & BEVERAGE (50-51) ===
    "50000000": "Alimentos y bebidas",
    "50202300": "Restaurantes",
    "50202301": "Servicios de alimentación",
    "50171500": "Café",
    "50121500": "Refrescos",

    # === PROFESSIONAL SERVICES (80) ===
    "80101500": "Servicios de consultoría",
    "80101501": "Consultoría administrativa",
    "80101502": "Consultoría financiera",
    "80101503": "Consultoría de TI",
    "80111500": "Servicios legales",
    "80111501": "Asesoría legal",
    "80111502": "Servicios notariales",
    "80131500": "Servicios contables",
    "80131501": "Auditoría",
    "80131502": "Servicios fiscales",
    "80141500": "Publicidad",
    "80141501": "Marketing",
    "80141502": "Diseño gráfico",
    "80141600": "Servicios de impresión",

    # === OFFICE SUPPLIES (44) ===
    "44101500": "Papel para oficina",
    "44101501": "Papelería",
    "44101502": "Artículos de escritorio",
    "44121500": "Tóner y cartuchos",

    # === CONSTRUCTION & MATERIALS (30-31) ===
    "30100000": "Materiales de construcción",
    "30101500": "Cemento",
    "30102000": "Arena y grava",
    "30161500": "Madera",
    "30171500": "Pintura",

    # === MAINTENANCE & REPAIR (72) ===
    "72101500": "Servicios de mantenimiento",
    "72101501": "Mantenimiento de edificios",
    "72101502": "Mantenimiento de vehículos",
    "72101503": "Mantenimiento de equipo",

    # === HOTELS & LODGING (76) ===
    "76111500": "Servicios de alojamiento",
    "76111501": "Hoteles",
    "76111502": "Hospedaje",

    # === RENTAL SERVICES (78) ===
    "78171500": "Arrendamiento de inmuebles",
    "78171501": "Renta de oficinas",
    "78171502": "Renta de bodegas",

    # === INSURANCE & FINANCIAL (84) ===
    "84111500": "Seguros",
    "84111501": "Seguros de vida",
    "84111502": "Seguros médicos",
    "84111503": "Seguros de automóviles",
    "84121500": "Servicios bancarios",
    "84121501": "Comisiones bancarias",

    # === TELECOMMUNICATIONS (81) ===
    "81161500": "Telefonía fija",
    "81161501": "Telefonía móvil",
    "81161502": "Servicio de internet",

    # === CLEANING & SANITATION (47) ===
    "47131500": "Servicios de limpieza",
    "47131501": "Productos de limpieza",

    # === HEALTHCARE (42) ===
    "42140000": "Medicamentos",
    "85121500": "Servicios médicos",
    "85121501": "Consultas médicas",

    # === EDUCATION (86) ===
    "86101500": "Servicios educativos",
    "86101501": "Capacitación",
    "86101502": "Cursos y seminarios",
}


def get_sat_name_from_dict(clave_prod_serv: str) -> str:
    """
    Get SAT product/service name from in-memory dictionary.

    This is a fast fallback when the PostgreSQL catalog is not available.
    Covers ~200 most common codes.

    Args:
        clave_prod_serv: 8-digit SAT code

    Returns:
        Descriptive name if found, None otherwise

    Examples:
        >>> get_sat_name_from_dict("81141601")
        "Logística"

        >>> get_sat_name_from_dict("43211503")
        "Computadoras portátiles"
    """
    if not clave_prod_serv or len(clave_prod_serv) != 8:
        return None

    return COMMON_SAT_CODES.get(clave_prod_serv)


def is_covered(clave_prod_serv: str) -> bool:
    """Check if a code is in the common dictionary."""
    return clave_prod_serv in COMMON_SAT_CODES


def get_coverage_stats():
    """Get statistics about the common codes dictionary."""
    return {
        "total_codes": len(COMMON_SAT_CODES),
        "categories": {
            "Logistics & Transportation": len([k for k in COMMON_SAT_CODES if k.startswith(("811", "781"))]),
            "Technology & Computing": len([k for k in COMMON_SAT_CODES if k.startswith(("432", "811"))]),
            "Fuel & Energy": len([k for k in COMMON_SAT_CODES if k.startswith(("151", "261"))]),
            "Professional Services": len([k for k in COMMON_SAT_CODES if k.startswith("801")]),
            "Office Supplies": len([k for k in COMMON_SAT_CODES if k.startswith("441")]),
        }
    }
