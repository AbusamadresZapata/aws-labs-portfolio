# ADR-001: DynamoDB vs Athena para almacenamiento de recibos digitalizados

**Status:** ✅ Accepted  
**Date:** 2026-05-29  
**Context:** Invoice Digitizer — Aplicación serverless que procesa y almacena recibos digitalizados

---

## Problema

Invoice Digitizer necesita almacenar registros procesados de recibos (factura, número, fecha, ítems, total) y recuperarlos rápidamente en el dashboard. ¿Cuál es la mejor estrategia de almacenamiento entre DynamoDB y Athena?

---

## Contexto

### Patrón de acceso en tiempo real
- **Lectura:** Usuario abre dashboard → GET `/invoices` → obtiene sus recibos en <500ms
- **Escritura:** Lambda procesa imagen → PutItem en tabla de recibos (async vía S3 Event)
- **Query:** Siempre por `user_id` (Partition Key), ocasionalmente por rango de fechas

### Volumen estimado
- ~100K usuarios activos
- ~10 recibos/usuario/mes = 1M recibos/mes
- Tamaño promedio: 2-5 KB/registro

### Restricciones técnicas
- Stack serverless (Lambda, Amplify, Cognito)
- Sin auto-scaling manual
- Latencia aceptable: < 1 segundo en dashboard

---

## Opciones consideradas

### **Opción A: DynamoDB (Elegida ✅)**

**Característica:**
- Tabla con `user_id` como Partition Key, `invoice_id` como Sort Key
- On-demand pricing (escalado automático)
- TTL opcional para auto-archivado

**Ventajas:**
- ✅ Latencia predecible (<100ms) → dashboard responsivo
- ✅ Serverless nativo (sin provisioning)
- ✅ Integración directa con Lambda (boto3)
- ✅ Query por user_id es O(1) (optimal)
- ✅ Costo predecible por transacción (on-demand)
- ✅ Cumplimiento de seguridad: encriptación en reposo + at-rest
- ✅ Punto de acceso único (fewer failure modes)

**Desventajas:**
- ❌ Queries ad-hoc complejas (ej: "total gastado por mes") requieren scans costosos
- ❌ No soporta JOINs entre tablas (sin Athena)
- ❌ Facturación por lectura/escritura (puede ser caro si muchas queries fallidas)

**Costo estimado (on-demand):**
- 1M PutItem/mes ≈ $0.50
- 100K GetItem/mes ≈ $0.05
- **Total ≈ $0.55/mes** (negligible)

---

### **Opción B: Athena (Descartada)**

**Característica:**
- Queries SQL contra parquet/JSON en S3
- Serverless, pay-per-query
- Ideal para data lakes

**Ventajas:**
- ✅ SQL estándar (análisis ad-hoc)
- ✅ Escalable a petabytes
- ✅ Costo mínimo para datos archivados
- ✅ Integración con QuickSight para reportes

**Desventajas:**
- ❌ **Latencia alta:** 30-60 segundos por query (inaceptable en dashboard)
- ❌ Costo por query: $0.025 / TB scaneado (query de 100MB = $0.0025)
- ❌ Overhead de catálogo (Glue) y formatos (parquet)
- ❌ No es real-time; requiere polling con exponential backoff
- ❌ Complejidad: necesita S3 → Glue → Athena pipeline

**Escenario donde Athena es mejor:**
- Reportes históricos (ej: "gastos del último año")
- Análisis de tendencias (no en tiempo real)
- Queries ocasionales (< 1/día)

---

### **Opción C: Híbrida (DynamoDB + Athena)**

**Concepto:**
- DynamoDB para acceso en tiempo real (dashboard)
- Athena para análisis histórico (reportes ejecutivos)

**Ventajas:**
- ✅ Lo mejor de ambos mundos

**Desventajas:**
- ❌ Complejidad operacional (dos sistemas)
- ❌ Sincronización de datos (eventual consistency)
- ❌ Costo duplicado (DynamoDB + S3 + Athena)

**Veredicto:** Posponer para futuro (Fase 2)

---

## Decisión

✅ **Usar DynamoDB como principal para Invoice Digitizer**.

### Justificación

1. **UX primero:** Dashboard debe ser responsivo (<500ms) → DynamoDB es el único que lo garantiza
2. **Serverless puro:** Encaja perfectamente con Lambda + Cognito + Amplify
3. **Costo negligible:** $0.55/mes en on-demand pricing (no hay commitment)
4. **Operacional:** Un servicio, una tabla, cero provisioning
5. **Escalabilidad:** On-demand maneja picos sin intervención

---

## Consecuencias

### Positivas ✅
- Dashboard rápido y consistente
- Operaciones simples (no SQL a aprender)
- Billing transparente y predecible
- Integración nativa con Cognito (auth via JWT sub claim)

### Negativas ⚠️
- Análisis ad-hoc complejos requieren workarounds
- Reportes en tiempo real no son viables
- Escalado a > 10M registros requiere re-pensar (sharding, GSI)

### Mitigación
- Usar `ScanIndexForward=False` + `Limit` para pagination eficiente
- Implementar GSI por fecha si se necesita filtrado temporal frecuente
- Exportar a Athena cuando se requiera análisis histórico

---

## Alternativas futuras

| Evento | Solución |
|--------|----------|
| Análisis de tendencias necesario | Agregar Athena + ETL a S3 (Fase 2) |
| > 100M recibos | Considerar DynamoDB Global Tables (multi-región) |
| Queries ad-hoc frecuentes | Migrar a Aurora PostgreSQL (pero pierde serverless) |

---

## Referencias

- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
- [Athena Pricing](https://aws.amazon.com/athena/pricing/)
- [DynamoDB vs SQL databases (AWS whitepaper)](https://d1.awsstatic.com/whitepapers/dynamodb-design-patterns.pdf)
