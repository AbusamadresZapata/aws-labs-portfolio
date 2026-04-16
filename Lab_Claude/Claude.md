# Lab Claude — Notas de uso de Claude Code desde el IDE

Apuntes personales sobre cómo trabajar con Claude Code eficientemente
desde Gravity (VS Code) durante el aprendizaje de AWS.

---

## Cómo funciona CLAUDE.md

Claude Code lee automáticamente el archivo `CLAUDE.md` en la raíz del repo
al iniciar cada sesión. Es como darle un briefing a Claude antes de empezar.

El archivo principal está en:
```
aws-labs-portfolio/CLAUDE.md
```

No necesitas repetirle el contexto del proyecto en cada conversación.

---

## Patrones de prompts que funcionan bien

### Para implementar algo nuevo
```
Implementa X en el archivo Y. El objetivo es Z.
No cambies nada fuera de lo necesario.
```

### Para revisar antes de tocar código
```
Analiza [archivo] y dime qué hace antes de modificarlo.
```

### Para deploy y producción
```
Hazlo tú. Estás autorizado. Asegúrate que sigue funcionando en producción.
```

### Para entender un error
```
[pega el error] — ¿qué está pasando y cómo lo resuelvo?
```

---

## Lo que Claude Code puede hacer solo (sin pedir permiso)

- Leer cualquier archivo del repo
- Editar código y crear archivos
- Hacer `git add`, `git commit`, `git push`
- Buscar patrones en el código con grep/glob

## Lo que Claude Code pregunta antes de hacer

- Acciones destructivas (borrar archivos, `git reset --hard`)
- Push a producción si no fue explícitamente autorizado
- Cambios en infraestructura que afecten datos de usuarios

---

## Flujo de trabajo recomendado

1. **Describe el problema**, no la solución — Claude infiere qué cambiar
2. **Muestra evidencia** cuando hay un bug (screenshot, log, mensaje de error)
3. **Autoriza explícitamente** cuando quieres que haga commit + push
4. **Revisa el diff** antes de cerrar la sesión — Claude muestra qué cambió

---

## Comandos útiles en el IDE

| Acción | Cómo |
|--------|------|
| Abrir Claude Code | Terminal → `claude` |
| Ver historial de sesión | Claude Code guarda contexto automáticamente |
| Forzar que lea un archivo | "lee el archivo X antes de responder" |
| Pedir resumen del repo | "analiza el proyecto y dame sugerencias" |

---

## Lecciones aprendidas usando Claude Code en este proyecto

- Decirle **el objetivo final** (ej: "que quede funcional en producción")
  es más efectivo que describir los pasos
- Cuando hay un **screenshot de error**, pegarlo directamente — lo interpreta mejor que texto
- Claude recuerda el contexto dentro de la sesión pero no entre sesiones —
  por eso el `CLAUDE.md` es tan importante
- Para tareas de **múltiples archivos**, es mejor una sola instrucción clara
  que varias instrucciones separadas

---

## Recursos

- Documentación Claude Code: https://docs.anthropic.com/claude-code
- Issues y feedback: https://github.com/anthropics/claude-code/issues
