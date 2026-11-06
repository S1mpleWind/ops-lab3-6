"""Export supporting Prometheus evidence without changing official CSV outputs."""
from pathlib import Path
import csv,json,urllib.request,urllib.parse,datetime,sys
root=Path('/home/sbse/lab3')
queries={
 'instance_cpu':'rate(cgroup_cpu_usage_seconds_total{job="instances"}[30s])',
 'instance_memory':'cgroup_memory_current_bytes{job="instances"}',
 'instance_start':'process_start_time_seconds{job="instances"}',
 'instance_up':'up{job="instances"}',
 'backend_p99':'histogram_quantile(0.99,sum by (backend,le)(rate(lb_request_duration_seconds_bucket[30s])))',
 'backend_rps':'sum by (backend)(rate(lb_requests_total[15s]))',
 'backend_codes':'sum by (backend,code)(rate(lb_requests_total[15s]))',
 'instance_throttling':'rate(cgroup_cpu_throttled_periods_total{job="instances"}[30s])/rate(cgroup_cpu_periods_total{job="instances"}[30s])',
 'restart_changes':'sum(changes(process_start_time_seconds{job="instances"}[10m]))',
 'host_cpu':'rate(node_cpu_seconds_total{mode!="idle"}[30s])',
}
for run in sys.argv[1:]:
 d=root/'runs'/run
 rows=[r for r in csv.DictReader((d/'steps.csv').open()) if r['step']!='all']
 start=float(rows[0]['start_unix']); end=float(rows[-1]['end_unix'])
 out=d/'prometheus';out.mkdir(exist_ok=True)
 for name,q in queries.items():
  p=out/(name+'.json')
  if p.exists():continue
  args=dict(query=q,start=start,end=end,step=1)
  u='http://127.0.0.1:19090/api/v1/query_range?'+urllib.parse.urlencode(args)
  response=json.load(urllib.request.urlopen(u,timeout=60))
  evidence=dict(exported=datetime.datetime.now().astimezone().isoformat(),request=args,response=response)
  p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
 print(run,'exported',flush=True)
