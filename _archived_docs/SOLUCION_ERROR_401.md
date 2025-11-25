# ✅ Solución Error 401 - Autenticación

## 🔧 Cambios Realizados

He actualizado el sistema para que **automáticamente redirija al login** cuando:
1. No hay token de autenticación en localStorage
2. El token existe pero es inválido (error 401)
3. La sesión ha expirado

### Modificaciones:

**Archivo:** `static/voice-expenses.source.jsx`

1. **Verificación de token al inicio:**
   - Si no existe `access_token` en localStorage → Redirige a `/auth-login.html`

2. **Manejo de error 401:**
   - Si el backend responde con 401 → Limpia los tokens y redirige al login
   - Muestra mensaje: "Tu sesión ha expirado. Por favor inicia sesión nuevamente."

---

## 🚀 Cómo Usar el Sistema

### Paso 1: Iniciar Sesión

1. Abre tu navegador y ve a:
   ```
   http://localhost:8000/auth-login.html
   ```

2. Usa uno de estos usuarios de prueba:
   - **Admin:** `admin` / `admin123`
   - **Contador:** `maria.garcia` / `accountant123`
   - **Empleado:** `juan.perez` / `employee123`

3. Selecciona una empresa del dropdown

4. Haz clic en "Iniciar Sesión"

### Paso 2: Acceder a Voice Expenses

Una vez autenticado, serás redirigido automáticamente a:
```
http://localhost:8000/voice-expenses
```

O puedes navegar directamente a esa URL. Si no tienes token válido, serás redirigido automáticamente al login.

---

## 🔍 Script de Debugging

Si quieres verificar el estado de tu autenticación, abre la consola del navegador (F12) y ejecuta:

```javascript
// 🔍 Verificar Token de Autenticación
(() => {
    const token = localStorage.getItem('access_token');
    const userData = localStorage.getItem('user_data');
    const tenantData = localStorage.getItem('tenant_data');

    console.log('=== 🔒 Estado de Autenticación ===');

    if (!token) {
        console.log('❌ NO hay token - Necesitas iniciar sesión');
        console.log('👉 Ve a: http://localhost:8000/auth-login.html');
    } else {
        console.log('✅ Token encontrado:', token.substring(0, 50) + '...');

        if (userData) {
            const user = JSON.parse(userData);
            console.log('👤 Usuario:', user);
        }

        if (tenantData) {
            const tenant = JSON.parse(tenantData);
            console.log('🏢 Empresa:', tenant);
        }

        // Verificar si el token es válido haciendo una petición de prueba
        fetch('/expenses?company_id=default', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => {
            if (response.status === 401) {
                console.log('❌ Token INVÁLIDO o EXPIRADO');
                console.log('🔄 Limpiando token...');
                localStorage.removeItem('access_token');
                localStorage.removeItem('user_data');
                localStorage.removeItem('tenant_data');
                console.log('👉 Inicia sesión nuevamente: http://localhost:8000/auth-login.html');
            } else if (response.ok) {
                console.log('✅ Token VÁLIDO - Autenticación exitosa');
            } else {
                console.log('⚠️ Respuesta inesperada:', response.status);
            }
        })
        .catch(error => {
            console.error('❌ Error verificando token:', error);
        });
    }

    console.log('=================================');
})();
```

---

## 🔄 Flujo de Autenticación Actualizado

```
┌─────────────────────────────────────────────┐
│  Usuario accede a /voice-expenses           │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │ ¿Hay token?        │
         └────────┬───────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
       NO                  SÍ
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────────┐
│ Redirigir a  │    │ Hacer request a  │
│ /auth-login  │    │ /expenses con    │
│              │    │ Bearer token     │
└──────────────┘    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                  200 OK           401
                    │                 │
                    ▼                 ▼
            ┌──────────────┐  ┌──────────────┐
            │ Cargar datos │  │ Limpiar token│
            │ normalmente  │  │ Redirigir a  │
            │              │  │ /auth-login  │
            └──────────────┘  └──────────────┘
```

---

## ⚡ Comandos Útiles

### Limpiar sesión manualmente (en consola del navegador):
```javascript
localStorage.clear();
location.reload();
```

### Ver todos los datos de localStorage:
```javascript
console.table({
    access_token: localStorage.getItem('access_token') ? '✅ Existe' : '❌ No existe',
    user_data: localStorage.getItem('user_data') ? '✅ Existe' : '❌ No existe',
    tenant_data: localStorage.getItem('tenant_data') ? '✅ Existe' : '❌ No existe',
    company_id: localStorage.getItem('mcp_company_id') || 'No definido'
});
```

---

## 🎯 Resultado Esperado

Después de estos cambios:

1. ✅ Si intentas acceder a `/voice-expenses` sin token → Redirige automáticamente a login
2. ✅ Si tu token es inválido/expirado → Limpia el token y redirige a login con mensaje
3. ✅ Si tu token es válido → Carga los datos normalmente
4. ✅ Mensaje descriptivo en la pantalla de login indicando por qué fuiste redirigido

---

## 📝 Notas Adicionales

- **Cache del navegador:** Si no ves los cambios, haz un hard refresh (Cmd+Shift+R en Mac, Ctrl+Shift+R en Windows)
- **Token JWT:** Los tokens JWT tienen un tiempo de expiración. Si trabajas mucho tiempo, puede que necesites volver a iniciar sesión
- **Multi-tenancy:** Asegúrate de seleccionar la empresa correcta al iniciar sesión

---

## 🐛 Troubleshooting

### "Sigo viendo el loader demo"
1. Abre la consola del navegador (F12)
2. Ejecuta el script de debugging de arriba
3. Verifica que tengas un token válido
4. Si no tienes token, ve a `/auth-login.html`

### "Me redirige al login pero no puedo autenticarme"
1. Verifica que el backend esté corriendo
2. Verifica que el endpoint `/auth/login` esté disponible
3. Verifica que el endpoint `/auth/tenants` esté disponible
4. Revisa los logs del backend

### "El token se borra todo el tiempo"
- Puede que el backend esté rechazando el token
- Verifica la configuración JWT en el backend
- Revisa los logs del servidor para ver por qué retorna 401

---

¡Listo! Ahora el sistema manejará correctamente la autenticación y redirigirá automáticamente al login cuando sea necesario. 🎉
