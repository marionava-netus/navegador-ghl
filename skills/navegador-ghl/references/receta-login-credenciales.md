# Receta — Login con credenciales del `.env` (validada en producción, jun-2026)

Iniciar sesión en un portal **headed (visible)** usando credenciales guardadas en `.env`, **sin exponer la contraseña** en ningún output, dejando la sesión persistida para reusarla.

> Validada contra el portal de intermediarios de una aseguradora. El patrón es genérico: sirve para el panel de GHL, portales de proveedores, correo o cualquier app con formulario de login. En los ejemplos, `PORTAL_URL` / `PORTAL_USER` / `PORTAL_PASSWORD` son las claves que tú defines en tu `.env`.

## Reglas de seguridad
- **Nunca imprimas la contraseña.** Usa `--raw` en los `fill` (omite el bloque "Ran Playwright code" que llevaría el valor) y pásala como variable de shell `"$VAR"` (así el comando muestra la variable, no el valor).
- Descubre los nombres de las claves sin volcar valores: `grep -iE '^[^=]*portal[^=]*=' .env | sed -E 's/=.*/=<oculto>/'`.
- El correo/usuario sí aparece en el snapshot (es un campo de texto) — es aceptable; la contraseña va en campo `type=password` (enmascarado).

## Pasos (un patrón reusable)
1. **Abrir headed + perfil persistente** (la URL no es secreta):
   ```bash
   npx playwright-cli -s=portal open "<PORTAL_URL>" --headed --persistent --profile=.auth/pw-ghl
   ```
   *Tip de compatibilidad:* si el portal se rompe con el Chromium alpha de la CLI (ej. error de `pattern`/regex `/v`, o render raro), reabre con tu **Chrome estable**: añade `--browser=chrome`.
2. **Snapshot** y localizar los refs de correo, contraseña y botón:
   ```bash
   npx playwright-cli -s=portal snapshot > /tmp/snap.txt 2>&1
   grep -iE 'correo|contrase|iniciar sesión|textbox|button' /tmp/snap.txt
   ```
3. **Llenar credenciales (en UN solo comando, sin fugas):**
   ```bash
   set +x
   U=$(grep -E '^PORTAL_USER=' .env | cut -d= -f2-)
   P=$(grep -E '^PORTAL_PASSWORD=' .env | cut -d= -f2-)
   npx playwright-cli -s=portal --raw fill <ref-correo> "$U" >/dev/null 2>&1
   npx playwright-cli -s=portal --raw fill <ref-pass>  "$P" >/dev/null 2>&1
   ```
   (El botón "Iniciar sesión" suele estar `[disabled]` hasta que ambos campos están llenos.)
4. **Enviar y ESPERAR la navegación:** clic en el botón y **verifica el estado EN VIVO** (no desde un snapshot previo — la navegación tarda):
   ```bash
   npx playwright-cli -s=portal click <ref-boton>
   sleep 4
   npx playwright-cli -s=portal --raw eval "({url: location.href, ok: !location.href.includes('/sesion')})"
   ```
5. **Geolocalización — algunos portales la exigen para mostrar datos.** Hay paneles cuyo dashboard sale **vacío** si no se concede ubicación; con ella cargan todas las secciones. En automatización hay que hacer **DOS cosas juntas** (conceder el permiso **y** fijar una coordenada — sin coordenada no hay GPS real y la página queda en blanco). Hazlo **justo después de abrir** y antes de operar; recárgalo si ya estabas dentro:
   ```bash
   npx playwright-cli -s=portal run-code "async page => { const c = page.context(); await c.grantPermissions(['geolocation'], { origin: '<PORTAL_URL>' }); await c.setGeolocation({ latitude: 19.4326, longitude: -99.1332 }); }"
   npx playwright-cli -s=portal reload
   ```
   ⚠️ El permiso puede quedar recordado en el perfil persistente, pero **`setGeolocation` es un override de runtime que NO persiste** → **vuelve a fijar la coordenada en cada apertura** de la sesión. (Coordenadas de ejemplo: CDMX 19.4326, -99.1332; ajústalas a tu plaza.)

   **Regla general:** denegar geolocalización por defecto; **concederla solo cuando el sitio la requiera** para mostrar datos. Cuando se conceda, fijar siempre una coordenada.
6. **Persistir la sesión:** queda en el perfil `.auth/pw-ghl`; además respalda el storage state:
   ```bash
   npx playwright-cli -s=portal state-save .auth/<portal>.json
   ```
   Tareas futuras con `-s=portal … --persistent --profile=.auth/pw-ghl` reusan la sesión sin re-login.

## Lecciones aprendidas
- **Verifica el estado en vivo tras el submit**, no un snapshot anterior — es fácil concluir "no entró" leyendo un snapshot viejo cuando el login sí había pasado.
- El **Chromium alpha** de la CLI puede marcar errores de `pattern`/regex y CORS/500 **cosméticos** que NO impiden el login. Si sí estorban, usa `--browser=chrome`.
- Muchos portales **no** tienen reto de reCAPTCHA aunque muestren el badge; intenta el login directo antes de asumir bloqueo.
- Mantén el navegador **headed** para observar y para resolver cualquier captcha/2FA real si apareciera (human-in-the-loop).
- **Nunca guardes las credenciales en el repo.** Van en `.env`, que está en el `.gitignore`.
