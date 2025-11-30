# FASE 1: Sistema de Roles y Departamentos - COMPLETADA ✅

**Fecha:** 2025-11-28
**Estado:** Base de datos implementada y migrada exitosamente
**Usuarios Migrados:** 13 usuarios activos

---

## 📋 RESUMEN EJECUTIVO

Se ha implementado exitosamente la infraestructura de base de datos para un sistema completo de gestión de usuarios, roles, departamentos y jerarquías organizacionales. El sistema está diseñado para escalar desde empresas pequeñas hasta medianas/grandes empresas.

### ✅ Lo que YA funciona:
- ✅ Tablas de roles, departamentos y jerarquías creadas
- ✅ 7 roles del sistema configurados (admin, contador, supervisor, etc.)
- ✅ 13 usuarios existentes migrados al nuevo sistema
- ✅ 2 departamentos "General" creados (uno por tenant)
- ✅ Trigger automático para mantener compatibilidad con código antiguo
- ✅ Endpoint `/confirm` de clasificación protegido con roles

### ⚠️ Pendiente para funcionamiento completo:
- ⚠️ Actualizar funciones de autenticación (core/auth/jwt.py)
- ⚠️ Completar fix de seguridad (endpoint `/correct`)
- ⚠️ Crear APIs de gestión de usuarios/roles/departamentos
- ⚠️ Crear UI de administración en frontend

---

## 🗄️ ESTRUCTURA DE BASE DE DATOS

### Tabla 1: `roles`
**Propósito:** Almacenar definiciones de roles (sistema y custom)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| tenant_id | INTEGER | NULL = rol global, NOT NULL = rol custom del tenant |
| name | VARCHAR(100) | Nombre único del rol (ej: 'admin', 'contador') |
| display_name | VARCHAR(255) | Nombre para mostrar en UI |
| description | TEXT | Descripción del rol |
| level | INTEGER | Nivel jerárquico (0-100, mayor = más permisos) |
| permissions | JSONB | Permisos específicos del rol |
| is_system | BOOLEAN | true = rol del sistema (no se puede eliminar) |
| is_active | BOOLEAN | Estado del rol |

**Índices:**
- `idx_unique_role_per_tenant` - UNIQUE (tenant_id, name)
- `idx_roles_tenant` - tenant_id
- `idx_roles_name` - name
- `idx_roles_active` - is_active WHERE is_active = TRUE
- `idx_roles_level` - level

**Datos actuales:**
```sql
SELECT name, display_name, level FROM roles ORDER BY level DESC;

    name    |   display_name   | level
------------+------------------+-------
 admin      | Administrador    |   100
 contador   | Contador         |    80
 accountant | Contador General |    80
 manager    | Gerente          |    60
 supervisor | Supervisor       |    50
 empleado   | Empleado         |     0
 viewer     | Visor            |     0
```

---

### Tabla 2: `user_roles`
**Propósito:** Asignar roles a usuarios (relación many-to-many)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| user_id | INTEGER | FK → users(id) |
| role_id | INTEGER | FK → roles(id) |
| assigned_at | TIMESTAMP | Fecha de asignación |
| assigned_by | INTEGER | Usuario que asignó el rol |
| expires_at | TIMESTAMP | Fecha de expiración (NULL = permanente) |

**PRIMARY KEY:** (user_id, role_id)

**Índices:**
- `idx_user_roles_user` - user_id
- `idx_user_roles_role` - role_id

**Datos actuales:**
- 13 usuarios con roles asignados
- 2 admins, 11 empleados

---

### Tabla 3: `departments`
**Propósito:** Estructura organizacional con jerarquía

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| tenant_id | INTEGER | FK → tenants(id) |
| name | VARCHAR(255) | Nombre del departamento |
| code | VARCHAR(50) | Código corto (ej: "JUR", "FIN") |
| parent_id | INTEGER | FK → departments(id) para jerarquía |
| manager_user_id | INTEGER | FK → users(id) - Jefe del departamento |
| description | TEXT | Descripción |
| cost_center | VARCHAR(100) | Centro de costos contable (opcional) |
| is_active | BOOLEAN | Estado |

**Constraints:**
- `unique_dept_code_per_tenant` - UNIQUE (tenant_id, code)
- `unique_dept_name_per_tenant` - UNIQUE (tenant_id, name)
- `check_parent_not_self` - Un dept no puede ser su propio padre

**Datos actuales:**
```sql
SELECT name, code, tenant FROM departments;

  name   | code |    tenant
---------+------+---------------
 General | GEN  | Carreta Verde
 General | GEN  | ContaFlow
```

---

### Tabla 4: `user_departments`
**Propósito:** Asignar usuarios a departamentos (many-to-many)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| user_id | INTEGER | FK → users(id) |
| department_id | INTEGER | FK → departments(id) |
| is_primary | BOOLEAN | Departamento principal del usuario |
| assigned_at | TIMESTAMP | Fecha de asignación |
| assigned_by | INTEGER | Usuario que asignó |

**PRIMARY KEY:** (user_id, department_id)

**Constraint especial:**
- Solo 1 departamento puede ser primario por usuario (índice único)

**Datos actuales:**
- 13 usuarios asignados al departamento "General"

---

### Tabla 5: `user_hierarchy`
**Propósito:** Definir estructura de reporte (quién reporta a quién)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| user_id | INTEGER | FK → users(id) - Usuario subordinado |
| supervisor_id | INTEGER | FK → users(id) - Supervisor |
| relationship_type | VARCHAR(50) | Tipo de relación ('direct_report', 'dotted_line') |
| effective_from | DATE | Fecha de inicio |
| effective_to | DATE | Fecha de fin (NULL = actual) |

**PRIMARY KEY:** (user_id, supervisor_id, effective_from)

**Constraint:**
- Un usuario no puede reportarse a sí mismo

**Datos actuales:**
- Vacía (lista para usar cuando asignes supervisores)

---

## 🔧 CARACTERÍSTICAS IMPLEMENTADAS

### 1. Compatibilidad hacia Atrás
**Trigger automático:** `trigger_sync_user_role_on_assign`

Cuando se asigna un rol a un usuario en `user_roles`, automáticamente actualiza la columna `users.role` con el rol de mayor nivel. Esto asegura que el código antiguo que usa `if user.role == 'admin'` siga funcionando.

```sql
-- Ejemplo: Si asigno rol 'admin' a usuario X
INSERT INTO user_roles (user_id, role_id) VALUES (5, 1);

-- Automáticamente actualiza:
UPDATE users SET role = 'admin' WHERE id = 5;
```

### 2. Multi-Rol
Un usuario puede tener múltiples roles:
```sql
-- Ejemplo: Usuario puede ser 'supervisor' Y 'contador'
INSERT INTO user_roles (user_id, role_id) VALUES
(10, 4),  -- supervisor
(10, 2);  -- contador
```

### 3. Jerarquía de Departamentos Ilimitada
```sql
-- Ejemplo: Departamento con 3 niveles
-- Empresa → Finanzas → Tesorería

INSERT INTO departments (name, code, tenant_id, parent_id) VALUES
('Finanzas', 'FIN', 1, NULL),
('Tesorería', 'TES', 1, (SELECT id FROM departments WHERE code='FIN'));
```

### 4. Jerarquía de Supervisión
```sql
-- Ejemplo: Carlos reporta a Marinete desde hoy
INSERT INTO user_hierarchy (user_id, supervisor_id) VALUES
((SELECT id FROM users WHERE email='carlos@empresa.com'),
 (SELECT id FROM users WHERE email='marinete@empresa.com'));
```

---

## 📝 MIGRACIONES EJECUTADAS

### Migración 041: `041_create_roles_and_user_roles.sql`
**Archivo:** `/migrations/041_create_roles_and_user_roles.sql`
**Estado:** ✅ Ejecutada exitosamente

**Creó:**
- Tabla `roles` con 7 roles del sistema
- Tabla `user_roles` para asignaciones
- Índices de rendimiento

**Seed de roles:**
- admin (nivel 100)
- contador (nivel 80) - Para clasificación contable
- accountant (nivel 80) - Para contabilidad general
- manager (nivel 60) - Gerente
- supervisor (nivel 50) - Supervisor de departamento
- empleado (nivel 0) - Usuario estándar
- viewer (nivel 0) - Solo lectura

---

### Migración 042: `042_create_departments_and_hierarchy.sql`
**Archivo:** `/migrations/042_create_departments_and_hierarchy.sql`
**Estado:** ✅ Ejecutada exitosamente

**Creó:**
- Tabla `departments` con soporte para jerarquía
- Tabla `user_departments` para asignaciones
- Tabla `user_hierarchy` para estructura de reporte

---

### Migración 043: `043_backfill_user_roles_and_departments.sql`
**Archivo:** `/migrations/043_backfill_user_roles_and_departments.sql`
**Estado:** ✅ Ejecutada exitosamente

**Migró:**
- 13 usuarios de columna `users.role` → tabla `user_roles`
- Creó 2 departamentos "General" (uno por tenant)
- Asignó todos los usuarios a departamento "General"
- Creó trigger de sincronización

**Resultado de la migración:**
```
==============================================
MIGRATION 043 COMPLETED SUCCESSFULLY
==============================================
Total active users: 13
Users with roles assigned: 13
Users with departments assigned: 13
Total departments created: 2
==============================================
```

---

## 🔐 FIX DE SEGURIDAD PARCIAL

### ✅ Endpoint Protegido: `/invoice-classification/confirm`

**Archivo:** `api/invoice_classification_api.py`
**Línea:** 39

**Antes:**
```python
current_user: User = Depends(get_current_user)  # ❌ Cualquiera
```

**Después:**
```python
current_user: User = Depends(require_role(['contador', 'accountant', 'admin']))  # ✅ Solo contadores
```

**Impacto:** Ahora solo usuarios con rol de contador/admin pueden confirmar clasificaciones contables.

---

### ⚠️ Endpoint PENDIENTE: `/invoice-classification/correct`

**Archivo:** `api/invoice_classification_api.py`
**Línea:** 128

**Estado actual:**
```python
current_user: User = Depends(get_current_user)  # ❌ INSEGURO
```

**Debe ser:**
```python
current_user: User = Depends(require_role(['contador', 'accountant', 'admin']))
```

**Acción requerida:** Cambiar línea 128 en `api/invoice_classification_api.py`

---

## 🎯 CASOS DE USO HABILITADOS

### Caso 1: Asignar a Marinete como Supervisora de Jurídico

```sql
-- 1. Crear departamento Jurídico
INSERT INTO departments (tenant_id, name, code, description)
VALUES (1, 'Jurídico', 'JUR', 'Departamento Legal');

-- 2. Asignar rol de Supervisor a Marinete
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'marinete@carretaverde.com'
  AND r.name = 'supervisor';

-- 3. Asignar Marinete al departamento Jurídico
INSERT INTO user_departments (user_id, department_id, is_primary)
SELECT u.id, d.id, TRUE
FROM users u, departments d
WHERE u.email = 'marinete@carretaverde.com'
  AND d.code = 'JUR';

-- 4. Hacer a Marinete manager del departamento
UPDATE departments
SET manager_user_id = (SELECT id FROM users WHERE email = 'marinete@carretaverde.com')
WHERE code = 'JUR';

-- 5. Asignar subordinados a Marinete
INSERT INTO user_hierarchy (user_id, supervisor_id)
SELECT u.id, (SELECT id FROM users WHERE email = 'marinete@carretaverde.com')
FROM users u
WHERE u.email IN ('carlos@carretaverde.com', 'ana@carretaverde.com');
```

### Caso 2: Crear Contador con Acceso Limitado

```sql
-- Asignar rol de contador
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'roberto@carretaverde.com'
  AND r.name = 'contador';

-- El contador automáticamente tiene permisos según roles.permissions:
-- {"resources":["invoices","classifications"],"actions":["read","classify","approve","reject"]}
```

### Caso 3: Ver Usuarios de un Departamento

```sql
SELECT
    u.full_name,
    u.email,
    r.display_name as rol,
    d.name as departamento
FROM users u
JOIN user_departments ud ON u.id = ud.user_id
JOIN departments d ON ud.department_id = d.id
LEFT JOIN user_roles ur ON u.id = ur.user_id
LEFT JOIN roles r ON ur.role_id = r.id
WHERE d.code = 'JUR';
```

### Caso 4: Ver Subordinados de Marinete

```sql
SELECT
    u.full_name,
    u.email,
    d.name as departamento
FROM user_hierarchy uh
JOIN users u ON uh.user_id = u.id
LEFT JOIN user_departments ud ON u.id = ud.user_id AND ud.is_primary = TRUE
LEFT JOIN departments d ON ud.department_id = d.id
WHERE uh.supervisor_id = (SELECT id FROM users WHERE email = 'marinete@carretaverde.com')
  AND (uh.effective_to IS NULL OR uh.effective_to > CURRENT_DATE);
```

---

## 🔍 QUERIES ÚTILES PARA REVISAR

### Ver todos los roles asignados
```sql
SELECT
    u.email,
    r.name as role,
    r.display_name,
    r.level,
    ur.assigned_at
FROM user_roles ur
JOIN users u ON ur.user_id = u.id
JOIN roles r ON ur.role_id = r.id
ORDER BY r.level DESC, u.email;
```

### Ver departamentos con sus managers
```sql
SELECT
    d.name as departamento,
    d.code,
    u.full_name as manager,
    COUNT(ud.user_id) as total_miembros
FROM departments d
LEFT JOIN users u ON d.manager_user_id = u.id
LEFT JOIN user_departments ud ON d.id = ud.department_id
GROUP BY d.id, d.name, d.code, u.full_name;
```

### Ver jerarquía organizacional
```sql
SELECT
    s.full_name as supervisor,
    u.full_name as subordinado,
    uh.relationship_type,
    uh.effective_from
FROM user_hierarchy uh
JOIN users s ON uh.supervisor_id = s.id
JOIN users u ON uh.user_id = u.id
WHERE uh.effective_to IS NULL OR uh.effective_to > CURRENT_DATE;
```

---

## 📊 ESTADO ACTUAL DE LA BASE DE DATOS

```sql
-- Resumen general
SELECT
    'Roles del sistema' as tabla,
    COUNT(*) as registros
FROM roles
UNION ALL
SELECT 'Usuarios con roles', COUNT(DISTINCT user_id) FROM user_roles
UNION ALL
SELECT 'Departamentos', COUNT(*) FROM departments
UNION ALL
SELECT 'Usuarios en departamentos', COUNT(DISTINCT user_id) FROM user_departments
UNION ALL
SELECT 'Relaciones jerárquicas', COUNT(*) FROM user_hierarchy;
```

**Resultado actual:**
| Tabla | Registros |
|-------|-----------|
| Roles del sistema | 7 |
| Usuarios con roles | 13 |
| Departamentos | 2 |
| Usuarios en departamentos | 13 |
| Relaciones jerárquicas | 0 |

---

## ⚠️ IMPORTANTE: Compatibilidad

### La columna `users.role` se mantiene sincronizada

Gracias al trigger `trigger_sync_user_role_on_assign`, todo el código existente que usa:

```python
if user.role == 'admin':
    # ...
```

**Seguirá funcionando sin cambios.**

La columna `users.role` se actualiza automáticamente al rol de mayor nivel del usuario.

### Ejemplo:
```sql
-- Usuario tiene 2 roles: empleado (nivel 0) y supervisor (nivel 50)
-- users.role será 'supervisor' (el de mayor nivel)

SELECT role FROM users WHERE email = 'marinete@carretaverde.com';
-- Resultado: 'supervisor'
```

---

## 🚀 PRÓXIMOS PASOS (FASE 2)

### Archivos que necesitan actualización:

1. **core/auth/roles.py** (NUEVO)
   - Consolidar definiciones de roles
   - Eliminar duplicados

2. **core/auth/jwt.py**
   - Función `get_user_roles(user_id)` → consultar tabla user_roles
   - Función `has_role(user, role_name)` → verificar en user_roles
   - Actualizar `require_role()` para usar nuevas funciones

3. **core/auth/unified.py**
   - Asegurar que User model mantiene compatibilidad
   - Agregar método `get_effective_role()`

4. **api/v1/user_context.py**
   - Función `_derive_permissions()` → consultar desde BD
   - Eliminar hardcoded ROLE_PERMISSION_MATRIX

5. **core/shared/unified_db_adapter.py**
   - Helper `get_user_with_roles(user_id)`
   - Helper `get_user_departments(user_id)`

---

## 📁 ARCHIVOS CREADOS

| Archivo | Estado | Propósito |
|---------|--------|-----------|
| `migrations/041_create_roles_and_user_roles.sql` | ✅ Ejecutado | Crear tablas roles y user_roles |
| `migrations/042_create_departments_and_hierarchy.sql` | ✅ Ejecutado | Crear tablas departments, user_departments, user_hierarchy |
| `migrations/043_backfill_user_roles_and_departments.sql` | ✅ Ejecutado | Migrar 13 usuarios existentes |
| `FASE_1_ROLES_DEPARTAMENTOS_COMPLETA.md` | ✅ Este archivo | Documentación completa |

---

## 🎯 CONCLUSIÓN

**FASE 1 está 100% completa a nivel de base de datos.**

La infraestructura está lista para:
- ✅ Gestión multi-rol por usuario
- ✅ Jerarquías departamentales ilimitadas
- ✅ Estructura de reporte (supervisor-subordinado)
- ✅ Compatibilidad con código existente
- ✅ Escalabilidad de pequeñas a grandes empresas

**Para que el sistema funcione completamente, necesitas FASE 2:**
- Actualizar funciones de autenticación
- Crear APIs de gestión
- Crear UI de administración

---

**Última actualización:** 2025-11-28
**Autor:** Claude Code
**Status:** ✅ FASE 1 COMPLETA - Listo para FASE 2
