from pathlib import Path
import re,ipaddress
root=Path('/home/sbse/lab3')
problem=[]
for base in ['LAB3.md','runs','review']:
 p=root/base
 for f in ([p] if p.is_file() else p.rglob('*')):
  if not f.is_file():continue
  try:s=f.read_text(errors='ignore')
  except OSError:continue
  for candidate in set(re.findall(r'(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])',s)):
   try:ip=ipaddress.ip_address(candidate)
   except ValueError:continue
   if ip.is_global:problem.append((str(f.relative_to(root)),candidate))
print('Global IPv4 references:',len(problem))
for name,ip in problem[:15]:print(name,ip)
