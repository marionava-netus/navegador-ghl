---
name: emails-ghl
description: Crea y edita secuencias de email dentro de GHL como plantillas reales del Design editor — con la firma del agente (foto, logo, links) y el footer legal con enlace de baja — y entrega el prompt listo para que GHL arme el workflow. Úsala SIEMPRE que el agente diga "hazme una secuencia de correos", "emails de seguimiento para los que descargaron X", "una campaña de emails de renovación", "arma el nurture de mis prospectos", "pon estos correos en GHL", "edítame la plantilla de correo", o cuando tras captar leads haya que darles seguimiento por correo. NO es para mandar un correo suelto a una persona (eso es su cliente de correo).
---

# Secuencias de email en GHL

Convierte una secuencia de correos aprobada por el agente en **plantillas reales del Design editor** de GHL — editables después a mano, con su firma (foto + logo) y el footer legal con `{{email.unsubscribe_link}}`.

## Por qué por API y no a mano
Armar 7 correos en el editor visual son ~3 horas de clics y un formato que se desalinea entre uno y otro. Por API salen los 7 idénticos en un minuto, y el agente solo revisa. El script además **verifica el preview de cada uno** (firma presente, enlace de baja presente, botones renderizados) antes de decir que quedó.

## Antes de la primera corrida (una sola vez)
1. **`.env`** en la raíz del proyecto:
   ```
   GHL_PIT=<Private Integration Token de la sub-cuenta>
   GHL_LOCATION_ID=<id de la sub-cuenta>
   ```
   Cómo obtenerlos: [../../CONFIGURACION-GHL.md](../../CONFIGURACION-GHL.md).
2. **`context/ghl.json`** — copia [assets/ghl.ejemplo.json](assets/ghl.ejemplo.json) y llénalo: nombre, tagline, colores de marca, URLs de foto y logo, sitio, razón social y **dirección postal**.
3. **Sube la foto y el logo** al Media Storage de la sub-cuenta (Marketing → Media) y pega esas URLs en la config. No uses una URL de otra cuenta: el CDN sirve por ubicación y la imagen saldría rota.

> El script **se detiene con un mensaje claro si falta cualquiera de esos datos**. Nunca inventa un valor por defecto — un correo masivo firmado con datos equivocados es peor que uno que no salió.

## ⚖️ La dirección postal no es opcional
Todo correo masivo debe llevar **dirección física del remitente y una forma de darse de baja**. Es requisito de CAN-SPAM (EE. UU.) y buena práctica exigible en México; sin eso, los proveedores marcan el dominio como spam y se quema la reputación de envío del agente. Por eso `razon_social` y `direccion` son campos obligatorios de la config y el footer los imprime siempre.

## Flujo de trabajo
1. **Diseñar la secuencia con el agente primero**: cuántos correos, con qué días entre uno y otro, qué CTA lleva cada uno y qué dispara la entrada (un formulario, una etiqueta, una fecha de renovación). Preséntala en chat y **espera su OK antes de redactar**.
2. **Redactar el copy** siguiendo las reglas de abajo. Armar el spec JSON (formato en el docstring de `scripts/crear_secuencia.py`) y guardarlo **fuera del repo del asistente** (carpeta temporal), no versionado.
3. **Correr el script**:
   ```bash
   python3 .claude/skills/emails-ghl/scripts/crear_secuencia.py <spec.json>
   python3 .claude/skills/emails-ghl/scripts/crear_secuencia.py <spec.json> --update   # editar existentes
   python3 .claude/skills/emails-ghl/scripts/crear_secuencia.py --smoke-test           # ¿siguen válidos el PIT y la base?
   ```
4. **Documentar** la secuencia para el agente: tabla con id de plantilla, subject, día y CTA de cada correo.
5. **Generar el prompt del workflow** con [references/prompt-workflow.md](references/prompt-workflow.md) y entregárselo para que lo pegue en *Automation → Workflows → Build using AI*. Así no arma el flujo a mano.
6. **Recordarle los 2 pasos manuales** que quedan: revisar las plantillas a ojo, y verificar que cada paso del workflow tenga la plantilla y el subject correctos (el builder con IA a veces no los vincula).

## Reglas de copy
- Helpers del script: `h2()` (saludo), `p()` (párrafo), `SEP` (separador), `link()` (link de acento para CTA suave).
- **Un solo CTA por correo.** Suave = `link()` en el texto · fuerte = segment `button` (botón nativo con el color de marca).
- **No cierres con el nombre y el despacho en el cuerpo** — la sección de firma (foto + nombre + tagline) ya lo hace. Cierres cortos: "Saludos," / "Quedo al pendiente,".
- Tuteo o usted según cómo le hable el negocio a su base; honesto y con dominio real del tema. **Nunca inventes cifras, testimonios ni nombres de clientes**: son correos que van a personas reales y quien firma responde por ellos.
- Nada de promesas de resultados, precios ni condiciones que no estén por escrito en la oferta. Si el correo toca producto, que remita a la página de la oferta o a una llamada.
- **UTM en cada link propio**: `?utm_campaign=<secuencia>&utm_content=<utm-del-email>` — así se ve qué correo convierte.
- Merge fields útiles: `{{contact.first_name}}`, `{{contact.company_name}}`, y campos personalizados (`{{contact.fecha_renovacion}}`). Créalos antes en Settings → Custom Fields si no existen.

## ⚠️ Trampas conocidas
1. **Los botones son un elemento `mj-button`, NUNCA un `<a>` estilizado dentro de un texto** — el CSS del builder des-estiliza los links de texto (`p a {color:inherit; text-decoration:underline}`) y el botón sale como un link azul feo. El script ya lo hace bien con segments `button`.
2. **Los subjects NO se guardan por API** (probado con `subjectLine` y `subject`): viven en el paso de email del workflow. Inclúyelos siempre en la documentación que entregas con la secuencia, o se pierden.
3. El enlace de baja correcto es **`{{email.unsubscribe_link}}`** — ya viene en el footer de la plantilla base.
4. El CDN de GHL **rechaza MP3 por API** (`INVALID_FILE_TYPE`). Los audios se suben desde la UI de Media; las imágenes sí pasan por API.
5. Acentos y emojis: el spec va con `ensure_ascii=False`, sin problema.
6. **`--update` reescribe la plantilla completa**, no parchea. Si el agente editó algo a mano en el editor visual, se pierde: pregúntale antes de reescribir.

## Assets
- `assets/base-template-editorData.json` — el esqueleto MJML de la plantilla (preview, cuerpo, firma, footer legal). Los bloques de identidad vienen **vacíos a propósito**: los llena el script desde `context/ghl.json`.
- `assets/mj-button-reference.json` — atributos del botón nativo (radio, tipografía, `redirectAction: url`).
- `assets/ghl.ejemplo.json` — plantilla de configuración.
