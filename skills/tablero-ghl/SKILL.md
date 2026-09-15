---
name: tablero-ghl
description: Instala y ajusta el tablero de reportes (dashboard) de la cuenta de GHL — en español, con su marca y organizado por bloques: contactos → citas → ventas → higiene del CRM. Úsala SIEMPRE que se diga "arma mi tablero", "configura el dashboard", "quiero ver mis números", "no entiendo los reportes de la plataforma", "agrégame un widget de X", "cámbiale el color al tablero", o cuando en el arranque de su cuenta toque dejarle los reportes listos. NO es para reportes en PDF ni para páginas y funnels.
---

# Tablero de GHL

Deja la cuenta con un **tablero que se entiende de un vistazo**: en español, con tu marca y organizado por bloques que responden una pregunta cada uno.

**Por qué existe:** una cuenta recién creada estrena el dashboard genérico de la plataforma — en inglés, con widgets de e-commerce y de *email health* que no le dicen nada a un negocio de servicios. Cambiarlo a mano son ~40 clics y hay que saber qué filtro lleva cada widget.

## Qué instala
El perfil **estándar** (25 widgets), ordenado como se lee el negocio:

| Bloque | Responde |
|---|---|
| **Contactos nuevos** | ¿está entrando gente, y de dónde? |
| **Citas** | ¿esa gente se está sentando a hablar conmigo? |
| **Ventas** | embudo, negociaciones activas, cerradas, perdidas, tasa de conversión y eficiencia |
| **Higiene del CRM** | ¿hay contactos sin seguimiento, oportunidades estancadas, respuestas lentas? |

Las definiciones viven en [assets/plantilla-estandar.json](assets/plantilla-estandar.json). Sus `options` salen de configuraciones **probadas en producción**: para agregar un widget, **copia el bloque de uno parecido y cámbiale el filtro** en vez de inventar el `options` desde cero.

## Cómo se usa
```bash
# instalar el tablero
python3 .claude/skills/tablero-ghl/scripts/tablero.py plantilla \
  --loc <locationId> --nombre "Mi tablero"

# ver qué tableros ya tiene la cuenta
python3 .claude/skills/tablero-ghl/scripts/tablero.py listar --loc <locationId>

# reemplazar el contenido de uno existente (idempotente: borra y recrea)
... plantilla --loc <locationId> --dashboard <dashboardId>
```
Banderas útiles: `--dry-run` valida sin escribir nada · `--pipeline <id>` fija el embudo de los widgets de oportunidades (si no lo pasas, toma el primero de la cuenta) · `--base` si el panel no es el de `context/ghl.json` · `--default` lo deja como tablero de arranque.

## 🔒 Permiso antes de escribir
**Instalar un tablero es escribir en una cuenta viva.** Que el agente pida *construir* o *ajustar* la plantilla no autoriza a *aplicarla*: son dos permisos distintos. Verifica con `--dry-run`, y si hace falta instalarlo para que lo vea, pídelo en una frase y espera el sí. Lo mismo con `--default`: cambiar el tablero de arranque de la cuenta se pregunta.

El script verifica solo hasta cierto punto: cuenta los widgets que quedaron, confirma los permisos releyéndolos y te da el link. **Ábrelo y míralo** antes de decir que está listo — que el PUT responda 200 no garantiza que se vea bien.

## Antes de correrlo
- **Sesión vigente** en la cuenta, en el perfil `.auth/pw-profile`. Si expiró:
  `bash .claude/skills/navegador-ghl/scripts/login.sh "<url de la cuenta>" tablero`
- **El perfil admite un solo navegador a la vez.** Si otra sesión lo tiene tomado (revisa `npx playwright-cli list`), reutilízala con `--session <nombre>` en vez de cerrarla.
- Si la cuenta tiene **varios pipelines**, decide con el agente cuál va en el embudo antes de correr: el default (el primero) rara vez es el que quiere.

## Modificar el tablero
Editar un widget in-place **no existe**: el PUT solo entiende crear y borrar. Para cambiar un título, un color o un filtro se borra ese widget y se recrea. El script ya trabaja así (reemplaza el tablero entero), por eso reaplicar la plantilla es seguro y repetible.

Si te piden un widget a la medida ("quiero ver solo los leads que vienen de Facebook"), agrégalo a `plantilla-estandar.json` si sirve para cualquier agente, o arma un JSON aparte si es específico suyo. Los `identifier` disponibles se listan en `GET /reporting/dashboards/widgets-definitions?locationId=` (catálogo grande, ~500 KB — **léelo filtrando, no completo**).

## ⚠️ Ojo con esto
- El endpoint de **permisos** solo valida `isPrivate` y **acepta cualquier otro campo respondiendo `success:true` sin aplicarlo**. El campo bueno es `permissionAccess`. Nunca lo sondees a ciegas: un body inválido puede dejar el tablero privado y sin permisos, **también respondiendo éxito**. El script escribe y relee para confirmar.
- **Ponerlo como predeterminado da 403** si los roles todavía no tienen permisos. Por eso el script asigna permisos antes.
- Los widgets de sistema (Funnel, Conversion rate, Sales efficiency) muestran su título **traducido según el idioma del usuario que mira**, no el guardado. Con la interfaz en inglés se ven en inglés. No es un error del tablero — si el agente lo reporta como bug, es su preferencia de idioma.
- Los widgets de **Meta Ads y Google Ads** salen vacíos hasta que esas integraciones estén conectadas en la cuenta; por eso la plantilla estándar no los incluye. Agrégalos cuando el agente ya tenga la conexión.

Endpoints y formatos completos en [references/endpoints.md](references/endpoints.md).
