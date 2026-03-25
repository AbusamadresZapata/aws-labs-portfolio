# Lab 03: VPC Networking & Security (NACL vs SG)

## Descripción
Implementación de una arquitectura de red de dos capas en AWS, validando la jerarquía de seguridad entre Security Groups (Stateful) y Network ACLs (Stateless).

## Arquitectura
* **VPC:** 10.0.0.0/16 con segmentación en subredes públicas y privadas.
* **Capa Pública:** Subred con acceso a Internet Gateway (IGW) hospedando un servidor Apache (EC2).
* **Capa Privada:** Subred aislada para recursos internos, validando el aislamiento de red.

## Experimento de Seguridad: El "Muro" de la NACL
Para demostrar el funcionamiento de las NACL, se realizaron las siguientes pruebas:
1. **Validación inicial:** Acceso exitoso al servidor Apache vía HTTP (Puerto 80).
2. **Bloqueo por IP:** Se identificó la IP pública local mediante `ifconfig.me` y se configuró una regla de **DENY** en la NACL (Regla 50). Por orden de ejecucion 
3. **Resultado:** Bloqueo total del tráfico desde la IP específica, mientras que otras redes (datos móviles) mantuvieron el acceso, demostrando que la NACL opera a nivel de subred antes que el Security Group.

## Conclusiones Técnicas
* Las **NACL** son stateless y permiten reglas de denegación explícitas, siendo la primera línea de defensa.
* Los **Security Groups** son stateful y actúan a nivel de instancia.
* La importancia de distinguir entre IP Privada (local) e IP Pública (WAN) al configurar reglas de seguridad en la nube.
