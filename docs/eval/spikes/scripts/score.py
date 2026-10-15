import json, sys

A = '/tmp/hp-eval/artifacts/r4'
gt = json.load(open(f'{A}/ground-truth.json'))
win = json.load(open(f'{A}/windows.json'))
hits = json.load(open(f'{A}/hits.json'))

hit_lines = {}
rule_hits = {}
for r in hits['results']:
    f = r['path']
    ln = r['start']['line']
    hit_lines.setdefault(f, set()).add(ln)
    rule_hits[r['check_id']] = rule_hits.get(r['check_id'], 0) + 1

def in_window(f, ln):
    return any(a <= ln <= b for a, b in win.get(f, [[1, 10**9]]))

scored = {f: {l for l in ls if in_window(f, l)} for f, ls in hit_lines.items()}
unscored = {f: {l for l in ls if not in_window(f, l)} for f, ls in hit_lines.items()}

total_annot = sum(len(v) for v in gt.values())
tp0 = fp0 = 0
tp2 = fp2 = 0
for f, ls in scored.items():
    g = set(gt.get(f, []))
    for l in ls:
        if l in g:
            tp0 += 1; tp2 += 1
        else:
            if any(abs(l - x) <= 2 for x in g):
                tp2 += 1
            else:
                fp0 += 1; fp2 += 1
    missed_hits = {g for g in gt.get(f, []) if not any(abs(l - hline) <= 2 for hline in ls)}
    if missed_hits:
        print(f'MISS file {f}: {sorted(missed_hits)}', file=sys.stderr)

rec0 = sum(1 for f, ls in gt.items() for l in ls if l in scored.get(f, set()))
rec2 = sum(1 for f, ls in gt.items() for l in ls
           if any(abs(l - h) <= 2 for h in scored.get(f, set())))
prec0 = tp0 / (tp0 + fp0) if tp0 + fp0 else 0.0
prec2 = tp2 / (tp2 + fp2) if tp2 + fp2 else 0.0

print(f'annotated_lines={total_annot}')
print(f'recall_0={rec0}/{total_annot}={rec0/total_annot:.3f}')
print(f'recall_2={rec2}/{total_annot}={rec2/total_annot:.3f}')
print(f'scored_hit_lines={tp0+fp0} (tp0={tp0} fp0={fp0})')
print(f'precision_0={prec0:.3f}')
print(f'precision_2={prec2:.3f}')
print(f'unscored_hit_lines={sum(len(v) for v in unscored.values())}')
print('raw_hits=%d raw_hit_lines=%d' % (len(hits['results']), sum(len(v) for v in hit_lines.values())))
print('hits_per_rule:')
for k, v in sorted(rule_hits.items()):
    print(f'  {v:4d}  {k}')

print('\nPER-FILE recall_0/recall_2/annot/hitlines(scored):')
for f, ls in gt.items():
    g = set(ls)
    h = scored.get(f, set())
    r0 = sum(1 for l in g if l in h)
    r2 = sum(1 for l in g if any(abs(l - x) <= 2 for x in h))
    print(f'  {f}: {r0}/{len(g)} / {r2}/{len(g)}  scored_hit_lines={len(h)}')

print('\nMISSES (annotated, no hit within +-2), first 10:')
n = 0
for f, ls in gt.items():
    h = scored.get(f, set())
    for l in sorted(ls):
        if not any(abs(l - x) <= 2 for x in h):
            print(f'  {f}:{l}')
            n += 1
            if n >= 10: break
    if n >= 10: break

print('\nFPS (scored hit lines not within +-2 of annotation), first 10:')
n = 0
for f, ls in sorted(scored.items()):
    g = gt.get(f, [])
    for l in sorted(ls):
        if not any(abs(l - x) <= 2 for x in g):
            print(f'  {f}:{l}')
            n += 1
            if n >= 10: break
    if n >= 10: break
