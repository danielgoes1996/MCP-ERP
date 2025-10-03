/**
 * JWT Authentication Interceptor
 * Shared authentication logic for all protected pages
 */

// =====================================================
// TOKEN MANAGEMENT
// =====================================================

/**
 * Get JWT token from localStorage
 */
function getAuthToken() {
    return localStorage.getItem('access_token');
}

/**
 * Get current user data from localStorage
 */
function getCurrentUser() {
    const userData = localStorage.getItem('user_data');
    return userData ? JSON.parse(userData) : null;
}

/**
 * Check if user is logged in, redirect to login if not
 */
function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/static/auth-login.html';
        return false;
    }
    return true;
}

// =====================================================
// AUTHENTICATED FETCH
// =====================================================

/**
 * Create authenticated fetch with JWT token
 * Automatically adds Authorization header and handles 401/403 errors
 *
 * @param {string} url - URL to fetch
 * @param {object} options - Fetch options
 * @returns {Promise<Response>} - Fetch response
 */
async function authenticatedFetch(url, options = {}) {
    const token = getAuthToken();

    if (!token) {
        window.location.href = '/static/auth-login.html';
        throw new Error('No authentication token');
    }

    // Add Authorization header
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(url, { ...options, headers });

    // If 401 Unauthorized, session expired
    if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_data');
        window.location.href = '/static/auth-login.html?error=session_expired';
        throw new Error('Session expired');
    }

    // If 403 Forbidden, insufficient permissions
    if (response.status === 403) {
        const error = await response.json().catch(() => ({ detail: 'Acceso denegado' }));
        alert(`❌ Acceso denegado: ${error.detail || 'No tienes permisos para esta acción'}`);
        throw new Error('Forbidden');
    }

    return response;
}

// =====================================================
// LOGOUT
// =====================================================

/**
 * Logout function
 * Clears tokens and redirects to login
 */
function logout() {
    if (confirm('¿Cerrar sesión?')) {
        const token = getAuthToken();

        // Call logout endpoint
        if (token) {
            fetch('/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            }).catch(() => {
                // Ignore errors, we're logging out anyway
            });
        }

        // Clear local storage
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_data');

        // Redirect to login
        window.location.href = '/static/auth-login.html?logout=true';
    }
}

// =====================================================
// UI HELPERS
// =====================================================

/**
 * Show user info in header (if element exists)
 */
function showUserInfo() {
    const user = getCurrentUser();
    if (!user) return;

    // Try to find header element
    const headerEl = document.getElementById('user-info-header');
    if (headerEl) {
        const roleColors = {
            'admin': 'bg-purple-100 text-purple-800',
            'accountant': 'bg-blue-100 text-blue-800',
            'employee': 'bg-green-100 text-green-800'
        };

        const roleColor = roleColors[user.role] || 'bg-gray-100 text-gray-800';

        headerEl.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-sm text-gray-600">
                    <i class="fas fa-user mr-1"></i>
                    ${user.full_name || user.username}
                </span>
                <span class="px-2 py-1 text-xs font-medium rounded ${roleColor}">
                    ${user.role}
                </span>
                <button onclick="logout()" class="text-sm text-red-600 hover:text-red-800">
                    <i class="fas fa-sign-out-alt mr-1"></i>
                    Salir
                </button>
            </div>
        `;
    }
}

/**
 * Hide UI elements based on user role
 *
 * @param {string} requiredRole - Role required to see element
 * @param {string} elementId - ID of element to show/hide
 */
function hideIfNotRole(requiredRole, elementId) {
    const user = getCurrentUser();
    if (!user) return;

    const allowedRoles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];

    if (!allowedRoles.includes(user.role) && user.role !== 'admin') {
        const el = document.getElementById(elementId);
        if (el) {
            el.style.display = 'none';
        }
    }
}

// =====================================================
// INITIALIZATION
// =====================================================

// Auto-check auth on page load
document.addEventListener('DOMContentLoaded', function() {
    // Show user info if element exists
    setTimeout(() => showUserInfo(), 100);
});
