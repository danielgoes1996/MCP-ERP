"""
Modelos de datos para gastos empresariales completos
Definición de estructuras de datos para el MCP Server
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json


class PaymentMethod(Enum):
    """Formas de pago disponibles"""
    EFECTIVO = "efectivo"
    TARJETA_EMPRESA = "tarjeta_empresa"
    TARJETA_EMPLEADO = "tarjeta_empleado"
    TRANSFERENCIA = "transferencia"
    CHEQUE = "cheque"


class ExpenseStatus(Enum):
    """Estados del gasto"""
    BORRADOR = "draft"
    ENVIADO = "submit"
    APROBADO = "approve"
    PAGADO = "done"
    RECHAZADO = "refuse"


class WhoPaid(Enum):
    """Quién pagó el gasto"""
    EMPRESA = "company"
    EMPLEADO = "employee"


class AttachmentType(Enum):
    """Tipos de adjuntos"""
    CFDI_XML = "cfdi_xml"
    CFDI_PDF = "cfdi_pdf"
    COMPROBANTE_PAGO = "payment_receipt"
    EVIDENCIA = "evidence"
    FACTURA = "invoice"


@dataclass
class Supplier:
    """Información del proveedor"""
    name: str
    rfc: Optional[str] = None
    tax_id: Optional[str] = None  # Registro fiscal
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    def validate(self) -> List[str]:
        """Valida los datos del proveedor"""
        errors = []
        if not self.name or len(self.name.strip()) < 2:
            errors.append("Nombre del proveedor es requerido (mín. 2 caracteres)")

        if self.rfc and len(self.rfc) not in [12, 13]:
            errors.append("RFC debe tener 12 o 13 caracteres")

        return errors


@dataclass
class TaxInfo:
    """Información de impuestos"""
    subtotal: float
    iva_rate: float = 0.16  # 16% IVA por defecto
    iva_amount: float = 0.0
    total: float = 0.0

    def __post_init__(self):
        """Calcula automáticamente IVA y total si no se proporcionan"""
        if self.iva_amount == 0.0:
            self.iva_amount = round(self.subtotal * self.iva_rate, 2)

        if self.total == 0.0:
            self.total = round(self.subtotal + self.iva_amount, 2)


@dataclass
class Attachment:
    """Adjunto de un gasto"""
    filename: str
    content: Union[str, bytes]  # Base64 string o bytes
    attachment_type: AttachmentType
    mime_type: str = "application/octet-stream"
    description: Optional[str] = None

    def validate(self) -> List[str]:
        """Valida el adjunto"""
        errors = []

        if not self.filename:
            errors.append("Nombre de archivo es requerido")

        if not self.content:
            errors.append("Contenido del archivo es requerido")

        # Validaciones específicas por tipo
        if self.attachment_type == AttachmentType.CFDI_XML:
            if not self.filename.lower().endswith('.xml'):
                errors.append("Archivo CFDI XML debe tener extensión .xml")

        if self.attachment_type == AttachmentType.CFDI_PDF:
            if not self.filename.lower().endswith('.pdf'):
                errors.append("Archivo CFDI PDF debe tener extensión .pdf")

        return errors


@dataclass
class ExpenseModel:
    """Modelo completo de gasto empresarial"""

    # Campos básicos
    name: str
    description: str
    amount: float
    expense_date: datetime

    # Proveedor
    supplier: Supplier

    # Información financiera
    tax_info: TaxInfo

    # Clasificación contable
    account_code: Optional[str] = None
    analytic_account: Optional[str] = None  # Centro de costos/proyecto
    category: Optional[str] = None

    # Información de pago
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    who_paid: WhoPaid = WhoPaid.EMPLEADO

    # Empleado responsable
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None

    # Estado y control
    status: ExpenseStatus = ExpenseStatus.BORRADOR

    # Adjuntos
    attachments: List[Attachment] = field(default_factory=list)

    # CFDI específico (México)
    cfdi_uuid: Optional[str] = None
    cfdi_folio: Optional[str] = None

    # Metadatos
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    notes: Optional[str] = None

    def validate(self) -> List[str]:
        """Valida el modelo completo de gasto"""
        errors = []

        # Validaciones básicas
        if not self.name or len(self.name.strip()) < 5:
            errors.append("Nombre del gasto es requerido (mín. 5 caracteres)")

        if self.amount <= 0:
            errors.append("El monto debe ser mayor a 0")

        if not self.expense_date:
            errors.append("Fecha del gasto es requerida")

        # Validar que la fecha no sea futura
        if self.expense_date > datetime.now():
            errors.append("La fecha del gasto no puede ser futura")

        # Validar proveedor
        supplier_errors = self.supplier.validate()
        errors.extend([f"Proveedor: {error}" for error in supplier_errors])

        # Validar información de impuestos
        if self.tax_info.subtotal <= 0:
            errors.append("Subtotal debe ser mayor a 0")

        if abs(self.tax_info.total - self.amount) > 0.01:
            errors.append("El monto total debe coincidir con el monto del gasto")

        # Validar adjuntos
        for i, attachment in enumerate(self.attachments):
            attachment_errors = attachment.validate()
            errors.extend([f"Adjunto {i+1}: {error}" for error in attachment_errors])

        # Validaciones específicas para CFDI
        cfdi_xml_count = len([a for a in self.attachments if a.attachment_type == AttachmentType.CFDI_XML])
        if cfdi_xml_count > 1:
            errors.append("Solo se permite un archivo CFDI XML por gasto")

        return errors

    def to_odoo_expense_data(self) -> Dict[str, Any]:
        """Convierte el modelo a formato compatible con hr.expense de Odoo"""

        # Solo campos absolutamente básicos que sabemos que existen
        return {
            'name': self.name,
            'description': self.description,
            'price_unit': self.amount,
            'quantity': 1.0,
            'total_amount': self.tax_info.total,
            'date': self.expense_date.strftime('%Y-%m-%d'),
        }

    def _map_payment_method(self) -> str:
        """Mapea forma de pago a valores de Odoo"""
        mapping = {
            PaymentMethod.EFECTIVO: 'own_account',
            PaymentMethod.TARJETA_EMPRESA: 'company_account',
            PaymentMethod.TARJETA_EMPLEADO: 'own_account',
            PaymentMethod.TRANSFERENCIA: 'company_account',
            PaymentMethod.CHEQUE: 'company_account',
        }
        return mapping.get(self.payment_method, 'own_account')

    def _get_account_id(self) -> Optional[int]:
        """Obtiene el ID de la cuenta contable basado en el código"""
        # TODO: Implementar búsqueda en Odoo basada en account_code
        return None

    def _get_analytic_distribution(self) -> Optional[Dict]:
        """Obtiene la distribución analítica para centro de costos"""
        if self.analytic_account:
            # TODO: Implementar búsqueda de cuenta analítica en Odoo
            return {1: 100.0}  # Placeholder
        return None

    def to_json(self) -> str:
        """Serializa el modelo a JSON"""
        def datetime_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(self.__dict__, default=datetime_handler, indent=2)

    @classmethod
    def from_json(cls, json_data: Union[str, Dict[str, Any]]) -> 'ExpenseModel':
        """Crea un ExpenseModel desde JSON"""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        # Convertir fechas
        if 'expense_date' in data and isinstance(data['expense_date'], str):
            data['expense_date'] = datetime.fromisoformat(data['expense_date'])

        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        # Convertir enums
        if 'payment_method' in data:
            data['payment_method'] = PaymentMethod(data['payment_method'])

        if 'status' in data:
            data['status'] = ExpenseStatus(data['status'])

        if 'who_paid' in data:
            data['who_paid'] = WhoPaid(data['who_paid'])

        # Convertir objetos complejos
        if 'supplier' in data:
            data['supplier'] = Supplier(**data['supplier'])

        if 'tax_info' in data:
            data['tax_info'] = TaxInfo(**data['tax_info'])

        if 'attachments' in data:
            attachments = []
            for att_data in data['attachments']:
                att_data['attachment_type'] = AttachmentType(att_data['attachment_type'])
                attachments.append(Attachment(**att_data))
            data['attachments'] = attachments

        return cls(**data)