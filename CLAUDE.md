# CLAUDE.md — AWS Labs Portfolio

Guía de contexto para Claude Code. Este archivo se carga automáticamente en cada sesión.

---

## Quién soy

Juan Sebastian Arrechea, Ingeniero de Automatización en ruta a la certificación
AWS Solutions Architect Associate (SAA-C03). Tengo experiencia en Python y AWS pero
estoy aprendiendo React y el ecosistema frontend de Amplify.

---

## Proyecto principal activo: Invoice Digitizer

Aplicación serverless en producción. Frontend en AWS Amplify, backend en Lambda + DynamoDB.

### Stack
- **Frontend:** React 18, AWS Amplify v6, Cognito (auth)
- **Backend:** Python 3.12, AWS Lambda (x3 funciones), API Gateway REST
- **Storage:** S3 (bucket RAW + bucket PROCESSED), DynamoDB (`invoices`)
- **IA:** AWS Textract (FORMS + TABLES)
- **Notificaciones:** SNS → email
- **CI/CD:** GitHub Actions (workflows en `invoice-digitizer/.github/workflows/` — pendiente mover a raíz)
- **Hosting:** AWS Amplify (build definido en `amplify.yml`)

### Archivos clave
| Archivo | Rol |
|---------|-----|
| `amplify.yml` | Build del frontend para Amplify |
| `invoice-digitizer/backend/lambda/invoice_ocr_v2.py` | Pipeline OCR principal: S3 → Textract → DynamoDB → SNS |
| `invoice-digitizer/backend/lambda/get_upload_url.py` | Genera presigned URL para subida directa a S3 |
| `invoice-digitizer/backend/lambda/get_invoices.py` | Consulta historial de facturas por usuario |
| `invoice-digitizer/frontend/src/pages/Dashboard.jsx` | UI principal: upload, polling y listado |
| `invoice-digitizer/frontend/src/aws-config.js` | Config Cognito + API endpoint (NO hardcodear nuevos secrets aquí) |

### Schema DynamoDB — tabla `invoices`
- PK: `user_id` (String) — UUID de Cognito
- SK: `invoice_id` (String) — UUID generado en upload
- Campos: `total`, `subtotal`, `discount`, `invoice_number`, `date`, `vendor`,
  `nit`, `client_name`, `address`, `items_count`, `items_json`, `confidence`, `s3_key`, `raw_text`

### Flujo de datos
```
React → POST /upload-url → Lambda → presigned URL
React → PUT imagen → S3 RAW
S3 event → Lambda OCR → Textract → DynamoDB + SNS
React polling → GET /invoices → Lambda → DynamoDB query
```

---

## Reglas de trabajo

### Siempre antes de editar
- Leer el archivo completo antes de modificarlo
- No cambiar código que no sea necesario para la tarea pedida
- No agregar comentarios, docstrings ni type hints en código que no modifiqué

### Python (Lambdas)
- Runtime: Python 3.12
- Los clientes boto3 se inicializan a nivel de módulo (fuera del handler) para reutilizar entre invocaciones
- La región siempre es `us-east-1` — está hardcodeada en los clientes (decisión consciente)
- Valores de DynamoDB que son monetarios van como `Decimal`, no `float`
- Los errores de Lambda NO deben lanzar excepciones al caller de S3 — siempre retornar `statusCode`
- `items_json` se guarda como string JSON (DynamoDB no admite listas con tipos mixtos)

### React / Frontend
- No usar Amplify REST client — usar `fetch` nativo con token JWT en header `Authorization`
- El token se obtiene con `fetchAuthSession()` de `aws-amplify/auth`
- No hay TypeScript, solo JSX
- Estilos inline (no hay CSS externo ni Tailwind)

### Git
- Commits en español o inglés con prefijo: `feat:`, `fix:`, `docs:`, `refactor:`
- Nunca commitear credenciales ni `.env`
- El push a `main` triggerea el build de Amplify automáticamente

### Seguridad
- Nunca escribir secrets, ARNs de cuentas reales, ni IDs de recursos en el código
- Las variables sensibles van en env vars de Lambda o en Amplify Console
- `aws-config.js` puede tener User Pool ID y App Client ID (son semi-públicos) pero NO API keys

---

## Tareas pendientes del proyecto

- [ ] Mover `.github/workflows/` a la raíz del repo para activar CI
- [ ] Agregar secrets `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` en GitHub para CI/CD
- [ ] Escribir tests en `backend/tests/test_lambdas.py` con `moto`
- [ ] Mover credenciales de `aws-config.js` a variables `REACT_APP_*` de Amplify
- [ ] Agregar campo `items_json` al componente `InvoiceCard.jsx` para mostrar productos en la app

---

## Comandos frecuentes

### Frontend local
```bash
npm install --prefix invoice-digitizer/frontend
npm start --prefix invoice-digitizer/frontend
```

### Deploy Lambda manual (desde CloudShell o terminal con AWS CLI)
```bash
cd invoice-digitizer/backend/lambda
zip invoice_ocr_v2.zip invoice_ocr_v2.py
aws lambda update-function-code --function-name invoice-ocr-processor --zip-file fileb://invoice_ocr_v2.zip
```

### Ver logs del Lambda OCR
```bash
aws logs tail /aws/lambda/invoice-ocr-v2 --follow
```

---

## Contexto de aprendizaje

Este repositorio es un portfolio técnico y bitácora de aprendizaje AWS.
Cada lab está documentado con README, decisiones de diseño y evidencias.
Priorizar claridad y buenas prácticas sobre optimización prematura.
