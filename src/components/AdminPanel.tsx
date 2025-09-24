'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth, withAuth } from './hooks/useAuth';
import { useAPI, useAPIList, useAPIMutation, API_ENDPOINTS } from './hooks/useAPI';
import { useRealTimeActivity, useRealTimeNotifications } from './hooks/useRealTime';
import { validateForm, VALIDATION_SCHEMAS, getFieldError } from './utils/validation';
import { 
  MagneticButton, 
  RippleButton, 
  TiltCard, 
  GlowCard, 
  MorphingButton,
  SlidingPanel 
} from './InteractiveElements';

// Types
interface AdminUser {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  company?: string;
  phone?: string;
  is_active: boolean;
  is_verified: boolean;
  permissions: string[];
  last_login?: string;
  login_count: number;
  projects_count: number;
  created_at: string;
  updated_at: string;
}

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user_id: string;
  username: string;
  action: string;
  resource: string;
  details: any;
  ip_address?: string;
  user_agent?: string;
  status: string;
}

interface CreateUserData {
  username: string;
  email: string;
  password: string;
  full_name: string;
  role: string;
  company?: string;
  phone?: string;
  is_active: boolean;
  permissions: string[];
}

interface UpdateUserData {
  email?: string;
  full_name?: string;
  company?: string;
  phone?: string;
  is_active?: boolean;
}

// Utility function
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 }
};

// User Stats Cards Component
const UserStatsCards: React.FC<{ users: AdminUser[] }> = ({ users }) => {
  const stats = React.useMemo(() => {
    const totalUsers = users.length;
    const activeUsers = users.filter(u => u.is_active).length;
    const verifiedUsers = users.filter(u => u.is_verified).length;
    const adminUsers = users.filter(u => u.role === 'admin' || u.role === 'super_admin').length;
    
    return [
      { label: 'Total Users', value: totalUsers, color: 'blue', icon: '👥' },
      { label: 'Active Users', value: activeUsers, color: 'green', icon: '✅' },
      { label: 'Verified Users', value: verifiedUsers, color: 'purple', icon: '🔐' },
      { label: 'Admin Users', value: adminUsers, color: 'orange', icon: '👑' },
    ];
  }, [users]);

  return (
    <motion.div 
      className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {stats.map((stat, index) => (
        <motion.div key={index} variants={itemVariants}>
          <GlowCard className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {stat.label}
                </p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white">
                  {stat.value}
                </p>
              </div>
              <div className="text-3xl">{stat.icon}</div>
            </div>
          </GlowCard>
        </motion.div>
      ))}
    </motion.div>
  );
};

// User Table Component
const UserTable: React.FC<{
  users: AdminUser[];
  loading: boolean;
  onEditUser: (user: AdminUser) => void;
  onDeleteUser: (userId: string) => void;
  onUpdateRole: (userId: string, role: string) => void;
}> = ({ users, loading, onEditUser, onDeleteUser, onUpdateRole }) => {
  
  const [sortField, setSortField] = useState<keyof AdminUser>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);

  const sortedUsers = React.useMemo(() => {
    return [...users].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      
      if (sortDirection === 'asc') {
        return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      } else {
        return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
      }
    });
  }, [users, sortField, sortDirection]);

  const handleSort = (field: keyof AdminUser) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const toggleUserSelection = (userId: string) => {
    setSelectedUsers(prev => 
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const toggleAllUsers = () => {
    setSelectedUsers(
      selectedUsers.length === users.length 
        ? [] 
        : users.map(u => u.user_id)
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedUsers.length === users.length}
                  onChange={toggleAllUsers}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              </th>
              {[
                { key: 'username', label: 'Username' },
                { key: 'email', label: 'Email' },
                { key: 'full_name', label: 'Full Name' },
                { key: 'role', label: 'Role' },
                { key: 'is_active', label: 'Status' },
                { key: 'last_login', label: 'Last Login' },
                { key: 'created_at', label: 'Created' },
              ].map(({ key, label }) => (
                <th 
                  key={key}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:text-gray-700 dark:hover:text-gray-300"
                  onClick={() => handleSort(key as keyof AdminUser)}
                >
                  <div className="flex items-center space-x-1">
                    <span>{label}</span>
                    {sortField === key && (
                      <span>
                        {sortDirection === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </div>
                </th>
              ))}
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            <AnimatePresence>
              {sortedUsers.map((user, index) => (
                <motion.tr
                  key={user.user_id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ delay: index * 0.05 }}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={selectedUsers.includes(user.user_id)}
                      onChange={() => toggleUserSelection(user.user_id)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-8 w-8">
                        <div className="h-8 w-8 rounded-full bg-gradient-to-r from-blue-400 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                          {user.username.charAt(0).toUpperCase()}
                        </div>
                      </div>
                      <div className="ml-3">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">
                          {user.username}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900 dark:text-white">{user.email}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900 dark:text-white">{user.full_name}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <select
                      value={user.role}
                      onChange={(e) => onUpdateRole(user.user_id, e.target.value)}
                      className="text-sm border-0 bg-transparent text-gray-900 dark:text-white focus:ring-0"
                    >
                      <option value="user">User</option>
                      <option value="moderator">Moderator</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={cn(
                      'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                      user.is_active 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
                    )}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex space-x-2 justify-end">
                      <button
                        onClick={() => onEditUser(user)}
                        className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDeleteUser(user.user_id)}
                        className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                        disabled={user.role === 'super_admin'}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
};

// User Form Component
const UserForm: React.FC<{
  user?: AdminUser | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateUserData | UpdateUserData) => void;
  loading: boolean;
}> = ({ user, isOpen, onClose, onSubmit, loading }) => {
  const isEdit = !!user;
  
  const [formData, setFormData] = useState<CreateUserData>({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'user',
    company: '',
    phone: '',
    is_active: true,
    permissions: []
  });
  
  const [errors, setErrors] = useState<any>([]);

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        password: '', // Don't populate password for edit
        full_name: user.full_name,
        role: user.role,
        company: user.company || '',
        phone: user.phone || '',
        is_active: user.is_active,
        permissions: user.permissions
      });
    } else {
      setFormData({
        username: '',
        email: '',
        password: '',
        full_name: '',
        role: 'user',
        company: '',
        phone: '',
        is_active: true,
        permissions: []
      });
    }
    setErrors([]);
  }, [user, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const schema = isEdit 
      ? { 
          ...VALIDATION_SCHEMAS.USER_PROFILE,
          role: { required: true }
        }
      : {
          ...VALIDATION_SCHEMAS.USER_PROFILE,
          username: VALIDATION_SCHEMAS.REGISTER.username,
          password: VALIDATION_SCHEMAS.REGISTER.password,
          role: { required: true }
        };
    
    const validation = validateForm(formData, schema);
    if (!validation.isValid) {
      setErrors(validation.errors);
      return;
    }

    if (isEdit) {
      // For edit, only send changed fields
      const { username, password, ...updateData } = formData;
      onSubmit(updateData);
    } else {
      onSubmit(formData);
    }
  };

  const updateField = (field: keyof CreateUserData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear errors for this field
    setErrors((prev: any) => prev.filter((e: any) => e.field !== field));
  };

  return (
    <SlidingPanel
      isOpen={isOpen}
      onClose={onClose}
      direction="right"
      size="md"
    >
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {isEdit ? 'Edit User' : 'Create User'}
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            {isEdit ? 'Update user information' : 'Add a new user to the system'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Username *
              </label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => updateField('username', e.target.value)}
                className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                disabled={loading}
              />
              {getFieldError(errors, 'username') && (
                <p className="mt-1 text-sm text-red-600">{getFieldError(errors, 'username')}</p>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Email *
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => updateField('email', e.target.value)}
              className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              disabled={loading}
            />
            {getFieldError(errors, 'email') && (
              <p className="mt-1 text-sm text-red-600">{getFieldError(errors, 'email')}</p>
            )}
          </div>

          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Password *
              </label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => updateField('password', e.target.value)}
                className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                disabled={loading}
              />
              {getFieldError(errors, 'password') && (
                <p className="mt-1 text-sm text-red-600">{getFieldError(errors, 'password')}</p>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Full Name *
            </label>
            <input
              type="text"
              value={formData.full_name}
              onChange={(e) => updateField('full_name', e.target.value)}
              className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              disabled={loading}
            />
            {getFieldError(errors, 'full_name') && (
              <p className="mt-1 text-sm text-red-600">{getFieldError(errors, 'full_name')}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Company
              </label>
              <input
                type="text"
                value={formData.company}
                onChange={(e) => updateField('company', e.target.value)}
                className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Phone
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => updateField('phone', e.target.value)}
                className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                disabled={loading}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Role *
              </label>
              <select
                value={formData.role}
                onChange={(e) => updateField('role', e.target.value)}
                className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                disabled={loading}
              >
                <option value="user">User</option>
                <option value="moderator">Moderator</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Status
              </label>
              <div className="flex items-center space-x-3 pt-2">
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="true"
                    checked={formData.is_active}
                    onChange={() => updateField('is_active', true)}
                    className="text-green-600"
                    disabled={loading}
                  />
                  <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">Active</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="false"
                    checked={!formData.is_active}
                    onChange={() => updateField('is_active', false)}
                    className="text-red-600"
                    disabled={loading}
                  />
                  <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">Inactive</span>
                </label>
              </div>
            </div>
          </div>

          <div className="flex space-x-4 pt-6">
            <MorphingButton
              type="submit"
              morphTo={loading ? 'loading' : undefined}
              disabled={loading}
              className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600"
            >
              {isEdit ? 'Update User' : 'Create User'}
            </MorphingButton>
            
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 px-6 py-3 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </SlidingPanel>
  );
};

// Audit Logs Component
const AuditLogs: React.FC<{
  logs: AuditLogEntry[];
  loading: boolean;
}> = ({ logs, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Activity</h3>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {logs.map((log, index) => (
          <motion.div
            key={log.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                <span className="text-blue-600 dark:text-blue-400 text-sm">
                  {log.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {log.username}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {log.action}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {log.resource}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(log.timestamp).toLocaleString()}
                  </p>
                  <span className={cn(
                    'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                    log.status === 'success' 
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
                  )}>
                    {log.status}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

// Main Admin Panel Component
const AdminPanelComponent: React.FC = () => {
  const { user, isAdmin } = useAuth();
  const { get, post, put, delete: deleteApi } = useAPI();
  
  // State management
  const [activeTab, setActiveTab] = useState<'users' | 'audit'>('users');
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [showUserForm, setShowUserForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // API hooks
  const {
    items: users,
    isLoading: usersLoading,
    error: usersError,
    refetch: refetchUsers
  } = useAPIList<AdminUser>(API_ENDPOINTS.ADMIN.USERS, {
    filters: {
      search: searchTerm,
      role: filterRole,
      status: filterStatus
    }
  });

  const {
    items: auditLogs,
    isLoading: logsLoading,
    error: logsError
  } = useAPIList<AuditLogEntry>(API_ENDPOINTS.ADMIN.AUDIT);

  // Real-time hooks
  const { activities } = useRealTimeActivity();
  const { notifications } = useRealTimeNotifications();

  // Mutations
  const createUserMutation = useAPIMutation(
    (data: CreateUserData) => post(API_ENDPOINTS.ADMIN.USERS, data),
    {
      onSuccess: () => {
        refetchUsers();
        setShowUserForm(false);
        setSelectedUser(null);
      }
    }
  );

  const updateUserMutation = useAPIMutation(
    ({ userId, data }: { userId: string; data: UpdateUserData }) => 
      put(API_ENDPOINTS.ADMIN.USER_BY_ID(userId), data),
    {
      onSuccess: () => {
        refetchUsers();
        setShowUserForm(false);
        setSelectedUser(null);
      }
    }
  );

  const deleteUserMutation = useAPIMutation(
    (userId: string) => deleteApi(API_ENDPOINTS.ADMIN.USER_BY_ID(userId)),
    {
      onSuccess: () => {
        refetchUsers();
      }
    }
  );

  const updateRoleMutation = useAPIMutation(
    ({ userId, role }: { userId: string; role: string }) =>
      put(API_ENDPOINTS.ADMIN.USER_ROLE(userId), { role }),
    {
      onSuccess: () => {
        refetchUsers();
      }
    }
  );

  // Handlers
  const handleCreateUser = () => {
    setSelectedUser(null);
    setShowUserForm(true);
  };

  const handleEditUser = (user: AdminUser) => {
    setSelectedUser(user);
    setShowUserForm(true);
  };

  const handleDeleteUser = (userId: string) => {
    if (window.confirm('Are you sure you want to delete this user?')) {
      deleteUserMutation.mutate(userId);
    }
  };

  const handleUpdateRole = (userId: string, role: string) => {
    updateRoleMutation.mutate({ userId, role });
  };

  const handleFormSubmit = (data: CreateUserData | UpdateUserData) => {
    if (selectedUser) {
      updateUserMutation.mutate({ 
        userId: selectedUser.user_id, 
        data: data as UpdateUserData 
      });
    } else {
      createUserMutation.mutate(data as CreateUserData);
    }
  };

  // Filter users based on search and filters
  const filteredUsers = React.useMemo(() => {
    return users.filter(user => {
      const matchesSearch = !searchTerm || 
        user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.full_name.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesRole = !filterRole || user.role === filterRole;
      const matchesStatus = !filterStatus || 
        (filterStatus === 'active' && user.is_active) ||
        (filterStatus === 'inactive' && !user.is_active);
      
      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, searchTerm, filterRole, filterStatus]);

  if (!isAdmin()) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Access Denied
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            You don't have permission to access the admin panel.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Admin Panel
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage users and monitor system activity
          </p>
        </motion.div>

        {/* Tabs */}
        <div className="mb-8">
          <nav className="flex space-x-8">
            {[
              { key: 'users', label: 'User Management', count: users.length },
              { key: 'audit', label: 'Audit Logs', count: auditLogs.length }
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={cn(
                  'pb-2 px-1 border-b-2 font-medium text-sm transition-colors',
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}
              >
                {tab.label} ({tab.count})
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <AnimatePresence mode="wait">
          {activeTab === 'users' && (
            <motion.div
              key="users"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              {/* Stats Cards */}
              <UserStatsCards users={users} />

              {/* Controls */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div className="flex flex-1 space-x-4">
                  <input
                    type="text"
                    placeholder="Search users..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="flex-1 rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  />
                  
                  <select
                    value={filterRole}
                    onChange={(e) => setFilterRole(e.target.value)}
                    className="rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  >
                    <option value="">All Roles</option>
                    <option value="user">User</option>
                    <option value="moderator">Moderator</option>
                    <option value="admin">Admin</option>
                  </select>
                  
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  >
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
                
                <RippleButton
                  onClick={handleCreateUser}
                  className="bg-gradient-to-r from-blue-600 to-purple-600"
                >
                  Create User
                </RippleButton>
              </div>

              {/* User Table */}
              <UserTable
                users={filteredUsers}
                loading={usersLoading}
                onEditUser={handleEditUser}
                onDeleteUser={handleDeleteUser}
                onUpdateRole={handleUpdateRole}
              />
            </motion.div>
          )}

          {activeTab === 'audit' && (
            <motion.div
              key="audit"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <AuditLogs
                logs={auditLogs}
                loading={logsLoading}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* User Form Modal */}
        <UserForm
          user={selectedUser}
          isOpen={showUserForm}
          onClose={() => {
            setShowUserForm(false);
            setSelectedUser(null);
          }}
          onSubmit={handleFormSubmit}
          loading={createUserMutation.isLoading || updateUserMutation.isLoading}
        />
      </div>
    </div>
  );
};

// Export with auth protection
export const AdminPanel = withAuth(AdminPanelComponent, [], ['admin', 'super_admin']);

export default AdminPanel;