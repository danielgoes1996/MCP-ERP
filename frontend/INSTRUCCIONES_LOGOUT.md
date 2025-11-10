# Instrucciones para actualizar los datos del usuario

## Problema
El header muestra "U Usuario admin" porque el formato de datos del usuario ha cambiado.

## Solución
Para ver los cambios correctamente, necesitas:

1. **Hacer logout** desde el botón en el header
2. **Hacer login nuevamente** con las credenciales:
   - Email: `daniel@contaflow.ai`
   - Password: `ContaFlow2025!`

## ¿Por qué?
Actualizamos la estructura de datos del usuario para incluir:
- `full_name` (en lugar de solo `name`)
- `username`
- Información del `tenant` (empresa)

Los datos antiguos en localStorage no tienen esta estructura, por eso aparece "U Usuario admin".

## Resultado esperado después del login
En el header deberías ver:
- **Avatar**: "D" (primera letra de Daniel)
- **Nombre**: "Daniel ContaFlow"
- **Empresa**: "ContaFlow"

En el menú desplegable verás:
- Badge con rol: "admin"
- Badge con empresa: "ContaFlow"
