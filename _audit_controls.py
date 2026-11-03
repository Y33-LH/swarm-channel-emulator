"""控件审计：列出 index.html 中所有交互控件，并判断它是否在 UI 脚本中被真正接线。
未被引用的控件 = 潜在空壳（点了没反应）。只读分析，不改变工程。
"""
import re, json, sys
from pathlib import Path

UI = Path(r'D:/Swarm_20261023_step29/app/ui')
html = (UI / 'index.html').read_text(encoding='utf-8')
js_text = '\n'.join(p.read_text(encoding='utf-8') for p in UI.glob('*.js'))
css_text = '\n'.join(p.read_text(encoding='utf-8') for p in UI.glob('*.css'))

# 1) 找出每个 id 所属的页面 section
section_of = {}
cur = '(header/全局)'
for m in re.finditer(r'<section\s+id="([a-z]+)"|<(/?)section>|<header|</header>', html):
    if m.group(1):
        cur = m.group(1)
    elif m.group(0) == '</section>':
        cur = '(header/全局)'
    section_of[m.start()] = cur
starts = sorted(section_of)

def page_at(pos):
    sec = '(header/全局)'
    for s in starts:
        if s <= pos:
            sec = section_of[s]
        else:
            break
    return sec

# 2) 提取所有交互控件
rows = []
for m in re.finditer(r'<(button|select|input|textarea)\b([^>]*)>', html):
    tag, attrs = m.group(1), m.group(2)
    idm = re.search(r'id="([A-Za-z0-9_-]+)"', attrs)
    if not idm:
        continue
    cid = idm.group(1)
    typem = re.search(r'type="([a-z]+)"', attrs)
    label = ''
    tail = html[m.end():m.end() + 120]
    tm = re.match(r'>([^<]{0,40})', tail)
    if tm:
        label = tm.group(1).strip()
    if not label:
        pre = html[max(0, m.start() - 160):m.start()]
        lm = re.search(r'<label[^>]*>([^<]{0,40})', pre[::-1][:0] or pre)
        if lm:
            label = lm.group(1).strip()
    rows.append(dict(id=cid, tag=tag, type=typem.group(1) if typem else '',
                     page=page_at(m.start()), label=label[:40]))

# 3) 判断是否在 JS 中被引用（只算真实取值/绑定，不算纯文本出现）
def referenced(cid):
    needles = ["$('%s')" % cid, '$("%s")' % cid,
               "E('%s')" % cid,
               "getElementById('%s')" % cid,
               "'%s'" % cid]
    for n in needles:
        if n in js_text:
            return True
    return ('#' + cid) in js_text or ('#' + cid) in css_text

for r in rows:
    r['wired'] = referenced(r['id'])

unwired = [r for r in rows if not r['wired']]
print('交互控件总数（带 id）:', len(rows))
print('在 JS 中被引用:', len(rows) - len(unwired))
print('未被引用（疑似空壳）:', len(unwired))
print()
print('=== 按页面统计 ===')
from collections import Counter
c = Counter(r['page'] for r in rows)
for k, v in c.most_common():
    bad = sum(1 for r in rows if r['page'] == k and not r['wired'])
    print('  %-16s 共 %2d 个，其中未接线 %d' % (k, v, bad))
print()
print('=== 未接线控件明细 ===')
for r in unwired:
    print('  [%s] %-18s %-8s %s' % (r['page'], r['id'], r['tag'] + (':' + r['type'] if r['type'] else ''), r['label']))

Path(r'D:/Swarm_20261023_step29/_audit_controls.json').write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print('\n明细已写入 _audit_controls.json')
