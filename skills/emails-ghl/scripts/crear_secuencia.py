#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crea/actualiza secuencias de email en GHL como plantillas del Design
editor — editables visualmente, con la firma y el footer legal del agente.

Uso:
    python3 crear_secuencia.py <spec.json>            # crea las plantillas
    python3 crear_secuencia.py <spec.json> --update   # actualiza (spec trae template_id)
    python3 crear_secuencia.py --smoke-test           # crea 1 de prueba, verifica y borra

Spec JSON:
{
  "emails": [
    {
      "title": "MiSecuencia — E0 Bienvenida (día 0)",
      "subject": "asunto (va en el workflow: la API NO lo guarda)",
      "utm": "misecuencia-e0",
      "template_id": "...",                 // solo con --update
      "segments": [
        {"type": "text",   "html": "<h2...>...</h2><p>...</p>"},
        {"type": "button", "url": "https://...", "label": "📥 Descargar"}
      ]
    }
  ]
}

Helpers de copy al importar este módulo: p(), h2(), SEP, link().

REQUISITOS
  .env del proyecto:            GHL_PIT=...   GHL_LOCATION_ID=...
  context/ghl.json:    identidad del agente (firma, footer, colores)
Ambos son obligatorios: si falta un dato el script se detiene con un mensaje
claro, nunca inventa un valor por defecto.
"""
import json, copy, os, sys, time, subprocess, pathlib

HERE   = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
# .claude/skills/emails-ghl/scripts -> raíz del proyecto
ROOT   = HERE.parents[3]
CONFIG = ROOT / "context" / "ghl.json"


# ---------- configuración ----------
def _falta(campo, donde):
    sys.exit(f"✗ Falta «{campo}» en {donde}.\n"
             f"  Complétalo antes de correr esta skill — no se asume ningún valor.")

def cfg():
    if not CONFIG.exists():
        sys.exit(f"✗ No existe {CONFIG}.\n"
                 f"  Copia la plantilla de la skill "
                 f"(.claude/skills/emails-ghl/assets/ghl.ejemplo.json) "
                 f"y llénala con los datos del agente.")
    c = json.load(open(CONFIG, encoding="utf-8"))
    f = c.get("firma") or {}
    for k in ("nombre", "tagline", "foto_url", "logo_url", "sitio_url",
              "sitio_label", "razon_social", "direccion"):
        if not f.get(k):
            _falta(f"firma.{k}", CONFIG)
    m = c.get("marca") or {}
    for k in ("navy", "naranja"):
        if not m.get(k):
            _falta(f"marca.{k}", CONFIG)
    return c

def _env():
    envf = ROOT / ".env"
    if not envf.exists():
        sys.exit(f"✗ No existe {envf} con GHL_PIT y GHL_LOCATION_ID.")
    env = {}
    for line in envf.read_text().splitlines():
        if line.startswith(("GHL_PIT=", "GHL_LOCATION_ID=")):
            k, v = line.split("=", 1)
            env[k] = v.strip()
    for k in ("GHL_PIT", "GHL_LOCATION_ID"):
        if not env.get(k):
            _falta(k, envf)
    return env["GHL_PIT"], env["GHL_LOCATION_ID"]


def _hex_a_rgb(h):
    h = h.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

_C = None
def colores():
    """(navy, naranja) en formato rgb() — se leen una sola vez."""
    global _C
    if _C is None:
        m = cfg()["marca"]
        _C = (_hex_a_rgb(m["navy"]), _hex_a_rgb(m["naranja"]))
    return _C


# ---------- helpers de copy ----------
SEP = '<p style="text-align: justify;"></p>'

def p(text, justify=True):
    navy, _ = colores()
    align = "justify" if justify else "left"
    return (f'<p style="text-align: {align};">'
            f'<span style="color: {navy}">{text}</span></p>')

def h2(text):
    navy, _ = colores()
    return (f'<h2 style="text-align: left;line-height: 1.15;">'
            f'<span style="color: {navy}">{text}</span></h2>')

def link(url, label):
    """Link de acento para CTAs suaves. Para CTAs fuertes usa un segment type=button."""
    _, naranja = colores()
    return (f'<a target="_blank" rel="noopener noreferrer nofollow" href="{url}">'
            f'<span style="color: {naranja}"><strong>{label}</strong></span></a>')


# ---------- firma y footer (generados desde la config) ----------
def _firma_html(c):
    navy = _hex_a_rgb(c["marca"]["navy"])
    f = c["firma"]
    partes = [
        f'<h1 style="line-height: 1.15;"><span style="color: {navy}; font-size: 24px">'
        f'{f["nombre"]}</span></h1>',
        f'<p style="line-height: 1.25;"><span style="color: rgb(82, 81, 81); font-size: 14px">'
        f'{f["tagline"]}</span></p>',
    ]
    def fila(emoji, url, label):
        return (f'<p style="line-height: 1.25;">'
                f'<span style="font-size: 18px">{emoji}</span>'
                f'<a target="_blank" rel="noopener noreferrer nofollow" href="{url}" title="{label}">'
                f'<span style="color: {navy}; font-size: 14px">{label}</span></a></p>')
    if f.get("linkedin_url"):
        partes.append(fila("👋", f["linkedin_url"], "Escríbeme en LinkedIn"))
    if f.get("whatsapp_link"):
        partes.append(fila("💡", f["whatsapp_link"], "Escríbeme en WhatsApp"))
    return "".join(partes)

def _footer_html(c, utm):
    """Footer legal. La dirección postal es OBLIGATORIA en email masivo
    (CAN-SPAM en EE. UU. y buena práctica en México)."""
    naranja = _hex_a_rgb(c["marca"]["naranja"])
    f = c["firma"]
    FONT = "font-family: arial, helvetica, sans-serif"
    sep  = "&" if "?" in f["sitio_url"] else "?"
    url  = f'{f["sitio_url"]}{sep}utm_campaign=secuencia&amp;utm_content={utm}'
    out = [f'<p style="line-height: 1.5;">'
           f'<span style="color: rgb(0, 0, 0); font-size: 14px; {FONT}"><strong>Contáctanos en: </strong></span>'
           f'<a target="_blank" rel="noopener noreferrer nofollow" href="{url}">'
           f'<span style="color: {naranja}; font-size: 14px; {FONT}">{f["sitio_label"]}</span></a></p>']
    lineas = [f["razon_social"]] + list(f["direccion"])
    for ln in lineas:
        out.append(f'<p style="line-height: 1.25;">'
                   f'<span style="color: rgb(82, 81, 81); font-size: 12px; {FONT}">{ln}</span></p>')
    return "".join(out)


# ---------- API ----------
def api(path, payload, method="POST"):
    pit, _ = _env()
    cmd = ["curl", "-s", "-X", method, f"https://services.leadconnectorhq.com{path}",
           "-H", f"Authorization: Bearer {pit}", "-H", "Version: 2021-07-28",
           "-H", "Content-Type: application/json"]
    if payload is not None:
        cmd += ["--data-binary", "@-"]
    r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                       capture_output=True, text=True)
    return json.loads(r.stdout)


# ---------- construcción del dnd ----------
def build_dnd(segments, utm):
    c = cfg()
    base     = json.load(open(ASSETS / "base-template-editorData.json", encoding="utf-8"))
    btn_ref  = json.load(open(ASSETS / "mj-button-reference.json", encoding="utf-8"))
    text_attrs = base["attrs"]["mj-text-GwdwamnQ"]["attributes"]

    ed  = copy.deepcopy(base)
    col = ed["elements"][0]["children"][0]           # primera columna = cuerpo
    preview, divider = col["children"][0], col["children"][2]
    children = [preview]
    slug = "".join(ch for ch in utm if ch.isalnum())
    for i, seg in enumerate(segments, 1):
        if seg["type"] == "text":
            nid = f"mj-text-{slug}{i:02d}"
            children.append({"id": nid, "tagName": "mj-text", "children": []})
            ed["attrs"][nid] = {"attributes": copy.deepcopy(text_attrs),
                                "content": seg["html"], "tagName": "mj-text"}
        elif seg["type"] == "button":
            nid = f"mj-button-{slug}{i:02d}"
            children.append({"id": nid, "tagName": "mj-button", "children": []})
            b = copy.deepcopy(btn_ref)
            for a in b["attributes"]:
                if a["name"] in ("href", "url"):
                    a["default"] = seg["url"]
                if a["name"] == "background-color":
                    a["default"] = c["marca"]["naranja"] + "FF"
            b["content"] = seg["label"]
            ed["attrs"][nid] = b
        else:
            raise ValueError(f"segment type desconocido: {seg['type']}")
    children.append(divider)
    col["children"] = children
    del ed["attrs"]["mj-text-GwdwamnQ"]              # el cuerpo de ejemplo de la base

    # --- identidad del agente ---
    f = c["firma"]
    ed["attrs"]["mj-text-o0KlIJG0"]["content"]  = _firma_html(c)
    ed["attrs"]["mj-footer-d7y748sr"]["content"] = _footer_html(c, utm)
    _img(ed, "mj-image-5YzsqZxv", f["foto_url"], f.get("linkedin_url") or f["sitio_url"],
         f'{f["nombre"]}')
    _img(ed, "mj-image-jse1KA4o", f["logo_url"], f["sitio_url"], f["razon_social"])

    # --- color de fondo del cuerpo ---
    for at in ed["templateSettings"]["body"]:
        if at["name"] == "background-color":
            at["default"] = c["marca"]["navy"]
    return ed

def _img(ed, key, src, href, alt):
    for at in ed["attrs"][key]["attributes"]:
        if at["name"] == "src":  at["default"] = src
        if at["name"] == "href": at["default"] = href
        if at["name"] == "alt":  at["default"] = alt


# ---------- flujo principal ----------
def crear_email(email, update=False):
    c = cfg()
    autor = c["firma"]["nombre"]
    _, loc = _env()
    if update:
        tid = email["template_id"]
    else:
        created = api("/emails/builder", {"locationId": loc, "type": "builder",
                                          "title": email["title"], "updatedBy": autor})
        tid = created.get("id")
        if not tid:
            return {"title": email["title"], "error": created}
    ed  = build_dnd(email["segments"], email["utm"])
    upd = api("/emails/builder/data", {"locationId": loc, "templateId": tid,
              "updatedBy": autor, "html": "", "editorType": "builder",
              "dnd": ed, "previewText": ""})
    if not upd.get("ok"):
        return {"title": email["title"], "id": tid, "error": upd.get("message")}
    time.sleep(2)
    html = subprocess.run(["curl", "-s", upd["previewUrl"]],
                          capture_output=True, text=True).stdout
    checks = {
        "firma":   autor in html,
        "unsub":   "desuscribirme" in html,
        "botones": all(s["label"] in html for s in email["segments"] if s["type"] == "button"),
    }
    return {"title": email["title"], "id": tid, "subject": email.get("subject", ""),
            "previewUrl": upd["previewUrl"], "checks": checks,
            "ok": all(checks.values())}

def borrar(tid):
    _, loc = _env()
    return api(f"/emails/builder/{loc}/{tid}", None, method="DELETE")

def smoke_test():
    """Verifica que el PIT, la config y la plantilla base sigan válidos."""
    sitio = cfg()["firma"]["sitio_url"]
    email = {"title": "SMOKE TEST — borrar", "utm": "smoke-test", "segments": [
        {"type": "text", "html": h2("Hola {{contact.first_name}},") + SEP +
                                 p("Prueba de humo de la skill de emails.")},
        {"type": "button", "url": sitio, "label": "🧪 Botón de prueba"}]}
    r = crear_email(email)
    print("crear+verificar:", json.dumps(r.get("checks"), ensure_ascii=False), "ok =", r.get("ok"))
    if r.get("id"):
        print("borrar:", borrar(r["id"]).get("ok"))
    return r.get("ok")


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        sys.exit(0 if smoke_test() else 1)
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec_path = sys.argv[1]
    update = "--update" in sys.argv
    spec = json.load(open(spec_path, encoding="utf-8"))
    out = []
    for email in spec["emails"]:
        r = crear_email(email, update=update)
        out.append(r)
        estado = "✅" if r.get("ok") else f"❌ {r.get('error')}"
        print(f"{r['title']}: {r.get('id')} {estado}")
    json.dump(out, open(spec_path.replace(".json", "-resultados.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
