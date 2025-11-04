(() => {
    const STORAGE_COMPANY_ID = 'mcp_company_id';
    const STORAGE_COMPANY_LABEL = 'mcp_company_label';
    const STORAGE_USER_EMAIL = 'mcp_user_email';
    const STORAGE_USER_NAME = 'mcp_user_name';
    const TOKEN_KEY = 'access_token';

    const routeMap = {
        'voice-expenses': ['/voice-expenses'],
        'facturacion': ['/advanced-ticket-dashboard.html', '/advanced-ticket-dashboard', '/dashboard'],
        'cuentas': ['/payment-accounts.html', '/payment-accounts'],
        'conciliacion': ['/bank-reconciliation'],
        'configuracion': ['/client-settings', '/client-settings.html']
    };

    const readStorage = (key) => {
        try {
            return localStorage.getItem(key);
        } catch (error) {
            console.warn('No se pudo leer de localStorage:', error);
            return null;
        }
    };

    const writeStorage = (key, value) => {
        try {
            if (value) {
                localStorage.setItem(key, value);
            } else {
                localStorage.removeItem(key);
            }
        } catch (error) {
            console.warn('No se pudo escribir en localStorage:', error);
        }
    };

    const formatLabel = (value, fallback) => {
        if (!value) return fallback;
        const cleaned = value === 'default' ? '' : value.replace(/[_-]+/g, ' ').trim();
        if (!cleaned) return fallback;
        const shouldTitleCase = cleaned === cleaned.toLowerCase() || cleaned === cleaned.toUpperCase();
        const label = shouldTitleCase ? cleaned.replace(/\b\w/g, (c) => c.toUpperCase()) : cleaned;
        return label.trim();
    };

    const deriveCompanyFromEmail = (email) => {
        if (!email || !email.includes('@')) return null;
        const domain = email.split('@')[1] || '';
        const base = domain.split('.')[0] || '';
        return base || null;
    };

    const deriveNameFromEmail = (email) => {
        if (!email || !email.includes('@')) return null;
        const localPart = email.split('@')[0] || '';
        return localPart.replace(/[._-]+/g, ' ');
    };
    const getAuthHeaders = () => {
        const token = readStorage(TOKEN_KEY);
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    function initMcpHeader() {
        const header = document.querySelector('[data-mcp-header]');
        if (!header) return;

        const companyEl = header.querySelector('[data-company]');
        const userEl = header.querySelector('[data-user]');
        const navLinks = header.querySelectorAll('[data-nav]');

        const highlightNavigation = () => {
            const currentPath = window.location.pathname.toLowerCase();
            navLinks.forEach((link) => {
                const key = link.getAttribute('data-nav');
                const routes = routeMap[key] || [];
                const isActive = routes.some((route) => currentPath.startsWith(route));
                link.classList.toggle('is-active', isActive);
                if (isActive) {
                    link.setAttribute('aria-current', 'page');
                } else {
                    link.removeAttribute('aria-current');
                }
            });
        };

        const renderCompany = (explicitLabel) => {
            if (!companyEl) return;
            const storedLabel = explicitLabel || readStorage(STORAGE_COMPANY_LABEL) || readStorage(STORAGE_COMPANY_ID);
            if (storedLabel) {
                companyEl.textContent = formatLabel(storedLabel, 'Empresa Demo');
                return;
            }

            const email = readStorage(STORAGE_USER_EMAIL);
            const derived = deriveCompanyFromEmail(email);
            companyEl.textContent = formatLabel(derived, 'Empresa Demo');
        };

        const renderUser = (explicitName) => {
            if (!userEl) return;
            const storedName = explicitName || readStorage(STORAGE_USER_NAME);
            if (storedName) {
                userEl.textContent = formatLabel(storedName, 'Usuario Demo');
                return;
            }

            const email = readStorage(STORAGE_USER_EMAIL);
            const derived = deriveNameFromEmail(email);
            userEl.textContent = formatLabel(derived, 'Usuario Demo');
        };

        const fetchCompanyContext = async () => {
            try {
                const authHeaders = getAuthHeaders();
                if (!authHeaders.Authorization) {
                    return null;
                }

                const response = await fetch('/api/v1/companies/context/status', {
                    headers: {
                        Accept: 'application/json',
                        ...authHeaders,
                    },
                });

                if (!response.ok) {
                    return null;
                }

                return await response.json();
            } catch (error) {
                console.warn('No se pudo obtener company context:', error);
                return null;
            }
        };

        const updateFromProfile = async () => {
            try {
                let infoLoaded = false;

                const storedUserRaw = readStorage('user_data');
                if (storedUserRaw) {
                    try {
                        const storedUser = JSON.parse(storedUserRaw);
                        if (storedUser?.email) {
                            writeStorage(STORAGE_USER_EMAIL, storedUser.email);
                        }
                        if (storedUser?.full_name || storedUser?.name) {
                            const fullName = storedUser.full_name || storedUser.name;
                            writeStorage(STORAGE_USER_NAME, fullName);
                            renderUser(fullName);
                        } else {
                            renderUser();
                        }
                        infoLoaded = true;
                    } catch (parseError) {
                        console.warn('No se pudo interpretar user_data almacenado:', parseError);
                    }
                }

                const storedTenantRaw = readStorage('tenant_data');
                if (storedTenantRaw) {
                    try {
                        const storedTenant = JSON.parse(storedTenantRaw);
                        if (storedTenant?.name) {
                            writeStorage(STORAGE_COMPANY_LABEL, storedTenant.name);
                            renderCompany(storedTenant.name);
                        }
                        if (storedTenant?.id) {
                            writeStorage(STORAGE_COMPANY_ID, storedTenant.id);
                        }
                        infoLoaded = true;
                    } catch (parseError) {
                        console.warn('No se pudo interpretar tenant_data almacenado:', parseError);
                    }
                }

                if (infoLoaded) {
                    return;
                }

                const context = await fetchCompanyContext();
                if (context && context.company && context.company.company_name) {
                    const label = context.company.company_name;
                    writeStorage(STORAGE_COMPANY_LABEL, label);
                    renderCompany(label);
                }

                const authHeaders = getAuthHeaders();
                if (!authHeaders.Authorization) {
                    return;
                }

                const response = await fetch('/auth/me', {
                    headers: {
                        Accept: 'application/json',
                        ...authHeaders,
                    },
                });

                if (!response.ok) {
                    return;
                }

                const user = await response.json();
                if (user.email) {
                    writeStorage(STORAGE_USER_EMAIL, user.email);
                }
                if (user.full_name || user.name) {
                    const fullName = user.full_name || user.name;
                    writeStorage(STORAGE_USER_NAME, fullName);
                    renderUser(fullName);
                } else {
                    renderUser();
                }

                if (user.company_name) {
                    writeStorage(STORAGE_COMPANY_LABEL, user.company_name);
                    renderCompany(user.company_name);
                } else {
                    renderCompany();
                }

                if (user.company_id) {
                    writeStorage(STORAGE_COMPANY_ID, user.company_id);
                } else if (user.tenant_id) {
                    writeStorage(STORAGE_COMPANY_ID, user.tenant_id);
                }
            } catch (error) {
                console.warn('No se pudo cargar el perfil del usuario:', error);
            }
        };

        const handleStorageChange = (event) => {
            if (!event) return;
            if ([STORAGE_COMPANY_LABEL, STORAGE_COMPANY_ID].includes(event.key)) {
                renderCompany();
            }
            if ([STORAGE_USER_EMAIL, STORAGE_USER_NAME].includes(event.key)) {
                renderUser();
            }
        };

        highlightNavigation();
        renderCompany();
        renderUser();

        if (header.dataset.mcpInitialized === 'true') {
            return;
        }

        header.dataset.mcpInitialized = 'true';
        updateFromProfile();

        window.addEventListener('storage', handleStorageChange);
        window.addEventListener('mcp-company-change', () => {
            renderCompany();
            updateFromProfile();
        });

        const removeVoiceExpensesChrome = () => {
            document.querySelectorAll('#app-root header.backdrop-blur').forEach((node) => node.remove());

            const quickActionsRow = document.querySelector('#app-root section .flex.justify-center.gap-3.flex-wrap');
            if (quickActionsRow) {
                quickActionsRow.remove();
            }

            document.querySelectorAll('#app-root .absolute.left-0.top-0.bottom-0').forEach((drawer) => {
                const brandingBlock = drawer.querySelector('.flex.items-center.gap-2');
                if (brandingBlock) {
                    brandingBlock.remove();
                }
            });
        };

        if (window.location.pathname.includes('voice-expenses')) {
            const appRoot = document.getElementById('app-root');
            if (appRoot) {
                const observer = new MutationObserver(() => removeVoiceExpensesChrome());
                observer.observe(appRoot, { childList: true, subtree: true });
                removeVoiceExpensesChrome();
            } else {
                removeVoiceExpensesChrome();
            }
        }
    }

    window.initMcpHeader = initMcpHeader;
    document.addEventListener('DOMContentLoaded', initMcpHeader);
})();
