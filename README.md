# AWS Labs Portfolio: Cloud Practitioner to Architect
¡Hola! Soy **Juan Sebastian Arrechea**, Ingeniero de Automatización. Este repositorio es una bitácora técnica de mi ruta de aprendizaje hacia la certificación **AWS Solutions Architect Associate (SAA-C03)**. 

Aquí encontrarás laboratorios prácticos documentando el despliegue de infraestructuras escalables, seguras y altamente disponibles.

---

## 🛠️ Stack Tecnológico
![AWS](https://img.shields.io/badge/AWS-%23232F3E.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Terraform](https://img.shields.io/badge/terraform-%235835CC.svg?style=for-the-badge&logo=terraform&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)

---

## ⭐ Proyecto Insignia

### [Invoice Digitizer — Digitalizador Serverless de Recibos con IA](./invoice-digitizer)
Aplicación end-to-end en producción que permite a usuarios subir fotos de recibos y facturas para extraer automáticamente sus datos (total, número, fecha, comercio, ítems) usando **AWS Textract** y **Claude AI**.

* **Arquitectura:** React SPA (Amplify) → API Gateway → Lambda → Textract/Claude → DynamoDB + SNS
* **Servicios:** Amplify Hosting, Cognito, API Gateway, Lambda (3 funciones), S3 (2 buckets event-driven), Textract, DynamoDB, SNS
* **Características:**
  - ✅ Autenticación con Cognito User Pool + JWT
  - ✅ Presigned URLs para upload directo a S3 (sin overhead API Gateway)
  - ✅ Two-layer parsing: Textract (FORMS + TABLES) + regex fallback
  - ✅ Notificaciones por email vía SNS
  - ✅ Dashboard con historial filtrable y polling inteligente

---

## 🚀 Laboratorios Completados

### [Lab 01: Alojamiento Web Estático con S3 y CloudFront](./lab-01-s3-cloudfront)
* **Objetivo:** Despliegue de un sitio estático con baja latencia global.
* **Servicios:** S3, CloudFront, OAI (Origin Access Identity).

### [Lab 02: Arquitectura Serverless con API Gateway y Lambda](./lab-02-serverless-api)
* **Objetivo:** Creación de una API REST funcional sin gestión de servidores.
* **Servicios:** API Gateway, Lambda, DynamoDB.

### [Lab 03: VPC Networking & Security (NACL vs SG)](./lab-03-vpc-networking)
* **Objetivo:** Configuración de redes de 2 capas y auditoría de seguridad perimetral.
* **Servicios:** VPC, EC2, Internet Gateway, Route Tables, NACLs, Security Groups.
* **Logro:** Validación de comportamiento *Stateless* mediante bloqueo de IP pública local.

### [Lab 04: Alta Disponibilidad y Auto Scaling (Self-Healing)](./lab-04-ha-autoscaling)
* **Objetivo:** Implementación de una arquitectura resiliente y elástica en múltiples zonas de disponibilidad.
* **Servicios:** ALB (Application Load Balancer), ASG (Auto Scaling Group), Launch Templates, Target Groups.
* **Logro:** Configuración de escalado dinámico por CPU y recuperación automática de instancias.

### [Lab 05: Seguridad + Auditoría con IAM y CloudTrail](./lab-05-security-iam)
* **Objetivo:** Implementación de seguridad perimetral, auditoría y control de presupuestos.
* **Servicios:** IAM Policies & Roles, CloudTrail, AWS Budgets, CloudWatch Logs.
* **Logro:** Auditoría de principio de mínimo privilegio y trazabilidad de eventos.

---

## 📈 Próximos Pasos
- [ ] **Lab 06: Pipeline ETL**: Procesamiento de datos con S3, Glue, Athena y QuickSight.
- [ ] **Lab 07: Disaster Recovery (DR)**: Backup automatizado y replicación multi-región.
- [ ] **Invoice Digitizer — Mejoras**: Tests unitarios, IaC con Terraform, X-Ray tracing.
- [ ] **Infraestructura como Código (IaC)**: Migración completa a Terraform para todos los labs.

---

## 📬 Contacto
¿Te interesa mi perfil o quieres colaborar?

* **Email:** Juanzarrechea@gmail.com
