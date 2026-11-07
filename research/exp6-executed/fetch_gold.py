"""Download OSWorld's gold/expected files for the Exp 6 subset (used only by the official-checker run)."""
import json, glob, os, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
SUBSET = ['42e0a640','1273e544','6054afcb','a9f325aa','f23acfd2','57667013','21760ecb',
          'd53ff5ee','88fe4b2d','936321ce','ecc2413d','4d117223','23393935',
          # Exp 6 blind-state tasks not listed above (22 of the 34 blind tasks): gold for the official checker
          '0326d92d','06ca5602','08c73485','26150609','386dbd0e','51719eea','550ce7e7',
          '554785e9','5bc63fb9','66399b0d','6a33f9b9','6ed0a554','7ae48c60','8e116af7','9b7bc335',
          'd68204bf','dd84e895','e2dd0213','f201fbc3','f4aec372','f918266a','fba2c100']
jobs = []
for f in glob.glob(os.path.join(HERE, '..', 'OSWorld', 'evaluation_examples', 'examples', '*', '*.json')):
    tid = os.path.basename(f)[:-5]
    if not any(tid.startswith(s) for s in SUBSET): continue
    ev = json.load(open(f)).get('evaluator', {})
    exps = ev.get('expected', [])
    exps = exps if isinstance(exps, list) else [exps]
    for e in exps:
        if isinstance(e, dict) and e.get('type') == 'cloud_file':
            jobs.append((tid[:8], e['path'], e['dest']))
def get(j):
    tid, url, dest = j
    d = os.path.join(HERE, 'osworld_gold', tid, dest)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.exists(d) and os.path.getsize(d) > 0: return tid, dest, 'cached'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as r, open(d, 'wb') as o: o.write(r.read())
        return tid, dest, 'ok'
    except Exception as ex:
        return tid, dest, 'FAIL ' + str(ex)[:100]
with cf.ThreadPoolExecutor(6) as ex:
    for r in ex.map(get, jobs): print(*r)
