#!/usr/bin/env bash
set -euo pipefail
cd /home/sbse/lab3
export PROM=http://127.0.0.1:19090 GEN_CPUS=0
export PATH=/home/sbse/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.0.linux-amd64/bin:$PATH
exec > >(tee -a review/task-bcd-driver.log) 2>&1
PS4='+ $(date -Iseconds) ${LINENO}: '; set -x
LBPID=; SCPID=
stopscale(){ if [ -n "$SCPID" ]; then kill -TERM "$SCPID" 2>/dev/null || true; for i in $(seq 1 40); do kill -0 "$SCPID" 2>/dev/null || break; sleep 1; done; wait "$SCPID" || true; SCPID=; fi; }
startlb(){ if [ -n "$LBPID" ]; then kill "$LBPID"; wait "$LBPID" || true; fi; taskset -c 0 bin/lbd -addr 127.0.0.1:18080 "$@" >> review/lbd.log 2>&1 & LBPID=$!; sleep 4; }
startscale(){ stopscale; taskset -c 0 bin/scaler -prom "$PROM" -cpus 1 "$@" >> review/scaler.log 2>&1 & SCPID=$!; for i in $(seq 1 150); do sleep 1; if curl -sf http://127.0.0.1:8090/backends | python3 -c 'import json,sys; a=json.load(sys.stdin); a=a.get("backends",[]) if isinstance(a,dict) else a; sys.exit(0 if a and all(x.get("up") for x in a) else 1)'; then return; fi; done; echo READY_TIMEOUT; return 1; }
run(){ scripts/run3.sh "$1" -url http://127.0.0.1:18080/api/courses/1 "${@:2}"; }
startlb
startscale -mode fixed -replicas 1
run b0-confirm -rates 80,100,120,140,160,180 -step 20s
python3 - <<'PY'
import csv,json,math
rs=[r for r in csv.DictReader(open('runs/b0-confirm/steps.csv')) if r['step']!='all']
good=[r for r in rs if float(r['error_rate'])==0 and float(r['ok_rps'])>0]
if not good: raise SystemExit('No error-free B0 phase; review required')
u=max(float(r['ok_rps']) for r in good); C=0.7*u; P=round(4*C/10)*10; base=max(1,round(P/10)); load=round(2*C)
json.dump(dict(upper=u,C=C,P=P,base=base,load=load),open('review/capacity.json','w'),indent=2)
open('review/capacity.env','w').write(f'C={C}\nP={P}\nBASE={base}\nLOAD={load}\n')
PY
source review/capacity.env
PLAN=$(scripts/plan.sh "$BASE" "$P")
cat > runs/predictions/b-confirm.md <<EOF
# B prediction before B1-B3
B0 calibration: review/capacity.json. Plan: $PLAN. Peak needs ceil(P/C) about 4 instances. Reactive metric/decision delay about 0-35s plus 20s pull plus 60-65s readiness; total about 85-120s after rise starts. Deficit roughly 60-120s, depends on headroom and health failures. Scheduled increase at +20s gives about 100s before ramp at +120s. Constant four instances should minimize deficit but cost ~42 instance-min; reactive costs less but catches up late. Compare both CPU and per-instance arrival signal on identical plan. Prediction is approximate, frozen before measurement.
EOF
CPU='avg(rate(cgroup_cpu_usage_seconds_total{job="instances"}[15s])) / ${quota}'
QPS='sum(rate(lb_requests_total{backend!="none"}[15s])) / count(up{job="instances"} == 1)'
startscale -mode fixed -replicas 4; run b1-fixed -plan "$PLAN"
startscale -mode reactive -min 2 -max 4 -signal "$CPU"; run b2-cpu -plan "$PLAN"
startscale -mode reactive -min 2 -max 4 -target "$C" -signal "$QPS"; run b2-qps -plan "$PLAN"
startscale -mode reactive -min 2 -max 4 -schedule '+20s=4,+480s=2' -signal "$CPU"; run b3-sched -plan "$PLAN"
cat > runs/predictions/c.md <<EOF
# C prediction before injection
Constant arrival $LOAD ~2C, 3 replicas. Kill may be discovered by scaler and removed before health failure threshold. Pause 20s should fail 3 checks roughly 2-4.5s after injection; errors roughly arrival/3 x detection latency, plus timeouts already in flight. Pausing all 2s may be tolerated by fall=3 but fall=1/500ms/200ms can remove all and cause 503; faster detection can increase false positives. Slow instance around 85% CPU should increase latency while lightweight readiness passes; passive ejection can reduce p99 but reduces capacity and may oscillate.
EOF
startscale -mode fixed -replicas 3
(sleep 60; scripts/inject.sh kill 8102; sleep 100; scripts/inject.sh pause 8103 20) > review/c1-injection.log 2>&1 & INJ=$!
run c1-stop -plan "$LOAD@240s"; wait "$INJ"
# Capture baseline CPU by explicit range query from C1 first minute.
python3 - <<'PY'
import csv,json,urllib.request,urllib.parse
r=next(csv.DictReader(open('runs/c1-stop/steps.csv'))); t=float(r['start_unix'])+50
q='rate(cgroup_cpu_usage_seconds_total{job="instances"}[30s])'
u='http://127.0.0.1:19090/api/v1/query?'+urllib.parse.urlencode({'query':q,'time':t})
a=json.load(urllib.request.urlopen(u));json.dump(a,open('review/c1-baseline-cpu.json','w'),indent=2)
vals=[float(x['value'][1]) for x in a['data']['result'] if '8102' in str(x['metric'])]
if not vals: raise SystemExit('Missing 8102 baseline CPU')
U=vals[0]; Q=max(1,min(24,round(U/0.85*100)))
json.dump(dict(U=U,slow_quota_percent=Q),open('review/c3-calibration.json','w'),indent=2)
open('review/slow.env','w').write(f'SLOW={Q}\n')
PY
startscale -mode fixed -replicas 3
startlb; sleep 10
(sleep 40; scripts/inject.sh pause all 2) > review/c2-default-injection.log 2>&1 & INJ=$!
run c2-default -plan "$LOAD@120s"; wait "$INJ"
startlb -check-interval 500ms -check-timeout 200ms -fall 1; sleep 10
(sleep 40; scripts/inject.sh pause all 2) > review/c2-sensitive-injection.log 2>&1 & INJ=$!
run c2-sensitive -plan "$LOAD@120s"; wait "$INJ"
source review/slow.env
for MODE in slow outlier; do
 if [ "$MODE" = outlier ]; then startlb -outlier; else startlb; fi; sleep 10
 (sleep 60; scripts/inject.sh slow 8102 "$SLOW"; sleep 120; scripts/inject.sh restore 8102 25) > review/c3-$MODE-injection.log 2>&1 & INJ=$!
 run c3-$MODE -plan "$LOAD@240s"; wait "$INJ"
done
cat > runs/predictions/d.md <<EOF
# D prediction before rollout and leak runs
Three serial graceful replacements: roughly 3 x (20s pull+60s warmup+2-5s readiness+2s drain) ~252-270s; naive starts replacement every 5s and does not wait readiness, likely loses capacity of all replicas for ~60s, with 503 and connections reset. Graceful temporarily uses a fourth replica and takes longer but preserves ready capacity. D2 arrival $LOAD, each replica leaks LOAD/3*16 KiB/s. Approximate OOM time (64MiB-baseline-GC transient)/(LOAD/3*16KiB/s), likely tens of seconds; GC cannot free intentional retained leak. Similar arrival per instance may synchronize OOM and invalidate independent-failure assumptions. Alert on changes(process_start_time_seconds[10m]), cross-check NRestarts and instances.csv; scrape can miss fast restarts.
EOF
startlb; startscale -mode fixed -replicas 3
(sleep 30; curl -fsS -X POST '127.0.0.1:8091/rollout?version=v2&mode=naive') > review/d1-naive-rollout.log 2>&1 & INJ=$!
run d1-naive -plan "$LOAD@180s"; wait "$INJ"
startscale -mode fixed -replicas 3
(sleep 30; curl -fsS -X POST '127.0.0.1:8091/rollout?version=v3&mode=graceful') > review/d1-graceful-rollout.log 2>&1 & INJ=$!
run d1-graceful -plan "$LOAD@420s"; wait "$INJ"
startscale -mode fixed -replicas 3 -restart on-failure -memory 64M -args '-warmup 10s -work 1000000 -leak-kb 16'
run d2-heal -plan "$LOAD@480s"
for p in 8101 8102 8103; do systemctl show -p NRestarts lab3-inst-$p; done > runs/d2-heal/systemd-restarts.txt
curl -fsSG "$PROM/api/v1/query" --data-urlencode 'query=sum(changes(process_start_time_seconds{job="instances"}[10m]))' > runs/d2-heal/restart-query.json
stopscale
kill "$LBPID"; wait "$LBPID" || true
chown -R sbse:sbse review runs data
echo TASK_BCD_COMPLETE
