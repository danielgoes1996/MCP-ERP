class AuthLoginController {
    constructor() {
        this.form = document.getElementById('login-form');
        this.emailInput = document.getElementById('email');
        this.tenantSelect = document.getElementById('tenant');
        this.init();
    }

    init() {
        this.form.addEventListener('submit', this.handleLogin.bind(this));
        this.checkURLParams();

        if (this.emailInput) {
            const prefilledEmail = this.emailInput.value.trim();
            if (prefilledEmail) {
                this.loadTenants(prefilledEmail);
            } else {
                this.setTenantPlaceholder('Ingresa tu correo para listar empresas');
            }

            this.emailInput.addEventListener('blur', () => {
                const emailValue = this.emailInput.value.trim();
                if (emailValue) {
                    this.loadTenants(emailValue);
                } else {
                    this.resetTenantSelect();
                }
            });

            this.emailInput.addEventListener('input', () => {
                this._emailDirty = true;
            });
        } else {
            this.loadTenants();
        }

        // Watch changes in the select to keep it populated
        this.tenantSelect.addEventListener('change', () => {
            if (!this.tenantSelect.value) {
                const emailValue = this.emailInput?.value.trim() || '';
                if (emailValue) {
                    this.loadTenants(emailValue);
                }
            }
        });
    }

    setTenantPlaceholder(message) {
        this.tenantSelect.innerHTML = `<option value="">${message}</option>`;
        this.tenantSelect.disabled = true;
    }

    resetTenantSelect() {
        this.setTenantPlaceholder('Ingresa tu correo para listar empresas');
    }

    async loadTenants(email = '') {
        try {
            let url = '/auth/tenants';
            if (email) {
                url += `?email=${encodeURIComponent(email)}`;
            }

            const response = await fetch(url);

            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }

            const tenants = await response.json();

            if (!tenants || tenants.length === 0) {
                if (email) {
                    this.setTenantPlaceholder('No se encontraron empresas para este correo');
                } else {
                    this.setTenantPlaceholder('No hay empresas registradas');
                }
                return;
            }

            this.tenantSelect.disabled = false;
            this.tenantSelect.innerHTML = '<option value="">Selecciona una empresa</option>';

            tenants.forEach(tenant => {
                const option = document.createElement('option');
                option.value = tenant.id;
                option.textContent = tenant.name;
                this.tenantSelect.appendChild(option);
            });

            // Auto-select if only one tenant
            if (tenants.length === 1) {
                this.tenantSelect.value = tenants[0].id;
            }

            // If the current value remains valid, keep it selected
            const currentValue = this.tenantSelect.dataset.lastSelected;
            if (currentValue && tenants.some(t => String(t.id) === currentValue)) {
                this.tenantSelect.value = currentValue;
            }
        } catch (error) {
            console.error('Error fetching tenants:', error);
            this.setTenantPlaceholder('Error cargando empresas');
            this.showMessage('No se pudieron cargar las empresas. Intenta de nuevo.', 'error');
        }
    }

    checkURLParams() {
        const urlParams = new URLSearchParams(window.location.search);

        const email = urlParams.get('email');
        const tenant = urlParams.get('tenant');

        if (email && this.emailInput) {
            this.emailInput.value = email;
        }

        if (tenant) {
            this.tenantSelect.dataset.lastSelected = tenant;
        }

        if (urlParams.get('registered') === 'true') {
            this.showMessage('Cuenta creada exitosamente. Ahora puedes iniciar sesión.', 'success');
        }

        if (urlParams.get('logout') === 'true') {
            this.showMessage('Sesión cerrada correctamente.', 'success');
        }

        if (urlParams.get('error')) {
            this.showMessage(urlParams.get('error'), 'error');
        }
    }

    getAuthHeaders() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return null;
        }

        const tokenType = (localStorage.getItem('token_type') || 'bearer').toLowerCase() === 'bearer'
            ? 'Bearer'
            : localStorage.getItem('token_type') || 'Bearer';

        return {
            Authorization: `${tokenType} ${token}`
        };
    }

    async redirectAfterLogin() {
        const headers = this.getAuthHeaders();
        if (!headers) {
            window.location.href = '/auth-login.html?error=Tu sesión ha expirado. Inicia nuevamente.';
            return;
        }

        try {
            const response = await fetch('/api/v1/companies/context/status', { headers });

            if (response.status === 404) {
                window.location.href = '/static/onboarding-context.html?first_run=1';
                return;
            }

            if (response.ok) {
                const payload = await response.json();
                const summary = (payload.summary || '').trim();
                if (!summary || summary.length < 10) {
                    window.location.href = '/static/onboarding-context.html?first_run=1';
                    return;
                }
            } else {
                console.warn('Context status check returned', response.status);
            }
        } catch (error) {
            console.warn('Context status check failed', error);
        }

        window.location.href = '/advanced-ticket-dashboard.html?welcome=true';
    }

    async handleLogin(e) {
        e.preventDefault();

        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const tenantId = document.getElementById('tenant').value;
        const remember = document.getElementById('remember').checked;

        if (!tenantId) {
            this.showMessage('Por favor selecciona una empresa', 'error');
            return;
        }

        this.setLoading(true);

        try {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            formData.append('tenant_id', tenantId);

            const response = await fetch('/auth/login/form', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData
            });

            if (response.ok) {
                const data = await response.json();

                if (data.access_token) {
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('token_type', data.token_type || 'bearer');

                    if (data.user) {
                        localStorage.setItem('user_data', JSON.stringify(data.user));
                    }
                    if (data.tenant) {
                        localStorage.setItem('tenant_data', JSON.stringify(data.tenant));
                    }
                }

                this.showMessage('¡Bienvenido! Redirigiendo...', 'success');
                await this.redirectAfterLogin();
                return;
            } else {
                const errorData = await response.json();
                let errorMessage = 'Error en el inicio de sesión';

                if (errorData.detail) {
                    if (typeof errorData.detail === 'string') {
                        errorMessage = errorData.detail;
                    } else if (Array.isArray(errorData.detail)) {
                        errorMessage = errorData.detail.map(err => err.msg || err).join(', ');
                    } else {
                        errorMessage = JSON.stringify(errorData.detail);
                    }
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }

                this.showMessage(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showMessage('Error de conexión. Intenta de nuevo.', 'error');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(isLoading) {
        const btn = document.getElementById('login-btn');
        const text = document.getElementById('login-text');
        const loading = document.getElementById('login-loading');

        btn.disabled = isLoading;

        if (isLoading) {
            text.classList.add('hidden');
            loading.classList.remove('hidden');
        } else {
            text.classList.remove('hidden');
            loading.classList.add('hidden');
        }
    }

    showMessage(message, type) {
        const messageEl = document.getElementById('auth-message');
        messageEl.textContent = message;
        messageEl.className = `mb-4 p-3 rounded-lg text-sm ${
            type === 'success' ? 'bg-green-100 text-green-800 border border-green-300' :
            type === 'error' ? 'bg-red-100 text-red-800 border border-red-300' :
            'bg-blue-100 text-blue-800 border border-blue-300'
        }`;
        messageEl.classList.remove('hidden');

        if (type === 'success') {
            setTimeout(() => messageEl.classList.add('hidden'), 5000);
        }
    }
}

function togglePassword() {
    const passwordField = document.getElementById('password');
    const passwordIcon = document.getElementById('password-icon');

    if (passwordField.type === 'password') {
        passwordField.type = 'text';
        passwordIcon.className = 'fas fa-eye-slash';
    } else {
        passwordField.type = 'password';
        passwordIcon.className = 'fas fa-eye';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AuthLoginController();
});
