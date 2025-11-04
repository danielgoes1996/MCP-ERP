"""
Modelos de datos para cuentas de pago de usuarios
Incluye soporte para bancos, efectivo, terminales y tarjetas de crédito
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import sqlite3
import logging

logger = logging.getLogger(__name__)


class BankingInstitution(BaseModel):
    """Modelo para instituciones bancarias"""
    id: Optional[int] = None
    name: str
    short_name: Optional[str] = None
    type: str = "bank"
    active: bool = True
    sort_order: int = 100


class TipoCuenta(str, Enum):
    """Tipos de cuenta principales"""
    BANCARIA = "bancaria"
    EFECTIVO = "efectivo"
    TERMINAL = "terminal"


class SubtipoCuenta(str, Enum):
    """Subtipos de cuenta (solo para cuentas bancarias)"""
    DEBITO = "debito"
    CREDITO = "credito"


class EstadoSaldo(str, Enum):
    """Estados posibles del saldo"""
    POSITIVO = "positivo"
    CERO = "cero"
    NEGATIVO = "negativo"
    DISPONIBLE = "disponible"      # Para tarjetas de crédito con buen crédito
    MEDIO = "medio"                # Para tarjetas de crédito con crédito medio
    BAJO = "bajo"                  # Para tarjetas de crédito con poco crédito
    SIN_CREDITO = "sin_credito"    # Para tarjetas de crédito sin crédito


class UserPaymentAccount(BaseModel):
    """Modelo principal para cuentas de pago de usuarios"""

    # Campos obligatorios
    id: Optional[int] = None
    nombre: str = Field(..., min_length=1, max_length=200)
    tipo: TipoCuenta
    subtipo: Optional[SubtipoCuenta] = None
    moneda: str = Field(default="MXN", max_length=3)
    saldo_inicial: float = Field(default=0.0)
    saldo_actual: float = Field(default=0.0)
    propietario_id: int = Field(..., gt=0)
    tenant_id: int = Field(..., gt=0)
    activo: bool = Field(default=True)

    # Campos específicos para tarjetas de crédito
    limite_credito: Optional[float] = None
    fecha_corte: Optional[int] = None
    fecha_pago: Optional[int] = None
    credito_disponible: Optional[float] = None

    # Metadatos específicos por tipo
    proveedor_terminal: Optional[str] = None
    banco_nombre: Optional[str] = None
    numero_tarjeta: Optional[str] = None
    numero_cuenta: Optional[str] = None                    # Número de cuenta bancaria completo
    numero_cuenta_enmascarado: Optional[str] = None        # Versión enmascarada para mostrar
    clabe: Optional[str] = None                            # CLABE interbancaria (18 dígitos)
    numero_identificacion: Optional[str] = None

    # Auditoría
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('fecha_corte', 'fecha_pago')
    @classmethod
    def validate_fechas(cls, v):
        """Validar que las fechas estén en rango válido"""
        if v is not None and (v < 1 or v > 31):
            raise ValueError('Las fechas deben estar entre 1 y 31')
        return v

    @field_validator('limite_credito')
    @classmethod
    def validate_limite_credito(cls, v):
        """Validar que el límite de crédito sea positivo"""
        if v is not None and v <= 0:
            raise ValueError('El límite de crédito debe ser mayor a 0')
        return v

    @field_validator('numero_tarjeta')
    @classmethod
    def validate_numero_tarjeta(cls, v):
        """Validar formato de número de tarjeta"""
        if v is not None:
            # Permitir número completo (13-19 dígitos) o últimos 4 dígitos
            if not v.isdigit() or not (4 <= len(v) <= 19):
                raise ValueError('El número de tarjeta debe tener entre 4 y 19 dígitos')
        return v

    @field_validator('clabe')
    @classmethod
    def validate_clabe(cls, v):
        """Validar formato de CLABE (18 dígitos)"""
        if v is not None and v != '' and (not v.isdigit() or len(v) != 18):
            raise ValueError('La CLABE debe ser exactamente 18 dígitos')
        return v

    def model_post_init(self, __context):
        """Validaciones adicionales después de la inicialización"""
        # Validar que las cuentas bancarias tengan subtipo
        if self.tipo == TipoCuenta.BANCARIA and not self.subtipo:
            raise ValueError('Las cuentas bancarias requieren especificar subtipo (débito o crédito)')

        # Validar que solo las cuentas bancarias tengan subtipo
        if self.tipo != TipoCuenta.BANCARIA and self.subtipo:
            raise ValueError('Solo las cuentas bancarias pueden tener subtipo')

        # Validar campos específicos de tarjetas de crédito
        if self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.CREDITO:
            if not all([self.limite_credito, self.fecha_corte, self.fecha_pago, self.numero_tarjeta]):
                raise ValueError('Las tarjetas de crédito requieren: limite_credito, fecha_corte, fecha_pago y numero_tarjeta')

        # Validar campos específicos de cuentas bancarias
        if self.tipo == TipoCuenta.BANCARIA and not self.banco_nombre:
            raise ValueError('Las cuentas bancarias requieren especificar banco_nombre')

        # Validar campos específicos de terminales
        if self.tipo == TipoCuenta.TERMINAL and not self.proveedor_terminal:
            raise ValueError('Los terminales de pago requieren especificar proveedor_terminal')

    @property
    def estado_saldo(self) -> EstadoSaldo:
        """Calcular estado del saldo según el tipo de cuenta"""
        if self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.CREDITO and self.limite_credito:
            if not self.credito_disponible:
                return EstadoSaldo.SIN_CREDITO

            porcentaje_disponible = self.credito_disponible / self.limite_credito
            if porcentaje_disponible > 0.8:
                return EstadoSaldo.DISPONIBLE
            elif porcentaje_disponible > 0.5:
                return EstadoSaldo.MEDIO
            elif porcentaje_disponible > 0:
                return EstadoSaldo.BAJO
            else:
                return EstadoSaldo.SIN_CREDITO
        else:
            if self.saldo_actual > 0:
                return EstadoSaldo.POSITIVO
            elif self.saldo_actual == 0:
                return EstadoSaldo.CERO
            else:
                return EstadoSaldo.NEGATIVO

    @property
    def nombre_completo(self) -> str:
        """Generar nombre completo descriptivo"""
        if self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.DEBITO:
            return f"{self.banco_nombre} Débito {self.numero_cuenta_enmascarado or self.numero_tarjeta or ''}".strip()
        elif self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.CREDITO:
            return f"{self.banco_nombre} Crédito {self.numero_tarjeta}".strip()
        elif self.tipo == TipoCuenta.TERMINAL:
            return f"Terminal {self.proveedor_terminal or 'Genérico'}"
        else:
            return self.nombre

    @property
    def porcentaje_usado(self) -> Optional[float]:
        """Calcular porcentaje usado para tarjetas de crédito"""
        if self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.CREDITO and self.limite_credito and self.limite_credito > 0:
            return round((self.saldo_actual / self.limite_credito) * 100, 2)
        return None

    @property
    def tipo_descriptivo(self) -> str:
        """Generar descripción legible del tipo de cuenta"""
        if self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.DEBITO:
            return "Cuenta Bancaria (Débito)"
        elif self.tipo == TipoCuenta.BANCARIA and self.subtipo == SubtipoCuenta.CREDITO:
            return "Cuenta Bancaria (Crédito)"
        elif self.tipo == TipoCuenta.EFECTIVO:
            return "Efectivo"
        elif self.tipo == TipoCuenta.TERMINAL:
            return "Terminal de Pago"
        else:
            return self.tipo.value.title()


class CreateUserPaymentAccountRequest(BaseModel):
    """Request para crear nueva cuenta de pago"""
    nombre: str = Field(..., min_length=1, max_length=200)
    tipo: TipoCuenta
    subtipo: Optional[SubtipoCuenta] = None
    moneda: str = Field(default="MXN", max_length=3)
    saldo_inicial: float = Field(default=0.0)

    # Campos específicos para tarjetas de crédito
    limite_credito: Optional[float] = None
    fecha_corte: Optional[int] = None
    fecha_pago: Optional[int] = None

    # Metadatos específicos por tipo
    proveedor_terminal: Optional[str] = None
    banco_nombre: Optional[str] = None
    numero_tarjeta: Optional[str] = None
    numero_cuenta: Optional[str] = None
    numero_cuenta_enmascarado: Optional[str] = None
    clabe: Optional[str] = None
    numero_identificacion: Optional[str] = None


class UpdateUserPaymentAccountRequest(BaseModel):
    """Request para actualizar cuenta de pago"""
    nombre: Optional[str] = None
    tipo: Optional[TipoCuenta] = None
    subtipo: Optional[SubtipoCuenta] = None
    moneda: Optional[str] = None
    saldo_inicial: Optional[float] = None
    activo: Optional[bool] = None

    # Campos específicos para tarjetas de crédito
    limite_credito: Optional[float] = None
    fecha_corte: Optional[int] = None
    fecha_pago: Optional[int] = None

    # Metadatos específicos por tipo
    proveedor_terminal: Optional[str] = None
    banco_nombre: Optional[str] = None
    numero_tarjeta: Optional[str] = None
    numero_cuenta: Optional[str] = None
    numero_cuenta_enmascarado: Optional[str] = None
    clabe: Optional[str] = None
    numero_identificacion: Optional[str] = None


class UserPaymentAccountResponse(BaseModel):
    """Response completa con información calculada"""
    account: UserPaymentAccount
    estado_saldo: EstadoSaldo
    nombre_completo: str
    porcentaje_usado: Optional[float] = None

    # Información adicional para tarjetas de crédito
    proxima_fecha_corte: Optional[str] = None
    proxima_fecha_pago: Optional[str] = None


class UserPaymentAccountService:
    """Servicio para gestionar cuentas de pago de usuarios"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Obtener conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
        return conn

    def get_banking_institutions(self, active_only: bool = True) -> List[BankingInstitution]:
        """Obtener lista de instituciones bancarias"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, short_name, type, active, sort_order
                    FROM banking_institutions
                """

                if active_only:
                    query += " WHERE active = TRUE"

                query += " ORDER BY sort_order, name"

                cursor.execute(query)
                rows = cursor.fetchall()

                institutions = []
                for row in rows:
                    institution = BankingInstitution(
                        id=row["id"],
                        name=row["name"],
                        short_name=row["short_name"] if row["short_name"] else None,
                        type=row["type"],
                        active=bool(row["active"]),
                        sort_order=row["sort_order"]
                    )
                    institutions.append(institution)

                return institutions

        except sqlite3.Error as e:
            logger.error(f"Database error getting banking institutions: {e}")
            raise RuntimeError(f"Error al obtener instituciones bancarias: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting banking institutions: {e}")
            raise

    def create_account(self, request: CreateUserPaymentAccountRequest, user_id: int, tenant_id: int) -> UserPaymentAccount:
        """Crear nueva cuenta de pago"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Validar que el usuario existe
                cursor.execute("SELECT id FROM users WHERE id = ? AND tenant_id = ?", (user_id, tenant_id))
                if not cursor.fetchone():
                    raise ValueError("Usuario no encontrado")

                # Insertar nueva cuenta
                cursor.execute("""
                    INSERT INTO user_payment_accounts (
                        nombre, tipo, subtipo, moneda, saldo_inicial, saldo_actual,
                        propietario_id, tenant_id, limite_credito, fecha_corte, fecha_pago,
                        proveedor_terminal, banco_nombre, numero_tarjeta,
                        numero_cuenta, numero_cuenta_enmascarado, clabe, numero_identificacion, activo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request.nombre, request.tipo.value, request.subtipo.value if request.subtipo else None, request.moneda,
                    request.saldo_inicial, request.saldo_inicial,  # saldo_actual = saldo_inicial inicialmente
                    user_id, tenant_id,
                    request.limite_credito, request.fecha_corte, request.fecha_pago,
                    request.proveedor_terminal, request.banco_nombre, request.numero_tarjeta,
                    request.numero_cuenta, request.numero_cuenta_enmascarado, request.clabe, request.numero_identificacion, True
                ))

                account_id = cursor.lastrowid
                logger.info(f"Account created: {account_id} for user {user_id}")

                # Construir el objeto UserPaymentAccount directamente
                account_data = {
                    'id': account_id,
                    'nombre': request.nombre,
                    'tipo': request.tipo,
                    'subtipo': request.subtipo,
                    'moneda': request.moneda,
                    'saldo_inicial': request.saldo_inicial,
                    'saldo_actual': request.saldo_inicial,
                    'propietario_id': user_id,
                    'tenant_id': tenant_id,
                    'limite_credito': request.limite_credito,
                    'fecha_corte': request.fecha_corte,
                    'fecha_pago': request.fecha_pago,
                    'proveedor_terminal': request.proveedor_terminal,
                    'banco_nombre': request.banco_nombre,
                    'numero_tarjeta': request.numero_tarjeta,
                    'numero_cuenta': request.numero_cuenta,
                    'numero_cuenta_enmascarado': request.numero_cuenta_enmascarado,
                    'clabe': request.clabe,
                    'numero_identificacion': request.numero_identificacion,
                    'activo': True,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }

                return UserPaymentAccount(**account_data)

        except Exception as e:
            logger.error(f"Error creating account: {e}")
            raise

    def get_account(self, account_id: int, user_id: int, tenant_id: int) -> UserPaymentAccount:
        """Obtener cuenta específica"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM user_payment_accounts
                    WHERE id = ? AND propietario_id = ? AND tenant_id = ?
                """, (account_id, user_id, tenant_id))

                row = cursor.fetchone()
                if not row:
                    raise ValueError("Cuenta no encontrada")

                return self._row_to_account(row)

        except Exception as e:
            logger.error(f"Error getting account {account_id}: {e}")
            raise

    def get_user_accounts(self, user_id: int, tenant_id: int, active_only: bool = True) -> List[UserPaymentAccount]:
        """Obtener todas las cuentas de un usuario"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT * FROM user_payment_accounts
                    WHERE propietario_id = ? AND tenant_id = ?
                """
                params = [user_id, tenant_id]

                if active_only:
                    query += " AND activo = ?"
                    params.append(True)

                query += " ORDER BY tipo, nombre"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_account(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting user accounts for {user_id}: {e}")
            raise

    def update_account(self, account_id: int, user_id: int, tenant_id: int,
                      request: UpdateUserPaymentAccountRequest) -> UserPaymentAccount:
        """Actualizar cuenta existente"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Verificar que la cuenta existe y pertenece al usuario
                cursor.execute("""
                    SELECT id FROM user_payment_accounts
                    WHERE id = ? AND propietario_id = ? AND tenant_id = ?
                """, (account_id, user_id, tenant_id))

                if not cursor.fetchone():
                    raise ValueError("Cuenta no encontrada")

                # Construir query dinámico para actualizar solo campos proporcionados
                update_fields = []
                update_values = []

                for field, value in request.dict(exclude_unset=True).items():
                    if value is not None:
                        update_fields.append(f"{field} = ?")
                        # Manejar enums correctamente
                        if hasattr(value, 'value'):
                            update_values.append(value.value)
                        else:
                            update_values.append(value)

                if update_fields:
                    update_values.append(account_id)
                    query = f"UPDATE user_payment_accounts SET {', '.join(update_fields)} WHERE id = ?"
                    cursor.execute(query, update_values)

                logger.info(f"Account updated: {account_id}")
                return self.get_account(account_id, user_id, tenant_id)

        except Exception as e:
            logger.error(f"Error updating account {account_id}: {e}")
            raise

    def delete_account(self, account_id: int, user_id: int, tenant_id: int) -> bool:
        """Desactivar cuenta (soft delete)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE user_payment_accounts
                    SET activo = FALSE
                    WHERE id = ? AND propietario_id = ? AND tenant_id = ?
                """, (account_id, user_id, tenant_id))

                if cursor.rowcount == 0:
                    raise ValueError("Cuenta no encontrada")

                logger.info(f"Account deactivated: {account_id}")
                return True

        except Exception as e:
            logger.error(f"Error deactivating account {account_id}: {e}")
            raise

    def get_accounts_by_type(self, user_id: int, tenant_id: int, tipo: TipoCuenta) -> List[UserPaymentAccount]:
        """Obtener cuentas por tipo específico"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM user_payment_accounts
                    WHERE propietario_id = ? AND tenant_id = ? AND tipo = ? AND activo = ?
                    ORDER BY nombre
                """, (user_id, tenant_id, tipo.value, True))

                rows = cursor.fetchall()
                return [self._row_to_account(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting accounts by type {tipo} for user {user_id}: {e}")
            raise

    def _row_to_account(self, row: sqlite3.Row) -> UserPaymentAccount:
        """Convertir fila de base de datos a modelo"""
        return UserPaymentAccount(
            id=row['id'],
            nombre=row['nombre'],
            tipo=TipoCuenta(row['tipo']),
            subtipo=SubtipoCuenta(row['subtipo']) if row['subtipo'] else None,
            moneda=row['moneda'],
            saldo_inicial=row['saldo_inicial'],
            saldo_actual=row['saldo_actual'],
            propietario_id=row['propietario_id'],
            tenant_id=row['tenant_id'],
            limite_credito=row['limite_credito'],
            fecha_corte=row['fecha_corte'],
            fecha_pago=row['fecha_pago'],
            credito_disponible=row['credito_disponible'],
            proveedor_terminal=row['proveedor_terminal'],
            banco_nombre=row['banco_nombre'],
            numero_tarjeta=row['numero_tarjeta'],
            numero_cuenta=row['numero_cuenta'],  # Added missing field
            numero_cuenta_enmascarado=row['numero_cuenta_enmascarado'],
            clabe=row['clabe'],  # Added missing field
            numero_identificacion=row['numero_identificacion'],
            activo=bool(row['activo']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )


# Instancia global del servicio
payment_account_service = UserPaymentAccountService()


if __name__ == "__main__":
    # Test básico del servicio
    service = UserPaymentAccountService()

    # Obtener cuentas del usuario de prueba
    try:
        accounts = service.get_user_accounts(9, 3)  # dgomezes96@gmail.com
        print(f"✅ Found {len(accounts)} accounts")

        for account in accounts:
            print(f"  - {account.nombre_completo} ({account.tipo.value})")
            print(f"    Saldo: {account.saldo_actual} {account.moneda}")
            print(f"    Estado: {account.estado_saldo.value}")
            if account.tipo == TipoCuenta.TARJETA_CREDITO:
                print(f"    Crédito disponible: {account.credito_disponible}")
                print(f"    Porcentaje usado: {account.porcentaje_usado}%")
            print()

    except Exception as e:
        print(f"❌ Test failed: {e}")
