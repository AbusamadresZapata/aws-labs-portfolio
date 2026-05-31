# Sistema de Reportes Biomig — Propuesta Arquitectónica
**Empresa:** Incomelec S.A.S | **PCM piloto:** Cali (PCM 14) | **Escalable a 7 PCMs**
**Presupuesto:** ≤ $25 USD/mes | **Stack:** AWS Serverless + Amplify + GitHub Actions
**Versión:** 3.1 — Mayo 2026 | **Autor:** Juan Sebastian Arrechea Zapata

---

## Cambios respecto a v2.0 → v3.0

| # | Problema v2 | Solución v3 | Sección |
|---|---|---|---|
| 1 | Fingerprint sobre primeros 10KB → colisiones silenciosas | SHA-256 sobre archivo completo vía Web Crypto API | §4.1 |
| 2 | POST /reports/request sin mecanismo async real → timeout 29s de API GW | SQS como buffer: endpoint escribe mensaje, retorna reportId inmediatamente | §3.6, §5.2 |
| 3 | report-processor monolítico 900s sin visibilidad por etapa | Step Functions: 4 estados con retry granular y catch independiente | §3.5, §5.3 |
| 4 | Lambda Layers pesados (pandas + matplotlib + python-docx > 250MB) | Container Image ECR para report-generator; layers solo en Lambdas ligeras | §3.4 |
| 5 | Templates DOCX bundled con código → redeploy por cambio de plantilla | Templates en S3 (biomig-csv-inputs/templates/), cargados en runtime | §3.3, §8 |
| 6 | Sin trazabilidad distribuida entre Lambdas | X-Ray habilitado en todas las Lambdas y Step Functions | §3.4 |
| 7 | Sin límite de concurrencia para report-generator | ReservedConcurrency = 3 en report-generator container | §3.4 |
| 8 | Lambda Authorizer llamaba a Cognito API por request → latencia extra | Authorizer lee groups del JWT directamente (claim `cognito:groups`) | §3.2 |

## Cambios v3.0 → v3.1

| # | Mejora | Motivo | Sección |
|---|---|---|---|
| 9 | OIDC entre GitHub Actions y AWS (sin access keys estáticas) | Access keys en Secrets son el vector #1 de incidentes CI/CD | §9.2, §9.3, §9.4 |
| 10 | AWS Budgets: alarma $10 (80%) + $25 (100%) en template.yaml | Protege contra loop infinito de Lambda que gasta $200 en una noche | §12, §14 |
| 11 | cfn-lint en pipeline test-pr.yml | Detecta errores de configuración SAM antes del deploy | §9.1 |
| 12 | Deep Archive en lugar de eliminación en lifecycle CSV (36+ meses) | Retención auditable a $0.04/mes; borrar es irreversible | §3.3 |
| 13 | customHeaders.yml en Amplify (HSTS, CSP, X-Frame-Options) | Headers de seguridad sin costo — previene clickjacking y protocolo downgrade | §3.1, §10 |

---

## Índice

1. [Visión general](#1-visión-general)
2. [Arquitectura de alto nivel](#2-arquitectura-de-alto-nivel)
3. [Componentes AWS detallados](#3-componentes-aws-detallados)
4. [Gestión de lotes de CSVs](#4-gestión-de-lotes-de-csvs)
5. [Pipeline de generación — Informe de Movimientos](#5-pipeline-de-generación--informe-de-movimientos)
6. [Pipeline de generación — Informe de Novedades](#6-pipeline-de-generación--informe-de-novedades)
7. [Validaciones cruzadas](#7-validaciones-cruzadas)
8. [Estructura del repositorio GitHub](#8-estructura-del-repositorio-github)
9. [CI/CD con GitHub Actions](#9-cicd-con-github-actions)
10. [Seguridad](#10-seguridad)
11. [Auditoría y trazabilidad](#11-auditoría-y-trazabilidad)
12. [Estimación de costos](#12-estimación-de-costos)
13. [Well-Architected Framework](#13-well-architected-framework)
14. [Hoja de ruta de implementación](#14-hoja-de-ruta-de-implementación)
15. [Decisiones de diseño consolidadas](#15-decisiones-de-diseño-consolidadas)
16. [Glosario técnico](#16-glosario-técnico)

---

## 1. Visión general

### El problema que resuelve

Hoy se generan dos informes mensuales en un proceso de 1.5 a 3 horas por informe
y por PCM: 8 sesiones de Power Query en Excel, 4 notebooks de Google Colab,
descarga manual de imágenes, edición de tablas en Word y 18 reemplazos de imagen
en orden exacto. Este proceso se repite para cada PCM activo y es 100% manual,
propenso a errores de orden, errores numéricos en tablas y pérdida de tiempo
operativo que podría dedicarse a soporte técnico real.

### Los dos informes

| Informe | Fuente de datos | Gráficas | Tablas |
|---|---|---|---|
| Movimientos Migratorios | 7 CSVs grandes del proveedor (~200K filas c/u) | 10 | 5 |
| Novedades / Incidencias | 1 CSV propio con separador `;` (acumulativo anual) | 8 | 3 |

### El Gold Movement

```
Usuario sube los CSVs una sola vez por mes (cualquier PCM)
         ↓
Sistema calcula SHA-256 completo y detecta si el lote ya existe
         ↓
  [Lote nuevo]                    [Lote existente]
  Sube a S3, valida,              Muestra: "Archivos cargados el
  registra en DynamoDB            DD/MM/AAAA por usuario@incomelec.com
         ↓                        PCMs disponibles: 1,10,12,13,14,15,18"
         └──────────────────┬─────────────────────────────┘
                            ↓
            Sistema detecta PCMs disponibles
                            ↓
            Usuario selecciona PCM + tipo de informe
                            ↓
            POST /reports/request → SQS → Step Functions
                            ↓
            Step Functions orquesta 4 etapas con retry por etapa
                            ↓
            Usuario descarga el .docx listo:
              • Todas las tablas numéricas pobladas
              • Las gráficas ya incrustadas en los placeholders correctos
              • Mes/período actualizado en todos los campos de texto
              • Historial guardado para auditoría
                            ↓
            Usuario revisa, ajusta la conclusión si quiere, exporta PDF

Tiempo total desde que el lote ya existe: < 90 segundos.
```

### Alcance V1

| Ítem | Estado |
|---|---|
| Informe de Movimientos Migratorios | ✅ V1 |
| Informe de Novedades / Incidencias | ✅ V1 |
| Selección dinámica de PCM post-upload | ✅ V1 |
| Reutilización de lotes entre PCMs | ✅ V1 |
| Historial centralizado de reportes | ✅ V1 |
| Gestión de lotes (archivar / eliminar) para admin | ✅ V1 |
| Reemplazo de lote con CSVs corregidos | ✅ V1 |
| Multi-PCM simultáneo desde UI | ⬜ arquitectura · UI en V2 |
| Distribución por nacionalidad extranjeros | ⏳ V2 |
| Mensajes de UI detallados en flujo de lote existente | ⏳ V2 |
| Justificación escrita al eliminar lote | ⏳ V2 |
| Conclusiones auto-generadas con IA | ⏳ V2 opcional |

---

## 2. Arquitectura de alto nivel

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN                          │
│                                                                       │
│   AWS Amplify (React + Vite SPA)                                      │
│   • CI/CD automático desde GitHub → push a main = deploy en ~2 min   │
│   • HTTPS + dominio custom                                            │
│   • Cognito UI integrada (@aws-amplify/ui-react)                      │
│   • Vistas: Upload/Lotes · Procesamiento · Historial · Admin         │
└──────────────────────────┬──────────────────────────────────────────┘
                            │ HTTPS + JWT
┌──────────────────────────▼──────────────────────────────────────────┐
│                      CAPA DE AUTENTICACIÓN                            │
│                                                                       │
│   Amazon Cognito User Pool                                            │
│   • Grupos: admin · engineer-14 (Cali) · engineer-12 · engineer-N    │
│   • JWT con claims custom:pcm_id y cognito:groups                    │
│   • Lambda Authorizer lee grupos del token sin llamada a Cognito API │
│   • MFA obligatorio para admin · opcional para engineers             │
└──────────────────────────┬──────────────────────────────────────────┘
                            │ JWT validado + contexto PCM
┌──────────────────────────▼──────────────────────────────────────────┐
│                          CAPA DE API                                  │
│                                                                       │
│   API Gateway REST · Throttling: 10 req/s por usuario                │
│                                                                       │
│   POST /uploads/check          → λ lote-checker                      │
│   POST /uploads/presigned      → λ upload-handler                    │
│   POST /uploads/confirm        → λ lote-registrar                    │
│   POST /reports/request        → λ report-requester ──→ SQS ──┐     │
│   GET  /reports/status/{id}    → λ status-handler              │     │
│   GET  /reports/history        → λ history-handler             │     │
│   GET  /reports/download/{id}  → λ download-handler            │     │
│   GET  /lotes                  → λ lotes-handler               │     │
│   PUT  /lotes/{id}/archivar    → λ lotes-admin                 │     │
│   PUT  /lotes/{id}/reemplazar  → λ lotes-admin                 │     │
│   DELETE /lotes/{id}           → λ lotes-admin                 │     │
└─────────────────────────────────────────────────────────────────│───┘
                                                                   │
┌─────────────────────────────────────────────────────────────────▼───┐
│                  CAPA DE ORQUESTACIÓN (nuevo en v3)                   │
│                                                                       │
│   SQS — BiomigReportsQueue                                            │
│   • Visibility timeout: 900s · Retención: 24h                        │
│   • DLQ: BiomigReportsDLQ (retiene fallidos 7 días)                  │
│   • 3 intentos antes de pasar a DLQ                                  │
│                          │ trigger                                    │
│   λ sf-trigger (128MB, 15s)                                          │
│   • Lee mensaje SQS · inicia ejecución de Step Functions             │
│                          │                                            │
│   Step Functions — BiomigReportStateMachine                           │
│   ┌───────────────────────────────────────────────────────────┐      │
│   │                                                           │      │
│   │  ValidateAndLoad → ProcessData → GenerateArtifacts        │      │
│   │    (256MB/30s)     (1024MB/120s)  (Container/3008MB/600s) │      │
│   │                                         │                 │      │
│   │                     SaveAndNotify ←──────┘                │      │
│   │                       (256MB/30s)                         │      │
│   │                                                           │      │
│   │   Catch en cada estado → MarkFailed (256MB/15s)           │      │
│   └───────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
            │ S3 GetObject/PutObject                │ DynamoDB R/W
┌───────────▼────────────────┐         ┌────────────▼────────────────┐
│      ALMACENAMIENTO         │         │          METADATOS           │
│                             │         │                              │
│   biomig-csv-inputs/        │         │   DynamoDB On-Demand         │
│   ├── lotes/                │         │   BiomigLotes                │
│   │   └── {año}-{mes}_{fp}/ │         │   BiomigReportsHistory       │
│   ├── incidencias/          │         │   BiomigCSVUploads           │
│   └── templates/            │         │                              │
│       ├── movimientos.docx  │         │   X-Ray traces correlacionan │
│       └── novedades.docx    │         │   cada ejecución de SF       │
│                             │         │                              │
│   biomig-reports-output/    │         │                              │
│   └── {pcm}/{año}/{mes}/    │         │                              │
└─────────────────────────────┘         └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILIDAD Y AUDITORÍA                         │
│                                                                       │
│  AWS X-Ray  (trazas distribuidas Lambda + Step Functions)             │
│  CloudTrail (todas las API calls y accesos S3)                        │
│  CloudWatch Logs (logs estructurados de cada Lambda)                  │
│  CloudWatch Alarms (error rate, eliminaciones, logins fallidos)       │
│  S3 Access Logging (reports-out → bucket de logs separado)            │
│  AWS Config (S3 no público, encriptación activa, trail activo)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Componentes AWS detallados

### 3.1 AWS Amplify

| Parámetro | Valor |
|---|---|
| Framework | React + Vite |
| Deploy trigger | Push a rama `main` en GitHub |
| Build time estimado | ~2 minutos |
| Autenticación | `@aws-amplify/ui-react` (componentes pre-construidos) |
| Variables de entorno | `VITE_API_URL` · `VITE_COGNITO_POOL_ID` · `VITE_COGNITO_CLIENT_ID` |
| Región | sa-east-1 (São Paulo) |
| Security headers | `customHeaders.yml` en raíz del repo (HSTS · CSP · X-Frame-Options) |

**customHeaders.yml:**
```yaml
customHeaders:
  - pattern: '**'
    headers:
      - key: Strict-Transport-Security
        value: max-age=31536000; includeSubDomains
      - key: X-Frame-Options
        value: DENY
      - key: X-Content-Type-Options
        value: nosniff
      - key: Content-Security-Policy
        value: default-src 'self'; connect-src 'self' https://*.amazonaws.com
```

**Vistas de la aplicación:**

```
/login          → LoginPage (Cognito UI)
/upload         → UploadPanel + LoteChecker + PCMSelector
/processing     → ProcessingStatus (polling /reports/status)
/history        → ReportHistory (lista descargable por PCM/mes)
/lotes          → LotesPanel (lista de lotes disponibles)
/admin/lotes    → AdminLotes (archivar / reemplazar / eliminar)
                  Solo visible para grupo admin
```

### 3.2 Amazon Cognito

```
User Pool
├── Grupo: admin
│   • Acceso a todos los PCMs
│   • Puede archivar, reemplazar y eliminar lotes
│   • MFA obligatorio
│
├── Grupo: engineer-14   (Cali)
│   • custom:pcm_id   = "14"
│   • custom:pcm_name = "Cali"
│   • Solo puede generar informes para PCM 14
│
└── Grupo: engineer-N    (N = cualquier PCM activo)

Política de contraseña:
• Mínimo 12 caracteres · Mayúscula + número + símbolo obligatorios

Token validity:
• Access token:  1 hora
• Refresh token: 30 días
```

**Lambda Authorizer — v3:** extrae `cognito:groups` y `custom:pcm_id`
directamente del payload del JWT (base64 decode, sin llamada a Cognito API).
Esto elimina la latencia de red por request. La firma del token ya fue
verificada por API Gateway antes de llegar al Authorizer.

### 3.3 S3 — Estructura completa de buckets

```
biomig-csv-inputs-{account-id}/
│
├── lotes/
│   ├── 2026-03_a3f9b2c1/
│   │   ├── manifest.json        ← fingerprints SHA-256 por archivo
│   │   ├── inmigracion.csv
│   │   ├── emigracion_col.csv
│   │   ├── emigracion_ext.csv
│   │   ├── enrolamientos.csv
│   │   ├── no_paso_emigracion.csv
│   │   ├── no_paso_emigracion_ext.csv
│   │   └── no_paso_inmigracion.csv
│   └── archivados/
│       └── 2026-01_c1a4d8e0/
│
├── incidencias/
│   ├── 2026_PCM14_incidencias.csv
│   └── 2026_PCM12_incidencias.csv
│
└── templates/                   ← NUEVO en v3: plantillas DOCX en S3
    ├── informe_movimientos_template.docx
    └── informe_novedades_template.docx

Lifecycle CSVs (lotes/):
  0–12 meses  → S3 Standard           ($0.023/GB/mes)
  12–24 meses → S3 Standard-IA        ($0.0125/GB/mes)
  24–36 meses → S3 Glacier Inst.      ($0.004/GB/mes)
  36+ meses   → S3 Glacier Deep Archive ($0.00099/GB/mes)
  (42 GB acumulado año 3 = ~$0.04/mes — no se elimina; disponible para auditoría)

──────────────────────────────────────────────────────────────────

biomig-reports-output-{account-id}/
└── reports/
    └── {pcmId}/
        └── {año}/
            └── {mes:02d}/
                └── {reportType}/
                    └── {reportId}/
                        └── informe_{tipo}_PCM{id}_{mes}{año}.docx

Lifecycle reportes:
  0–6 meses   → S3 Standard
  6–24 meses  → S3 Standard-IA
  25+ meses   → Eliminación automática (Ley 1581/2012 Colombia)

Configuraciones aplicadas a ambos buckets:
  • Block Public Access: habilitado a nivel de cuenta y bucket
  • SSE-S3 (AES-256): habilitado por defecto en todos los objetos
  • Versioning: habilitado en reports-output
  • MFA Delete: habilitado en reports-output
  • S3 Access Logging: habilitado → bucket dedicado de logs
```

### 3.4 Lambda — Configuración detallada

| Lambda | Tipo | Memory | Timeout | X-Ray | Propósito |
|---|---|---|---|---|---|
| lote-checker | .zip | 256 MB | 15s | ✅ | SHA-256 completo + consulta DynamoDB |
| upload-handler | .zip | 256 MB | 30s | ✅ | Genera pre-signed URLs de subida |
| lote-registrar | .zip | 512 MB | 60s | ✅ | Valida CSVs, registra lote, detecta PCMs |
| report-requester | .zip | 128 MB | 10s | ✅ | Crea registro PENDING + escribe a SQS |
| sf-trigger | .zip | 128 MB | 15s | ✅ | Lee SQS, inicia Step Functions execution |
| sf-validate-load | .zip | 256 MB | 30s | ✅ | Estado 1 SF: descarga CSVs, V01-V06 |
| sf-process-data | .zip | 1024 MB | 120s | ✅ | Estado 2 SF: filtro PCM, agregación, V07-V25 |
| **sf-generate-artifacts** | **Container ECR** | **3008 MB** | **600s** | ✅ | Estado 3 SF: gráficas + DOCX (pandas, matplotlib, python-docx) |
| sf-save-notify | .zip | 256 MB | 30s | ✅ | Estado 4 SF: S3 PutObject + DynamoDB COMPLETED |
| sf-mark-failed | .zip | 128 MB | 15s | ✅ | Catch global SF: DynamoDB FAILED + mensaje |
| status-handler | .zip | 256 MB | 15s | ✅ | Consulta estado de job en DynamoDB |
| history-handler | .zip | 256 MB | 30s | ✅ | Lista reportes del usuario/PCM |
| download-handler | .zip | 256 MB | 15s | ✅ | Genera pre-signed URL de descarga |
| lotes-handler | .zip | 256 MB | 30s | ✅ | Lista lotes disponibles |
| lotes-admin | .zip | 512 MB | 60s | ✅ | Archivar / reemplazar / eliminar lotes |

**ReservedConcurrency:**
- `sf-generate-artifacts`: máximo 3 ejecuciones simultáneas
  (protege el presupuesto; 3 reportes simultáneos es más que suficiente para 7 PCMs)

**Container Image — sf-generate-artifacts:**
```dockerfile
FROM public.ecr.aws/lambda/python:3.12
RUN pip install pandas==2.2.* numpy matplotlib seaborn python-docx
COPY sf_generate_artifacts/ ${LAMBDA_TASK_ROOT}/
CMD ["handler.lambda_handler"]
```
La imagen vive en ECR: `{account}.dkr.ecr.sa-east-1.amazonaws.com/biomig-report-generator:latest`

**Lambda Layers compartidos** (solo para Lambdas .zip ligeras):
```
layer-utils → biomig_utils/ (validators, csv_processor,
                              metrics, constants, lote_manager)
```
Las dependencias pesadas (pandas, matplotlib, python-docx) se eliminan de
los Layers y viven solo en la imagen del container.

### 3.5 AWS Step Functions — BiomigReportStateMachine (nuevo en v3)

```yaml
# Definición Amazon States Language (ASL) — simplificada
BiomigReportStateMachine:
  Type: EXPRESS          # Express Workflows: < 5 min por ejecución, costo por ejecución
  Comment: "Pipeline de generación de informes Biomig"

  States:

    ValidateAndLoad:
      Type: Task
      Resource: arn:aws:lambda:::function:sf-validate-load
      Retry:
        - ErrorEquals: ["Lambda.ServiceException", "Lambda.AWSLambdaException"]
          IntervalSeconds: 2
          MaxAttempts: 2
          BackoffRate: 2
      Catch:
        - ErrorEquals: ["States.ALL"]
          Next: MarkFailed
          ResultPath: "$.error"
      Next: ProcessData

    ProcessData:
      Type: Task
      Resource: arn:aws:lambda:::function:sf-process-data
      Retry:
        - ErrorEquals: ["States.TaskFailed"]
          IntervalSeconds: 3
          MaxAttempts: 2
          BackoffRate: 1.5
      Catch:
        - ErrorEquals: ["States.ALL"]
          Next: MarkFailed
          ResultPath: "$.error"
      Next: GenerateArtifacts

    GenerateArtifacts:
      Type: Task
      Resource: arn:aws:lambda:::function:sf-generate-artifacts
      TimeoutSeconds: 600
      Retry:
        - ErrorEquals: ["States.TaskFailed"]
          IntervalSeconds: 5
          MaxAttempts: 1      # solo 1 retry: la ejecución es cara
          BackoffRate: 1
      Catch:
        - ErrorEquals: ["States.ALL"]
          Next: MarkFailed
          ResultPath: "$.error"
      Next: SaveAndNotify

    SaveAndNotify:
      Type: Task
      Resource: arn:aws:lambda:::function:sf-save-notify
      Retry:
        - ErrorEquals: ["States.ALL"]
          IntervalSeconds: 2
          MaxAttempts: 3
      Catch:
        - ErrorEquals: ["States.ALL"]
          Next: MarkFailed
          ResultPath: "$.error"
      End: true

    MarkFailed:
      Type: Task
      Resource: arn:aws:lambda:::function:sf-mark-failed
      End: true
```

**Input de cada ejecución:**
```json
{
  "reportId":   "rpt_14_202603_mov_1748291234",
  "loteId":     "2026-03_a3f9b2c1",
  "pcmId":      "14",
  "reportType": "movimientos",
  "mes":        3,
  "año":        2026,
  "userId":     "juan.arrechea@incomelec.com"
}
```

**Por qué Express Workflows:** las ejecuciones duran < 10 minutos, se pagan
por ejecución y por duración (no por estado), y no necesitan historial de 90
días (el historial lo guarda DynamoDB). Son ~70% más baratos que Standard
Workflows para este caso de uso.

### 3.6 SQS — Desacople async (nuevo en v3)

```
BiomigReportsQueue (cola principal)
  • Visibility timeout:  900s  (= timeout máximo de sf-trigger + tiempo de arranque SF)
  • Message retention:   24h
  • Delivery delay:      0s
  • Max message size:    256KB (el payload es JSON pequeño ~500 bytes)
  • Max receive count:   3    (después de 3 intentos fallidos → DLQ)

BiomigReportsDLQ (dead-letter queue)
  • Message retention:   7 días
  • CloudWatch Alarm:    mensajes > 0 → alerta inmediata al admin

Flujo:
  POST /reports/request
    → λ report-requester (escribe a SQS, retorna reportId en < 1s)
    → SQS BiomigReportsQueue
    → λ sf-trigger (trigger por SQS, inicia Step Functions execution)
    → Step Functions BiomigReportStateMachine
```

**Por qué SQS y no EventBridge o invocación directa:**
- API Gateway tiene timeout de 29s — sin SQS el pipeline falla por timeout
- SQS da retry automático si sf-trigger falla al arrancar la ejecución
- La DLQ captura mensajes que no pudieron procesarse → no se pierden solicitudes
- Desacople total: el endpoint responde en < 200ms independientemente de la carga

### 3.7 DynamoDB — Esquema completo

**Tabla: `BiomigLotes`** — entidad central del sistema de lotes

```json
{
  "loteId":       "2026-03_a3f9b2c1",
  "fingerprint":  "sha256:a3f9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9",
  "fingerprintsPorArchivo": {
    "inmigracion":           "sha256:...",
    "emigracion_col":        "sha256:...",
    "emigracion_ext":        "sha256:...",
    "enrolamientos":         "sha256:...",
    "no_paso_emigracion":    "sha256:...",
    "no_paso_emigracion_ext":"sha256:...",
    "no_paso_inmigracion":   "sha256:..."
  },
  "mes":         3,
  "año":         2026,
  "periodoLabel": "Marzo 2026",
  "tipoLote":    "movimientos",
  "estado":      "ACTIVO",
  "version":     1,
  "subidoPor":   "juan.arrechea@incomelec.com",
  "subidoEn":    "2026-03-15T14:30:00Z",
  "pcmsDetectados": ["1", "10", "12", "13", "14", "15", "18"],
  "totalFilas": {
    "inmigracion":            208860,
    "emigracion_col":         170432,
    "emigracion_ext":          18241,
    "enrolamientos":           67293,
    "no_paso_emigracion":       8420,
    "no_paso_emigracion_ext":    520,
    "no_paso_inmigracion":     11340
  },
  "reportesGenerados": {
    "14": "2026-03-15T14:47:23Z",
    "12": "2026-03-16T09:12:05Z"
  },
  "historialVersiones": [],
  "s3Prefix": "lotes/2026-03_a3f9b2c1/",
  "ttl": 1843833600
}
```

Estados del lote: `PENDIENTE · ACTIVO · ARCHIVADO · ELIMINADO · CORRUPTO · REEMPLAZADO`

**Tabla: `BiomigReportsHistory`**

```json
{
  "reportId":      "rpt_14_202603_mov_1748291234",
  "userId":        "juan.arrechea@incomelec.com",
  "pcmId":         "14",
  "loteId":        "2026-03_a3f9b2c1",
  "loteVersion":   1,
  "reportType":    "movimientos",
  "mes":           3,
  "año":           2026,
  "periodoLabel":  "Marzo 2026",
  "generadoEn":    "2026-03-15T14:47:23Z",
  "estado":        "COMPLETED",
  "sfExecutionArn": "arn:aws:states:...:execution:BiomigReportStateMachine:rpt_...",
  "s3Key":         "reports/14/2026/03/movimientos/rpt_.../informe.docx",
  "tamañoBytes":   2847291,
  "duracionMs":    47823,
  "validaciones": {
    "ejecutadas":   25,
    "pasadas":      25,
    "advertencias":  0,
    "errores":       0,
    "detalle":      []
  },
  "ttl": 1811462400
}
```

**GSIs:**

```
BiomigLotes:
  • fingerprint-index  → buscar lote por fingerprint combinado
  • mes-año-index      → listar lotes de un período

BiomigReportsHistory:
  • userId-index       → historial por usuario
  • pcmId-mes-index    → historial por PCM y mes
```

---

## 4. Gestión de lotes de CSVs

### 4.1 Flujo de detección de lote (pre-upload) — Fingerprint v3

```
[1] Usuario selecciona archivos en la UI (drag & drop o selector)

[2] Frontend calcula SHA-256 de cada archivo COMPLETO en el browser
    usando Web Crypto API (sin subir nada):

    async function sha256File(file) {
      const buffer = await file.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    Tiempo típico: ~1-2s por archivo de 200MB (CPU del navegador)
    Resultado: fingerprint por archivo + fingerprint combinado del lote
               (SHA-256 de la concatenación ordenada de los hashes individuales)

[3] Frontend envía al endpoint POST /uploads/check:
    {
      "fingerprintLote": "sha256:...",
      "fingerprintsPorArchivo": { "inmigracion": "sha256:...", ... },
      "tipoCSV": "movimientos"
    }

[4] Lambda lote-checker:
    a. Consulta BiomigLotes usando fingerprint-index (GSI) por fingerprintLote
    b. Si hay coincidencia: verifica también fingerprintsPorArchivo para
       confirmar que todos los archivos coinciden (no solo el hash combinado)

[5a] LOTE NUEVO → responde { "estado": "NUEVO" }
     → Frontend procede con upload completo

[5b] LOTE EXISTENTE → responde:
     {
       "estado": "EXISTENTE",
       "loteId": "2026-03_a3f9b2c1",
       "periodoLabel": "Marzo 2026",
       "subidoEn": "2026-03-15T14:30:00Z",
       "subidoPor": "juan.arrechea@incomelec.com",
       "pcmsDetectados": ["1","10","12","13","14","15","18"],
       "reportesGenerados": { "14": "2026-03-15T14:47:23Z" }
     }
     → Usuario va directo al selector de PCM sin subir nada
```

**Por qué SHA-256 del archivo completo (no primeros 10KB):**
El proveedor puede corregir filas en medio del archivo sin cambiar el
encabezado ni los primeros registros. Con solo 10KB, el sistema detectaría
el archivo corregido como "lote existente" y serviría datos desactualizados.
SHA-256 completo garantiza que cualquier cambio de 1 byte se detecta.

### 4.2 Flujo de upload completo (lote nuevo)

```
[1] Frontend solicita pre-signed URLs: POST /uploads/presigned
    (una URL por CSV, TTL 5 minutos)

[2] Frontend sube cada CSV directamente a S3 con las pre-signed URLs
    (no pasa por Lambda → soporta archivos de 200MB+ sin timeout)

[3] Frontend confirma: POST /uploads/confirm
    { "uploadId": "...", "archivos": { "inmigracion": "s3Key", ... } }

[4] Lambda lote-registrar:
    a. Ejecuta validaciones V01-V07 (estructura, columnas, encoding)
    b. Lee muestra de fechas para detectar el mes del lote (V24, V25)
    c. Detecta todos los PCMs presentes en los CSVs
    d. Crea registro en BiomigLotes con estado ACTIVO
    e. Crea manifest.json en S3 con fingerprintsPorArchivo
    f. Retorna: { "loteId": "...", "pcmsDetectados": [...] }

[5] UI muestra el selector de PCM con los PCMs detectados
```

### 4.3 Flujo de reemplazo (CSVs corregidos) — solo admin

```
[1] Admin sube los nuevos CSVs → sistema recalcula SHA-256 completo
    → detecta que el mes ya tiene un lote activo (diferente fingerprint)

[2] Sistema informa: "Ya existe un lote de Marzo 2026 subido el 15/03/2026.
    Los CSVs anteriores serán eliminados físicamente de S3.
    Los informes ya generados se conservan. [Confirmar] [Cancelar]"

[3] Admin confirma → Lambda lotes-admin:
    a. Elimina CSVs anteriores de S3
    b. Sube los nuevos CSVs al mismo prefijo
    c. Actualiza manifest.json con nuevos fingerprints
    d. DynamoDB BiomigLotes:
       • fingerprintLote + fingerprintsPorArchivo → nuevos valores
       • version → incrementa (1 → 2)
       • historialVersiones → agrega entrada con datos de la versión anterior
       • estado → ACTIVO

[4] Los reportes generados con la versión anterior se conservan en S3
    con nota en DynamoDB: "csvVersion": 1, "csvReemplazadoEn": "2026-04-10T..."
```

### 4.4 Administración de lotes — solo admin

```
ARCHIVAR (reversible)
  • CSVs se mueven a s3://biomig-csv-inputs/lotes/archivados/
  • DynamoDB: estado → ARCHIVADO
  • El lote desaparece del selector de todos los usuarios
  • El admin puede restaurarlo: estado → ACTIVO, CSVs vuelven a /lotes/

ELIMINAR DEFINITIVO (irreversible — doble confirmación en UI)
  • Lambda lotes-admin elimina los CSVs físicamente de S3
  • DynamoDB: estado → ELIMINADO (el registro permanece para auditoría)
  • CloudTrail registra: quién, cuándo, qué loteId
  • Los reportes generados permanecen descargables
  • En el historial aparece: "CSV fuente eliminado el DD/MM/AAAA"
```

---

## 5. Pipeline de generación — Informe de Movimientos

### 5.1 Fuente de datos

```
7 CSVs del proveedor (separador: ',', encoding: latin-1)
Columnas: DIA · HORA · ES_VIP · NACIONALIDAD · GENERO ·
          FECHA_DE_NACIMIENTO · CANTIDAD · PUESTO_CONTROL_MIGRATORIO

Volumen típico por CSV (todos los PCMs):
  inmigracion.csv       → ~208.860 filas
  emigracion_col.csv    → ~170.000 filas
  emigracion_ext.csv    →  ~18.000 filas
  enrolamientos.csv     →  ~67.000 filas
  no_paso_emigracion    →   ~8.000 filas
  no_paso_emigracion_ext →    ~500 filas
  no_paso_inmigracion   →  ~11.000 filas

Para PCM 14 (Cali) filtrado:
  inmigracion:    ~8.153 filas · emigracion_col: ~5.615 · ext: ~451
  enrolamientos:  ~2.137 filas
```

### 5.2 Flujo completo — con SQS + Step Functions (v3)

```
[1] Usuario selecciona lote (existente o recién subido)
    → Selecciona PCM 14 + "Movimientos Migratorios" + Marzo 2026

[2] POST /reports/request → λ report-requester
    a. Crea registro en BiomigReportsHistory: estado = PENDING
    b. Escribe mensaje a SQS: { reportId, loteId, pcmId, reportType, mes, año, userId }
    c. Retorna inmediatamente: { "reportId": "rpt_14_202603_mov_..." }
       (tiempo de respuesta: < 200ms, no hay timeout)

[3] SQS → λ sf-trigger
    a. Lee mensaje de la cola
    b. Inicia ejecución de BiomigReportStateMachine con el input del mensaje
    c. DynamoDB: estado = PROCESSING, sfExecutionArn = arn de la ejecución

[4] Frontend inicia polling a GET /reports/status/{reportId}
    → Muestra barra de progreso con la etapa actual

[5] Step Functions ejecuta los 4 estados (ver §5.3)

[6] Estado SaveAndNotify completa:
    → DynamoDB: estado = COMPLETED, s3Key, tamañoBytes, duracionMs
    → DynamoDB BiomigLotes: reportesGenerados["14"] = timestamp

[7] Siguiente poll del frontend detecta COMPLETED
    → Muestra botón "Descargar informe"

[8] GET /reports/download/{reportId}
    → λ download-handler genera pre-signed URL (TTL 15 min)
    → Usuario descarga el .docx

Si algo falla en cualquier estado:
    → MarkFailed actualiza DynamoDB: estado = FAILED + errorMessage + etapa_fallida
    → Si sf-trigger falla 3 veces: mensaje va a DLQ → alarma CloudWatch
    → Usuario ve el error con el mensaje exacto, puede reintentar
```

### 5.3 Procesamiento interno — estados de Step Functions (v3)

```
ESTADO 1: ValidateAndLoad (λ sf-validate-load, 256MB, 30s)
──────────────────────────────────────────────────────────
Input:  { reportId, loteId, pcmId, reportType, mes, año }
Output: { csvKeys, filasCount, encodingDetectado, mesPeriodo }

• Descarga los 7 CSVs del lote desde S3 a memoria (BytesIO)
• Detecta encoding: prueba utf-8-sig → latin-1 → cp1252 → utf-8
• Ejecuta validaciones V01-V06 (estructura, columnas, no vacío)
• Si V01-V06 falla → lanza excepción → SF va a MarkFailed
• Output incluye las s3Keys confirmadas de cada CSV

ESTADO 2: ProcessData (λ sf-process-data, 1024MB, 120s)
──────────────────────────────────────────────────────────
Input:  output del Estado 1
Output: { metricsResult, validaciones, chartsInput }

• Descarga CSVs de S3 (paralelo, thread pool)
• Filtra PUESTO_CONTROL_MIGRATORIO == pcmId para cada CSV
• Agrupa por DIA, cuenta filas (cada fila = 1 pasajero)
• Merge de los 7 DataFrames por fecha → tabla maestra de 28-31 filas x 11 cols
• Calcula métricas derivadas: totales, promedios, max/min, tasa de éxito
• Ejecuta validaciones V07-V25 (guarda resultado en DynamoDB parcial)
• Output: metricsResult completo listo para graficar y ensamblar

ESTADO 3: GenerateArtifacts (λ sf-generate-artifacts, Container 3008MB, 600s)
──────────────────────────────────────────────────────────────────────────────
Input:  { metricsResult, reportId, pcmId, reportType, mes, año }
Output: { s3KeyDocx, tamañoBytes }

• Descarga template DOCX desde S3 (templates/informe_movimientos_template.docx)
  [por estar en S3, cambiar la plantilla no requiere redeploy]

• Genera 10 gráficas en memoria (BytesIO, matplotlib.use('Agg'), 150 DPI):
  G01 → Extranjeros Emigra vs No Pasaron        (barras agrupadas)
  G02 → Colombianos Inmigra vs No Pasaron       (barras agrupadas)
  G03 → Colombianos Emigra vs No Pasaron        (barras agrupadas)
  G04 → Enrolamientos por Día                   (barras + línea promedio)
  G05 → Extranjeros por Día                     (barras)
  G06 → Resumen por Día de la Semana            (barras agrupadas 3 series)
  G07 → Colombianos Emigra vs Inmigra por Día   (barras agrupadas)
  G08 → Movimientos Diarios con Promedios       (barras + líneas promedio)
  G09 → No Pasos: totales del mes y evolución   (panel doble)
  G10 → Promedio por Día de la Semana (4 cols)  (barras agrupadas)

  Paleta corporativa: AZUL '#1F4E79' · NARANJA '#ED7D31' · VERDE '#70AD47'

• Ensambla DOCX con python-docx sobre la plantilla:
  1. Find-and-replace de placeholders {{MES_NOMBRE}}, {{AÑO}}, {{TOTAL_MOV}}...
  2. Pobla 7 tablas (resumen, no pasos, promedios, datos diarios x 2, estadístico, anual)
  3. Inserta G01-G10 en los placeholders del XML del template

• PutObject del DOCX a S3: reports/{pcmId}/{año}/{mes}/{reportType}/{reportId}/informe.docx
• Output: { s3KeyDocx, tamañoBytes }

ESTADO 4: SaveAndNotify (λ sf-save-notify, 256MB, 30s)
──────────────────────────────────────────────────────────
Input:  output del Estado 3 + reportId + validaciones del Estado 2
Output: { estado: "COMPLETED" }

• UpdateItem en DynamoDB BiomigReportsHistory:
  estado = COMPLETED, s3Key, tamañoBytes, duracionMs, validaciones
• UpdateItem en DynamoDB BiomigLotes:
  reportesGenerados[pcmId] = timestamp

ESTADO MarkFailed (λ sf-mark-failed, 128MB, 15s)
──────────────────────────────────────────────────
• Recibe el error de cualquier estado anterior
• UpdateItem en DynamoDB BiomigReportsHistory:
  estado = FAILED, errorMessage = $.error.Cause, etapaFallida = nombre del estado
• El usuario puede reintentar desde la UI (POST /reports/request de nuevo)
```

---

## 6. Pipeline de generación — Informe de Novedades

### 6.1 Fuente de datos

```
1 CSV acumulativo anual (separador: ';', encoding: latin-1/cp1252)
18 columnas (17 datos + 1 vacía por arrastre de Excel)

Columnas clave:
  DÍA · FECHA · HORA DE REPORTE · HORA DE ATENCIÓN · HORA DE SOLUCIÓN ·
  TIEMPO DE ATENCIÓN · TIEMPO DE SOLUCIÓN · SERIAL EQUIPO · ID EQUIPO ·
  UBICACIÓN · REPORTE CLIENTE · TIPO DE REPORTE · NIVEL DE REPORTE ·
  BREVE DESCRIPCIÓN DE REPORTE · TEC EN TURNO · ESTADO

Características especiales:
  • ~1001 líneas totales → solo ~82 filas con datos reales
  • Filas válidas: DÍA está en DIAS_VALIDOS
  • Horas con formato inconsistente: "7:21" y "7:15:00" coexisten
  • Acumula el año completo → se filtra por mes seleccionado
```

### 6.2 Flujo completo

Idéntico al flujo de Movimientos (§5.2) con SQS + Step Functions.
Los 4 estados ejecutan las mismas responsabilidades pero con la lógica
de novedades en `sf-process-data` y `sf-generate-artifacts`.

### 6.3 Gráficas del informe de Novedades

```
G1 → Histórico meses anteriores          (barras agrupadas, últimos 4 meses)
G2 → Totales por área                    (barras simples Emigración/Inmigración)
G3 → Distribución porcentual             (donut por REPORTE_CLIENTE)
G4 → Niveles de servicio Emigración      (barras Nivel 1/2/3)
G5 → Niveles de servicio Inmigración     (barras Nivel 1/2/3)
G6 → Promedio reportes por novedad       (barras horizontales, coloreadas por nivel)
G7 → Distribución horaria                (línea + área, pico anotado)
G8 → Resumen niveles ambas áreas         (barras agrupadas Emig vs Inmig por nivel)

Paleta: AZUL '#1F4788' · NARANJA '#E07B00' · ROJO '#C0392B'
        Nivel 1 = AZUL · Nivel 2 = NARANJA · Nivel 3 = ROJO
```

---

## 7. Validaciones cruzadas

El sistema aplica 25 validaciones en cascada. Las **bloqueantes** (V01-V06,
V14, V21, V24) detienen el pipeline y nunca generan un informe con esos datos.
Las demás son **advertencias**: el informe se genera pero la UI muestra un
banner "Generado con N advertencias — revisar antes de entregar".

Cada ejecución guarda el resultado completo de las 25 validaciones en
DynamoDB (`BiomigReportsHistory.validaciones`).

### V01-V06 — Estructura (bloqueantes, ambos tipos)

```
[V01] Encoding detectado correctamente (utf-8-sig → latin-1 → cp1252 → utf-8)
[V02] Separador correcto según tipo (movimientos: ',' · novedades: ';')
[V03] Columnas obligatorias presentes
[V04] CSV no vacío después de descartar encabezados y filas vacías
[V05] Formato de fecha válido (dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy)
[V06] PCM seleccionado existe en el archivo (solo Movimientos)
```

### V08-V15 — Integridad Movimientos (advertencias)

```
[V08] Total calculado == suma de valores diarios
[V09] Rango de fechas idéntico entre todos los CSVs del lote
[V10] Sin fechas duplicadas para el mismo PCM en un CSV
[V11] Valores numéricos son enteros no negativos
[V12] CANTIDAD == 1 en cada fila
[V13] Completitud: todos los días del mes están presentes
[V14] Movimiento Migratorio Total = emigra + inmigra + ext (BLOQUEANTE)
[V15] Consistencia día de semana vs fecha
```

### V16-V23 — Integridad Novedades (advertencias)

```
[V16] UBICACIÓN solo contiene 'Emigración' o 'Inmigración'
[V17] NIVEL DE REPORTE normalizable a 'NIVEL 1/2/3'
[V18] ESTADO solo 'Cerrado' o 'Abierto'
[V19] HORA DE REPORTE en rango 00:00-23:59
[V20] Sin duplicados exactos (FECHA + SERIAL + HORA)
[V21] Total novedades del mes == filas válidas filtradas (BLOQUEANTE)
[V22] Conteo histórico coherente con datos reales del CSV
[V23] Completitud de campos clave por fila
```

### V24-V25 — Validaciones de lote

```
[V24] Coherencia temporal: todos los CSVs cubren el mismo período (BLOQUEANTE)
[V25] Mes del lote coherente con el período esperado (advertencia con confirmación)
```

---

## 8. Estructura del repositorio GitHub

```
biomig-reports/
│
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml      # Amplify en push a main (paths: frontend/**)
│       ├── deploy-lambdas.yml       # SAM deploy en push a main (paths: backend/**)
│       ├── deploy-container.yml     # ECR build+push en push a main (paths: backend/functions/sf_generate_artifacts/**)
│       ├── test-pr.yml              # pytest + lint en cada PR
│       └── security-scan.yml        # bandit + safety en cada PR
│
├── infrastructure/
│   ├── template.yaml                # AWS SAM: todos los recursos AWS
│   ├── samconfig.toml
│   └── parameters/
│       ├── dev.json
│       └── prod.json
│
├── backend/
│   ├── layers/
│   │   └── utils/
│   │       └── python/
│   │           └── biomig_utils/
│   │               ├── __init__.py
│   │               ├── constants.py      # Paletas, columnas, tipos válidos
│   │               ├── validators.py     # V01-V25 completas
│   │               ├── csv_processor.py  # Carga, filtro PCM, agregación
│   │               ├── lote_manager.py   # Fingerprint SHA-256, ciclo de vida
│   │               ├── metrics.py        # Cálculo de métricas derivadas
│   │               └── docx_assembler.py # Ensamblaje DOCX tablas + imágenes
│   │
│   ├── functions/
│   │   ├── lote_checker/            handler.py
│   │   ├── upload_handler/          handler.py
│   │   ├── lote_registrar/          handler.py
│   │   ├── report_requester/        handler.py   # escribe a SQS
│   │   ├── sf_trigger/              handler.py   # lee SQS, inicia SF
│   │   ├── sf_validate_load/        handler.py   # Estado 1 SF
│   │   ├── sf_process_data/         handler.py   # Estado 2 SF
│   │   ├── sf_generate_artifacts/              # Estado 3 SF — Container Image
│   │   │   ├── handler.py
│   │   │   ├── chart_builder.py     # 10 gráficas movimientos + 8 novedades
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt     # pandas, numpy, matplotlib, seaborn, python-docx
│   │   ├── sf_save_notify/          handler.py   # Estado 4 SF
│   │   ├── sf_mark_failed/          handler.py   # Catch global SF
│   │   ├── status_handler/          handler.py
│   │   ├── history_handler/         handler.py
│   │   ├── download_handler/        handler.py
│   │   ├── lotes_handler/           handler.py
│   │   └── lotes_admin/             handler.py
│   │
│   └── tests/
│       ├── unit/
│       │   ├── test_validators.py           # 25 validaciones
│       │   ├── test_csv_processor.py
│       │   ├── test_lote_manager.py         # fingerprint SHA-256, ciclo de vida
│       │   ├── test_metrics.py
│       │   └── test_docx_assembler.py
│       ├── integration/
│       │   ├── test_movimientos_pipeline.py
│       │   ├── test_novedades_pipeline.py
│       │   └── test_lote_lifecycle.py
│       └── fixtures/
│           ├── sample_inmigracion_pcm14.csv
│           ├── sample_incidencias_abr.csv
│           ├── expected_movimientos_mar2026.json
│           └── expected_novedades_abr2026.json
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Auth/            LoginPage.jsx
│       │   ├── Lotes/           LotesPanel.jsx · LoteCard.jsx
│       │   ├── Upload/          UploadPanel.jsx · LoteChecker.jsx · PCMSelector.jsx
│       │   │                    [LoteChecker calcula SHA-256 con Web Crypto API]
│       │   ├── Processing/      ProcessingStatus.jsx
│       │   ├── History/         ReportHistory.jsx
│       │   └── Admin/           AdminLotes.jsx
│       ├── services/
│       │   ├── api.js
│       │   └── auth.js
│       ├── App.jsx
│       └── main.jsx
│
└── docs/
    ├── arquitectura.md          # Este documento
    ├── runbook.md
    ├── troubleshooting.md
    └── validaciones.md
```

---

## 9. CI/CD con GitHub Actions

### 9.1 Flujo de trabajo

```
Rama feature/* o fix/*
         ↓
Pull Request a main
         ↓
test-pr.yml + security-scan.yml (paralelos):
  • cfn-lint infrastructure/template.yaml      ← valida SAM antes de deploy
  • pytest backend/tests/unit/ + backend/tests/integration/
  • bandit -r backend/
  • safety check
  → Si falla cualquier check: PR bloqueado

Merge a main
         ↓
  ┌──────────────────────────────────────────────────────┐
  │  deploy-lambdas.yml    deploy-frontend.yml           │
  │  (paths: backend/**)   (paths: frontend/**)          │
  │  sam build             npm ci && npm run build       │
  │  sam deploy            amplify publish --yes         │
  │       ↑                                              │
  │  deploy-container.yml                                │
  │  (paths: backend/functions/sf_generate_artifacts/**) │
  │  docker build → ECR push → sam deploy               │
  └──────────────────────────────────────────────────────┘
```

### 9.2 Workflow deploy-container.yml (nuevo en v3)

```yaml
name: Build y deploy container report-generator
on:
  push:
    branches: [main]
    paths: ['backend/functions/sf_generate_artifacts/**']

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: sa-east-1

      - uses: aws-actions/amazon-ecr-login@v2

      - name: Build y push imagen
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build \
            -t $ECR_REGISTRY/biomig-report-generator:$IMAGE_TAG \
            -t $ECR_REGISTRY/biomig-report-generator:latest \
            backend/functions/sf_generate_artifacts/
          docker push $ECR_REGISTRY/biomig-report-generator:$IMAGE_TAG
          docker push $ECR_REGISTRY/biomig-report-generator:latest

      - name: Actualizar función Lambda con nueva imagen
        run: |
          aws lambda update-function-code \
            --function-name sf-generate-artifacts \
            --image-uri ${{ steps.login-ecr.outputs.registry }}/biomig-report-generator:${{ github.sha }}
```

### 9.3 Workflow deploy-lambdas.yml

```yaml
name: Deploy Lambdas y Layers
on:
  push:
    branches: [main]
    paths: ['backend/**', 'infrastructure/**']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r backend/tests/requirements.txt
      - run: pytest backend/tests/ -v --tb=short

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: sa-east-1
      - uses: aws-actions/setup-sam@v2
      - run: sam build
      - run: sam deploy --config-env prod --no-confirm-changeset
```

### 9.4 GitHub Secrets requeridos

```
AWS_DEPLOY_ROLE_ARN        → ARN del rol IAM para OIDC (ej: arn:aws:iam::906401006146:role/BiomigGitHubActionsRole)
AMPLIFY_APP_ID             → ID de la app en Amplify Console
ECR_REPOSITORY             → URI del repositorio ECR
```

No se usan access keys estáticas. GitHub Actions obtiene credenciales temporales (1 hora)
mediante OIDC, usando el rol BiomigGitHubActionsRole con trust policy condicionada a
`repo:incomelec/biomig-reports:ref:refs/heads/main`.

**Configuración OIDC (una vez, en IAM Console):**
```
Identity Provider URL:   https://token.actions.githubusercontent.com
Audience:                sts.amazonaws.com
Rol trust policy condition: token.actions.githubusercontent.com:sub = repo:incomelec/biomig-reports:ref:refs/heads/main
```

### 9.5 Convención de ramas

```
main        → producción (protegida, requiere PR + todos los checks verdes)
develop     → integración pre-producción
feature/xxx → nueva funcionalidad
fix/xxx     → corrección de bug
hotfix/xxx  → fix urgente → PR directo a main con aprobación obligatoria
```

---

## 10. Seguridad

### 10.1 IAM Roles — mínimo privilegio por Lambda

| Lambda | S3 permisos | DynamoDB permisos | Otros |
|---|---|---|---|
| lote-checker | — | `Query` BiomigLotes (fingerprint-index) | — |
| upload-handler | `PutObject` csv-inputs/lotes/* | `PutItem` BiomigCSVUploads | — |
| lote-registrar | `GetObject` csv-inputs/lotes/* | `PutItem` BiomigLotes · `UpdateItem` BiomigCSVUploads | — |
| report-requester | — | `PutItem` BiomigReportsHistory | `sqs:SendMessage` |
| sf-trigger | — | `UpdateItem` BiomigReportsHistory | `states:StartExecution` · `sqs:ReceiveMessage` |
| sf-validate-load | `GetObject` csv-inputs/lotes/* | — | — |
| sf-process-data | `GetObject` csv-inputs/lotes/* | `UpdateItem` BiomigReportsHistory (validaciones parciales) | — |
| sf-generate-artifacts | `GetObject` csv-inputs/templates/* · `PutObject` reports-output/* | — | — |
| sf-save-notify | — | `UpdateItem` BiomigReportsHistory · `UpdateItem` BiomigLotes | — |
| sf-mark-failed | — | `UpdateItem` BiomigReportsHistory | — |
| download-handler | `GetObject` reports-output/* | `GetItem` BiomigReportsHistory | — |
| lotes-admin | `DeleteObject` + `CopyObject` csv-inputs | `UpdateItem` BiomigLotes | — |

### 10.2 Protección de datos

```
En tránsito:
  • TLS 1.2+ en API Gateway, Amplify/CloudFront, pre-signed URLs

En reposo:
  • SSE-S3 (AES-256) en todos los objetos de ambos buckets
  • DynamoDB encryption at rest (clave AWS-managed)
```

### 10.3 Controles adicionales

```
• Block Public Access: habilitado a nivel de cuenta y en cada bucket
• Pre-signed URLs TTL: 5 min para upload · 15 min para descarga
• Versioning + MFA Delete en reports-output
• API Gateway throttling: 10 req/s, burst 50 por usuario
• Endpoints admin (/lotes/*/archivar, /eliminar, /reemplazar):
  validación de grupo 'admin' en Lambda (no solo en Authorizer)
• CORS: solo desde dominio de Amplify, no wildcard *
```

---

## 11. Auditoría y trazabilidad

### 11.1 Eventos trazados

| Evento | Registro en |
|---|---|
| Login / logout | Cognito logs + CloudTrail |
| Upload CSV a S3 | CloudTrail (S3 PutObject) + DynamoDB BiomigCSVUploads |
| Verificación de lote (fingerprint) | CloudWatch Logs + X-Ray trace |
| Solicitud de reporte (POST /reports/request) | CloudWatch + DynamoDB PENDING |
| Inicio de ejecución Step Functions | CloudTrail + sfExecutionArn en DynamoDB |
| Resultado por estado de SF | X-Ray trace por estado |
| Resultado de las 25 validaciones | DynamoDB (objeto validaciones completo) |
| DOCX generado exitosamente | CloudWatch + DynamoDB COMPLETED + X-Ray |
| Error en cualquier estado de SF | CloudWatch + DynamoDB FAILED + mensaje exacto |
| Descarga de informe | CloudTrail (S3 GetObject) + CloudWatch |
| Lote archivado / reemplazado / eliminado | CloudTrail + DynamoDB |
| Mensaje en DLQ | CloudWatch Alarm → email inmediato al admin |

### 11.2 CloudWatch Alarms

```
• sf-generate-artifacts error rate > 0        → email admin
• BiomigReportsDLQ mensajes > 0               → email admin (solicitud perdida)
• λ lotes-admin invocada                      → email admin (acción crítica)
• S3 reports-output DeleteObject              → email admin
• Cognito logins fallidos > 5 / hora          → email admin
```

### 11.3 Retención de registros

```
CloudWatch Logs:  90 días
CloudTrail:       365 días en bucket biomig-logs dedicado
DynamoDB TTL:     25 meses (campo ttl, auto-eliminación)
X-Ray traces:     30 días (retención por defecto, sin costo adicional)
S3 csv-inputs:    0-12m Standard · 12-24m IA · 24-36m Glacier · 36m+ eliminado
S3 reports-output:0-6m Standard · 6-24m IA · 25m+ eliminado (Ley 1581/2012)
```

---

## 12. Estimación de costos

### 12.1 Supuestos (escenario base)

- 4 generaciones de informe por mes (2 tipos × 2 PCMs activos)
- 1 upload de lote por mes (los demás reutilizan el lote existente)
- 50 usuarios acceden al historial
- Almacenamiento acumulado año 1: ~42 GB CSVs + ~500 MB reportes

### 12.2 Desglose mensual — escenario base v3

| Servicio | Uso estimado | Costo/mes |
|---|---|---|
| AWS Amplify Hosting | 5 GB servidos, ~30 builds/mes | ~$0.50 |
| Amazon Cognito | < 50.000 MAU (tier gratuito) | $0.00 |
| API Gateway REST | ~1.000 requests/mes | ~$0.004 |
| SQS | ~100 mensajes/mes (bien dentro del free tier: 1M mensajes) | $0.00 |
| Step Functions Express | 4 ejecuciones/mes × ~5 min = 20 min totales | ~$0.01 |
| Lambda sf-generate-artifacts (container) | 4 × 5 min × 3 GB | ~$0.30 |
| Lambda resto (sf-validate-load, sf-process-data, sf-save-notify, etc.) | ~200 invocaciones ligeras | ~$0.02 |
| ECR (imagen container ~1.5 GB) | ~1.5 GB almacenamiento | ~$0.15 |
| S3 csv-inputs (lotes) | ~4 GB nuevos/mes + acceso | ~$0.12 |
| S3 reports-output | ~50 MB nuevos/mes + historial | ~$0.08 |
| DynamoDB On-Demand | ~300 writes + ~1.500 reads/mes | ~$0.03 |
| CloudWatch Logs | ~1 GB logs/mes | ~$0.50 |
| X-Ray | ~200 trazas/mes (bien dentro del free tier: 100K) | $0.00 |
| CloudTrail | Primer trail gratuito | $0.00 |
| AWS Budgets | 2 alertas activas | $0.00 |
| S3 Deep Archive (CSVs >36 meses) | ~42 GB en año 3 | ~$0.04 |
| **TOTAL ESTIMADO** | | **~$1.75 – $2.75/mes** |

**Margen disponible: ~$22/mes dentro del presupuesto de $25.**

*El Step Functions Express y SQS añaden ~$0.01/mes vs la v2 — insignificante
frente al valor que aportan en confiabilidad y observabilidad.*

### 12.3 Escenario de crecimiento (7 PCMs × 2 informes × 4 veces/mes)

| Métrica | Valor |
|---|---|
| Generaciones/mes | ~56 |
| Lambda container + SF | ~$4.50 |
| S3 + ECR acumulado año 2 | ~$2.50 |
| CloudWatch + otros | ~$1.50 |
| **Total estimado** | **~$8.50/mes** |

Aún con margen de ~$16.50 dentro del presupuesto de $25.

---

## 13. Well-Architected Framework

### Operational Excellence
- Todo el código en GitHub con historia completa
- Tests automáticos en cada PR bloquean código roto antes del deploy
- Step Functions provee visibilidad por etapa: se sabe exactamente en qué estado falló sin revisar logs manualmente
- X-Ray correlaciona trazas distribuidas a través de Lambdas y Step Functions en un solo mapa de servicio
- La DLQ captura solicitudes perdidas con alarma inmediata
- Los runbooks en `/docs/` permiten operar sin conocer la infraestructura

### Security
- Cognito con grupos por PCM — cada engineer solo genera informes de su PCM
- Lambda Authorizer lee claims del JWT directamente (sin llamada a Cognito API)
- IAM mínimo privilegio por Lambda: 15 roles distintos, cada uno con solo los permisos exactos
- Pre-signed URLs con TTL corto — reportes y CSVs nunca son accesibles de forma permanente
- Todos los datos encriptados en reposo (SSE-S3, DynamoDB) y en tránsito (TLS 1.2+)
- MFA obligatorio para cuentas de administrador
- CloudTrail registra cada acción sobre lotes — eliminaciones completamente auditables

### Reliability
- SQS garantiza que ninguna solicitud de reporte se pierde, aunque sf-trigger falle temporalmente
- Step Functions con retry por estado: si GenerateArtifacts falla, solo se reintenta esa etapa, no todo el pipeline
- La DLQ retiene mensajes fallidos 7 días — tiempo suficiente para diagnosticar y reinyectar
- Las 25 validaciones garantizan que el sistema nunca produce un informe con datos incorrectos
- SHA-256 completo previene colisiones silenciosas en la detección de lotes
- DynamoDB On-Demand — no hay capacidad que aprovisionar, nunca se satura
- S3 tiene 11 nueves de durabilidad — los reportes históricos no se pierden

### Performance Efficiency
- Upload directo a S3 con pre-signed URL — CSVs de 200MB sin pasar por Lambda
- Lambda container de 3 GB RAM para generación — pandas procesa 200K filas en ~5s
- SHA-256 en browser con Web Crypto API — cálculo en paralelo por archivo, ~2s total
- Gráficas en memoria (BytesIO, matplotlib Agg backend) — sin escritura a disco
- DynamoDB GSI por fingerprint — búsqueda de lote existente en ~5ms
- sf-process-data (1 GB RAM) maneja pandas filtrado por PCM en < 30s

### Cost Optimization
- Todo serverless — costo cero cuando nadie usa el sistema
- SQS y Step Functions Express añaden < $0.01/mes al escenario base
- Lambda Layers solo para utilitarios ligeros — container ECR solo para la Lambda pesada
- Reutilización de lotes entre PCMs — 7 PCMs comparten 1 upload
- S3 lifecycle automático — CSVs envejecen a IA y Glacier solos
- DynamoDB TTL automático — registros se eliminan a los 25 meses
- Cognito gratuito para < 50K MAU

### Sustainability
- Serverless = recursos de cómputo solo cuando hay trabajo — huella mínima
- ReservedConcurrency = 3 en report-generator — evita sobreprovisionar capacidad de cómputo
- Reutilización de lotes evita que 7 PCMs transfieran y almacenen el mismo archivo 7 veces
- S3 lifecycle a IA y Glacier reduce energía de almacenamiento con el tiempo

---

## 14. Hoja de ruta de implementación

### Fase 1 — Infraestructura base (Semana 1-2)
```
☐ Crear cuenta AWS en sa-east-1
☐ Configurar OIDC entre GitHub Actions y AWS (un rol IAM BiomigGitHubActionsRole)
☐ Instalar AWS SAM CLI y Docker localmente
☐ Crear repositorio GitHub: biomig-reports
☐ Configurar GitHub Secrets: AWS_DEPLOY_ROLE_ARN, AMPLIFY_APP_ID, ECR_REPOSITORY
☐ Escribir template.yaml inicial:
    S3 (2 buckets con lifecycles + templates/ + Deep Archive en lifecycle)
    DynamoDB (3 tablas + GSIs + TTL)
    Cognito (User Pool + grupos + custom attributes)
    SQS (BiomigReportsQueue + BiomigReportsDLQ)
    ECR (biomig-report-generator)
    Step Functions (BiomigReportStateMachine)
    API Gateway (endpoints vacíos)
    AWS Budgets (alarma $10 al 80% + alarma $25 al 100%)
☐ sam deploy → infraestructura vacía en AWS
☐ Crear customHeaders.yml en raíz del repo (HSTS, CSP, X-Frame-Options)
☐ Conectar Amplify con GitHub → primer deploy del frontend vacío
☐ Verificar que HTTPS funciona y Cognito muestra el login
```

### Fase 2 — Backend core (Semana 2-4)
```
☐ Implementar biomig_utils/constants.py + validators.py (V01-V25)
☐ Tests unitarios de las 25 validaciones con fixtures reales anonimizados
☐ Implementar biomig_utils/lote_manager.py (SHA-256 completo, ciclo de vida)
☐ Tests: lote nuevo, existente, fingerprint idéntico con datos diferentes
☐ Implementar biomig_utils/csv_processor.py + metrics.py
☐ Tests con muestra real anonimizada de PCM 14 (200 filas)
☐ Implementar chart_builder.py (10 gráficas + 8 novedades) en container
☐ Construir imagen Docker localmente y verificar gráficas visualmente
☐ Implementar docx_assembler.py
☐ Tests de DOCX: comparar output con informe manual de referencia
☐ Implementar los 15 handlers de Lambda
☐ Implementar definición ASL de Step Functions
☐ Tests de integración: pipelines completos con moto (S3, DynamoDB, SQS)
☐ sam deploy + docker push → stack completo en producción
```

### Fase 3 — Frontend (Semana 3-5)
```
☐ Setup React + Vite + @aws-amplify/ui-react
☐ Implementar LoteChecker con SHA-256 (Web Crypto API)
☐ Implementar UploadPanel + PCMSelector
☐ Implementar ProcessingStatus con polling GET /reports/status
☐ Implementar ReportHistory con descarga
☐ Implementar AdminLotes (solo grupo admin)
☐ Deploy en Amplify
☐ Prueba end-to-end con datos reales
```

### Fase 4 — Hardening y go-live (Semana 5-6)
```
☐ Configurar CloudWatch Alarms (5 alarmas)
☐ Verificar X-Ray en consola: mapa de servicio completo visible
☐ Verificar DLQ: simular fallo y confirmar alarma llega por email
☐ Prueba de reemplazo de lote con CSVs corregidos
☐ Prueba de archivado, restauración y eliminación de lote
☐ Prueba con CSVs reales de Cali: movimientos marzo 2026 + novedades abril 2026
☐ Comparar DOCX generado vs informe manual → deben coincidir al 100%
☐ Ajustar templates en S3 si algún placeholder no coincide
☐ Escribir docs/runbook.md
☐ Crear usuario admin + engineer-14 en Cognito
☐ Capacitación de uso: 30 minutos máximo
☐ Go-live
```

### V2 — Backlog priorizado
```
☐ Mensajes de UI detallados en flujo de lote existente (V2.1)
☐ Distribución por nacionalidad de extranjeros en Informe Movimientos (V2.2)
☐ Justificación escrita al eliminar lote + registro en DynamoDB (V2.3)
☐ Multi-PCM simultáneo desde una sola UI (V2.4)
☐ Export directo a PDF sin pasar por Word (V2.5)
☐ Dashboard de tendencias: comparativa trimestral entre PCMs (V2.6)
☐ Conclusiones auto-redactadas con Claude Haiku vía Amazon Bedrock (V2.7 — opcional)
```

---

## 15. Decisiones de diseño consolidadas

| Decisión | Definición final |
|---|---|
| Stack AWS | Amplify + Cognito + API Gateway + SQS + Step Functions + Lambda + S3 + DynamoDB + ECR |
| Región | sa-east-1 (São Paulo) |
| IaC | AWS SAM (`template.yaml`) |
| CI/CD | GitHub Actions → SAM deploy + ECR push + Amplify deploy en merge a main |
| Presupuesto | ≤ $25 USD/mes · estimado real $1.75-$2.75/mes |
| Desacople async | SQS entre POST /reports/request y el pipeline (sin SQS → timeout de API GW a los 29s) |
| Orquestación del pipeline | Step Functions Express Workflows: retry por estado, visibilidad por etapa, sin límite de tiempo en el flujo total |
| Dependencias pesadas | Container Image ECR para sf-generate-artifacts (pandas + matplotlib + python-docx > 250MB); Lambda Layers solo para utils |
| Fingerprint de lote | SHA-256 del archivo completo calculado en browser con Web Crypto API (10KB insuficiente: cambios en filas > 10KB son invisibles) |
| Templates DOCX | S3 en biomig-csv-inputs/templates/ — cambiar la plantilla no requiere redeploy de Lambda |
| Observabilidad | X-Ray habilitado en todas las Lambdas y Step Functions |
| Concurrencia | ReservedConcurrency = 3 para sf-generate-artifacts |
| Lambda Authorizer | Lee `cognito:groups` y `custom:pcm_id` del JWT directamente (sin llamada a Cognito API) |
| Informe Movimientos | 10 gráficas + 5 tablas + DOCX listo |
| Informe Novedades | 8 gráficas + 3 tablas + DOCX listo |
| Validaciones cruzadas | 25 validaciones · V01-V06, V14, V21, V24 bloqueantes |
| Detección de PCM | Dinámica post-upload · selector visual con PCMs detectados |
| Lotes de CSVs | Entidad global del sistema · compartida entre todos los PCMs |
| Reutilización de lotes | Por mes · fingerprint SHA-256 completo · sin re-subida |
| Ciclo de vida de lotes | PENDIENTE → ACTIVO → ARCHIVADO → ELIMINADO · REEMPLAZADO · CORRUPTO |
| Corrección de lote | Admin reemplaza · CSVs anteriores eliminados · reportes se conservan · historialVersiones en DynamoDB |
| IA para conclusiones | V2 opcional vía Bedrock |

---

## 16. Glosario técnico

| Término | Significado en este contexto |
|---|---|
| PCM | Puesto de Control Migratorio |
| Lote | Conjunto de CSVs del proveedor correspondientes a un mes · unidad de datos compartida entre todos los PCMs |
| Fingerprint | SHA-256 calculado sobre el archivo completo · identifica unívocamente cada CSV y el lote combinado |
| Gold Movement | El entregable final: DOCX listo con tablas pobladas, gráficas incrustadas y mes actualizado · el ingeniero solo revisa y exporta a PDF |
| SAM | AWS Serverless Application Model · framework para definir infraestructura AWS como código YAML |
| Container Image | Imagen Docker desplegada en Lambda vía ECR · permite dependencias de hasta 10 GB · usada para sf-generate-artifacts |
| ECR | Amazon Elastic Container Registry · almacena la imagen Docker del report-generator |
| Lambda Layer | Paquete de dependencias Python compartido entre múltiples Lambdas · en v3 solo para biomig_utils (deps ligeras) |
| Step Functions Express | Servicio de orquestación de AWS · permite encadenar Lambdas en estados con retry, catch y visibilidad por etapa |
| SQS | Amazon Simple Queue Service · cola que desacopla el endpoint HTTP del pipeline de procesamiento y da retry automático |
| DLQ | Dead-Letter Queue · cola que recibe mensajes que fallaron N veces en la cola principal · alarma inmediata si hay mensajes |
| Pre-signed URL | URL temporal de S3 con permisos embebidos · expira automáticamente (5 min para upload, 15 min para descarga) |
| GSI | Global Secondary Index · índice adicional en DynamoDB para queries eficientes sin scan de tabla |
| TTL | Time To Live · campo Unix timestamp en DynamoDB que elimina el registro automáticamente al vencerse |
| SSE-S3 | Server-Side Encryption con clave gestionada por S3 · AES-256 · sin costo adicional |
| X-Ray | AWS X-Ray · servicio de tracing distribuido · correlaciona llamadas entre Lambdas y Step Functions en un mapa de servicio |
| Web Crypto API | API nativa del browser para operaciones criptográficas · usada para calcular SHA-256 del CSV sin subirlo |
| BytesIO | Objeto Python que simula un archivo en memoria · evita escritura a disco en Lambda (el filesystem de Lambda es limitado) |
| Placeholder | Marcador en el template DOCX (ej: `{{MES_NOMBRE}}`) que el sistema reemplaza con el valor real al ensamblar |
| ASL | Amazon States Language · formato JSON para definir la máquina de estados de Step Functions |

---

*Sistema de Reportes Biomig — Incomelec S.A.S*
*Documento de arquitectura v3.0 — Mayo 2026*
*Juan Sebastian Arrechea Zapata · Ingeniero de Soporte Técnico · PCM Alfonso Bonilla Aragón*
