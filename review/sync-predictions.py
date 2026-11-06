from pathlib import Path
import time,datetime
root=Path('/home/sbse/lab3');p=root/'LAB3.md'
sections={'b-confirm.md':'B1–B3 测量前预测（容量补测后）','c.md':'C 测量前预测','d.md':'D 测量前预测'}
seen=set()
while len(seen)<len(sections):
 for name,label in sections.items():
  f=root/'runs/predictions'/name
  if f.exists() and name not in seen:
   content=f.read_text()
   if len(content)<40:continue
   with p.open('a') as out:
    out.write('\n\n## '+label+'\n\n记录时间：'+datetime.datetime.now().astimezone().isoformat()+'；原文：`runs/predictions/'+name+'`。\n\n'+content+'\n')
   seen.add(name);print('Added before measurement:',name,flush=True)
 time.sleep(2)
