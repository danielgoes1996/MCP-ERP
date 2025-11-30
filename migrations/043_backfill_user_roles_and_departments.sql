-- Migration 043: Backfill User Roles and Departments
-- Purpose: Migrate existing users to new role/department system
-- Date: 2025-11-28

-- =====================================================
-- STEP 1: CREATE DEFAULT DEPARTMENT FOR EACH TENANT
-- =====================================================

-- Create "General" department for each existing tenant
INSERT INTO departments (tenant_id, name, code, description, is_active)
SELECT DISTINCT
    t.id,
    'General',
    'GEN',
    'Departamento general para usuarios sin asignación específica',
    TRUE
FROM tenants t
WHERE NOT EXISTS (
    SELECT 1 FROM departments d
    WHERE d.tenant_id = t.id AND d.code = 'GEN'
)
ON CONFLICT (tenant_id, code) DO NOTHING;

-- =====================================================
-- STEP 2: MIGRATE EXISTING USER ROLES
-- =====================================================

-- Map existing users.role to new roles table
-- This handles the current role values: 'admin', 'user', etc.

INSERT INTO user_roles (user_id, role_id, assigned_at)
SELECT
    u.id,
    r.id,
    u.created_at
FROM users u
CROSS JOIN LATERAL (
    SELECT r.id
    FROM roles r
    WHERE r.is_system = TRUE
      AND (
          -- Map 'admin' → 'admin' role
          (LOWER(u.role) = 'admin' AND r.name = 'admin')
          OR
          -- Map 'user' → 'empleado' role
          (LOWER(u.role) = 'user' AND r.name = 'empleado')
          OR
          -- Map 'accountant' → 'accountant' role
          (LOWER(u.role) = 'accountant' AND r.name = 'accountant')
          OR
          -- Map 'contador' → 'contador' role
          (LOWER(u.role) = 'contador' AND r.name = 'contador')
          OR
          -- Map 'manager' → 'manager' role
          (LOWER(u.role) = 'manager' AND r.name = 'manager')
          OR
          -- Map 'supervisor' → 'supervisor' role
          (LOWER(u.role) = 'supervisor' AND r.name = 'supervisor')
          OR
          -- Map 'viewer' → 'viewer' role
          (LOWER(u.role) = 'viewer' AND r.name = 'viewer')
      )
    LIMIT 1
) r
WHERE u.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = u.id AND ur.role_id = r.id
  )
ON CONFLICT (user_id, role_id) DO NOTHING;

-- For any users that don't have a recognized role, assign 'empleado' as default
INSERT INTO user_roles (user_id, role_id, assigned_at)
SELECT
    u.id,
    r.id,
    u.created_at
FROM users u
JOIN roles r ON r.name = 'empleado' AND r.is_system = TRUE
WHERE u.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id
  )
ON CONFLICT (user_id, role_id) DO NOTHING;

-- =====================================================
-- STEP 3: ASSIGN USERS TO DEFAULT DEPARTMENT
-- =====================================================

-- Assign all users to the "General" department of their tenant
INSERT INTO user_departments (user_id, department_id, is_primary, assigned_at)
SELECT
    u.id,
    d.id,
    TRUE,  -- Set as primary department
    u.created_at
FROM users u
JOIN departments d ON d.tenant_id = u.tenant_id AND d.code = 'GEN'
WHERE u.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM user_departments ud WHERE ud.user_id = u.id
  )
ON CONFLICT (user_id, department_id) DO NOTHING;

-- =====================================================
-- STEP 4: CREATE TRIGGER TO SYNC users.role COLUMN
-- =====================================================

-- This trigger keeps users.role column in sync with user_roles table
-- for backward compatibility
CREATE OR REPLACE FUNCTION sync_user_role_column()
RETURNS TRIGGER AS $$
BEGIN
    -- When a role is assigned, update users.role with the highest-level role
    UPDATE users
    SET role = (
        SELECT r.name
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = NEW.user_id
        ORDER BY r.level DESC
        LIMIT 1
    )
    WHERE id = NEW.user_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sync_user_role_on_assign
AFTER INSERT OR UPDATE ON user_roles
FOR EACH ROW
EXECUTE FUNCTION sync_user_role_column();

-- =====================================================
-- STEP 5: VERIFICATION QUERIES
-- =====================================================

-- Log results of migration
DO $$
DECLARE
    total_users INTEGER;
    users_with_roles INTEGER;
    users_with_departments INTEGER;
    total_departments INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_users FROM users WHERE is_active = TRUE;
    SELECT COUNT(DISTINCT user_id) INTO users_with_roles FROM user_roles;
    SELECT COUNT(DISTINCT user_id) INTO users_with_departments FROM user_departments;
    SELECT COUNT(*) INTO total_departments FROM departments WHERE is_active = TRUE;

    RAISE NOTICE '==============================================';
    RAISE NOTICE 'MIGRATION 043 COMPLETED SUCCESSFULLY';
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'Total active users: %', total_users;
    RAISE NOTICE 'Users with roles assigned: %', users_with_roles;
    RAISE NOTICE 'Users with departments assigned: %', users_with_departments;
    RAISE NOTICE 'Total departments created: %', total_departments;
    RAISE NOTICE '==============================================';

    -- Validation: All users should have at least one role
    IF users_with_roles < total_users THEN
        RAISE WARNING 'Some users do not have roles assigned! Expected %, got %', total_users, users_with_roles;
    END IF;

    -- Validation: All users should have at least one department
    IF users_with_departments < total_users THEN
        RAISE WARNING 'Some users do not have departments assigned! Expected %, got %', total_users, users_with_departments;
    END IF;
END $$;

COMMIT;
