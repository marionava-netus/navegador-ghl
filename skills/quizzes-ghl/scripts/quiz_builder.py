#!/usr/bin/env python3
"""Monta un quiz completo en GHL desde un spec JSON.

Los quizzes de GHL son `forms` con `productType: "quiz"`. Todo el
contenido vive en `formData` y se escribe por la API pública con un PIT:

    POST /forms/                -> crea el quiz (devuelve _id)
    POST /forms/{id}            -> escribe {name, formData}   (NO PUT/PATCH)

Cada pregunta se respalda en un custom field RADIO del contacto, así que el
builder los crea antes de armar los slides.

Uso:
    python3 quiz_builder.py spec.json --location <id> --pit-env GHL_PIT
    python3 quiz_builder.py spec.json --location <id> --dry-run
    python3 quiz_builder.py spec.json --location <id> --form-id <id>   # actualiza
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import time
import sys
import uuid

BASE = "https://services.leadconnectorhq.com"
VERSION = "2021-07-28"
ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

# Semáforo de riesgo: se queda rojo/ámbar/verde a propósito. Los colores de marca
# aquí romperían la lectura instantánea del resultado.
TIER_COLORS = ["#F04438", "#F79009", "#12B76A"]

# La identidad NO se incrusta: sale de context/ghl.json (o del bloque "brand"
# del spec). Si falta un dato, el builder se detiene diciendo cual — nunca
# inventa un default, porque un quiz con la marca equivocada es peor que ninguno.
BRAND_KEYS = ("primary", "dark", "footerBg", "onDark", "font",
              "brandName", "domain", "logoURL", "backgroundURL")

# Lo unico con default sensato: tonos neutros que no son marca de nadie.
BRAND_OPCIONALES = {"footerBg": "F2F4F7", "onDark": "FFFFFF", "backgroundURL": ""}


def panel_base() -> str:
    """El dominio del panel sale de context/ghl.json; si no hay, el de GHL."""
    for base in (pathlib.Path.cwd(), *pathlib.Path.cwd().parents):
        cfg = base / "context" / "ghl.json"
        if cfg.exists():
            return json.loads(cfg.read_text()).get("panel_base", "").rstrip("/") or "https://app.gohighlevel.com"
    return "https://app.gohighlevel.com"


def brand_desde_config() -> dict:
    """Lee context/ghl.json y lo traduce al vocabulario del builder."""
    for base in (pathlib.Path.cwd(), *pathlib.Path.cwd().parents):
        cfg = base / "context" / "ghl.json"
        if cfg.exists():
            c = json.loads(cfg.read_text())
            m, f = c.get("marca", {}), c.get("firma", {})
            return {k: v for k, v in {
                "primary": m.get("naranja"),          # color de acento -> CTA
                "dark": m.get("navy"),                # color principal -> fondos
                "font": m.get("font"),
                "brandName": f.get("razon_social"),
                "domain": (f.get("sitio_label") or "").strip(),
                "logoURL": f.get("logo_url"),
            }.items() if v}
    return {}


def resolver_brand(spec: dict) -> dict:
    """Config < spec. Se detiene si falta algo que no tenga default neutro."""
    brand = {**BRAND_OPCIONALES, **brand_desde_config(), **spec.get("brand", {})}
    faltan = [k for k in BRAND_KEYS
              if k not in brand or (brand[k] is None)
              or (str(brand[k]).startswith("<") and str(brand[k]).endswith(">"))]
    if faltan:
        raise SystemExit(
            "Faltan datos de marca para montar el quiz: " + ", ".join(faltan) +
            "\n  Llenalos en context/ghl.json (marca/firma) o en el bloque "
            "'brand' del spec. El logo debe estar en el Media Storage de TU "
            "sub-cuenta: una imagen de otra cuenta se ve rota para el visitante.")
    return brand


# ---------------------------------------------------------------- HTTP (curl)

def curl(method: str, path: str, pit: str, body: dict | None = None) -> dict:
    """Cloudflare devuelve 403 al user-agent de urllib -> siempre curl."""
    cmd = [
        "curl", "-s", "-X", method, f"{BASE}{path}",
        "-H", f"Authorization: Bearer {pit}",
        "-H", f"Version: {VERSION}",
        "-H", "Content-Type: application/json",
    ]
    if body is not None:
        cmd += ["-d", json.dumps(body, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise SystemExit(f"Respuesta no-JSON de {method} {path}:\n{out[:800]}")


# ------------------------------------------------------------------- helpers

def slug(text: str) -> str:
    """El `value` de una categoría: espacios -> _, conserva acentos y comas."""
    return re.sub(r"\s+", "_", text.strip())


def short_id(n: int = 6) -> str:
    """Los tier ids de GHL son cortos y alfanuméricos."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    import random
    return "".join(random.choice(alphabet) for _ in range(n))


def hexa(color: str) -> str:
    """Normaliza a RRGGBBAA como lo guarda GHL."""
    c = color.lstrip("#").upper()
    return c if len(c) == 8 else c + "FF"


def load_base(brand: dict) -> dict:
    """Plantilla de estilos con los tokens de marca sustituidos."""
    raw = (ASSETS / "base-quiz.json").read_text()
    for token, value in [
        ("{{PRIMARY}}", brand["primary"].lstrip("#").upper()),
        ("{{DARK}}", brand["dark"].lstrip("#").upper()),
        ("{{FOOTER_BG}}", brand["footerBg"].lstrip("#").upper()),
        ("{{ON_DARK}}", brand["onDark"].lstrip("#").upper()),
        ("{{FONT}}", brand["font"]),
        ("{{BRAND_NAME}}", brand["brandName"]),
        ("{{DOMAIN}}", brand["domain"]),
        ("{{LOGO_URL}}", brand["logoURL"]),
        ("{{BACKGROUND_URL}}", brand.get("backgroundURL", "")),
    ]:
        raw = raw.replace(token, value)
    return json.loads(raw)


# ------------------------------------------------------- tiers: puntos -> %

def tiers_from_points(spec_tiers: list[dict], max_score: int, min_score: int) -> list[dict]:
    """Convierte rangos de PUNTOS a los PORCENTAJES que usa GHL.

    GHL guarda los tiers en `fromPercent`/`toPercent`, no en puntos. El corte se
    pone en el PUNTO MEDIO entre dos puntajes contiguos, para que no dependa de
    si GHL trunca o redondea el porcentaje (ver gotcha #2 en SKILL.md).
    """
    def pct(points: float) -> float:
        return points / max_score * 100.0

    out = []
    for i, t in enumerate(spec_tiers):
        if i == 0:
            frm = 0
        else:
            prev_to = spec_tiers[i - 1]["toPoints"]
            frm = int(round((pct(prev_to) + pct(t["fromPoints"])) / 2)) + 1
        if i == len(spec_tiers) - 1:
            to = 100
        else:
            nxt_from = spec_tiers[i + 1]["fromPoints"]
            to = int(round((pct(t["toPoints"]) + pct(nxt_from)) / 2))
        out.append({
            "id": t.get("id") or short_id(),
            "label": t["label"],
            "color": t.get("color") or TIER_COLORS[min(i, len(TIER_COLORS) - 1)],
            "fromPercent": frm,
            "toPercent": to,
        })
    return out


# ------------------------------------------------------------- calendarios

BOOKING_URL = "https://api.leadconnectorhq.com/widget/booking/{}"

# El CTA debe llevar al calendario que corresponde al TEMA del quiz: si tienes
# un calendario por servicio y el quiz es de ese servicio, ahi apunta; si solo
# tienes uno, a ese. El tema y sus sinonimos los declara el propio spec:
#
#     "tema": {"nombre": "seo", "palabras": ["seo", "posicionamiento", "google"]}
#     "tema": "seo"          <- forma corta: el nombre es tambien la palabra
#
# Asi la skill sirve para cualquier giro sin tocar el codigo.


def tema_del_spec(spec: dict) -> tuple[str, list[str]]:
    tema = spec.get("tema") or spec.get("ramo") or ""
    if isinstance(tema, dict):
        nombre = (tema.get("nombre") or "").strip()
        palabras = [p for p in (tema.get("palabras") or []) if p] or ([nombre] if nombre else [])
    else:
        nombre = str(tema).strip()
        palabras = [nombre] if nombre else []
    return nombre, palabras


def _fold(text: str) -> str:
    """Minusculas sin acentos, para comparar nombres de calendario."""
    import unicodedata
    n = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def resolve_calendar(tema: str, palabras: list[str], location: str, pit: str) -> dict:
    """Elige el calendario que corresponde al tema del quiz.

    Reglas (en orden):
      1. Un solo calendario activo -> ese.
      2. Exactamente uno cuyo nombre/descripcion casa con el tema -> ese.
      3. Cualquier otro caso -> SE DETIENE y lista los calendarios. Nunca
         adivina: un CTA a la agenda equivocada quema el lead.
    """
    res = curl("GET", f"/calendars/?locationId={location}", pit)
    cals = [c for c in res.get("calendars", []) if c.get("isActive")]
    if not cals:
        raise SystemExit(
            "La cuenta no tiene calendarios activos. Crea el calendario del tema "
            "antes de montar el quiz, o pon 'buttonLink' explicito en el spec.")

    if len(cals) == 1:
        print(f"  calendario unico -> {cals[0]['name'].strip()}")
        return cals[0]

    if not palabras:
        raise SystemExit(
            "Hay varios calendarios activos y el spec no declara 'tema'. "
            "Agrega  \"tema\": {\"nombre\": \"...\", \"palabras\": [\"...\"]}  "
            "o pon 'buttonLink' explicito en cada tier del spec.")

    # Por PALABRA COMPLETA, no substring: "auto" no debe casar con
    # "Consultoria Automatiza tu Despacho" (falso positivo real, 2026-09-10).
    def casa(cal: dict) -> bool:
        texto = _fold(cal.get("name")) + " " + _fold(re.sub(r"<[^>]+>", " ", cal.get("description") or ""))
        # (?:e?s)? tolera el plural: "auto" casa con "Autos", no con "Automatiza".
        return any(re.search(rf"(?<![a-z]){re.escape(w)}(?:e?s)?(?![a-z])", texto)
                   for w in palabras)

    hits = [c for c in cals if casa(c)]

    if len(hits) == 1:
        print(f"  calendario de {tema.upper()} -> {hits[0]['name'].strip()}")
        return hits[0]

    listado = "\n".join(f"    {c['id']}  {c['name'].strip()}" for c in cals)
    causa = (f"{len(hits)} calendarios casan con '{tema}'" if hits
             else f"ningun calendario casa con '{tema}'")
    raise SystemExit(
        f"No puedo elegir el calendario del CTA: {causa} y hay {len(cals)} activos.\n"
        f"{listado}\n"
        "  Pon 'buttonLink' explicito en cada tier del spec, o nombra el "
        "calendario del tema (ej. 'Diagnostico SEO').")


def apply_cta_links(spec: dict, location: str, pit: str, dry: bool) -> None:
    """Rellena los buttonLink que esten en 'auto' o ausentes."""
    cta = spec.get("results", {}).get("cta", {})
    faltan = [t for t, v in cta.items()
              if not v.get("buttonLink") or v["buttonLink"] == "auto"]
    if not faltan:
        return
    if dry:
        for t in faltan:
            cta[t]["buttonLink"] = "https://DRY-RUN/calendario"
        return

    nombre, palabras = tema_del_spec(spec)
    cal = resolve_calendar(nombre, palabras, location, pit)
    base = BOOKING_URL.format(cal["id"])
    campana = (nombre or "quiz").lower()
    for t in faltan:
        term = re.sub(r"\s+", "+", t.strip().lower())
        cta[t]["buttonLink"] = (f"{base}?utm_source=quiz&utm_campaign={campana}"
                                f"&utm_content=cta&utm_term={term}")


# ------------------------------------------------------------ custom fields

def ensure_fields(spec: dict, location: str, pit: str, dry: bool) -> list[dict]:
    """Un custom field RADIO por pregunta. IDEMPOTENTE: reusa el que ya exista
    con el mismo nombre, si no cada corrida duplicaría los 12 campos."""
    existing = {}
    if not dry:
        res = curl("GET", f"/locations/{location}/customFields?model=contact", pit)
        existing = {f.get("name"): f for f in res.get("customFields", [])}

    fields = []
    for i, q in enumerate(spec["questions"], start=1):
        options = [o["t"] for o in q["options"]]
        # El nombre del campo manda sobre el fieldKey: que se lea la pregunta.
        name = (q.get("fieldName") or f"Q{i:02d} {strip_html(q['q'])}")[:100]
        if dry:
            fields.append({
                "id": f"DRY{i:02d}", "fieldKey": f"contact.dry_{i:02d}",
                "parentId": "DRYFOLDER", "name": name, "picklistOptions": options,
            })
            continue
        if name in existing:
            fields.append(existing[name])
            print(f"  campo {i:2d}/{len(spec['questions'])}: reusado {existing[name]['fieldKey']}")
            continue
        res = curl("POST", f"/locations/{location}/customFields", pit, {
            "name": name, "dataType": "RADIO", "model": "contact", "options": options,
        })
        if "customField" not in res:
            raise SystemExit(f"No pude crear el campo de la pregunta {i}: {res}")
        fields.append(res["customField"])
        print(f"  campo {i:2d}/{len(spec['questions'])}: creado {res['customField']['fieldKey']}")
    return fields


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


# ------------------------------------------------------------------- slides

def text_slide(html: str, brand: dict, color: str | None = None, weight: int = 500) -> dict:
    return {
        "active": False, "align": "left", "bgColor": "FFFFFF00",
        "border": {"border": 0, "color": "FFFFFF", "radius": 0, "type": "none"},
        "color": hexa(color or brand["onDark"]),
        "fontFamily": brand["font"],
        "hiddenFieldQueryKey": "header",
        "label": html,
        "padding": {"bottom": 0, "left": 0, "right": 0, "top": 0},
        "placeholder": "header",
        "shadow": {"blur": 0, "color": "FFFFFF", "horizontal": 0, "spread": 0, "vertical": 0},
        "standard": True, "tag": "header", "type": "h1", "typeLabel": "Text",
        "uuid": str(uuid.uuid4()), "weight": weight,
    }


def question_slide(q: dict, field: dict, cats: list[dict], slide_index: int) -> dict:
    """Un slide = una pregunta radio con su scoreByCategory."""
    cat = cats[q["category"] + 1]  # +1: cats[0] es overAllScore
    score_by_cat = {
        str(idx): {
            "category": cat["value"], "categoryId": cat["id"],
            "elementIndex": 0, "index": idx,
            "score": opt["score"], "slideIndex": slide_index,
        }
        for idx, opt in enumerate(q["options"])
    }
    return {
        "id": field["id"],
        "slideName": f"Page {slide_index + 1}",
        "slideData": [{
            "__pendingClone": False, "active": False, "custom": True,
            "customEdited": True, "customfieldUpdated": True,
            "dataType": "RADIO", "documentType": "field",
            "fieldKey": field["fieldKey"],
            "hiddenFieldQueryKey": field["fieldKey"].replace("contact.", ""),
            "id": field["id"], "isAllowedCustomOption": False,
            "label": q["q"], "locationId": field.get("locationId", ""),
            "model": "contact", "name": field["name"],
            "parentId": field.get("parentId", ""), "placeholder": "",
            "position": 50, "required": True,
            "scoreByCategory": score_by_cat,
            "standard": False, "tag": field["id"], "type": "radio",
            "typeLabel": "Single Choice", "uuid": str(uuid.uuid4()),
            "picklistOptions": [o["t"] for o in q["options"]],
        }],
    }


def contact_slide(spec: dict, brand: dict, index: int) -> dict:
    labels = spec.get("contactSlide", {})
    return {
        "id": str(uuid.uuid4()),
        "slideName": f"Page {index + 1}",
        "slideData": [
            text_slide(
                labels.get("heading", "<p>Compártenos tus datos para enviarte tus resultados</p>"),
                brand, color=brand["primary"], weight=600,
            ),
            {"active": False, "fieldKey": "nombre_completo", "hiddenFieldQueryKey": "full_name",
             "label": labels.get("nameLabel", "Nombre Completo"),
             "placeholder": labels.get("nameLabel", "Nombre Completo"),
             "preview": '<span style="color: #000000;">Nombre Completo</span>',
             "required": True, "standard": True, "tag": "full_name", "type": "text",
             "typeLabel": "Text", "uuid": str(uuid.uuid4())},
            {"active": False, "hiddenFieldQueryKey": "email", "label": "Email",
             "placeholder": "Email", "required": True, "standard": True, "tag": "email",
             "type": "email", "typeLabel": "Email", "uuid": str(uuid.uuid4())},
            {"active": False, "enableCountryPicker": False, "fieldKey": "whatsapp",
             "hiddenFieldQueryKey": "phone", "label": labels.get("phoneLabel", "WhatsApp"),
             "placeholder": labels.get("phoneLabel", "WhatsApp"),
             "preview": '<span style="color: #000000;">WhatsApp</span>',
             "required": True, "standard": True, "tag": "phone", "type": "text",
             "typeLabel": "Phone", "uuid": str(uuid.uuid4())},
        ],
    }


# ----------------------------------------------------------- resultTemplate

def result_template(spec: dict, cats: list[dict], tiers: list[dict], brand: dict) -> dict:
    """5 secciones: header, puntaje global, miniresultados, CTA, footer."""
    by_tier = {t["label"]: t["id"] for t in tiers}
    res = spec.get("results", {})

    def tiered(mapping: dict) -> dict:
        """{label del tier -> contenido}  ->  {tierId -> contenido}"""
        return {by_tier[label]: html for label, html in mapping.items() if label in by_tier}

    overall = {"overAllScore": tiered(res.get("overall", {}))}
    titles = {"overAllScore": {t["id"]: spec.get("scoreTitle", "Tu puntaje") for t in tiers}}

    # Miniresultados: {categoryId -> {tierId -> texto}}
    cat_headings = {}
    for c in cats[1:]:
        per_cat = res.get("byCategory", {}).get(c["label"], {})
        cat_headings[c["id"]] = tiered(per_cat)

    # CTA: heading/botón/link, cada uno por tier
    cta = res.get("cta", {})
    cta_heading = {"overAllScore": tiered({k: v.get("heading", "") for k, v in cta.items()})}
    cta_text = {"overAllScore": tiered({k: v.get("buttonText", "Agendar") for k, v in cta.items()})}
    cta_link = {"overAllScore": tiered({k: v.get("buttonLink", "") for k, v in cta.items()})}

    pad = {"margin": {"bottom": "auto", "left": "auto", "right": "auto", "top": "auto"},
           "padding": {"bottom": "16", "left": "16", "right": "16", "top": "16"}}

    header = spec.get("header", {})
    footer = spec.get("footer", {})

    return {
        "tiers": tiers,
        "categoryScoreSettings": None, "ctaSettings": None, "footerSettings": None,
        "headerSettings": None, "individualCategorySettings": None,
        "overallScoreSettings": None,
        "sections": [
            {"id": str(uuid.uuid4()), "hide": False, "type": "headerSettings", "config": {
                "backgroundColor": hexa(brand["dark"]),
                "enableBusinessName": True,
                "headerImage": header.get("image", brand["logoURL"]),
                "headerLayout": "default",
                "headingHtml": header.get(
                    "headingHtml",
                    f'<p style="padding-left: 0px!important;"><span style="font-size: 22px;'
                    f' font-family: {brand["font"]}; color: rgba(255,255,255,1) !important">'
                    f'{spec.get("title", "Resultados del Quiz")}</span></p>'),
                "imageHeight": header.get("imageHeight", "50"),
                "imageWidth": header.get("imageWidth", "50"),
                "marginPadding": pad, "socialLinks": False}},

            {"id": str(uuid.uuid4()), "hide": False, "type": "overallScoreSettings", "config": {
                "backgroundColor": "FFFFFFFF", "category": "overAllScore",
                "content": overall, "dynamicContent": True, "marginPadding": pad,
                "overallScoreFormat": "percentage", "overallScoreTitle": titles,
                "scorePosition": "left", "showOverallScore": True, "showTiers": True,
                "socialLinks": False,
                "staticContent": {"content": "", "overallScoreTitle": spec.get("scoreTitle", "Tu puntaje")}}},

            {"id": str(uuid.uuid4()), "hide": False, "type": "categoryScoreSettings", "config": {
                "category": cats[-1]["id"], "categoryBackground": "FFFFFF",
                "dynamicContent": True, "heading": cat_headings,
                "marginPadding": {"margin": {"bottom": -1, "left": 0, "right": "auto", "top": 0},
                                  "padding": {"bottom": 10, "left": 20, "right": 20, "top": 10}},
                "orderCategories": "highestOrder", "scoreFormat": "percentage",
                "sectionBackground": hexa(brand["dark"]), "showScore": True,
                "staticContent": {"heading": ""}}},

            {"id": str(uuid.uuid4()), "hide": False, "type": "ctaSettings", "config": {
                "backgroundColor": hexa(brand["dark"]),
                "buttonColor": hexa(brand["primary"]),
                "buttonLink": cta_link, "buttonText": cta_text,
                "buttonTextColor": "FFFFFFFF", "category": "overAllScore",
                "categoryBackground": "FFFFFF", "dynamicContent": True,
                "heading": cta_heading, "marginPadding": pad, "socialLinks": False,
                "staticContent": {"heading": "", "buttonText": "Agendar", "buttonLink": ""},
                "tier": tiers[0]["id"]}},

            {"id": str(uuid.uuid4()), "hide": False, "type": "footerSettings", "config": {
                "allowRowsToTakeFullWidth": True, "backgroundColor": "FFFFFF",
                "backgroundImage": "", "enableBusinessName": True,
                "footerHTML": footer.get("html", f'<p style="padding-left: 0px!important;">By {brand["brandName"]}</p>'),
                "footerImage": footer.get("image", ""),
                "imageHeight": "32", "imageWidth": "72",
                "marginPadding": {"margin": {"bottom": "auto", "left": "auto", "right": "auto", "top": "auto"},
                                  "padding": {"bottom": 10, "left": 20, "right": 20, "top": 10}},
                "showAddSocials": bool(footer.get("socialLinks")),
                "socialLinks": footer.get("socialLinks", []), "sticky": False}},
        ],
    }


# --------------------------------------------------------------- formData

def build_form_data(spec: dict, fields: list[dict], brand: dict) -> dict:
    base = load_base(brand)

    cats = [{"id": "overAllScore", "label": "Overall Only", "value": "overAllScore"}]
    for name in spec["categories"]:
        cats.append({"id": str(uuid.uuid4()), "label": name, "value": slug(name)})

    max_score = sum(max(o["score"] for o in q["options"]) for q in spec["questions"])
    min_score = sum(min(o["score"] for o in q["options"]) for q in spec["questions"])
    tiers = tiers_from_points(spec["tiers"], max_score, min_score)

    slides = [{"id": str(uuid.uuid4()), "slideName": "Page 1",
               "slideData": [text_slide(spec["intro"], brand)]}]
    for i, (q, f) in enumerate(zip(spec["questions"], fields), start=1):
        slides.append(question_slide(q, f, cats, i))
    slides.append(contact_slide(spec, brand, len(slides)))

    form = base["form"]
    form["formAction"] = form.get("formAction", {})

    return {
        "fieldCSS": base["fieldCSS"],
        "mobileFieldCSS": base["mobileFieldCSS"],
        "form": form,
        "logic": {},
        "slides": slides,
        "category": cats,
        "emailNotifications": False,
        "autoResponder": False,
        "resultTemplate": result_template(spec, cats, tiers, brand),
        "categoryCustomFields": [],
        "parentFolderId": "",
        "parentFolderName": "",
        "language": spec.get("language", "es-MX"),
    }, tiers, max_score, min_score


# ------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--location", required=True)
    ap.add_argument("--pit-env", default="GHL_PIT")
    ap.add_argument("--form-id", help="actualiza un quiz existente en vez de crear")
    ap.add_argument("--dry-run", action="store_true", help="no toca la cuenta; escribe el blob a disco")
    ap.add_argument("--emit-only", action="store_true",
                    help="resuelve los campos reales y escribe el payload {name, formData} "
                         "a --out, sin guardar. Para guardarlo con la sesion UI (ver SKILL.md).")
    ap.add_argument("--out", default="quiz-formdata.json")
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text())
    brand = resolver_brand(spec)

    n_q = len(spec["questions"])
    if n_q != 12:
        print(f"⚠️  el spec trae {n_q} preguntas (el molde recomendado son 12: 4 por categoría)")
    if len(spec["categories"]) != 3:
        print(f"⚠️  el spec trae {len(spec['categories'])} categorías (el molde son 3)")

    pit = ""
    if not args.dry_run:
        pit = read_env(args.pit_env)
        if not pit:
            raise SystemExit(f"No encontré {args.pit_env} en .env")

    print("CTA…")
    apply_cta_links(spec, args.location, pit, args.dry_run)

    print(f"Campos personalizados ({n_q})…")
    fields = ensure_fields(spec, args.location, pit, args.dry_run)

    form_data, tiers, max_score, min_score = build_form_data(spec, fields, brand)
    print(f"\nTiers (puntos {min_score}–{max_score} → porcentaje):")
    for t, st in zip(tiers, spec["tiers"]):
        print(f"  {t['label']:<14} {st['fromPoints']:>2}–{st['toPoints']:<2} pts"
              f"  →  {t['fromPercent']:>3}–{t['toPercent']:<3}%   id={t['id']}")

    if args.dry_run:
        pathlib.Path(args.out).write_text(json.dumps(form_data, ensure_ascii=False, indent=1))
        print(f"\n[dry-run] blob escrito a {args.out} — no se tocó la cuenta.")
        return

    if args.emit_only:
        payload = {"name": spec["name"], "formData": form_data}
        pathlib.Path(args.out).write_text(json.dumps(payload, ensure_ascii=False))
        print(f"\n[emit-only] payload listo en {args.out} ({len(json.dumps(payload))} bytes).")
        print("Guárdalo con la sesión UI: ver 'Cómo guardar' en SKILL.md")
        return

    form_id = args.form_id
    if not form_id:
        created = curl("POST", "/forms/", pit, {
            "locationId": args.location, "name": spec["name"], "productType": "quiz"})
        form_id = created.get("form", {}).get("_id")
        if not form_id:
            raise SystemExit(f"No pude crear el quiz: {created}")
        print(f"\nQuiz creado: {form_id}")

    # Un quiz recién creado puede tardar en ser visible para el endpoint de
    # guardado (read-after-write): el primer POST devuelve 404. Se reintenta.
    res = {}
    for attempt in range(1, 6):
        res = curl("POST", f"/forms/{form_id}", pit, {"name": spec["name"], "formData": form_data})
        if "form" in res:
            break
        if res.get("statusCode") == 404:
            print(f"  aún no visible (intento {attempt}/5), reintento en 3 s…")
            time.sleep(3)
            continue
        raise SystemExit(f"El guardado falló: {json.dumps(res)[:600]}")
    if "form" not in res:
        raise SystemExit(f"El guardado falló tras 5 intentos: {json.dumps(res)[:600]}")
    print(f"Guardado ✓  version={res['form'].get('version')}")
    panel = panel_base()
    print(f"\nBuilder: {panel}/v2/location/{args.location}/quiz-builder/{form_id}/edit")
    print(f"Quiz publico: https://api.leadconnectorhq.com/widget/quiz/{form_id}")


def read_env(key: str) -> str:
    """Lee una llave del .env del repo sin ejecutarlo (trae líneas raras)."""
    for base in (pathlib.Path.cwd(), *pathlib.Path.cwd().parents):
        env = base / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
            break
    return os.environ.get(key, "")


if __name__ == "__main__":
    main()
