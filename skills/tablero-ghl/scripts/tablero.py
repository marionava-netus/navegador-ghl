#!/usr/bin/env python3
"""
Tablero (dashboard) de GHL por API interna.

  plantilla  Instala el tablero estándar en la cuenta.
  listar     Muestra qué tableros ya tiene la cuenta.

Uso:
  python3 tablero.py plantilla --loc <locationId> [--base <panel>]
                               [--nombre "Mi tablero"] [--pipeline <id>]
                               [--dashboard <id>] [--default] [--dry-run]

  python3 tablero.py listar --loc <locationId> [--base <panel>]

Si no pasas --base, se lee `panel_base` de context/ghl.json.

Requiere el navegador con sesión iniciada en la cuenta, en el perfil Playwright
`.auth/pw-profile`. Si expiró, corre el login asistido de navegador-ghl:
  bash .claude/skills/navegador-ghl/scripts/login.sh "<url de la cuenta>" tablero

Por qué API interna y no la pública: `services.leadconnectorhq.com` NO expone
dashboards (404). Todo vive en `backend.leadconnectorhq.com/reporting/dashboards`
con los tokens de la sesión UI. Detalle en references/endpoints.md.
"""
import argparse, json, os, re, secrets, subprocess, sys, tempfile, time

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or os.getcwd()
CLI = ["npx", "playwright-cli"]
API = "https://backend.leadconnectorhq.com"
AQUI = os.path.dirname(os.path.abspath(__file__))
PLANTILLA = os.path.join(AQUI, "..", "assets", "plantilla-estandar.json")

def panel_base():
    """Dominio del panel. Sale de context/ghl.json; si falta, se detiene
    en vez de adivinar — una base equivocada da un 401 difícil de diagnosticar."""
    cfg = os.path.join(ROOT, "context", "ghl.json")
    if not os.path.exists(cfg):
        sys.exit(f"✗ Falta {cfg} (o pasa --base explícitamente).")
    b = json.load(open(cfg, encoding="utf-8")).get("panel_base")
    if not b:
        sys.exit(f"✗ Falta «panel_base» en {cfg}.")
    return b.rstrip("/")


# ---------------------------------------------------------------- sesión ----
def run_cli(args, session):
    return subprocess.run(CLI + ["-s=" + session] + args, cwd=ROOT,
                          capture_output=True, text=True)


def run_code(js, session):
    """Corre un snippet run-code y devuelve el JSON (--raw viene doble-encodeado)."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        r = run_cli(["run-code", "--filename=" + path, "--raw"], session)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    out = r.stdout.strip()
    if not out:
        raise RuntimeError("run-code sin salida. stderr:\n" + r.stderr[:800])
    d = json.loads(out)
    if isinstance(d, str):
        d = json.loads(d)
    return d


CAPTURA_JS = """
async page => {
  let auth = null;
  page.on('request', req => {
    const u = req.url(), h = req.headers();
    if (u.includes('/reporting/dashboards') && h['token-id'] && h['authorization'] && !auth) {
      auth = {
        'authorization': h['authorization'],
        'token-id': h['token-id'],
        'source': h['source'] || 'WEB_USER',
        'channel': h['channel'] || 'APP',
        'version': h['version'] || '2021-04-15',
        'x-reporting-api-version': '3',
        'content-type': 'application/json'
      };
    }
  });
  await page.goto('__URL__', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 60 && !auth; i++) await page.waitForTimeout(500);
  return JSON.stringify(auth || {});
}
"""


def capturar_auth(base, loc, session, profile):
    """Abre el tablero de la cuenta y roba los headers de la sesión UI.

    Los tokens viven ~1h. Se capturan por listener de requests porque el
    comando `request <n>` de la CLI muestra headers pero no el body, y aquí
    lo que necesitamos es justo la cabecera de una llamada que la app hace sola.
    """
    url = f"{base}/v2/location/{loc}/dashboard"
    sonda = run_cli(["--raw", "eval", "1"], session)
    abierta = "not open" not in (sonda.stdout + sonda.stderr)
    if not abierta:
        r = run_cli(["open", url, "--persistent", "--profile=" + profile,
                     "--browser=chrome"], session)
        if "not open" in r.stderr or r.returncode != 0:
            # El perfil admite un solo navegador a la vez. Si otra sesión lo tiene
            # tomado, no la mates (puede ser un cron): abre ahí una pestaña o usa
            # --session apuntando a esa sesión.
            raise SystemExit(
                f"No se pudo abrir el navegador con el perfil {profile}.\n"
                f"{r.stderr[:400]}\n"
                f"Si otra sesión lo tiene ocupado (`npx playwright-cli list`), pásala "
                f"con --session <nombre> en vez de cerrarla.")
        time.sleep(3)
    auth = run_code(CAPTURA_JS.replace("__URL__", url), session)
    if not auth or "token-id" not in auth:
        raise SystemExit(
            f"No se pudo capturar la sesión de {base}.\n"
            f"Lo más probable es que el login haya expirado. Corre:\n"
            f"  bash .claude/skills/playwright-web/scripts/login.sh \"{url}\" {session}\n"
            f"(perfil {profile}) y vuelve a intentar.")
    return auth


# ------------------------------------------------------------------ http ----
def curl(metodo, url, auth, body=None):
    """Usa curl y no urllib: Cloudflare bloquea el user-agent de urllib con 403."""
    cmd = ["curl", "-s", "-X", metodo, url, "-w", "\n__HTTP__%{http_code}"]
    for k, v in auth.items():
        cmd += ["-H", f"{k}: {v}"]
    tmp = None
    if body is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(body, tmp, ensure_ascii=False)
        tmp.close()
        cmd += ["--data-binary", "@" + tmp.name]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        if tmp:
            os.unlink(tmp.name)
    txt, _, code = r.stdout.rpartition("\n__HTTP__")
    try:
        data = json.loads(txt) if txt.strip() else {}
    except json.JSONDecodeError:
        data = {"_raw": txt[:500]}
    return int(code or 0), data


def listar(base, loc, auth):
    c, d = curl("GET", f"{API}/reporting/dashboards?locationId={loc}", auth)
    if c != 200:
        raise SystemExit(f"No se pudieron listar los tableros (HTTP {c}): {d}")
    dd = d["data"]
    return dd["defaultDashboardId"], dd.get("dashboard", []) + dd.get("sharedDashboards", [])


def leer(base, loc, dash_id, auth):
    c, d = curl("GET", f"{API}/reporting/dashboards/{dash_id}?locationId={loc}", auth)
    if c != 200:
        raise SystemExit(f"No se pudo leer el tablero {dash_id} (HTTP {c}): {d}")
    return d["data"]


def crear_tablero(loc, nombre, auth):
    # `isPrivate` es obligatorio aunque no lo parezca: sin él, 422.
    c, d = curl("POST", f"{API}/reporting/dashboards?locationId={loc}", auth,
                {"locationId": loc, "title": nombre, "type": "custom", "isPrivate": False})
    if c not in (200, 201):
        raise SystemExit(f"No se pudo crear el tablero (HTTP {c}): {d}\n"
                         "Crea uno vacío desde la UI (+ New) y pásalo con --dashboard.")
    return (d.get("data") or {}).get("_id") or (d.get("data") or {}).get("id")


def oid():
    """Los IDs de widget los generamos nosotros: ObjectId de 24 hex."""
    return secrets.token_hex(12)


def escribir(loc, dash_id, titulo, creates, deletes, layout, tema, auth):
    """Un solo PUT reemplaza el tablero: create + delete + layout van juntos."""
    payload = {
        "title": titulo,
        "activityBuffer": {"create": creates, "delete": deletes},
        "layout": sorted(layout, key=lambda e: (e["y"], e["x"])),
        "themeConfig": {"dashboardTheme": tema or {}, "widgetTheme": {}},
        "version": 0,
    }
    c, d = curl("PUT", f"{API}/reporting/dashboards/{dash_id}?locationId={loc}", auth, payload)
    if c != 200:
        raise SystemExit(f"El PUT del tablero falló (HTTP {c}): {json.dumps(d)[:600]}")
    return d


def permisos(loc, dash_id, auth, agencia="full", admin="write", usuario="read"):
    """OJO: el DTO solo valida `isPrivate`. Cualquier otro nombre de campo se
    ignora en silencio y responde success:true — el campo bueno es
    `permissionAccess`. Por eso verificamos leyendo después de escribir."""
    body = {"locationId": loc, "isPrivate": False,
            "permissionAccess": [{"role": "agency_user", "permission": agencia},
                                 {"role": "account_admin", "permission": admin},
                                 {"role": "account_user", "permission": usuario}]}
    curl("POST", f"{API}/reporting/dashboards/{dash_id}/permissions?locationId={loc}", auth, body)
    c, d = curl("GET", f"{API}/reporting/dashboards/{dash_id}/permissions?locationId={loc}", auth)
    got = {p["role"]: p["permission"] for p in (d.get("data", {}).get("permission") or [])}
    esperado = {"agency_user": agencia, "account_admin": admin, "account_user": usuario}
    return got == esperado, got


def por_defecto(loc, dash_id, auth):
    """Da 403 mientras los roles no tengan permisos; corre permisos() antes."""
    c, d = curl("POST", f"{API}/reporting/dashboards/{dash_id}/set-default", auth,
                {"locationId": loc})
    if c not in (200, 201):
        return False, d.get("message", "")
    _, lista = listar(None, loc, auth)
    return True, ""


def pipelines(loc, auth):
    c, d = curl("GET", f"{API}/opportunities/pipelines?locationId={loc}", auth)
    if c == 200 and d.get("pipelines"):
        return d["pipelines"]
    c, d = curl("GET", f"https://services.leadconnectorhq.com/opportunities/pipelines?locationId={loc}", auth)
    return d.get("pipelines", []) if c == 200 else []


# ------------------------------------------------------------ ensamblado ----
def ensambla(defs, loc):
    """Convierte definiciones de widget en (creates, layout) con IDs nuevos.

    Cada widget necesita DOS ids: la clave dentro de `create` (widgetId) y su
    `dashboardWidgetId`, que es el que va en la entrada de `layout`.
    """
    creates, layout = [], []
    for w in defs:
        pos = w.get("_pos") or w.get("layout") or {}
        wid, dwid = oid(), oid()
        d = {k: w.get(k) for k in ("chartType", "group", "identifier", "module",
                                   "moduleName", "title", "options", "apiConfig",
                                   "objectWidgetOptions", "extras") if w.get(k) is not None}
        d.update({"locationId": loc, "externalDataConfig": None, "version": 0,
                  "hasTrimmedFilters": False, "deleted": False,
                  "layout": {"minW": pos.get("minW", 2), "minH": pos.get("minH", 2),
                             "noResize": pos.get("noResize", False)},
                  "dashboardWidgetId": dwid})
        d.setdefault("options", {})
        creates.append({wid: d})
        layout.append({"x": pos["x"], "y": pos["y"], "w": pos["w"], "h": pos["h"],
                       "minW": pos.get("minW", 2), "minH": pos.get("minH", 2),
                       "noResize": pos.get("noResize", False),
                       "cellHeight": pos.get("cellHeight", "54px"), "id": dwid})
    return creates, layout


def revisa_residuos(creates, prohibidos):
    raw = json.dumps(creates, ensure_ascii=False)
    return {p: raw.count(p) for p in prohibidos if p and raw.count(p)}


# --------------------------------------------------------------- comandos ---
def cmd_plantilla(a, auth):
    plantilla = json.load(open(PLANTILLA, encoding="utf-8"))
    defs = plantilla["widgets"]

    pipes = pipelines(a.loc, auth)
    pid, pnombre = a.pipeline, ""
    if not pid and pipes:
        pid, pnombre = pipes[0]["id"], pipes[0]["name"]
    elif pid:
        pnombre = next((p["name"] for p in pipes if p["id"] == pid), "")
    if not pid:
        print("Aviso: la cuenta no tiene pipelines; los widgets de oportunidades "
              "quedarán sin filtro de embudo.")
    raw = json.dumps(defs, ensure_ascii=False)
    raw = raw.replace("__PIPELINE_ID__", pid or "").replace("__PIPELINE_NOMBRE__", pnombre or "")
    defs = json.loads(raw)

    creates, layout = ensambla(defs, a.loc)
    # Guarda: ningún placeholder sin sustituir ni id de otra cuenta debe llegar al PUT.
    malos = revisa_residuos(creates, ["__PIPELINE", "__LOCATION"])
    if malos:
        raise SystemExit(f"Se quedaron residuos en la plantilla: {malos}")

    # El dry-run se resuelve ANTES de crear nada: un ensayo que deja tableros
    # basura en la cuenta del agente no es un ensayo.
    if a.dry_run:
        previos = len(leer(a.base, a.loc, a.dashboard, auth).get("widgets", [])) if a.dashboard else 0
        print(f"[dry-run] {len(creates)} widgets a crear, {previos} a borrar, "
              f"pipeline={pnombre or '(ninguno)'}, "
              f"tablero={'existente ' + a.dashboard if a.dashboard else 'se crearía uno nuevo'}")
        return None

    dash_id = a.dashboard
    if not dash_id:
        dash_id = crear_tablero(a.loc, a.nombre, auth)
        print(f"Tablero creado: {dash_id}")
    deletes = [w["_id"] for w in leer(a.base, a.loc, dash_id, auth).get("widgets", [])]
    escribir(a.loc, dash_id, a.nombre, creates, deletes, layout,
             {"themeName": "blue", "titleColor": "#101828", "backgroundColor": "#FFFFFF",
              "metricColor": "#334155", "linkColor": "#2970ff"}, auth)
    print(f"Instalados {len(creates)} widgets (borrados {len(deletes)} previos).")
    return dash_id


def verifica(a, dash_id, auth, esperados):
    final = leer(a.base, a.loc, dash_id, auth)
    n = len(final.get("widgets", []))
    print(f"Verificación: {n}/{esperados} widgets en el destino, "
          f"{len(final.get('dashboardWidgets', []))} posiciones.")
    return n == esperados


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comunes(p):
        p.add_argument("--loc", required=True, help="locationId de la cuenta destino")
        p.add_argument("--base", help="dominio del panel (default: panel_base de la config)")
        p.add_argument("--dashboard", help="ID de un tablero existente a reemplazar")
        p.add_argument("--session", default="tablero")
        p.add_argument("--profile", default=".auth/pw-profile")
        p.add_argument("--default", action="store_true", help="dejarlo como tablero por defecto")
        p.add_argument("--dry-run", action="store_true")

    p1 = sub.add_parser("plantilla", help="instala el tablero estándar del agente")
    comunes(p1)
    p1.add_argument("--nombre", default="Mi tablero")
    p1.add_argument("--pipeline", help="pipeline para los widgets de oportunidades")

    p3 = sub.add_parser("listar", help="lista los tableros de la cuenta")
    p3.add_argument("--loc", required=True)
    p3.add_argument("--base", help="dominio del panel (default: panel_base de la config)")
    p3.add_argument("--session", default="tablero")
    p3.add_argument("--profile", default=".auth/pw-profile")

    a = ap.parse_args()
    if not a.base:
        a.base = panel_base()
    auth = capturar_auth(a.base, a.loc, a.session, a.profile)

    if a.cmd == "listar":
        pordef, lista = listar(a.base, a.loc, auth)
        for d in lista:
            marca = " (por defecto)" if d["_id"] == pordef else ""
            print(f"{d['_id']}  {d['title']}{marca}")
        return

    esperados = len(json.load(open(PLANTILLA, encoding="utf-8"))["widgets"])
    dash_id = cmd_plantilla(a, auth)
    if a.dry_run:
        return

    verifica(a, dash_id, auth, esperados)

    ok, got = permisos(a.loc, dash_id, auth)
    print(f"Permisos: {'ok' if ok else 'REVISAR'} → {got}")
    if a.default:
        hecho, msg = por_defecto(a.loc, dash_id, auth)
        print(f"Por defecto: {'ok' if hecho else 'falló — ' + msg}")
    print(f"\nÁbrelo en: {a.base}/v2/location/{a.loc}/dashboard/{dash_id}")


if __name__ == "__main__":
    main()
