# Prompt para el "Build using AI" de los workflows

Tras crear las plantillas, genera SIEMPRE este prompt (relleno con los datos de la secuencia) y entrégaselo al agente para que lo pegue en **Automation → Workflows → Build using AI**. Va **en inglés**: el builder con IA responde mejor así. Los nombres de plantillas y los subjects van textuales aunque estén en español.

**Límite conocido del builder:** crea la ESTRUCTURA (trigger, emails, esperas, if/else, etiquetas) pero **puede no vincular la plantilla exacta ni pegar el subject** en cada paso. Por eso el prompt los nombra textualmente — así cada paso queda rotulado y el agente solo confirma.

## Plantilla del prompt

```
Create a workflow named "<NOMBRE>".

TRIGGER: <trigger — ej. "Contact tag added: X" o "Form submitted: Y">.

STEPS:
1. Send Email immediately using template "<PLANTILLA E0>" with subject "<SUBJECT E0>".
2. Wait <N> days.
3. Send Email using template "<PLANTILLA E1>" with subject "<SUBJECT E1>".
   [... un par Send Email + Wait por cada correo ...]

SETTINGS:
- Email sending window: Monday to Friday, 9am to 12pm in the contact's timezone (except step 1, send immediately at any time).
- If the contact REPLIES to any email: remove them from this workflow.
- If the contact BOOKS AN APPOINTMENT (calendar: <CALENDARIO>): remove them from this workflow.
- When the workflow ends without a booking, add the tag "<TAG-FINAL>".

EXTRA BRANCH (if supported): if a contact clicks the booking link but does not book within 24 hours, send a short reminder email reusing the last template.
```

## Ejemplo relleno — seguimiento de una cotización enviada

```
Create a workflow named "Cotización — seguimiento".

TRIGGER: Contact tag added: "cotizacion-enviada".

STEPS:
1. Send Email immediately using template "Cotización — E0 Te la envío (día 0)" with subject "tu cotización, ya lista".
2. Wait 2 days.
3. Send Email using template "Cotización — E1 Qué mirar antes del precio (día 2)" with subject "antes de comparar precio, mira esto".
4. Wait 3 days.
5. Send Email using template "Cotización — E2 Un caso real (día 5)" with subject "lo que pasa cuando se elige solo por precio".
6. Wait 3 days.
7. Send Email using template "Cotización — E3 Última llamada (día 8)" with subject "¿la dejamos para después?".

SETTINGS:
- Email sending window: Monday to Friday, 9am to 12pm in the contact's timezone (except step 1, send immediately at any time).
- If the contact REPLIES to any email: remove them from this workflow.
- If the contact BOOKS AN APPOINTMENT (calendar: "Asesoría — 20 min"): remove them from this workflow.
- When the workflow ends without a booking, add the tag "cotizacion-sin-respuesta".
```

## Checklist después de que la IA lo arme
1. Cada paso de email tiene **la plantilla correcta seleccionada** y **el subject pegado**.
2. El trigger apunta al tag o formulario real (no a uno inventado con nombre parecido).
3. Las salidas por respuesta y por cita quedaron como **condiciones reales**, no como texto suelto.
4. Ventana de envío activa y en la zona horaria del contacto.
5. Dejarlo en Draft → probar con un contacto de prueba propio → recién entonces Publish.
