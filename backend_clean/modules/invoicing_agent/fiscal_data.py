"""
Módulo para gestión de datos fiscales
Maneja la carga y validación de Constancia de Situación Fiscal (CSF)
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import PyPDF2

logger = logging.getLogger(__name__)


class FiscalDataManager:
    """
    Gestiona los datos fiscales de los usuarios/empresas
    Puede extraer información de CSF o recibirla manualmente
    """

    # Regímenes fiscales vigentes en México
    REGIMENES_FISCALES = {
        "601": "General de Ley Personas Morales",
        "603": "Personas Morales con Fines no Lucrativos",
        "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
        "606": "Arrendamiento",
        "607": "Régimen de Enajenación o Adquisición de Bienes",
        "608": "Demás ingresos",
        "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
        "611": "Ingresos por Dividendos (socios y accionistas)",
        "612": "Personas Físicas con Actividades Empresariales y Profesionales",
        "614": "Ingresos por intereses",
        "615": "Régimen de los ingresos por obtención de premios",
        "616": "Sin obligaciones fiscales",
        "620": "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
        "621": "Incorporación Fiscal",
        "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
        "623": "Opcional para Grupos de Sociedades",
        "624": "Coordinados",
        "625": "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
        "626": "Régimen Simplificado de Confianza",
    }

    # Usos de CFDI
    USOS_CFDI = {
        "G01": "Adquisición de mercancías",
        "G02": "Devoluciones, descuentos o bonificaciones",
        "G03": "Gastos en general",
        "I01": "Construcciones",
        "I02": "Mobiliario y equipo de oficina por inversiones",
        "I03": "Equipo de transporte",
        "I04": "Equipo de cómputo y accesorios",
        "I05": "Dados, troqueles, moldes, matrices y herramental",
        "I06": "Comunicaciones telefónicas",
        "I07": "Comunicaciones satelitales",
        "I08": "Otra maquinaria y equipo",
        "D01": "Honorarios médicos, dentales y gastos hospitalarios",
        "D02": "Gastos médicos por incapacidad o discapacidad",
        "D03": "Gastos funerales",
        "D04": "Donativos",
        "D05": "Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)",
        "D06": "Aportaciones voluntarias al SAR",
        "D07": "Primas por seguros de gastos médicos",
        "D08": "Gastos de transportación escolar obligatoria",
        "D09": "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones",
        "D10": "Pagos por servicios educativos (colegiaturas)",
        "P01": "Por definir",
        "S01": "Sin efectos fiscales",
        "CP01": "Pagos",
        "CN01": "Nómina",
    }

    def __init__(self):
        self.fiscal_data_storage = Path("data/fiscal_data.json")
        self.fiscal_data_storage.parent.mkdir(exist_ok=True)
        self.load_stored_data()

    def load_stored_data(self) -> Dict[str, Any]:
        """Carga datos fiscales almacenados"""
        if self.fiscal_data_storage.exists():
            try:
                with open(self.fiscal_data_storage, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando datos fiscales: {e}")
        return {}

    def save_fiscal_data(self, rfc: str, data: Dict[str, Any]) -> bool:
        """Guarda datos fiscales"""
        try:
            stored_data = self.load_stored_data()
            stored_data[rfc] = {
                **data,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.fiscal_data_storage, 'w') as f:
                json.dump(stored_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error guardando datos fiscales: {e}")
            return False

    async def extract_from_csf_pdf(self, pdf_content: bytes) -> Optional[Dict[str, Any]]:
        """
        Extrae información de una Constancia de Situación Fiscal en PDF

        Args:
            pdf_content: Contenido del PDF en bytes

        Returns:
            Datos fiscales extraídos o None si falla
        """
        try:
            import io
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Extraer texto de todas las páginas
            full_text = ""
            for page in pdf_reader.pages:
                full_text += page.extract_text()

            # Extraer información con patrones
            return self._parse_csf_text(full_text)

        except Exception as e:
            logger.error(f"Error extrayendo datos de CSF: {e}")
            return None

    def _parse_csf_text(self, text: str) -> Dict[str, Any]:
        """Parsea el texto de una CSF"""
        data = {}

        # Patrones de búsqueda
        patterns = {
            'rfc': r'RFC[:\s]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})',
            'nombre': r'(?:Nombre|Razón Social|Denominación)[:\s]*(.+?)(?:\n|RFC)',
            'regimen': r'Régimen[:\s]*(\d{3})\s*-?\s*(.+?)(?:\n|$)',
            'cp': r'(?:Código Postal|C\.P\.)[:\s]*(\d{5})',
            'estado': r'(?:Estado|Entidad)[:\s]*(.+?)(?:\n|$)',
            'municipio': r'(?:Municipio|Delegación)[:\s]*(.+?)(?:\n|$)',
            'colonia': r'(?:Colonia)[:\s]*(.+?)(?:\n|$)',
            'calle': r'(?:Calle)[:\s]*(.+?)(?:\n|$)',
            'numero_exterior': r'(?:Número Exterior|No\. Ext\.)[:\s]*(.+?)(?:\n|$)',
            'numero_interior': r'(?:Número Interior|No\. Int\.)[:\s]*(.+?)(?:\n|$)',
            'email': r'(?:Correo Electrónico|Email)[:\s]*([^\s]+@[^\s]+)',
            'fecha_inicio': r'(?:Fecha de Inicio|Fecha inicio de operaciones)[:\s]*(\d{2}/\d{2}/\d{4})',
        }

        # Buscar patrones
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                if field == 'regimen':
                    data['regimen_fiscal'] = {
                        'clave': match.group(1),
                        'descripcion': match.group(2).strip()
                    }
                else:
                    data[field] = match.group(1).strip()

        # Validar RFC
        if 'rfc' in data:
            data['rfc'] = data['rfc'].upper()
            data['tipo_persona'] = 'moral' if len(data['rfc']) == 12 else 'fisica'

        # Construir dirección completa
        if any(k in data for k in ['calle', 'numero_exterior', 'colonia', 'cp']):
            direccion_parts = []
            if 'calle' in data:
                direccion_parts.append(data['calle'])
            if 'numero_exterior' in data:
                direccion_parts.append(f"No. {data['numero_exterior']}")
            if 'numero_interior' in data:
                direccion_parts.append(f"Int. {data['numero_interior']}")
            if 'colonia' in data:
                direccion_parts.append(f"Col. {data['colonia']}")
            if 'cp' in data:
                direccion_parts.append(f"C.P. {data['cp']}")
            if 'municipio' in data:
                direccion_parts.append(data['municipio'])
            if 'estado' in data:
                direccion_parts.append(data['estado'])

            data['direccion_completa'] = ", ".join(direccion_parts)

        return data

    def validate_rfc(self, rfc: str) -> bool:
        """
        Valida formato de RFC mexicano

        Args:
            rfc: RFC a validar

        Returns:
            True si es válido
        """
        # Patrón para persona moral (12 caracteres)
        moral_pattern = r'^[A-Z&Ñ]{3}\d{6}[A-Z0-9]{3}$'
        # Patrón para persona física (13 caracteres)
        fisica_pattern = r'^[A-Z&Ñ]{4}\d{6}[A-Z0-9]{3}$'

        rfc = rfc.upper().strip()
        return bool(re.match(moral_pattern, rfc) or re.match(fisica_pattern, rfc))

    def validate_codigo_postal(self, cp: str) -> bool:
        """Valida código postal mexicano (5 dígitos)"""
        return bool(re.match(r'^\d{5}$', str(cp)))

    def create_fiscal_profile(
        self,
        rfc: str,
        nombre: str,
        regimen_fiscal: str,
        codigo_postal: str,
        estado: str,
        municipio: str,
        email: Optional[str] = None,
        telefono: Optional[str] = None,
        direccion: Optional[str] = None,
        uso_cfdi_default: str = "G03"
    ) -> Dict[str, Any]:
        """
        Crea un perfil fiscal completo

        Args:
            rfc: RFC del contribuyente
            nombre: Nombre o razón social
            regimen_fiscal: Clave del régimen fiscal
            codigo_postal: Código postal
            estado: Estado
            municipio: Municipio/Ciudad
            email: Email opcional
            telefono: Teléfono opcional
            direccion: Dirección completa opcional
            uso_cfdi_default: Uso de CFDI por defecto

        Returns:
            Perfil fiscal completo
        """
        if not self.validate_rfc(rfc):
            raise ValueError(f"RFC inválido: {rfc}")

        if not self.validate_codigo_postal(codigo_postal):
            raise ValueError(f"Código postal inválido: {codigo_postal}")

        if regimen_fiscal not in self.REGIMENES_FISCALES:
            raise ValueError(f"Régimen fiscal inválido: {regimen_fiscal}")

        profile = {
            'rfc': rfc.upper(),
            'nombre': nombre,
            'tipo_persona': 'moral' if len(rfc) == 12 else 'fisica',
            'regimen_fiscal': {
                'clave': regimen_fiscal,
                'descripcion': self.REGIMENES_FISCALES[regimen_fiscal]
            },
            'codigo_postal': codigo_postal,
            'estado': estado,
            'municipio': municipio,
            'email': email,
            'telefono': telefono,
            'direccion': direccion,
            'uso_cfdi_default': uso_cfdi_default,
            'created_at': datetime.now().isoformat(),
            'active': True
        }

        # Guardar perfil
        self.save_fiscal_data(rfc, profile)

        return profile

    def get_fiscal_profile(self, rfc: str) -> Optional[Dict[str, Any]]:
        """Obtiene un perfil fiscal por RFC"""
        stored_data = self.load_stored_data()
        return stored_data.get(rfc.upper())

    def list_regimenes_fiscales(self) -> List[Dict[str, str]]:
        """Lista todos los regímenes fiscales disponibles"""
        return [
            {'clave': k, 'descripcion': v}
            for k, v in self.REGIMENES_FISCALES.items()
        ]

    def list_usos_cfdi(self) -> List[Dict[str, str]]:
        """Lista todos los usos de CFDI disponibles"""
        return [
            {'clave': k, 'descripcion': v}
            for k, v in self.USOS_CFDI.items()
        ]


# Función helper para usar desde la API
async def extract_fiscal_data_from_csf(file_content: bytes) -> Optional[Dict[str, Any]]:
    """
    Extrae datos fiscales de una CSF

    Args:
        file_content: Contenido del archivo CSF

    Returns:
        Datos fiscales extraídos
    """
    manager = FiscalDataManager()
    return await manager.extract_from_csf_pdf(file_content)


def create_or_update_fiscal_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea o actualiza un perfil fiscal

    Args:
        data: Datos del perfil fiscal

    Returns:
        Perfil fiscal creado/actualizado
    """
    manager = FiscalDataManager()
    return manager.create_fiscal_profile(**data)


if __name__ == "__main__":
    # Test del módulo
    manager = FiscalDataManager()

    # Test crear perfil
    test_profile = manager.create_fiscal_profile(
        rfc="XAXX010101000",
        nombre="Empresa de Prueba SA de CV",
        regimen_fiscal="601",
        codigo_postal="01000",
        estado="Ciudad de México",
        municipio="Álvaro Obregón",
        email="facturacion@empresa.com",
        direccion="Av. Insurgentes Sur 1234, Col. Del Valle"
    )

    print("Perfil fiscal creado:")
    print(json.dumps(test_profile, indent=2, ensure_ascii=False))

    # Listar regímenes
    print("\nRegímenes fiscales disponibles:")
    for regimen in manager.list_regimenes_fiscales()[:5]:
        print(f"  {regimen['clave']}: {regimen['descripcion']}")