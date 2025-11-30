/**
 * Admin Users Page
 *
 * Manage users, roles, and department assignments
 */

'use client';

import { useState, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { PageHeader } from '@/components/ui/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Users as UsersIcon, Shield, Building2, X, Plus, Search, Pause, Play, Trash2, Edit } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  roles: string[];
  tenant_id: number;
  is_active: boolean;
  created_at: string;
  department_id?: number;
  departments: number[];
}

interface Role {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  level: number;
  is_system: boolean;
  is_active: boolean;
}

interface Department {
  id: number;
  name: string;
  code?: string;
  description?: string;
  is_active: boolean;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  // Modal states
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('auth_token');

      // Fetch users, roles, and departments in parallel
      const [usersRes, rolesRes, deptsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/admin/users/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/api/admin/roles/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/api/admin/departments/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      if (!usersRes.ok || !rolesRes.ok || !deptsRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const [usersData, rolesData, deptsData] = await Promise.all([
        usersRes.json(),
        rolesRes.json(),
        deptsRes.json(),
      ]);

      setUsers(usersData);
      setRoles(rolesData.filter((r: Role) => r.is_active));
      setDepartments(deptsData.filter((d: Department) => d.is_active));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setIsEditModalOpen(true);
  };

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setEditingUser(null);
  };

  const handleAssignRole = async (userId: number, roleName: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const role = roles.find(r => r.name === roleName);

      if (!role) {
        throw new Error('Role not found');
      }

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/roles`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ role_id: role.id }),
      });

      if (!response.ok) {
        throw new Error('Failed to assign role');
      }

      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to assign role');
    }
  };

  const handleRemoveRole = async (userId: number, roleName: string) => {
    try {
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/roles/${roleName}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to remove role');
      }

      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to remove role');
    }
  };

  const handleAssignDepartment = async (userId: number, departmentId: number, isPrimary: boolean = false) => {
    try {
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/departments`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          department_id: departmentId,
          is_primary: isPrimary,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to assign department');
      }

      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to assign department');
    }
  };

  const handleRemoveDepartment = async (userId: number, departmentId: number) => {
    try {
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/departments/${departmentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to remove department');
      }

      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to remove department');
    }
  };

  const handleToggleActive = async (userId: number, isActive: boolean) => {
    try {
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_active: !isActive }),
      });

      if (!response.ok) {
        throw new Error('Failed to update user status');
      }

      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update user status');
    }
  };

  const handleDeleteUser = async () => {
    if (!deletingUser) return;

    try {
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${API_BASE_URL}/api/admin/users/${deletingUser.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete user');
      }

      await fetchData();
      setIsDeleteModalOpen(false);
      setDeletingUser(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete user');
    }
  };

  const handleOpenDeleteModal = (user: User) => {
    setDeletingUser(user);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setDeletingUser(null);
  };

  // Filter users based on search and filters
  const filteredUsers = users.filter(user => {
    // Search filter
    const matchesSearch = !searchTerm ||
      user.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase());

    // Role filter
    const matchesRole = selectedRole === 'all' || user.roles.includes(selectedRole);

    // Department filter
    const matchesDepartment = selectedDepartment === 'all' ||
      user.departments.includes(parseInt(selectedDepartment));

    // Status filter
    const matchesStatus = selectedStatus === 'all' ||
      (selectedStatus === 'active' && user.is_active) ||
      (selectedStatus === 'inactive' && !user.is_active);

    return matchesSearch && matchesRole && matchesDepartment && matchesStatus;
  });

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-4 text-gray-600">Cargando usuarios...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Header */}
          <PageHeader
            title="Gestión de Usuarios"
            subtitle="Administra usuarios, roles y departamentos"
          />

          {/* Filters and Search */}
          <Card className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Search */}
              <div className="lg:col-span-2 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar por nombre o email..."
                  className="w-full pl-10 pr-4 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#60b97b]/20 focus:border-[#60b97b]"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              {/* Role Filter */}
              <select
                className="px-3 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#60b97b]/20 focus:border-[#60b97b]"
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
              >
                <option value="all">Todos los roles</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.name}>
                    {role.display_name}
                  </option>
                ))}
              </select>

              {/* Department Filter */}
              <select
                className="px-3 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#60b97b]/20 focus:border-[#60b97b]"
                value={selectedDepartment}
                onChange={(e) => setSelectedDepartment(e.target.value)}
              >
                <option value="all">Todos los departamentos</option>
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id.toString()}>
                    {dept.name} {dept.code && `(${dept.code})`}
                  </option>
                ))}
              </select>

              {/* Status Filter */}
              <select
                className="px-3 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#60b97b]/20 focus:border-[#60b97b]"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
              >
                <option value="all">Todos los estados</option>
                <option value="active">Activos</option>
                <option value="inactive">Inactivos</option>
              </select>
            </div>

            {/* Results count */}
            <div className="mt-3 text-sm text-gray-600">
              Mostrando {filteredUsers.length} de {users.length} usuarios
            </div>
          </Card>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card variant="gradient-primary" className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Usuarios</p>
                  <p className="text-3xl font-bold text-[#11446e] mt-1">{users.length}</p>
                </div>
                <div className="p-3 bg-[#11446e]/10 rounded-lg">
                  <UsersIcon className="w-6 h-6 text-[#11446e]" />
                </div>
              </div>
            </Card>

            <Card variant="gradient-green" className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Usuarios Activos</p>
                  <p className="text-3xl font-bold text-[#60b97b] mt-1">
                    {users.filter(u => u.is_active).length}
                  </p>
                </div>
                <div className="p-3 bg-[#60b97b]/10 rounded-lg">
                  <Shield className="w-6 h-6 text-[#60b97b]" />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Con Departamento</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {users.filter(u => u.departments.length > 0).length}
                  </p>
                </div>
                <div className="p-3 bg-blue-50 rounded-lg">
                  <Building2 className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </Card>
          </div>

          {/* Users Table */}
          <Card noPadding className="overflow-hidden">
            <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Usuario
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Roles
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Departamentos
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredUsers.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-10 w-10 bg-primary-100 rounded-full flex items-center justify-center">
                        <span className="text-primary-700 font-semibold text-sm">
                          {user.full_name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">
                          {user.full_name}
                        </div>
                        <div className="text-sm text-gray-500">
                          ID: {user.id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{user.email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {user.roles.map((role) => (
                        <span
                          key={role}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800"
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleToggleActive(user.id, user.is_active)}
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                        user.is_active
                          ? 'bg-green-100 text-green-800 hover:bg-green-200'
                          : 'bg-red-100 text-red-800 hover:bg-red-200'
                      }`}
                    >
                      {user.is_active ? 'Activo' : 'Inactivo'}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-500">
                      {user.departments.length > 0
                        ? `${user.departments.length} dept(s)`
                        : 'Sin asignar'}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      {/* Pausar/Reactivar */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleActive(user.id, user.is_active)}
                        title={user.is_active ? 'Pausar usuario' : 'Reactivar usuario'}
                      >
                        {user.is_active ? (
                          <Pause className="w-4 h-4 text-yellow-600" />
                        ) : (
                          <Play className="w-4 h-4 text-green-600" />
                        )}
                      </Button>

                      {/* Editar roles/departamentos */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditUser(user)}
                        title="Editar roles y departamentos"
                      >
                        <Edit className="w-4 h-4 text-[#11446e]" />
                      </Button>

                      {/* Eliminar */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenDeleteModal(user)}
                        title="Eliminar usuario"
                      >
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
              </table>
            </div>

            {users.length === 0 && (
              <EmptyState
                icon={UsersIcon}
                title="No hay usuarios"
                description="Los usuarios aparecerán aquí cuando sean creados."
              />
            )}
          </Card>

          {/* Edit User Modal */}
          {isEditModalOpen && editingUser && (
            <EditUserModal
              user={editingUser}
              roles={roles}
              departments={departments}
              onClose={handleCloseEditModal}
              onAssignRole={handleAssignRole}
              onRemoveRole={handleRemoveRole}
              onAssignDepartment={handleAssignDepartment}
              onRemoveDepartment={handleRemoveDepartment}
            />
          )}

          {/* Delete Confirmation Modal */}
          {isDeleteModalOpen && deletingUser && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 bg-black bg-opacity-50 z-40"
                onClick={handleCloseDeleteModal}
              />

              {/* Modal */}
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                  {/* Header */}
                  <div className="px-6 py-4 border-b border-gray-200">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-red-100 rounded-lg">
                        <Trash2 className="w-6 h-6 text-red-600" />
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold text-gray-900">
                          Eliminar Usuario
                        </h2>
                        <p className="text-sm text-gray-600 mt-1">
                          Esta acción no se puede deshacer
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Body */}
                  <div className="px-6 py-4">
                    <p className="text-gray-700">
                      ¿Estás seguro que deseas eliminar al usuario{' '}
                      <span className="font-semibold">{deletingUser.full_name}</span>
                      {' '}({deletingUser.email})?
                    </p>
                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                      <p className="text-sm text-red-800">
                        <strong>Advertencia:</strong> Se eliminarán todos los roles y
                        departamentos asignados a este usuario.
                      </p>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={handleCloseDeleteModal}
                    >
                      Cancelar
                    </Button>
                    <Button
                      variant="primary"
                      onClick={handleDeleteUser}
                      className="bg-red-600 hover:bg-red-700"
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      Eliminar Usuario
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

// Edit User Modal Component
interface EditUserModalProps {
  user: User;
  roles: Role[];
  departments: Department[];
  onClose: () => void;
  onAssignRole: (userId: number, roleName: string) => Promise<void>;
  onRemoveRole: (userId: number, roleName: string) => Promise<void>;
  onAssignDepartment: (userId: number, departmentId: number, isPrimary: boolean) => Promise<void>;
  onRemoveDepartment: (userId: number, departmentId: number) => Promise<void>;
}

function EditUserModal({
  user,
  roles,
  departments,
  onClose,
  onAssignRole,
  onRemoveRole,
  onAssignDepartment,
  onRemoveDepartment,
}: EditUserModalProps) {
  const [selectedRole, setSelectedRole] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [isPrimaryDept, setIsPrimaryDept] = useState(false);
  const [loading, setLoading] = useState(false);

  const availableRoles = roles.filter(r => !user.roles.includes(r.name));
  const availableDepartments = departments.filter(d => !user.departments.includes(d.id));

  const handleAddRole = async () => {
    if (!selectedRole) return;

    setLoading(true);
    try {
      await onAssignRole(user.id, selectedRole);
      setSelectedRole('');
    } finally {
      setLoading(false);
    }
  };

  const handleAddDepartment = async () => {
    if (!selectedDepartment) return;

    setLoading(true);
    try {
      await onAssignDepartment(user.id, parseInt(selectedDepartment), isPrimaryDept);
      setSelectedDepartment('');
      setIsPrimaryDept(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  Editar Usuario
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                  {user.full_name} ({user.email})
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
              >
                <X className="w-6 h-6" />
              </Button>
            </div>
          </div>

          {/* Body */}
          <div className="px-6 py-4 space-y-6">
            {/* Roles Section */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary-600" />
                Roles Asignados
              </h3>

              {/* Current Roles */}
              <div className="mb-4">
                {user.roles.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {user.roles.map((role) => (
                      <div
                        key={role}
                        className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-50 text-primary-700 rounded-lg border border-primary-200"
                      >
                        <span className="text-sm font-medium">{role}</span>
                        <button
                          onClick={() => onRemoveRole(user.id, role)}
                          disabled={loading}
                          className="text-primary-600 hover:text-primary-800 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Sin roles asignados</p>
                )}
              </div>

              {/* Add Role */}
              {availableRoles.length > 0 && (
                <div className="flex gap-2">
                  <select
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    disabled={loading}
                  >
                    <option value="">Seleccionar rol...</option>
                    {availableRoles.map((role) => (
                      <option key={role.id} value={role.name}>
                        {role.display_name} (Nivel {role.level})
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleAddRole}
                    disabled={!selectedRole || loading}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Agregar
                  </Button>
                </div>
              )}
            </div>

            {/* Departments Section */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" />
                Departamentos Asignados
              </h3>

              {/* Current Departments */}
              <div className="mb-4">
                {user.departments.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {user.departments.map((deptId) => {
                      const dept = departments.find(d => d.id === deptId);
                      return (
                        <div
                          key={deptId}
                          className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg border border-blue-200"
                        >
                          <span className="text-sm font-medium">
                            {dept?.name || `Dept #${deptId}`}
                            {dept?.code && ` (${dept.code})`}
                          </span>
                          <button
                            onClick={() => onRemoveDepartment(user.id, deptId)}
                            disabled={loading}
                            className="text-blue-600 hover:text-blue-800 transition-colors"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Sin departamentos asignados</p>
                )}
              </div>

              {/* Add Department */}
              {availableDepartments.length > 0 && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <select
                      value={selectedDepartment}
                      onChange={(e) => setSelectedDepartment(e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      disabled={loading}
                    >
                      <option value="">Seleccionar departamento...</option>
                      {availableDepartments.map((dept) => (
                        <option key={dept.id} value={dept.id}>
                          {dept.name} {dept.code && `(${dept.code})`}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleAddDepartment}
                      disabled={!selectedDepartment || loading}
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Agregar
                    </Button>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={isPrimaryDept}
                      onChange={(e) => setIsPrimaryDept(e.target.checked)}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      disabled={loading}
                    />
                    Marcar como departamento principal
                  </label>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
            <Button
              variant="secondary"
              onClick={onClose}
            >
              Cerrar
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
