# Lab 05: Seguridad, Auditoría y FinOps

## Descripción
Implementación de las mejores prácticas de gobierno de cuenta de AWS, centradas en la seguridad de la identidad, auditoría de eventos y control proactivo de costos.

## Implementación Técnica

### 1. Gobernanza de Costos (FinOps)
- **AWS Budgets**: Configuración de un presupuesto mensual de $15.00 USD.
- **Alertas**: Notificaciones automáticas vía email al alcanzar el 80% del umbral de gasto para evitar sorpresas en la facturación.

### 2. Auditoría y Cumplimiento
- **AWS CloudTrail**: Activación de un "Trail" global cifrado con **KMS** para registrar cada llamada a la API en todas las regiones.
- **Integridad**: Validación de archivos de registro habilitada para prevenir alteraciones en los logs.

### 3. Gestión de Identidades (IAM)
- **MFA (Multi-Factor Authentication)**: Activación obligatoria para la cuenta Root y usuarios administradores.
- **Políticas JSON**: Creación de grupos con permisos limitados y condiciones de seguridad avanzadas.

## Resultados
- Cuenta protegida contra accesos no autorizados.
- Visibilidad total de quién, qué y cuándo se realizan cambios en la infraestructura.
- Control financiero estricto sobre los recursos desplegados.