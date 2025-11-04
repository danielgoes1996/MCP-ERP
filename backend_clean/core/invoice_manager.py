#!/usr/bin/env python3
"""
Manager para gestión completa de facturas
"""

import os
import json
import sqlite3
import logging
import datetime
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class InvoiceStatus(Enum):
    PENDIENTE = "pendiente"
    DESCARGANDO = "descargando"
    COMPLETA = "completa"
    FALLIDA = "fallida"
    NO_DISPONIBLE = "no_disponible"
    VALIDANDO = "validando"

class AttachmentType(Enum):
    PDF = "pdf"
    XML = "xml"
    IMAGE = "image"

@dataclass
class InvoiceAttachment:
    id: int
    ticket_id: int
    file_type: AttachmentType
    file_path: str
    file_size: int
    uploaded_at: str
    is_valid: bool
    validation_details: str

@dataclass
class InvoiceData:
    ticket_id: int
    status: InvoiceStatus
    pdf_path: Optional[str]
    xml_path: Optional[str]
    metadata: Dict[str, Any]
    failure_reason: Optional[str]
    last_check: str
    uuid: Optional[str]
    sat_validation: Optional[Dict[str, Any]]

class InvoiceManager:
    """
    Manager para manejar el ciclo completo de facturas
    """

    def __init__(self, db_path: str = './data/mcp_internal.db'):
        self.db_path = db_path
        self.attachments_dir = Path('./data/invoice_attachments')
        self.attachments_dir.mkdir(exist_ok=True)

    def update_invoice_status(
        self,
        ticket_id: int,
        status: InvoiceStatus,
        failure_reason: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Actualizar el estado de factura de un ticket
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Preparar datos
            current_time = datetime.datetime.now().isoformat()
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

            cursor.execute("""
                UPDATE tickets
                SET
                    invoice_status = ?,
                    invoice_failure_reason = ?,
                    invoice_metadata = ?,
                    invoice_last_check = ?
                WHERE id = ?
            """, (
                status.value,
                failure_reason,
                metadata_json,
                current_time,
                ticket_id
            ))

            conn.commit()
            conn.close()

            logger.info(f"✅ Ticket {ticket_id} invoice status updated: {status.value}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating invoice status for ticket {ticket_id}: {e}")
            return False

    def attach_invoice_file(
        self,
        ticket_id: int,
        file_content: bytes,
        file_type: AttachmentType,
        original_filename: str = None
    ) -> Optional[InvoiceAttachment]:
        """
        Adjuntar archivo de factura (PDF o XML)
        """
        try:
            # Generar nombre único para el archivo
            file_extension = file_type.value
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"ticket_{ticket_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"

            # Crear directorio por ticket
            ticket_dir = self.attachments_dir / f"ticket_{ticket_id}"
            ticket_dir.mkdir(exist_ok=True)

            file_path = ticket_dir / unique_filename

            # Guardar archivo
            with open(file_path, 'wb') as f:
                f.write(file_content)

            file_size = len(file_content)

            # Validar archivo
            validation_result = self._validate_attachment(file_path, file_type)

            # Guardar en base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO invoice_attachments
                (ticket_id, file_type, file_path, file_size, uploaded_at, is_valid, validation_details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_id,
                file_type.value,
                str(file_path),
                file_size,
                datetime.datetime.now().isoformat(),
                validation_result["is_valid"],
                json.dumps(validation_result, ensure_ascii=False)
            ))

            attachment_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Actualizar paths en tickets table
            self._update_ticket_attachment_paths(ticket_id)

            logger.info(f"✅ Archivo {file_type.value} adjuntado para ticket {ticket_id}: {file_path}")

            return InvoiceAttachment(
                id=attachment_id,
                ticket_id=ticket_id,
                file_type=file_type,
                file_path=str(file_path),
                file_size=file_size,
                uploaded_at=datetime.datetime.now().isoformat(),
                is_valid=validation_result["is_valid"],
                validation_details=json.dumps(validation_result, ensure_ascii=False)
            )

        except Exception as e:
            logger.error(f"❌ Error attaching file for ticket {ticket_id}: {e}")
            return None

    def get_invoice_data(self, ticket_id: int) -> Optional[InvoiceData]:
        """
        Obtener datos completos de factura para un ticket
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    invoice_status, invoice_pdf_path, invoice_xml_path,
                    invoice_metadata, invoice_failure_reason, invoice_last_check,
                    invoice_uuid, invoice_sat_validation
                FROM tickets
                WHERE id = ?
            """, (ticket_id,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            status_str, pdf_path, xml_path, metadata_str, failure_reason, last_check, uuid_val, sat_validation_str = result

            # Parsear JSON fields
            metadata = json.loads(metadata_str) if metadata_str else {}
            sat_validation = json.loads(sat_validation_str) if sat_validation_str else None

            return InvoiceData(
                ticket_id=ticket_id,
                status=InvoiceStatus(status_str) if status_str else InvoiceStatus.PENDIENTE,
                pdf_path=pdf_path,
                xml_path=xml_path,
                metadata=metadata,
                failure_reason=failure_reason,
                last_check=last_check or "",
                uuid=uuid_val,
                sat_validation=sat_validation
            )

        except Exception as e:
            logger.error(f"❌ Error getting invoice data for ticket {ticket_id}: {e}")
            return None

    def get_attachments(self, ticket_id: int) -> List[InvoiceAttachment]:
        """
        Obtener todos los adjuntos de un ticket
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, ticket_id, file_type, file_path, file_size,
                       uploaded_at, is_valid, validation_details
                FROM invoice_attachments
                WHERE ticket_id = ?
                ORDER BY uploaded_at DESC
            """, (ticket_id,))

            results = cursor.fetchall()
            conn.close()

            attachments = []
            for row in results:
                id, ticket_id, file_type, file_path, file_size, uploaded_at, is_valid, validation_details = row

                attachments.append(InvoiceAttachment(
                    id=id,
                    ticket_id=ticket_id,
                    file_type=AttachmentType(file_type),
                    file_path=file_path,
                    file_size=file_size,
                    uploaded_at=uploaded_at,
                    is_valid=bool(is_valid),
                    validation_details=validation_details
                ))

            return attachments

        except Exception as e:
            logger.error(f"❌ Error getting attachments for ticket {ticket_id}: {e}")
            return []

    def mark_invoice_complete(self, ticket_id: int) -> bool:
        """
        Marcar factura como completa cuando tenemos PDF + XML válidos
        """
        attachments = self.get_attachments(ticket_id)

        has_valid_pdf = any(att.file_type == AttachmentType.PDF and att.is_valid for att in attachments)
        has_valid_xml = any(att.file_type == AttachmentType.XML and att.is_valid for att in attachments)

        if has_valid_pdf and has_valid_xml:
            return self.update_invoice_status(
                ticket_id,
                InvoiceStatus.COMPLETA,
                metadata={"pdf_count": len([a for a in attachments if a.file_type == AttachmentType.PDF]),
                         "xml_count": len([a for a in attachments if a.file_type == AttachmentType.XML])}
            )
        else:
            missing = []
            if not has_valid_pdf:
                missing.append("PDF")
            if not has_valid_xml:
                missing.append("XML")

            return self.update_invoice_status(
                ticket_id,
                InvoiceStatus.FALLIDA,
                failure_reason=f"Faltan archivos válidos: {', '.join(missing)}"
            )

    def explain_failure_with_llm(self, ticket_id: int, error_context: str) -> str:
        """
        Usar LLM para explicar por qué no se pudo descargar la factura
        """
        try:
            import openai

            # Obtener detalles del ticket
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT merchant_name, raw_data FROM tickets WHERE id = ?", (ticket_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return "No se pudo obtener información del ticket"

            merchant_name, raw_data = result

            prompt = f"""
Eres un experto en facturación electrónica mexicana. Explica en español por qué no se pudo descargar automáticamente la factura para este ticket.

CONTEXTO DEL ERROR:
{error_context}

INFORMACIÓN DEL TICKET:
- Merchant: {merchant_name}
- Ticket ID: {ticket_id}

INSTRUCCIONES:
1. Explica de manera simple y clara qué pudo haber pasado
2. Sugiere pasos manuales que el usuario puede seguir
3. Mantén la explicación en 2-3 oraciones máximo
4. Sé específico sobre el problema encontrado

RESPONDE SOLO CON LA EXPLICACIÓN, SIN FORMATO ADICIONAL:
"""

            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )

            explanation = response.choices[0].message.content.strip()

            # Guardar explicación en la base de datos
            self.update_invoice_status(
                ticket_id,
                InvoiceStatus.FALLIDA,
                failure_reason=explanation
            )

            return explanation

        except Exception as e:
            logger.error(f"❌ Error generating LLM explanation for ticket {ticket_id}: {e}")
            return f"Error técnico en el proceso de descarga: {error_context}"

    def _validate_attachment(self, file_path: Path, file_type: AttachmentType) -> Dict[str, Any]:
        """
        Validar que el archivo adjuntado sea válido
        """
        try:
            if file_type == AttachmentType.PDF:
                return self._validate_pdf(file_path)
            elif file_type == AttachmentType.XML:
                return self._validate_xml(file_path)
            else:
                return {"is_valid": True, "message": "Tipo de archivo no requiere validación específica"}

        except Exception as e:
            return {"is_valid": False, "error": str(e)}

    def _validate_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Validar archivo PDF"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(10)

            if header.startswith(b'%PDF'):
                return {"is_valid": True, "message": "PDF válido", "type": "application/pdf"}
            else:
                return {"is_valid": False, "message": "No es un archivo PDF válido"}

        except Exception as e:
            return {"is_valid": False, "error": str(e)}

    def _validate_xml(self, file_path: Path) -> Dict[str, Any]:
        """Validar archivo XML"""
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(file_path)
            root = tree.getroot()

            # Verificar si es un CFDI válido
            if "Comprobante" in root.tag:
                uuid_element = root.find(".//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital")
                uuid_val = uuid_element.get("UUID") if uuid_element is not None else None

                return {
                    "is_valid": True,
                    "message": "CFDI XML válido",
                    "type": "cfdi",
                    "uuid": uuid_val
                }
            else:
                return {"is_valid": True, "message": "XML válido (formato no CFDI)", "type": "xml"}

        except Exception as e:
            return {"is_valid": False, "error": str(e)}

    def _update_ticket_attachment_paths(self, ticket_id: int):
        """Actualizar paths de archivos en la tabla tickets"""
        try:
            attachments = self.get_attachments(ticket_id)

            pdf_path = next((att.file_path for att in attachments
                           if att.file_type == AttachmentType.PDF and att.is_valid), None)
            xml_path = next((att.file_path for att in attachments
                           if att.file_type == AttachmentType.XML and att.is_valid), None)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE tickets
                SET invoice_pdf_path = ?, invoice_xml_path = ?
                WHERE id = ?
            """, (pdf_path, xml_path, ticket_id))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Error updating attachment paths for ticket {ticket_id}: {e}")

# Instancia global
invoice_manager = InvoiceManager()