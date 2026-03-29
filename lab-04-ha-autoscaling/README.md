# Lab 04: Alta Disponibilidad con ALB y Auto Scaling

## Descripción
Implementación de una arquitectura resiliente en AWS utilizando un Application Load Balancer (ALB) y un Auto Scaling Group (ASG) configurado en dos Zonas de Disponibilidad (Multi-AZ).

## Componentes
- **VPC personalizada** con subredes públicas.
- **Launch Template**: Configurado con Apache y metadatos de instancia.
- **ALB**: Balanceo de carga en puerto 80.
- **ASG**: Escalado automático basado en 50% de uso de CPU y Self-Healing.

## Pruebas de Funcionamiento
1. **Acceso vía DNS del ALB**: Verificación de la página personalizada.
2. **Prueba de Resiliencia**: Terminación manual de una instancia y recuperación automática por el ASG.