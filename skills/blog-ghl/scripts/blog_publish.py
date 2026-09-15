#!/usr/bin/env python3
"""
blog_publish.py — Crea y publica posts de blog en GHL vía la API interna.

Uso:
    python3 blog_publish.py <spec.json> [--session blog] [--profile .auth/pw-profile] [--dry-run]

Requiere: navegador con sesión iniciada en la sub-cuenta, en el perfil de Playwright
(.auth/pw-profile). Si la sesión expiró, corre el login asistido de la skill navegador-ghl.

Formato del spec (JSON, UTF-8, ensure_ascii=False):
{
  "locationId": "<id de la sub-cuenta>",          // obligatorio
  "blogId":     "<id del sitio de blog>",         // obligatorio; el sitio se crea 1 vez por UI (ver SKILL.md)
  "accountBase":"<panel_base>",                   // opcional; si falta, se lee de context/ghl.json
  "author":     {"name":"<Nombre que firma>","imageUrl":"https://.../foto.png","imageAltText":"<alt>"},
                                                 // opcional; se crea si no existe un autor con ese name. O usa "authorId".
  "authorId":   null,                            // opcional; si lo sabes, reusa ese id y omite "author"
  "posts": [
    {
      "title": "El error que le cuesta clientes a la mayoría de los negocios locales",
      "urlSlug": "porque-tener-un-gmm",          // sin acentos, kebab-case
      "status": "PUBLISHED",                     // PUBLISHED | DRAFT | SCHEDULED | ARCHIVED
      "rawHTML": "<h2>...</h2><p>...</p>",        // cuerpo (sin repetir el H1/título)
      "description": "Meta description 120-160 chars con la keyword.",
      "categories": ["Salud","GMM"],             // labels (se crean/deduplican) o ids destino
      "image": "https://.../foto.png",           // URL ya hospedada  O  ruta local a subir (se detecta)
      "imageAltText": "...",
      "readTimeInMinutes": 3,                     // opcional (si falta, se estima de wordCount)
      "wordCount": 500,                           // opcional (si falta, se cuenta del rawHTML)
      "publishedAt": "2025-04-28T23:49:15.000Z",  // opcional
      "tags": []
    }
  ]
}
"""
import argparse, json, os, re, subprocess, sys, tempfile, html

ROOT = subprocess.run(["git","rev-parse","--show-toplevel"], capture_output=True, text=True).stdout.strip() or os.getcwd()
CONFIG = os.path.join(ROOT, "context", "ghl.json")

def _panel_base():
    """Dominio del panel. Sale de context/ghl.json; si falta, se detiene
    en vez de adivinar — una base equivocada da un 401 difícil de diagnosticar."""
    if not os.path.exists(CONFIG):
        sys.exit(f"✗ Falta {CONFIG} (o pasa 'accountBase' en el spec).")
    b = json.load(open(CONFIG, encoding="utf-8")).get("panel_base")
    if not b:
        sys.exit(f"✗ Falta «panel_base» en {CONFIG}.")
    return b.rstrip("/")
CLI = ["npx","playwright-cli"]

def run_cli(args, session):
    return subprocess.run(CLI+["-s="+session]+args, cwd=ROOT, capture_output=True, text=True)

def run_code(js, session):
    """Run a run-code snippet via a temp file, return parsed --raw JSON (handles double-encoding)."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", dir=os.path.join(ROOT,"downloads") if os.path.isdir(os.path.join(ROOT,"downloads")) else None, delete=False, encoding="utf-8") as f:
        f.write(js); path=f.name
    try:
        r = run_cli(["run-code","--filename="+path,"--raw"], session)
    finally:
        try: os.unlink(path)
        except OSError: pass
    out = r.stdout.strip()
    if not out:
        raise RuntimeError("run-code sin salida. stderr:\n"+r.stderr[:800])
    d = json.loads(out)
    if isinstance(d, str): d = json.loads(d)
    return d

AUTH_JS = """
  let auth=null;
  page.on('request', req=>{const h=req.headers(); if(h['token-id']&&!auth) auth={'token-id':h['token-id'],'source':h['source']||'WEB_USER','channel':h['channel']||'APP','version':h['version']||'2021-07-28','content-type':'application/json'};});
"""

def blogs_url(base, loc, blog_id):
    return f"{base}/v2/location/{loc}/blogs/site/{blog_id}?tab=blog-posts"

def media_url(base, loc):
    return f"{base}/v2/location/{loc}/media-storage"

def wc(text):
    return len(re.findall(r"\w+", re.sub(r"<[^>]+>"," ", text or "")))

# ---------- image upload ----------
def upload_images(spec, base, loc, session):
    """Upload local images to destination Media Storage; return {abspath: dest_url}."""
    locals_ = []
    for p in spec["posts"]:
        img = p.get("image")
        if img and not img.startswith("http"):
            ap = img if os.path.isabs(img) else os.path.join(ROOT, img)
            if not os.path.isfile(ap):
                raise SystemExit(f"Imagen local no encontrada: {img}")
            locals_.append(ap)
    au = spec.get("author",{}).get("imageUrl")
    if au and not au.startswith("http"):
        ap = au if os.path.isabs(au) else os.path.join(ROOT, au)
        if os.path.isfile(ap): locals_.append(ap)
    locals_ = sorted(set(locals_))
    if not locals_:
        return {}
    print(f"→ Subiendo {len(locals_)} imágenes locales al Media Storage…")
    run_cli(["goto", media_url(base,loc)], session)
    files_json = json.dumps(locals_)
    up = ("async page => {\n  await page.goto(%r);\n  await page.waitForTimeout(5000);\n"
          "  const files=%s;\n  await page.setInputFiles('#file-upload-input', files);\n  await page.waitForTimeout(1500);\n"
          "  return JSON.stringify({set:files.length});\n}\n") % (media_url(base,loc), files_json)
    run_code(up, session)
    # fetch media list, map basename->url
    fetch = ("async page => {\n"+AUTH_JS+
      "  await page.goto(%r); await page.waitForTimeout(6000);\n  if(!auth) return JSON.stringify({error:'no-auth'});\n"
      "  const out=await page.evaluate(async(H)=>{ const loc=%r; let all=[],off=0;\n"
      "    for(let i=0;i<6;i++){ const u='https://services.leadconnectorhq.com/medias/files/?altId='+loc+'&altType=location&parentId=&offset='+off+'&limit=100&query=&type=file&sortBy=updatedAt&sortOrder=desc&mode=public';\n"
      "      const j=await (await fetch(u,{headers:H})).json(); const fs=j.files||[]; all=all.concat(fs.map(f=>({name:f.name,url:f.url}))); if(fs.length<100) break; off+=100; }\n"
      "    return all; }, auth);\n  return JSON.stringify(out);\n}\n") % (media_url(base,loc), loc)
    lst = run_code(fetch, session)
    byname={}
    for f in lst:
        byname.setdefault(f["name"], f["url"])
    mapping={}
    for ap in locals_:
        bn=os.path.basename(ap)
        if bn not in byname:
            raise SystemExit(f"La imagen '{bn}' no aparece en el Media Storage tras subir. Revisa manualmente.")
        mapping[ap]=byname[bn]
    return mapping

# ---------- main publish ----------
PUBLISH_JS = ("async page => {\n"+AUTH_JS+
  "  await page.goto(%(url)r); await page.waitForTimeout(6000);\n"
  "  if(!auth) return JSON.stringify({error:'no-auth'});\n"
  "  const PLAN=%(plan)s;\n"
  "  const out=await page.evaluate(async(args)=>{\n"
  "    const {H,PLAN}=args; const loc=PLAN.loc, blogId=PLAN.blogId, base='https://services.leadconnectorhq.com';\n"
  "    // existing cats/authors\n"
  "    const ec=await (await fetch(base+'/blogs/posts/unique/category?locationId='+loc+'&blogId='+blogId,{headers:H})).json();\n"
  "    const ea=await (await fetch(base+'/blogs/posts/unique/author?locationId='+loc+'&blogId='+blogId,{headers:H})).json();\n"
  "    const catByLabel={}; (ec.categories||[]).forEach(c=>catByLabel[c.label.toLowerCase()]=c._id);\n"
  "    const authByName={}; (ea.authors||[]).forEach(a=>authByName[a.name.toLowerCase()]=a._id);\n"
  "    // ensure categories\n"
  "    for(const c of PLAN.categories){ const k=c.label.toLowerCase(); if(!catByLabel[k]){ const r=await fetch(base+'/blogs/categories/',{method:'POST',headers:H,body:JSON.stringify({locationId:loc,label:c.label,urlSlug:c.urlSlug,description:c.description||''})}); const j=await r.json(); const id=(j.category&&j.category[0]&&j.category[0]._id)||null; if(id) catByLabel[k]=id; } await new Promise(x=>setTimeout(x,250)); }\n"
  "    // ensure author\n"
  "    let authorId=PLAN.authorId||null;\n"
  "    if(!authorId && PLAN.author){ const k=PLAN.author.name.toLowerCase(); if(authByName[k]) authorId=authByName[k]; else { const r=await fetch(base+'/blogs/authors/',{method:'POST',headers:H,body:JSON.stringify({locationId:loc,name:PLAN.author.name,imageUrl:PLAN.author.imageUrl||'',imageAltText:PLAN.author.imageAltText||''})}); const j=await r.json(); authorId=(j.author&&(j.author._id||(j.author[0]&&j.author[0]._id)))||j._id||null; } }\n"
  "    // create posts\n"
  "    const results=[];\n"
  "    for(const p of PLAN.posts){\n"
  "      const cats=(p.categories||[]).map(c=>/^[0-9a-f]{20,}$/i.test(c)?c:catByLabel[String(c).toLowerCase()]).filter(Boolean);\n"
  "      const body={locationId:loc,blogId:blogId,title:p.title,rawHTML:p.rawHTML,status:p.status||'DRAFT',urlSlug:p.urlSlug,author:authorId,categories:cats,imageUrl:p.imageUrl||'',imageAltText:p.imageAltText||'',description:p.description||'',readTimeInMinutes:p.readTimeInMinutes,wordCount:p.wordCount,tags:p.tags||[]};\n"
  "      if(p.publishedAt) body.publishedAt=p.publishedAt;\n"
  "      const r=await fetch(base+'/blogs/posts/',{method:'POST',headers:H,body:JSON.stringify(body)});\n"
  "      let j=null; try{ j=await r.json(); }catch(e){}\n"
  "      let imgStatus=null; if(body.imageUrl){ try{ imgStatus=(await fetch(body.imageUrl)).status; }catch(e){ imgStatus='ERR'; } }\n"
  "      results.push({title:p.title, status:r.status, id:(j&&j.blogPost&&j.blogPost._id)||null, catCount:cats.length, imgStatus, err:(r.status>=400? JSON.stringify(j).slice(0,200):null)});\n"
  "      await new Promise(x=>setTimeout(x,400));\n"
  "    }\n"
  "    return {authorId, catMap:catByLabel, results};\n"
  "  }, {H:auth, PLAN});\n"
  "  return JSON.stringify(out);\n}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--session", default="blog")
    ap.add_argument("--profile", default=".auth/pw-profile")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    spec = json.load(open(a.spec, encoding="utf-8"))
    loc = spec["locationId"]; blog_id = spec["blogId"]
    base = spec.get("accountBase") or _panel_base()
    burl = blogs_url(base, loc, blog_id)

    # normalize posts (wordCount/readTime)
    for p in spec["posts"]:
        if not p.get("wordCount"): p["wordCount"] = wc(p.get("rawHTML",""))
        if not p.get("readTimeInMinutes"): p["readTimeInMinutes"] = round(max(1, p["wordCount"]/200), 1)
        p.setdefault("status","DRAFT")

    # open session + login check
    run_cli(["open", burl, "--persistent", "--profile="+a.profile], a.session)
    loc_href = run_cli(["eval","location.href","--raw"], a.session).stdout.strip().strip('"')
    if "logout" in loc_href or "/login" in loc_href or loc not in loc_href:
        print("✗ No hay sesión en la sub-cuenta.\n  Corre el login asistido y pide al agente que inicie sesión:\n"
              f"    bash .claude/skills/navegador-ghl/scripts/login.sh \"{burl}\" {a.session}\n"
              "  (perfil {}). Luego vuelve a correr este script.".format(a.profile))
        sys.exit(2)
    print(f"✓ Sesión OK en {loc}. Blog {blog_id}.")

    if a.dry_run:
        print(f"[dry-run] {len(spec['posts'])} posts, categorías: "
              + ", ".join(sorted({c for p in spec['posts'] for c in p.get('categories',[])})))
        for p in spec["posts"]:
            print(f"  - [{p['status']}] {p['title']}  (/{p['urlSlug']}, {p['wordCount']}w ~{p['readTimeInMinutes']}min)")
        return

    # images
    img_map = upload_images(spec, base, loc, a.session)
    for p in spec["posts"]:
        img = p.get("image")
        if img and not img.startswith("http"):
            ap_ = img if os.path.isabs(img) else os.path.join(ROOT, img)
            p["imageUrl"] = img_map[ap_]
        elif img:
            p["imageUrl"] = img
    au = spec.get("author",{}).get("imageUrl")
    if au and not au.startswith("http"):
        ap_ = au if os.path.isabs(au) else os.path.join(ROOT, au)
        spec["author"]["imageUrl"] = img_map.get(ap_, au)

    # build plan + publish
    plan = {
        "loc": loc, "blogId": blog_id,
        "categories": _plan_categories(spec),
        "author": spec.get("author"), "authorId": spec.get("authorId"),
        "posts": [{k:p.get(k) for k in ("title","urlSlug","status","rawHTML","description","categories","imageUrl","imageAltText","readTimeInMinutes","wordCount","publishedAt","tags")} for p in spec["posts"]],
    }
    js = PUBLISH_JS % {"url": burl, "plan": json.dumps(plan, ensure_ascii=False)}
    res = run_code(js, a.session)
    if res.get("error"):
        raise SystemExit("Error de sesión: "+res["error"])

    ok = sum(1 for r in res["results"] if r["status"]==201)
    print(f"\n=== Resultado: {ok}/{len(res['results'])} posts creados ===")
    print(f"autor destino: {res.get('authorId')}")
    for r in res["results"]:
        tag = "✓" if r["status"]==201 else "✗"
        line = f"  {tag} {r['status']} | cats {r['catCount']} | img {r['imgStatus']} | {r['title'][:44]}"
        if r.get("err"): line += f"\n      ERROR: {r['err']}"
        print(line)
    print("\nVer en el panel: "+burl)

def _plan_categories(spec):
    seen={}; out=[]
    for p in spec["posts"]:
        for c in p.get("categories",[]):
            if re.fullmatch(r"[0-9a-fA-F]{20,}", c):  # already an id
                continue
            k=c.lower()
            if k not in seen:
                seen[k]=1
                slug=re.sub(r"[^a-z0-9]+","-", c.lower()).strip("-")
                out.append({"label":c, "urlSlug":slug, "description":""})
    return out

if __name__ == "__main__":
    main()
