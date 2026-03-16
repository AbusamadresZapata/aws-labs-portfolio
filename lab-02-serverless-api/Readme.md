
# AWS Cloud Resume Project - Serverless Architecture

## Objetivo del Proyecto

Implementar una arquitectura web desacoplada en Amazon Web Services (AWS) que transicione de un sitio estático a una aplicación dinámica funcional. El sistema registra y visualiza el conteo de visitantes en tiempo real mediante servicios administrados y computación bajo demanda.

## Arquitectura y Componentes Técnicos

### 1. Capa de Presentación (Frontend)

* **Servicios:** Amazon S3 y Amazon CloudFront.
* **Justificación:** El contenido se almacena en un bucket privado de S3 para garantizar la integridad de los datos. CloudFront actúa como Content Delivery Network (CDN) para distribuir el archivo index.html a través de Edge Locations, reduciendo la latencia y permitiendo el uso de Origin Access Control (OAC) para restringir el acceso público directo al bucket.

### 2. Capa de Interfaz de Programación (API Layer)

* **Servicio:** Amazon API Gateway (HTTP API).
* **Configuración:** Ruta `/visit` con método `GET`.
* **Justificación:** Proporciona un punto de enlace seguro para que el cliente (navegador) interactúe con el backend. Se configuraron políticas de Cross-Origin Resource Sharing (CORS) para permitir peticiones exclusivamente desde el dominio de CloudFront, mitigando riesgos de seguridad.

### 3. Capa de Lógica de Negocio (Compute)

* **Servicio:** AWS Lambda ejecutando Python.
* **Justificación:** Se seleccionó un modelo Serverless para optimizar costos y escalabilidad. La función se invoca únicamente cuando existe una petición HTTP, procesando el incremento del contador y retornando una respuesta JSON al frontend.

### 4. Capa de Persistencia (Database)

* **Servicio:** Amazon DynamoDB.
* **Justificación:** Al ser una base de datos NoSQL de baja latencia, permite actualizaciones atómicas del contador de visitas sin la sobrecarga de gestionar un servidor de base de datos relacional.

## Flujo de Comunicación de Datos

1. El usuario solicita el dominio a través de **CloudFront**.
2. El navegador carga el archivo **index.html** y ejecuta el script de JavaScript integrado.
3. La función `fetch` realiza una petición asíncrona hacia el endpoint de **API Gateway**.
4. **API Gateway** valida la ruta y el método, activando la función **Lambda**.
5. **Lambda** interactúa con **DynamoDB** para leer, incrementar y guardar el valor del contador.
6. La respuesta viaja de regreso al navegador, donde el DOM se actualiza para mostrar la cifra final al usuario.

## Seguridad y Control de Acceso

Se implementó el Principio de Mínimo Privilegio mediante políticas de Identity and Access Management (IAM). La función Lambda cuenta con permisos restringidos únicamente para las acciones `UpdateItem` y `GetItem` sobre el ARN específico de la tabla de base de datos, garantizando que no existan permisos excesivos en la infraestructura.

## Repositorio del Proyecto

El código fuente de este laboratorio se encuentra organizado de la siguiente manera:

* `/lab-01-static-web`: Archivos de configuración de S3 y CloudFront.
* `/lab-02-serverless-api`: Código de la función Lambda y definición de políticas IAM.
* `index.html`: Archivo principal con la lógica de integración de la API.

---

**Proyecto desarrollado por Juan Zarrechea**
*Estudiante de AWS Solutions Architect*
