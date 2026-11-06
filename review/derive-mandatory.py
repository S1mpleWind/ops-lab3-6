"""Reconcile independent raw files; never rewrite original experiment output."""
from pathlib import Path
import csv,json,re,math,hashlib,subprocess,datetime
root=Path('/home/sbse/lab3')
required=['a2-base','a2-q100','a2-q50','a2-q60','a2-serial','a3-oom','a3-larger','a3-bounded','b0-one','b0-confirm','b1-fixed','b2-cpu','b2-qps','b3-sched','c1-stop','c2-default','c2-sensitive','c3-slow','c3-outlier','d1-naive','d1-graceful','d2-heal']
results={};issues=[]
for name in required:
 d=root/'runs'/name
 try: rows=list(csv.DictReader((d/'steps.csv').open()))
 except FileNotFoundError: issues.append(name+': missing steps.csv');continue
 phases=[x for x in rows if x['step']!='all'];allrow=next(x for x in rows if x['step']=='all')
 for col in ['sent','ok','http_err','timeout','net_err','dropped']:
  if sum(int(x[col]) for x in phases)!=int(allrow[col]):issues.append(name+': phase/all mismatch '+col)
 r={'start':int(phases[0]['start_unix']),'end':int(phases[-1]['end_unix']),'all':allrow,'phases':phases,'source':'runs/'+name+'/steps.csv'}
 if (d/'timeline.csv').exists():
  secs=list(csv.DictReader((d/'timeline.csv').open()));errs=sum(int(x['errors']) for x in secs)
  gap=sum(1 for x in secs if int(x['errors'])>0 or (x['p99_ms'] and float(x['p99_ms'])>200))
  for col in ['sent','ok']:
   if sum(int(x[col]) for x in secs)!=int(allrow[col]):issues.append(name+': timeline/all mismatch '+col)
  expected=sum(int(allrow[k]) for k in ['http_err','timeout','net_err'])
  if errs!=expected:issues.append(name+': timeline/all errors mismatch')
  summary=(d/'summary.md').read_text()
  m=re.search(r'实例·分钟（从创建算起，只计负载期间）：([0-9.]+)',summary)
  r.update(gap_seconds=gap,timeline_errors=errs,instance_minutes=float(m[1]) if m else None,summary='runs/'+name+'/summary.md')
  m=re.search(r'缺口共 (\d+) 秒',summary)
  if (int(m[1]) if m else 0)!=gap:issues.append(name+': summary/timeline gap mismatch')
  r['peak_phase']=max((x for x in phases if '~' not in x['target_rps']),key=lambda x:float(x['target_rps'])) if name.startswith('b') else None
 results[name]=r
payload={'generated':datetime.datetime.now().astimezone().isoformat(),'results':results,'issues':issues}
(root/'review/mandatory-derived.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
# Raw hashes make later review detect accidental edits; excludes this derived directory.
files=sorted(p for p in (root/'runs').rglob('*') if p.is_file())
(root/'review/raw-sha256.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in files))
print(json.dumps({'runs':len(results),'issues':issues},ensure_ascii=False,indent=2))
if issues:raise SystemExit(1)
