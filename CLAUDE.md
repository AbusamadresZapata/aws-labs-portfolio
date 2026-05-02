# CLAUDE.md

## Quién soy

Juan Sebastian Arrechea, Ingeniero de Automatización, AWS Solutions Architect Associate (SAA-C03) en progreso. Experiencia sólida en Python y AWS; aprendiendo arquitectura de soluciones en la nube para entornos industriales y de IoT. Portfolio técnico y bitácora de aprendizaje AWS.

## Proyecto principal

**Invoice Digitizer** — app serverless en producción. Detalles de arquitectura, reglas por capa y comandos en `.claude/rules/`.

---

## 1. Pensar antes de codificar

Antes de implementar cualquier cosa:
- Exponer supuestos explícitamente. Si hay incertidumbre, preguntar.
- Si existen múltiples interpretaciones válidas, presentarlas — no elegir en silencio.
- Si hay un enfoque más simple, decirlo. Justificar cuando se rechaza una idea.
- Si algo no está claro, nombrar qué es confuso y preguntar antes de continuar.

## 2. Cambios quirúrgicos

- Leer el archivo completo antes de modificarlo.
- Tocar únicamente el código necesario para la tarea pedida.
- No refactorizar, no mejorar formato, no limpiar código adyacente que no se pidió.
- No agregar comentarios, docstrings ni type hints en código que no modifiqué.
- Si noto dead code no relacionado, lo menciono — no lo borro.

## 3. Simplicidad

- Implementar solo lo que se pidió. Cero features especulativos.
- Sin abstracciones para uso único. Sin "flexibilidad" no solicitada.
- Sin manejo de errores para escenarios imposibles.
- Si el resultado tiene 200 líneas y podría ser 50, reescribir.

## 4. Ejecución orientada a objetivos

Para tareas de múltiples pasos, presentar un plan breve antes de ejecutar:
```
1. [Paso] → verificar: [criterio]
2. [Paso] → verificar: [criterio]
```
No reportar tarea como completa hasta que el criterio de verificación se cumpla.

---

## Git

- Prefijo obligatorio: `feat:`, `fix:`, `docs:`, `refactor:`
- Push a `main` activa el build de Amplify automáticamente.

## Seguridad

- Sin secrets, ARNs de cuenta reales ni IDs de recursos en el código.
- Variables sensibles van en env vars de Lambda o Amplify Console.
- `aws-config.js` admite User Pool ID y App Client ID (semi-públicos), no API keys.
