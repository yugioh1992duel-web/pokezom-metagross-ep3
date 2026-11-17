import json, os, shutil

B = os.path.dirname(os.path.abspath(__file__))
words = json.load(open(os.path.join(B, 'word_timings_v2.json')))['words']
types = json.load(open('/home/hatch/workspace/pokezom_factory/types.json'))
template = open(os.path.join(B, 'template', 'index.html')).read()
anchors = json.load(open(os.path.join(B, 'anchors.json')))
GOLD = {"3", "600", "700", "150", "110", "eight", "gold", "shadow", "shiny", "mega",
        "metagross", "beldum", "metang", "cipher", "nascour", "steven", "seventy-eight",
        "meteor", "mash", "clear", "tough", "claws", "catch", "supercomputer", "heart",
        "colosseum", "champion", "mossdeep", "ultra", "balls", "jet", "legendaries",
        "realgam", "salamence", "golden", "x"}

# ---- caption dictionary pass: whisper garbles -> script-canonical spellings ----
FIX = {'beltem': 'Beldum', 'beldam': 'Beldum', 'beldom': 'Beldum', 'beldum': 'Beldum',
       'matang': 'Metang', 'metang': 'Metang', 'metagross': 'Metagross',
       'nazcor': 'Nascour', 'nascor': 'Nascour', 'nascour': 'Nascour',
       'cypher': 'Cipher', 'cipher': 'Cipher', 'pokemon': 'Pokémon', 'pokedex': 'Pokédex',
       'hoenn': 'Hoenn', 'gamecube': 'GameCube', 'colosseum': 'Colosseum',
       'mossdeep': 'Mossdeep', 'realgam': 'Realgam', 'axe': 'X',
       'tyranitar': 'Tyranitar', 'dragonite': 'Dragonite', 'salamence': 'Salamence',
       'mewtwo': 'Mewtwo', 'rayquaza': 'Rayquaza', 'steven': 'Steven',
       'emerald': 'Emerald', 'ruby': 'Ruby', 'sapphire': 'Sapphire'}
MERGE = {('pseudo', '-legendary'): 'pseudo-legendary', ('half', 'asly'): 'half-asleep',
         ('real', 'gametower'): 'Realgam Tower'}
LEVELNUM = {'20': 'twenty', '45': 'forty-five', '50': 'fifty', '58': 'fifty-eight', '78': 'seventy-eight'}

def fix_words(ws):
    out, i = [], 0
    while i < len(ws):
        w = ws[i]; raw = w['w']; core = raw.strip('.,!?'); trail = raw[len(raw.rstrip('.,!?')):] if raw.rstrip('.,!?') != raw else ''
        low = core.lower()
        nxt = ws[i + 1]['w'].strip('.,!?').lower() if i + 1 < len(ws) else ''
        prv = ws[i - 1]['w'].strip('.,!?').lower() if i > 0 else ''
        if (low, nxt) in MERGE:
            merged = MERGE[(low, nxt)]
            t2 = ws[i + 1]['w']; tr2 = t2[len(t2.rstrip('.,!?')):] if t2.rstrip('.,!?') != t2 else ''
            out.append({'w': merged + tr2, 's': w['s'], 'e': ws[i + 1]['e']}); i += 2; continue
        if low == '50' and nxt == 'ultra':
            out.append({'w': 'fifty' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == '1200':
            out.append({'w': 'twelve hundred' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low in LEVELNUM and prv == 'level':
            out.append({'w': LEVELNUM[low] + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == 'ultra' and nxt in ('balls', 'ball'):
            out.append({'w': 'Ultra' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == 'balls' and prv == 'ultra':
            out.append({'w': 'Balls' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == 'mega' and nxt in ('metagross', 'evolution', 'evolves', 'evolve'):
            out.append({'w': 'Mega' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == 'shadow' and nxt in ('metagross', 'pokémon', 'pokemon', 'tyranitar'):
            out.append({'w': 'Shadow' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low == 'go' and prv in ('pokemon', 'pokémon'):
            out.append({'w': 'GO' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        poss = low.endswith("'s")
        base = low[:-2] if poss else low
        if base in FIX:
            rep = FIX[base] + ("'s" if poss else '')
            parts = rep.split(' ')
            parts[-1] = parts[-1] + trail
            out.append({'w': ' '.join(parts), 's': w['s'], 'e': w['e']}); i += 1; continue
        out.append(w); i += 1
    return out

def merge_tokens(ws):
    # ASR splits hyphenated words / numbers / percents into fragments
    # ('1' ',200' '-pound', '20' '%', 'mid' '-air'): rejoin so captions never
    # show a space before the fragment or start a line with one.
    out = []
    for w in ws:
        if out and (w['w'].startswith(('-', ',', '%'))):
            p = out[-1]
            out[-1] = {'w': p['w'] + w['w'], 's': p['s'], 'e': w['e']}
        else:
            out.append(dict(w))
    return out

def captions(start, end):
    ws = merge_tokens([w for w in fix_words(words) if start <= w['s'] < end])
    chunks, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= 9 or (len(cur) >= 5 and w['w'].rstrip().endswith(('.', '!', '?'))):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    # reflow: a split 'Episode 1.' must complete inside the first caption
    for i in range(len(chunks) - 1):
        if chunks[i] and chunks[i + 1] and chunks[i][-1]['w'].lower().strip('.,!?') == 'episode' \
                and chunks[i + 1][0]['w'].strip() in ('1.', '1'):
            chunks[i].append(chunks[i + 1].pop(0))
    chunks = [c for c in chunks if c]
    return [[round(c[0]['s'] - start, 2), ' '.join(w['w'] for w in c),
             [round(w['s'] - start, 2) for w in c],
             [i for i, w in enumerate(c) if w['w'].lower().strip('.,!?') in GOLD]] for c in chunks]

# ---------- OPTICAL SCALING (Ep.2 solver) ----------
from PIL import Image as _Im
_PLACE_SPEC = {  # art: (bbox height fraction of 1080, art right edge, feet y)
 "Beldum": (0.62, 1885, 975), "Metang": (0.78, 1885, 965),
 "Metagross": (0.88, 1885, 975), "Shadow_Metagross": (0.88, 1885, 975),
 "Shiny_Metagross": (0.88, 1885, 975), "Mega_Metagross": (0.90, 1885, 980)}
def _place(art):
    im = _Im.open(os.path.join(B, "assets", art + ".png")).convert("RGBA")
    W, H = im.size; bb = im.getchannel("A").getbbox()
    frac, right, feet = _PLACE_SPEC[art]
    k = (frac * 1080) / (bb[3] - bb[1]); S = k * max(W, H)
    ox = (S - W * k) / 2; oy = (S - H * k) / 2
    return dict(size=int(round(S)), x=int(round(right - ox - bb[2] * k)), y=int(round(feet - oy - bb[3] * k)))
PLACE = {a: _place(a) for a in _PLACE_SPEC}
print("optical placements:", {a: (p["size"], p["x"], p["y"]) for a, p in PLACE.items()})

def gpos(art, fx, fy):
    p = PLACE[art]
    return int(round(p["x"] + fx * p["size"])), int(round(p["y"] + fy * p["size"]))

def hero(name, size=760, x=1080, y=185, tin=0.3, tout=None, sil=0, punch=None, white=False,
         evoIn=False, evoOutAt=None, moves=None, place=True, jet=None):
    h = {"art": name + ".png", "sil": name + "_sil.png", "x": x, "y": y, "size": size,
         "in": tin, "silUntil": sil, "idle": [tin + 1.2, 999]}
    if place and name in PLACE:
        h["size"], h["x"], h["y"] = PLACE[name]["size"], PLACE[name]["x"], PLACE[name]["y"]
    if tout is not None: h["out"] = tout
    if punch: h["punch"] = punch
    if white: h["white"] = name + "_white.png"
    if evoIn: h["evoIn"] = True
    if evoOutAt is not None: h["evoOutAt"] = evoOutAt
    if moves: h["moves"] = moves
    if jet: h["jet"] = jet
    return h

def hl(t, html, out, x=70, y=560, size=76): return {"at": t, "html": html, "out": out, "x": x, "y": y, "size": size}
def chip(t, html, out, x=70, y=858): return {"at": t, "html": html, "out": out, "x": x, "y": y}
def clip(seq, frames, t, dur, label=None, hideHud=False, x=520, y=250, w=880, h=494):
    c = {"dir": seq, "frames": frames, "at": t, "dur": dur, "mode": "framed"}
    if label: c["label"] = label
    c.update({"x": x, "y": y, "w": w, "h": h})
    if hideHud: c["hideHud"] = True
    return c

def still(img, at, out, label=None, x=70, y=545, w=700, h=330, fit=None):
    s = {"img": img, "at": at, "out": out, "x": x, "y": y, "w": w, "h": h}
    if label: s["label"] = label
    if fit: s["fit"] = fit
    return s

eye_x, eye_y = gpos("Metagross", *anchors['metagross_eye'])
shiny_x, shiny_y = gpos("Shiny_Metagross", *anchors['shiny_gold_x'])
print("gleam anchors: metagross eye", (eye_x, eye_y), "| shiny X", (shiny_x, shiny_y))

STEEL_PSY = ["Steel", "Psychic"]
# ---------- Ep.3 segment map (all beat times section-relative) ----------
SEGS = [
 dict(id='s0', start=0.0, dur=50.44, types=STEEL_PSY, formLabel="",
      heroes=[hero("Beldum", tin=0.9, tout=15.6, sil=99),
              hero("Metang", tin=15.6, tout=18.8, sil=99),
              hero("Metagross", tin=18.8, tout=25.9, sil=99),
              hero("Shadow_Metagross", tin=25.9, tout=28.5, sil=99),
              hero("Shiny_Metagross", tin=28.5, tout=36.1, sil=99),
              hero("Mega_Metagross", tin=36.1, tout=44.6, sil=99)],
      titleCard={"at": 44.9, "big": "EVERY METAGROSS", "sub": "EXPLAINED — AND RANKED", "out": 50.2}),
 dict(id='s1', start=50.44, dur=92.43, types=STEEL_PSY, formLabel="FORM 1 OF 6",
      heroes=[hero("Beldum", white=True, evoOutAt=90.8,
                   moves=[{"kind": "sway", "at": 2.0, "dur": 80}, {"kind": "shake", "at": 62.4}])],
      nameBlock={"name": "BELDUM", "sub": "THE IRON BALL POKÉMON · #374", "pills": STEEL_PSY, "at": 0.5},
      clips=[clip("seqBeldum", 126, 48.3, 5.25, "HOENN LEAGUE — MORRISON'S BELDUM", hideHud=True)],
      chips=[chip(25.5, "CATCH RATE <span class='gold'>3</span> — THE LOWEST IN THE SERIES", 33.0),
             chip(40.3, "<span class='gold'>50 ULTRA BALLS</span> — EVERY ONE BOUNCES OFF", 47.0),
             chip(68.0, "RUBY / SAPPHIRE / EMERALD: <span class='gold'>GIFT ONLY</span>", 75.5),
             chip(77.0, "LEFT BY THE CHAMPION IN <span class='gold'>MOSSDEEP CITY</span>", 84.0)]),
 dict(id='s2', start=142.87, dur=50.47, types=STEEL_PSY, formLabel="FORM 2 OF 6",
      heroes=[hero("Metang", white=True, evoIn=True, evoOutAt=49.2, jet={"at": 31.4},
                   moves=[{"kind": "sway", "at": 2.5, "dur": 40}])],
      nameBlock={"name": "METANG", "sub": "THE IRON CLAW POKÉMON · #375", "pills": STEEL_PSY, "at": 0.5},
      clips=[clip("seqMetang", 168, 40.9, 7.0, "HOENN LEAGUE — MORRISON'S METANG", hideHud=True)],
      chips=[chip(10.2, "TWO BELDUM <span class='gold'>FUSED</span> — BRAINS WIRED BY MAGNETS", 17.0),
             chip(18.5, "TOTAL STATS <span class='gold'>420</span>", 24.0),
             chip(25.5, "STEEL ARMOR: <span class='gold'>JET-PROOF</span> — NOT A SCRATCH", 31.0)]),
 dict(id='s3', start=193.34, dur=81.77, types=STEEL_PSY, formLabel="FORM 3 OF 6",
      heroes=[hero("Metagross", white=True, evoIn=True, punch=65.7)],
      nameBlock={"name": "METAGROSS", "sub": "THE IRON LEG POKÉMON · #376", "pills": STEEL_PSY, "at": 0.5},
      clips=[clip("seqMetagross", 154, 55.3, 6.42, "HOENN LEAGUE FINAL — TYSON'S METAGROSS", hideHud=True)],
      gleams=[{"x": eye_x, "y": eye_y, "at": 16.9, "size": 150, "color": "#ff5a4d", "n": 2}],
      quoteCard={"at": 14.2, "text": "Metagross has four brains in total. Combined, the four brains can breeze through difficult calculations faster than a supercomputer. This Pokémon can float in the air by tucking in its four legs.", "src": "POKÉDEX — POKÉMON RUBY", "out": 26.5},
      statAnim={"at": 27.9, "from": 0, "to": 600, "label": "TOTAL STATS", "x": 70, "y": 798, "out": 34.0},
      chips=[chip(38.2, "<span class='gold'>1,212.5 LBS</span> — AS HEAVY AS A GRAND PIANO", 45.0),
             chip(56.8, "ABILITY: <span class='gold'>CLEAR BODY</span> — STATS CAN'T BE LOWERED", 63.0),
             chip(65.7, "SIGNATURE MOVE: <span class='gold'>METEOR MASH</span>", 72.0)],
      headlines=[hl(43.2, "IT EATS THROUGH A MOUTH<br/>ON ITS <span class='gold'>STOMACH</span>", 50.0)]),
 dict(id='s4', start=275.11, dur=65.76, types=STEEL_PSY, formLabel="FORM 4 OF 6", mood="shadow",
      heroes=[hero("Shadow_Metagross", moves=[{"kind": "shake", "at": 34.1}])],
      nameBlock={"name": "SHADOW METAGROSS", "sub": "POKÉMON COLOSSEUM · CIPHER'S WEAPON", "pills": STEEL_PSY, "at": 0.5},
      chips=[chip(2.0, "ITS HEART WAS <span class='gold'>SLAMMED SHUT</span> BY CIPHER", 8.0),
             chip(15.8, "CIPHER ADMIN <span class='gold'>NASCOUR</span> — REALGAM TOWER", 22.0),
             chip(46.2, "<span class='gold'>+20% ATTACK</span>", 49.5),
             chip(48.2, "<span class='red'>−20% DEFENSE</span>", 52.0, x=540)],
      headlines=[hl(25.1, "SHADOW TYRANITAR'S BOSS<br/>FROM <span class='gold'>EPISODE ONE</span>", 32.0, y=690),
                 hl(55.0, "THE SAFETY IS <span class='gold'>OFF</span>", 63.0, y=705)]),
 dict(id='s5', start=340.87, dur=66.74, types=STEEL_PSY, formLabel="FORM 5 OF 6",
      habitat={"img": "hab_cave_dark.jpg", "in": 0.4, "out": 60.0, "shade": 0.35},
      nameScrim=True,
      heroes=[hero("Shiny_Metagross")],
      nameBlock={"name": "STEVEN'S METAGROSS", "sub": "THE CHAMPION'S PARTNER · STEVEN STONE", "pills": STEEL_PSY, "at": 0.5},
      gleams=[{"x": shiny_x, "y": shiny_y, "at": 28.0, "size": 170, "color": "#ffd94d", "n": 2}],
      stills=[still("still_steven.png", 8.8, 20.0, "STEVEN STONE — CHAMPION OF HOENN", x=70, y=670, w=235, h=330, fit="contain")],
      chips=[chip(33.6, "RUBY / SAPPHIRE: <span class='gold'>LEVEL 58</span> — THE CHAMPION'S ACE", 40.0, y=770),
             chip(46.1, "EMERALD: HIDING IN <span class='gold'>METEOR FALLS</span>", 52.0),
             chip(58.5, "NO REFEREE. <span class='gold'>NO CROWD.</span>", 64.5)],
      headlines=[hl(51.2, "LEVEL <span class='gold'>SEVENTY-EIGHT</span>", 58.0, y=712, size=96)]),
 dict(id='s6', start=407.61, dur=92.61, types=STEEL_PSY, formLabel="FORM 6 OF 6", mood="mega-x",
      nameScrim=True,
      heroes=[dict(hero("Mega_Metagross", punch=1.2), coreX=anchors['mega_gold_x'][0], coreY=anchors['mega_gold_x'][1])],
      nameBlock={"name": "MEGA METAGROSS", "sub": "MEGA EVOLUTION · OMEGA RUBY / ALPHA SAPPHIRE", "pills": STEEL_PSY, "at": 0.6},
      gleams=[{"x": 0, "y": 0, "at": 29.5, "size": 170, "color": "#ffd94d", "n": 2}],  # x/y filled below from PLACE
      chips=[chip(15.2, "<span class='gold'>EIGHT BRAINS</span> — THINKING AT THE SAME TIME", 22.0),
             chip(39.5, "DEFENSE <span class='gold'>150</span> — TOUGHER THAN TANK ARMOR", 45.0, y=758),
             chip(41.0, "SPEED <span class='gold'>70 → 110</span>", 47.5),
             chip(48.3, "ABILITY: <span class='gold'>TOUGH CLAWS</span> — CONTACT HITS +30%", 55.0)],
      statAnim={"at": 33.9, "from": 600, "to": 700, "label": "TOTAL STATS", "x": 70, "y": 845, "out": 38.0},
      quoteCard={"at": 73.6, "text": "Its intellect surpasses its previous level, resulting in battles so cruel, they'll make you want to cover your eyes.", "src": "POKÉDEX — POKÉMON ULTRA SUN", "out": 84.5, "hideName": True},
      headlines=[hl(85.5, "IT LOST ITS <span class='gold'>HEART</span> COMPLETELY", 91.5, y=705)]),
 dict(id='s7', start=500.22, dur=71.43, types=STEEL_PSY, formLabel="THE RANKING",
      ranking={"slots": [{"art": a, "x": 34 + i * 314, "y": 352, "w": 280, "num": 6 - i, "name": n, "in": 0.4 + i * 0.15}
                          for i, (a, n) in enumerate([("Beldum.png", "BELDUM"), ("Metang.png", "METANG"),
                                                       ("Shadow_Metagross.png", "SHADOW"), ("Shiny_Metagross.png", "STEVEN'S"),
                                                       ("Metagross.png", "METAGROSS"), ("Mega_Metagross.png", "MEGA METAGROSS")])],
               "hits": [{"idx": i, "t": t} for i, t in enumerate([3.79, 12.37, 20.55, 31.25, 42.23, 50.25])]},
      headlines=[hl(61.95, "YOUR TURN — <span class='gold'>VOTE BELOW!</span>", 71.0, x=480, y=124, size=84)]),
]
# fill Mega gleam position from the optical placement + gold-X anchor
gx, gy = gpos("Mega_Metagross", *anchors['mega_gold_x'])
for cfg in SEGS:
    if cfg['id'] == 's6':
        cfg['gleams'][0]['x'], cfg['gleams'][0]['y'] = gx, gy
print("mega gleam at", gx, gy)

for cfg in SEGS:
    cfg['world'] = cfg['types']
    cfg['duration'] = cfg['dur']
    cfg['captions'] = captions(cfg['start'], cfg['start'] + cfg['dur'])
    d = os.path.join(B, 'segments', cfg['id']); os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
    html = template.replace('/*__CONFIG__*/', json.dumps(cfg)).replace('/*__TYPES__*/', json.dumps(types)).replace('__DURATION__', str(cfg['dur']))
    open(os.path.join(d, 'index.html'), 'w').write(html)
    json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json", "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry", "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}, open(os.path.join(d, 'hyperframes.json'), 'w'), indent=2)
    arts = [h['art'][:-4] for h in cfg.get('heroes', [])] + [s['art'][:-4] for s in cfg.get('ranking', {}).get('slots', [])]
    for h in cfg.get('heroes', []):
        if h.get('sil'):
            _sp = os.path.join(B, 'assets', h['sil'])
            if os.path.exists(_sp): shutil.copy(_sp, os.path.join(d, 'assets', h['sil']))
    for a in set(arts):
        for suf in ('.png', '_sil.png', '_white.png'):
            src = os.path.join(B, 'assets', a + suf)
            if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', a + suf))
    for c in cfg.get('clips', []):
        shutil.copytree(os.path.join(B, 'assets', c['dir']), os.path.join(d, 'assets', c['dir']), dirs_exist_ok=True)
    for st in cfg.get('stills', []):
        src = os.path.join(B, 'assets', st['img'])
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', st['img']))
        else: print('MISSING STILL:', cfg['id'], st['img'])
    if cfg.get('habitat'):
        src = os.path.join(B, 'assets', cfg['habitat']['img'])
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', cfg['habitat']['img']))
        else: print('MISSING HABITAT:', cfg['id'], cfg['habitat']['img'])
    shutil.copy('/home/hatch/workspace/pokezom_tristorm_build/hf/assets/gsap.min.js', os.path.join(d, 'assets', 'gsap.min.js'))
    print(cfg['id'], 'ok, caps', len(cfg['captions']))
print('ALL SEGMENTS BUILT (Ep.3 v2)')
