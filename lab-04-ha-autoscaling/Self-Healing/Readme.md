## 🛠️ Prueba de Resiliencia (Self-Healing)

Para validar la alta disponibilidad, se realizó una prueba de terminación forzada:

1. **Estado Inicial**: 2 instancias `t3.micro` en estado `Healthy` distribuidas en `us-east-1a` y `us-east-1b`.
2. **Simulación de Fallo**: Se terminó manualmente una de las instancias desde la consola de EC2.
3. **Detección**: El Auto Scaling Group (ASG) detectó que la capacidad actual (1) era inferior a la capacidad deseada (2) mediante el *Health Check*.
4. **Recuperación Automática**: El ASG lanzó una nueva instancia automáticamente en menos de 2 minutos.
5. **Resultado**: El servicio se mantuvo disponible en todo momento a través del ALB sin intervención manual.

> **Logro**: Disponibilidad del 100% durante el fallo de un nodo.
