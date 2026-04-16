# Invoice Digitizer — Digitalizador de Recibos con IA

Aplicación serverless end-to-end que permite a usuarios subir fotos de recibos y facturas para extraer automáticamente sus datos (total, número, fecha, comercio) usando AWS Textract.

**Demo en producción:** desplegada en AWS Amplify + API Gateway + Lambda + DynamoDB.

---

## Arquitectura

```
Usuario
  │
  │  (1) Login / Registro
  ▼
┌─────────────────────────────┐
│  React SPA (Amplify Hosting)│
│  Cognito User Pool (auth)   │
└────────────┬────────────────┘
             │
             │  (2) POST /upload-url  ──►  Lambda: get_upload_url
             │                              Genera presigned URL de S3
             │
             │  (3) PUT imagen ──────────►  S3 Bucket RAW (invoice-raw-*)
             │                              S3 Event Notification
             │                                     │
             │                                     ▼
             │                          Lambda: invoice_ocr_v2
             │                          ┌──────────────────────┐
             │                          │ 1. Textract           │
             │                          │    AnalyzeDocument    │
             │                          │    (FORMS + TABLES)   │
             │                          │ 2. Parse campos       │
             │                          │    (KV pairs + regex) │
             │                          │ 3. PUT resultado JSON │
             │                          │    → S3 Bucket        │
             │                          │      PROCESSED        │
             │                          │ 4. PutItem → DynamoDB │
             │                          │ 5. Publish → SNS      │
             │                          │    (email al usuario) │
             │                          └──────────────────────┘
             │
             │  (4) GET /invoices ───────►  Lambda: get_invoices
             │                              Query DynamoDB por user_id
             │
             ▼
         Dashboard con historial de recibos
```

---

## Servicios AWS utilizados

| Servicio | Rol |
|----------|-----|
| **Amplify Hosting** | Build y hosting del frontend React |
| **Cognito User Pool** | Autenticación y autorización (JWT) |
| **API Gateway (REST)** | Endpoints `/upload-url` y `/invoices` con Cognito Authorizer |
| **Lambda (x3)** | Lógica de negocio sin servidores |
| **S3 (x2)** | Bucket RAW para imágenes subidas, bucket PROCESSED para resultados JSON |
| **Textract** | OCR + extracción de pares clave-valor y tablas |
| **DynamoDB** | Almacenamiento de recibos procesados por usuario |
| **SNS** | Notificación por email al completar el procesamiento |

---

## Flujo detallado

### 1. Upload (presigned URL)
El frontend solicita una URL firmada de S3 en vez de subir la imagen a través del backend. Esto elimina el paso del API Gateway para archivos grandes y reduce costos y latencia.

```
React → POST /upload-url → Lambda → S3.generate_presigned_url() → React → PUT directo a S3
```

### 2. Procesamiento OCR
El trigger de S3 activa la Lambda `invoice_ocr_v2` de forma asíncrona. El procesamiento sigue esta estrategia de extracción en dos capas:

- **Capa 1 — FORMS (Textract):** detecta pares `clave: valor` estructurados (ej: `TOTAL: $55.000`). Más preciso para facturas formales.
- **Capa 2 — Regex (fallback):** si Textract no detecta el campo, se aplican expresiones regulares sobre el texto plano. Cubre tickets informales y tiquetes de caja.

### 3. Consulta del historial
`GET /invoices` hace una Query en DynamoDB usando `user_id` (extraído del JWT de Cognito) como Partition Key. Cada usuario solo ve sus propios recibos.

---

## Estructura del proyecto

```
invoice-digitizer/
├── frontend/
│   └── src/
│       ├── App.jsx              # Autenticador Amplify
│       ├── aws-config.js        # Config Cognito + API endpoint
│       ├── pages/Dashboard.jsx  # Upload, polling y listado
│       └── components/InvoiceCard.jsx
│
├── backend/
│   ├── lambda/
│   │   ├── get_upload_url.py    # Genera presigned URL
│   │   ├── invoice_ocr_v2.py    # Pipeline OCR (Textract → DynamoDB → SNS)
│   │   └── get_invoices.py      # Consulta historial por usuario
│   └── tests/
│       └── test_lambdas.py
│
├── infra/
│   ├── iam/
│   │   ├── lambda-ocr-policy.json   # Permisos S3 + Textract + DynamoDB + SNS
│   │   └── lambda-api-policy.json   # Permisos S3 + DynamoDB
│   ├── s3/
│   │   └── cors-config.json         # CORS para uploads desde el browser
│   └── dynamodb-schema.md
│
└── docs/
    └── decisions/
        └── ADR-001-dynamodb-vs-athena.md
```

---

## Schema DynamoDB

**Tabla:** `invoices`

| Atributo | Tipo | Rol |
|----------|------|-----|
| `user_id` | String | **Partition Key** — UUID de Cognito (`sub`) |
| `invoice_id` | String | **Sort Key** — UUID generado en el upload |
| `processed_at` | String | ISO 8601 UTC |
| `status` | String | `completed` / `error` |
| `total` | Decimal | Monto total extraído |
| `invoice_number` | String | Número de factura / ticket |
| `date` | String | Fecha del recibo |
| `vendor` | String | Nombre del comercio |
| `items_count` | Number | Productos detectados en la tabla |
| `confidence` | Decimal | Confianza promedio del OCR (0-100) |
| `s3_key` | String | Path de la imagen original en S3 |
| `raw_text` | String | Primeros 2000 chars del texto extraído (auditoría) |

---

## Decisiones de diseño

### Por qué presigned URL en lugar de subir por el backend
Subir la imagen a través de API Gateway tendría un límite de 10 MB en el payload y añadiría latencia innecesaria. Con presigned URL, el browser sube directo a S3 con el content-type validado, y el backend nunca toca los bytes de la imagen.

### Por qué DynamoDB y no RDS/Athena
Los patrones de acceso son simples y predecibles: siempre por `user_id`. DynamoDB ofrece latencia de un dígito en milisegundos, escala a cero en inactividad (importante para un proyecto de portfolio sin tráfico constante) y no requiere gestión de conexiones desde Lambda.

### Por qué polling y no WebSockets
Textract tarda ~15-25 segundos. WebSockets añadirían API Gateway WebSocket + Lambda de conexión + tabla DynamoDB de sesiones — complejidad desproporcionada. El polling con 6 intentos cada 5s (tras un delay inicial de 20s) resuelve el 95% de los casos con código simple.

---

## Despliegue

### Frontend (automático vía Amplify)
El build se configura en `amplify.yml` en la raíz del repositorio. Amplify ejecuta el build en cada push a `main`.

Variables de entorno requeridas en Amplify Console:
```
REACT_APP_API_ENDPOINT=https://<api-id>.execute-api.us-east-1.amazonaws.com/prod
```

### Backend (CI/CD vía GitHub Actions)
El workflow `backend-ci.yml` se activa en cambios a `invoice-digitizer/backend/**`.

> **Nota:** el directorio `.github/workflows/` debe estar en la raíz del repositorio para que GitHub lo detecte. Si el repositorio raíz es `aws-labs-portfolio/`, mover los workflows a `aws-labs-portfolio/.github/workflows/`.

Secrets requeridos en GitHub:
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

### Infraestructura manual (una sola vez)
1. Crear User Pool en Cognito y App Client
2. Crear buckets S3: `invoice-raw-<account>` y `invoice-processed-<account>`
3. Configurar S3 Event Notification en bucket RAW → trigger Lambda `invoice-ocr-processor`
4. Crear tabla DynamoDB `invoices` con PK=`user_id` (String), SK=`invoice_id` (String)
5. Crear topic SNS `invoice-notifications` y suscribir el email del usuario
6. Adjuntar políticas IAM de `infra/iam/` a cada rol Lambda
7. Configurar CORS en API Gateway (origin del dominio Amplify)

---

## Lecciones aprendidas

- **Textract FORMS** es significativamente más preciso que regex para facturas estructuradas (electrónicas), pero regex sigue siendo necesario como fallback para tiquetes de caja impresos con formato irregular.
- El **content-type del presigned URL** debe coincidir exactamente con el header que el browser envía en el PUT, o S3 rechaza el upload con 403.
- La región de los clientes boto3 debe coincidir con la región donde están los recursos; inicializarlos con `region_name` explícito evita problemas cuando `AWS_DEFAULT_REGION` no está seteado en el entorno Lambda.
- Los errores de Textract (`UnsupportedDocumentException`) deben capturarse por separado del `Exception` genérico para dar mensajes de error útiles al usuario.

---

## Postmortem

Ver [postmortem-aws-serverless.pdf](./postmortem-aws-serverless.pdf) — documento de análisis de un incidente real ocurrido durante el desarrollo, con causa raíz, impacto y remediación.
