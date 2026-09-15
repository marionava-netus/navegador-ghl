---
name: quizzes-ghl
description: Crea quizzes de diagnóstico (Sites → Quizzes) directamente en una cuenta de GHL por API — título, 3 categorías, 12 preguntas con puntaje 3/2/1, niveles de resultado, mensajes y miniresultados por categoría, y CTA por nivel — con los colores de la marca de la cuenta. Úsala SIEMPRE que se diga "hazme un quiz de X", "monta el quiz en GHL", "un diagnóstico interactivo para captar prospectos", "quiero un lead magnet que segmente", o cuando haga falta un lead magnet interactivo que clasifique al prospecto por nivel. NO es para formularios simples, encuestas ni landings.
allowed-tools: Bash(python3:*) Bash(curl:*) Bash(npx playwright-cli:*)
---

# Quizzes de diagnóstico en GHL

Convierte un tema en un **quiz interactivo publicado**: 12 preguntas, puntaje por categoría, resultado personalizado por nivel y CTA a la agenda. Es el lead magnet que convierte curiosidad en cita — y de paso **segmenta al prospecto antes de que hables con él**.

## Por qué así (y no a mano)
Montar un quiz en la UI son ~80 clics: 12 preguntas × 3 opciones × asignar categoría y puntaje, más 3 niveles × 3 mensajes globales × 3 miniresultados × 3 CTAs = **~40 bloques de contenido**. A mano se cometen errores silenciosos que solo se ven al contestarlo. Por API es un archivo JSON reejecutable.

## El modelo de datos (imprescindible)
Un quiz **es un `form` con `productType: "quiz"`**. Todo vive en `formData`:

| Clave | Qué es |
|---|---|
| `form` | Ajustes de estilo: `fieldStyle`, `footerStyle`, `mobileFooterStyle`, `company` |
| `fieldCSS` / `mobileFieldCSS` | CSS generado del tema (tipografía, inputs, labels) |
| `slides[]` | 14 slides: **0** intro · **1–12** una pregunta cada uno · **13** captura de contacto |
| `category[]` | 4 entradas: `overAllScore` (siempre primera) + tus 3 categorías |
| `resultTemplate` | `tiers[]` + `sections[]` (header, puntaje global, miniresultados, CTA, footer) |

- **Pregunta** = elemento `radio` con `picklistOptions[]` y `scoreByCategory` indexado por opción → `{category, categoryId, elementIndex, index, score, slideIndex}`.
- **Contenido por nivel** se indexa por **id del tier** (no por su etiqueta) dentro de `{categoryId: {tierId: html}}`.
- Cada pregunta se respalda en un **custom field RADIO del contacto** — así la respuesta queda en el CRM y es segmentable.

## Endpoints
```
GET  services.leadconnectorhq.com/forms/?locationId=…&type=quiz&productType=quiz   # listar
GET  services.leadconnectorhq.com/forms/{id}                                       # leer
POST services.leadconnectorhq.com/forms/                                           # crear  {locationId, name, productType:"quiz"}
POST services.leadconnectorhq.com/forms/{id}                                       # GUARDAR {name, formData}   ← NO existe PUT ni PATCH
POST services.leadconnectorhq.com/locations/{loc}/customFields                     # campo  {name, dataType:"RADIO", model:"contact", options:[…]}
```
- **Builder (UI):** `<tu-panel>/v2/location/{loc}/quiz-builder-v2/{formId}` · **Listado:** `…/quiz-builder/main`
- **Quiz público:** `https://api.leadconnectorhq.com/widget/quiz/{formId}`

## Flujo de trabajo
1. **Pregunta el tema y el objetivo** si no vienen dados: de qué servicio es el diagnóstico y a quién le habla. Sin eso no arranques.
2. **Confirma la marca**: se lee de `context/ghl.json` (colores, tipografía, logo, dominio). Si falta un dato, el builder **se detiene diciendo cuál** — no inventa defaults.
3. **Escribe el spec** en `quizzes/<slug>/quiz.json`. Molde recomendado: 3 categorías × 4 preguntas, opciones ✅3 / 🤔2 / ❌1, niveles 12–19 Alto / 20–28 Medio / 29–36 Bajo.
4. **Dry-run** — valida sin tocar la cuenta:
   ```bash
   python3 .claude/skills/quizzes-ghl/scripts/quiz_builder.py \
       quizzes/<slug>/quiz.json --location <locationId> --dry-run --out /tmp/dry.json
   ```
5. **Crea el quiz** (crea los 12 custom fields y el form vacío):
   ```bash
   python3 …/quiz_builder.py quizzes/<slug>/quiz.json --location <locationId>
   ```
   Si el guardado falla con `error in getting user`, es lo esperado: sigue al paso 6.
6. **Guarda el contenido con la sesión UI** (ver trampa #3):
   ```bash
   python3 …/quiz_builder.py quizzes/<slug>/quiz.json --location <loc> --emit-only --out /tmp/payload.json
   curl -s -X POST "https://services.leadconnectorhq.com/forms/{formId}" \
        -H "token-id: $(cat /tmp/token-id.txt)" -H "source: WEB_USER" -H "channel: APP" \
        -H "Version: 2021-07-28" -H "Content-Type: application/json" \
        --data-binary "@/tmp/payload.json"
   ```
7. **Prueba el quiz en vivo, siempre.** Abre `widget/quiz/{formId}` y contesta al menos **dos** corridas: el peor caso (todo ❌) y un caso **justo en la frontera** entre dos niveles. Verifica que el % caiga en el nivel correcto y que cambien mensaje global, miniresultados y CTA.
8. **Checkpoint con capturas** antes de difundirlo.

### Capturar el `token-id` de la sesión
Con la skill [navegador-ghl](../navegador-ghl/SKILL.md):
```bash
npx playwright-cli -s=ghl open "<tu-panel>/v2/location/<loc>/quiz-builder/main" \
    --headed --persistent --profile=.auth/pw-ghl --browser=chrome
# navega al quiz para disparar el GET /forms/{id}, luego:
npx playwright-cli -s=ghl requests            # localiza el request a services…/forms/
npx playwright-cli -s=ghl --raw request <n> | grep -i "token-id:" | sed -E 's/.*token-id:[[:space:]]*//' > /tmp/token-id.txt
```
Dura **~1 hora**. Si expira, vuelve a capturarlo.

## ⚠️ Trampas conocidas (no repetir)
1. **[LA GRANDE] Los niveles se guardan en PORCENTAJE, no en puntos.** Tú piensas en rangos de puntos (12–19 / 20–28 / 29–36); GHL solo entiende `fromPercent`/`toPercent`. El builder convierte y **pone el corte en el punto medio entre dos puntajes contiguos** (ej. 12–19 pts → 0–54 %), para que no dependa de si GHL trunca o redondea. Si copias cortes "exactos" (52/53), un puntaje de 19 (=52.78 %) puede caer en el nivel equivocado.
2. **Cada pregunta necesita un custom field RADIO que exista.** No basta con inventar un `fieldKey` en el slide. El builder los crea y **reusa por nombre** — si no, cada corrida duplicaría 12 campos en el CRM.
3. **El PIT puede leer y crear, pero NO puede guardar el `formData`.** `POST /forms/{id}` con PIT devuelve `400 "User API: error in getting user - undefined"`: el endpoint necesita el usuario que firma la versión. Hay que usar el **`token-id` de la sesión UI** (headers `token-id` + `source: WEB_USER` + `channel: APP`). Es el patrón de las dos APIs, explicado en `navegador-ghl`.
4. **Un quiz recién creado tarda en ser visible para el endpoint de guardado** (read-after-write): el primer `POST /forms/{id}` puede dar 404. El builder reintenta 5 veces cada 3 s.
5. **El slot del logo del header es CUADRADO (50×50).** Un logo horizontal sale aplastado e ilegible. Usa la versión cuadrada de tu marca.
6. **El `mobileFooterStyle` viene en el azul default de GHL (`#006EEE`)** y es un bloque aparte del footer de escritorio. Si no lo brandeas, el quiz se ve sin marca **en celular**, que es donde entra la mayoría. El builder lo brandea; no lo pierdas al editar a mano.
7. **La barra de progreso y el botón "siguiente" también traen azules de GHL** (`#84ADFF`). Ya están tokenizados en `assets/base-quiz.json` — si extraes una plantilla nueva de otra cuenta, vuelve a tokenizarlos.
8. **Los niveles se quedan rojo/ámbar/verde**, no en colores de marca: el semáforo es la lectura instantánea del resultado y la marca lo rompería. La marca va en header, CTA, fondos y tipografía.
9. **Para verificar que el lead entró, lee el contacto por id — NUNCA la búsqueda.** `POST /contacts/search` sirve un **índice cacheado que va atrasado** (horas): reporta "no existe" un contacto recién creado, y sigue listando uno recién borrado. El `POST /forms/submit` ya devuelve `{"status":true,"contactId":"…"}` — úsalo, o `GET /contacts/{id}`.
10. **`GET /forms/submissions` no cubre `productType=quiz`.** Devuelve 0 aunque el quiz sí esté capturando (los forms normales sí los reporta). Para auditar un quiz, **cuenta contactos por `source`** — el `source` del contacto queda con el nombre del quiz.
11. **Ojo con las plantillas clonadas de otro giro.** Un quiz montado clonando una plantilla ajena suele conservar los `fieldKey` originales (`contact.what_type_of_charges_are_you_facing`…): funciona de cara al prospecto, pero **los datos en el CRM quedan ilegibles y no se pueden segmentar**. Si heredas uno así, remóntalo con este builder.

## El CTA apunta al calendario DEL TEMA
El botón lleva al calendario que corresponde al tema del quiz. Se declara en el spec:

```json
{ "tema": { "nombre": "seo", "palabras": ["seo", "posicionamiento", "google"] },
  "results": { "cta": { "Nivel Alto": { "buttonLink": "auto", "buttonText": "…" } } } }
```
(Forma corta: `"tema": "seo"`.)

El builder lee `GET /calendars/?locationId=…` y decide:
1. **Un solo calendario activo** → ese.
2. **Exactamente uno** cuyo nombre o descripción casa con el tema → ese.
3. **Cualquier otro caso** → **se detiene y lista los calendarios**. Nunca adivina: un CTA a la agenda equivocada quema el lead. Ahí pones el `buttonLink` a mano o renombras el calendario.

La URL que arma es `https://api.leadconnectorhq.com/widget/booking/{calendarId}` (funciona sin dominio propio) + UTMs `utm_source=quiz&utm_campaign=<tema>&utm_content=cta&utm_term=<nivel>`, para medir qué nivel agenda más.

Un `buttonLink` explícito siempre gana.

⚠️ **La coincidencia es por palabra completa, no substring** — `auto` no debe casar con *"Consultoría **Auto**matiza tu Negocio"* (falso positivo real); sí casa con *"Cotización de Autos"* porque se toleran plurales. Si tocas el matcher, respeta esa regla.

## Escribir el contenido (la parte que vende)
- **Tono:** casual y directo pero **empático**, con la jerga real de tu sector. El prospecto debe sentir que quien pregunta sabe.
- **Título** corto y centrado en el beneficio o el miedo concreto, no en el producto.
- **Las opciones educan:** ✅ / 🤔 / ❌ con texto que ya enseña algo, no un "sí/no" seco.
- **Los miniresultados por categoría son el oro**: le dicen al prospecto *dónde* está mal, y a ti te dan el guion de la llamada.
- **CTA distinto por nivel**: urgencia en Alto, diagnóstico gratuito en Medio, optimización en Bajo.
- **Cero cifras o condiciones inventadas** en preguntas y resultados: solo con fuente. Un quiz orienta y lleva a una cita, **no es una recomendación personalizada**.
- Ortografía impecable — es material público de cara al cliente.

## Assets
- `scripts/quiz_builder.py` — el motor (custom fields idempotentes, conversión de niveles, autoría del `formData`, guardado).
- `assets/base-quiz.json` — plantilla de estilos con tokens `{{PRIMARY}}`, `{{DARK}}`, `{{FOOTER_BG}}`, `{{ON_DARK}}`, `{{FONT}}`, `{{LOGO_URL}}`, `{{BRAND_NAME}}`, `{{DOMAIN}}`, `{{BACKGROUND_URL}}`.

## Relación
- **navegador-ghl** — la infraestructura para capturar el `token-id` de la sesión.
- **landings-ghl** — para embeber el quiz en una página del funnel.
