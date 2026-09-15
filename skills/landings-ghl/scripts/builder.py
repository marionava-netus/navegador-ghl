#!/usr/bin/env python3
"""Motor de construcción de páginas NATIVAS del builder de GHL (editables).

Autora `pageData` (sections/rows/cols/elements reales del builder) reusando plantillas
de elementos reales, y lo inyecta vía la API interna autosave. Resultado: página 100%
editable en el builder (NO un bloque de Custom Code).

Uso típico (ver SKILL.md; se escribe un _build_native.py por funnel):

    from builder import *
    def build_hero(s):
        h = s.add(heading('<h1>Título</h1>', 52, 34, color=INK))
        cta = s.add(button('Reservar', action='scroll', target='section-FORM'))
        return [s.row([s.col([h, cta])])]
    secs = [section(build_hero, bg_css="linear-gradient(...), url('...') center/cover")]
    base = load_wrapper('downloads/<page>-current.json')   # blob actual (reusa general/pageStyles/fonts)
    register_theme_colors(base, {'cream':'#faf7f0','navy':'#101b33'})
    base['sections'] = secs
    save_blob(base, 'downloads/mi-pagina-native.json')
    # luego: inyectar con make_inject_js(...) vía playwright-cli run-code

Requiere las plantillas el-*.json en ../assets/ (ya vienen limpias, sin imágenes
de ninguna otra cuenta) y context/ghl.json con el dominio del panel.
"""
import json, copy, os, sys, pathlib

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'assets')
# .claude/skills/landings-ghl/scripts -> raíz del proyecto
ROOT   = pathlib.Path(__file__).resolve().parents[4]
CONFIG = ROOT / 'context' / 'ghl.json'

def panel_base():
    """Dominio del panel de GHL. Sale de context/ghl.json;
    si no está, se detiene en vez de adivinar (una URL equivocada = 401 confuso)."""
    if not CONFIG.exists():
        sys.exit(f'✗ Falta {CONFIG} — copia la plantilla de la skill emails-ghl y llénala.')
    b = json.load(open(CONFIG, encoding='utf-8')).get('panel_base')
    if not b:
        sys.exit(f'✗ Falta «panel_base» en {CONFIG}.')
    return b.rstrip('/')

def _load(k): return json.load(open(os.path.join(ASSETS, f'el-{k}.json')))
T = {k: _load(k) for k in ['paragraph', 'sub-heading', 'button', 'image', 'row', 'col', 'code']}
SECMETA = _load('section-meta')
FORM = _load('form')

# ---- paleta por defecto (sobreescribible por la página) ----
INK = '#1a2642'; GREY = '#788091'; TEXTBODY = '#3d4966'; CARDBORDER = '#eee5d6'
# los fondos de sección/columna DEBEN ser var(--...) del tema (ver register_theme_colors);
# el hex crudo NO renderiza como backgroundColor. El texto/borde sí aceptan hex.

_c = [0]
def nid(kind):
    _c[0] += 1
    return f"{kind}-x{_c[0]:03d}"
def reset_ids():
    _c[0] = 0

WMAP = {'black':'900','bold':'700','semibold':'600','medium':'500','normal':'400'}

# ---- limpieza CRÍTICA (los templates col/row del builder traen bgImage + un campo
#      recursivo 'element' con imágenes de OTRA cuenta -> si no se limpia, se cuela en TODO) ----
def clear_foreign(node, foreign_loc=None):
    """Vacía toda bgImage y borra urls que apunten a `foreign_loc` (la cuenta de donde
    salieron las plantillas). Recorre TODO incl. el campo recursivo 'element'."""
    def walk(n):
        if isinstance(n, dict):
            for k, v in list(n.items()):
                if k == 'bgImage' and isinstance(v, dict) and isinstance(v.get('value'), dict):
                    v['value']['url'] = ''; v['value']['mediaType'] = ''; v['value']['servingUrl'] = ''
                elif k in ('url','servingUrl','placeholderBase64') and isinstance(v, str) and foreign_loc and foreign_loc in v:
                    n[k] = ''
                else:
                    walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(node)
    return node

def register_theme_colors(base, colors, prefix='tre'):
    """Agrega colores custom (dict nombre->hex) a general.colors y al :root de pageStyles.
    Devuelve dict nombre-> 'var(--<prefix>-<nombre>)' para usar en fondos."""
    g = base.setdefault('general', {}).setdefault('general', {})
    cols = g.setdefault('colors', [])
    have = {c.get('label') for c in cols}
    css = ''; vmap = {}
    for name, val in colors.items():
        label = f'{prefix}-{name}'
        if label not in have:
            cols.append({'label': label, 'value': val, 'name': label})
        css += f'--{label}: {val};\n'
        vmap[name] = f'var(--{label})'
    ps = base.get('pageStyles', '') or ''
    marker = f'--{prefix}-'
    if ':root{' in ps and marker not in ps:
        ps = ps.replace(':root{', ':root{ ' + css, 1)
    elif marker not in ps:
        ps = ':root{ ' + css + ' }\n' + ps
    base['pageStyles'] = ps
    return vmap

def _wrap(mt=0, mb=0, ml=0, mr=0, align=None, width='auto'):
    w = {'marginTop':{'unit':'px','value':mt}, 'marginBottom':{'unit':'px','value':mb},
         'marginLeft':{'unit':'px','value':ml}, 'marginRight':{'unit':'px','value':mr},
         'width':{'value':width,'unit':'' if width=='auto' else 'px'}, 'height':{'value':'auto','unit':''}}
    if align is not None: w['textAlign'] = {'value': align}
    return w

# ---------- elementos hoja ----------
def heading(html, size_d, size_m=None, color=INK, align='center', weight='black',
            mt=0, mb=10, lineh=1.1, ls=0, tt='none'):
    e = clear_foreign(copy.deepcopy(T['sub-heading'])); i = nid('sub-heading'); e['id']=i; e['extra']['nodeId']='c'+i
    e['extra']['text'] = {'value': html}
    e['extra']['desktopFontSize'] = {'value': size_d, 'unit':'px'}
    e['extra']['mobileFontSize'] = {'value': size_m or max(20, int(size_d*0.72)), 'unit':'px'}
    e['styles']['color'] = {'value': color}; e['styles']['textAlign'] = {'value': align}
    e['styles']['fontWeight'] = {'value': weight, 'desktop': WMAP[weight]}
    e['styles']['lineHeight'] = {'value': lineh, 'unit':'em'}
    e['styles']['letterSpacing'] = {'value': str(ls), 'unit':'px'}
    e['styles']['textTransform'] = {'value': tt}
    e['styles']['paddingTop'] = {'unit':'px','value':0}; e['styles']['paddingBottom'] = {'unit':'px','value':0}
    e['wrapper'] = _wrap(mt=mt, mb=mb, align=align); e['mobileStyles']={}; e['mobileWrapper']={}
    return e

def para(html, size_d=17, size_m=None, color=TEXTBODY, align='center', weight='medium',
         mt=0, mb=16, lineh=1.5, maxw=None, bold_color=INK):
    e = clear_foreign(copy.deepcopy(T['paragraph'])); i = nid('paragraph'); e['id']=i; e['extra']['nodeId']='c'+i
    e['extra']['text'] = {'value': html}
    e['extra']['desktopFontSize'] = {'value': size_d, 'unit':'px'}
    e['extra']['mobileFontSize'] = {'value': size_m or max(14, int(size_d*0.9)), 'unit':'px'}
    e['styles']['color'] = {'value': color}; e['styles']['textAlign'] = {'value': align}
    e['styles']['fontWeight'] = {'value': weight, 'desktop': WMAP[weight]}
    e['styles']['lineHeight'] = {'value': lineh, 'unit':'em'}
    e['styles']['paddingTop'] = {'unit':'px','value':0}; e['styles']['paddingBottom'] = {'unit':'px','value':0}
    e['styles']['boldTextColor'] = {'value': bold_color}
    w = _wrap(mt=mt, mb=mb, align=align)
    if maxw: w['width'] = {'value': maxw, 'unit':'px'}
    e['wrapper'] = w; e['mobileStyles']={}; e['mobileWrapper']={}
    return e

def button(text, action='scroll', target='', url='', size_d=19, color='#ffffff', bg='#e08a3c',
           radius=999, pad_v=17, pad_h=46, align='center', mt=22, mb=6, weight='black', tt='none'):
    e = clear_foreign(copy.deepcopy(T['button'])); i = nid('button'); e['id']=i; e['extra']['nodeId']='c'+i
    e['extra']['text'] = {'value': text}
    e['extra']['desktopFontSize'] = {'value': size_d, 'unit':'px'}; e['extra']['mobileFontSize'] = {'value': size_d-2, 'unit':'px'}
    if action == 'scroll':
        e['extra']['action'] = {'value':'scrollToElement'}; e['extra']['scrollToElement'] = {'value': target}
    elif action == 'url':
        e['extra']['action'] = {'value':'visitWebsite'}; e['extra']['visitWebsite'] = {'value':{'url':url,'newTab':False}}
    else:
        e['extra']['action'] = {'value':'none'}
    e['extra']['theme'] = {'value': None}   # CLAVE: anular button_theme_4 o pisa tus estilos
    st = e['styles']
    st['backgroundColor'] = {'value': bg}; st['color'] = {'value': color}
    st['borderRadius'] = {'value': f'{radius}px'}
    st['paddingTop'] = {'unit':'px','value':pad_v}; st['paddingBottom'] = {'unit':'px','value':pad_v}
    st['paddingLeft'] = {'unit':'px','value':pad_h}; st['paddingRight'] = {'unit':'px','value':pad_h}
    st['fontWeight'] = {'value':weight,'desktop':WMAP[weight]}
    # la plantilla del builder fuerza MAYÚSCULAS; por defecto se respeta el texto tal cual
    st['textTransform'] = {'value': tt}
    st['borderWidth'] = {'value':'0px'}; st['borderStyle'] = {'value':'none'}; st['width'] = {'value':'auto','unit':'%'}
    e['wrapper'] = _wrap(mt=mt, mb=mb, align=align); e['mobileStyles']={}; e['mobileWrapper']={}
    return e

def image(url, width=None, radius=0, mt=0, mb=0, align='center', alt='', full=False):
    """width en px; `full=True` -> 100% del ancho de la columna.
    OJO: el ancho de la imagen vive en `styles.width` (la plantilla trae 200px por
    defecto), NO en el wrapper — si solo tocas el wrapper, la imagen sale a 200px."""
    e = clear_foreign(copy.deepcopy(T['image'])); i = nid('image'); e['id']=i; e['extra']['nodeId']='c'+i
    ip = copy.deepcopy(e['extra']['imageProperties']); ip['value'] = dict(ip.get('value', {}))
    ip['value']['url'] = url; ip['value']['altText'] = alt; ip['value']['compression'] = True
    e['extra']['imageProperties'] = ip
    e['styles']['borderRadius'] = {'value': f'{radius}px'}
    e['styles']['textAlign'] = {'value': align}
    if full:
        e['styles']['width'] = {'value': 100, 'unit': '%'}
    elif width:
        e['styles']['width'] = {'value': width, 'unit': 'px'}
    e['wrapper'] = _wrap(mt=mt, mb=mb, align=align); e['mobileStyles']={}; e['mobileWrapper']={}
    e['extra']['imageProperties']['value']['url'] = url   # re-fija (clear_foreign pudo tocar el 'element')
    return e

def code(raw_html, mt=0, mb=0):
    """Bloque Custom HTML/Javascript (para lo que el builder no tiene nativo:
    sliders, galerías con lightbox, widgets). NO es editable visualmente —
    úsalo solo donde la fidelidad lo exija (enfoque híbrido)."""
    e = clear_foreign(copy.deepcopy(T['code'])); i = nid('custom-code'); e['id']=i; e['extra']['nodeId']='c'+i
    e['extra']['customCode'] = {'value': {'rawCustomCode': raw_html}}
    e['wrapper'] = _wrap(mt=mt, mb=mb); e['mobileStyles']={}; e['mobileWrapper']={}
    return e

def form(form_id, label='Formulario'):
    e = clear_foreign(copy.deepcopy(FORM)); i = nid('form'); e['id']=i; e['extra']['nodeId']='c'+i
    e['extra']['formId'] = {'value': form_id, 'text': label}
    e['extra']['action'] = {'value':'none'}
    e['wrapper'] = _wrap(mt=0, mb=0); e['mobileStyles']={}; e['mobileWrapper']={}
    return e

# ---------- contenedores (elements[] plano cableado por child) ----------
class Sec:
    def __init__(self): self.flat = []
    def add(self, node): self.flat.append(node); return node['id']
    def col(self, child_ids, width=100, styles=None):
        c = clear_foreign(copy.deepcopy(T['col'])); i = nid('col'); c['id']=i
        c['child'] = list(child_ids)
        c['styles'] = c.get('styles', {})
        c['styles']['width'] = {'value': width, 'unit':'%'}
        c['styles']['paddingTop']={'unit':'px','value':0}; c['styles']['paddingBottom']={'unit':'px','value':0}
        c['styles']['paddingLeft']={'unit':'px','value':8}; c['styles']['paddingRight']={'unit':'px','value':8}
        c['styles']['textAlign'] = {'value':'center'}
        if styles: c['styles'].update(styles)
        c['mobileStyles']={}; c['mobileWrapper']={}
        self.flat.append(c); return i
    def row(self, col_ids, styles=None):
        r = clear_foreign(copy.deepcopy(T['row'])); i = nid('row'); r['id']=i
        r['child'] = list(col_ids); r['styles'] = r.get('styles', {})
        if styles: r['styles'].update(styles)
        r['mobileStyles']={}; r['mobileWrapper']={}
        self.flat.append(r); return i

def card_col(s, child_ids, width, bg='var(--white)', border=CARDBORDER, radius=14, pad=16):
    """Columna-tarjeta: fondo blanco opaco + borde + radio (bg debe ser un var(--...))."""
    return s.col(child_ids, width=width, styles={
        'backgroundColor':{'value':bg}, 'background':{'value':'none'},
        'borderColor':{'value':border}, 'borderWidth':{'value':'1px'}, 'borderStyle':{'value':'solid'},
        'borderRadius':{'value':f'{radius}px'},
        'paddingTop':{'unit':'px','value':pad}, 'paddingBottom':{'unit':'px','value':pad},
        'paddingLeft':{'unit':'px','value':pad}, 'paddingRight':{'unit':'px','value':pad}})

def section(build_fn, bg='var(--white)', bg_css=None, pad_t=38, pad_b=38, sec_id=None):
    """build_fn(s:Sec)->[row_ids]. bg = var(--...) para color sólido opaco;
    bg_css = string CSS completo (con url()) para imagen de fondo."""
    s = Sec(); row_ids = build_fn(s)
    meta = clear_foreign(copy.deepcopy(SECMETA))
    sid = sec_id or nid('section'); meta['id']=sid; meta['_id']=sid
    meta['child'] = list(row_ids)
    st = meta.get('styles', {})
    if bg_css:
        st['backgroundColor'] = {'value':'var(--transparent)'}; st['background'] = {'value': bg_css}
    else:
        st['backgroundColor'] = {'value': bg}; st['background'] = {'value':'none'}
    st['paddingTop']={'unit':'px','value':pad_t}; st['paddingBottom']={'unit':'px','value':pad_b}
    st['paddingLeft']={'unit':'px','value':16}; st['paddingRight']={'unit':'px','value':16}
    meta['styles'] = st; meta['mobileStyles']={}; meta['mobileWrapper']={}
    return {'id':sid, 'metaData':meta, 'elements':s.flat, 'sequence':0}

# ---------- ensamblado / inyección ----------
def load_wrapper(path):
    """Carga el blob ACTUAL de la página (para reusar settings/general/pageStyles/fonts)."""
    return json.load(open(path))

def save_blob(base, sections, out_path):
    for i, sc in enumerate(sections): sc['sequence'] = i
    base['sections'] = sections
    json.dump(base, open(out_path, 'w'), ensure_ascii=False)
    n = sum(len(x['elements']) for x in sections)
    print('wrote', out_path, '| sections:', len(sections), '| nodes:', n)
    # aviso: verifica que no queden imágenes de la cuenta plantilla
    return out_path

def make_inject_js(location_id, funnel_id, page_id, blob, base=None):
    """Devuelve el JS para `playwright-cli run-code --filename` que inyecta el blob por
    autosave (captura token con navegación in-script). blob = dict del pageData."""
    payload = json.dumps(blob)
    url = f"{base or panel_base()}/location/{location_id}/page-builder/{page_id}?source=funnel"
    return ('''async page => {
  page.on(String.fromCharCode(100,105,97,108,111,103), d=>{try{d.accept();}catch(e){}});
  const PAGE_ID=%s, FUNNEL_ID=%s, URL=%s; const SRC=%s;
  let tok=null, rec=null;
  page.on('request',req=>{const h=req.headers();if(h['token-id']&&req.url().includes('backend.leadconnectorhq.com'))tok=h['token-id'];});
  page.on('response',async r=>{if(r.url().includes('/funnels/page/'+PAGE_ID)&&r.request().method()==='GET'){try{rec=JSON.parse(await r.text());}catch(e){}}});
  try{await page.goto(URL,{waitUntil:'domcontentloaded'});}catch(e){}
  await page.waitForTimeout(7000);
  if(!tok)return JSON.stringify({ok:false,reason:'no token'});
  const pv=(rec&&rec.pageVersion?rec.pageVersion:1)+1;
  const body={funnelId:FUNNEL_ID,pageData:SRC,pageVersion:pv,pageType:'draft',manualSave:true,integrations:{videoBackground:false,blogMeta:{categoryNavigationList:[],selectedBlogCategories:[]},popup:false}};
  const st=await page.evaluate(async ({pageId,body,tok})=>{const r=await fetch('https://backend.leadconnectorhq.com/funnels/builder/autosave/'+pageId,{method:'POST',headers:{'token-id':tok,'source':'WEB_USER','channel':'APP','version':'2021-07-28','content-type':'application/json','accept':'application/json, text/plain, */*'},body:JSON.stringify(body)});return r.status;},{pageId:PAGE_ID,body,tok});
  return JSON.stringify({ok:true,pv,status:st});
}''' % (json.dumps(page_id), json.dumps(funnel_id), json.dumps(url), payload))
