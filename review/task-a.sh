#!/usr/bin/env bash
set -euo pipefail
cd /home/sbse/lab3
export PATH=/home/sbse/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.0.linux-amd64/bin:$PATH
export PROM=http://127.0.0.1:19090 GEN_CPUS=0
mkdir -p review runs/preflight runs/predictions data
exec > >(tee -a review/task-a-driver.log) 2>&1
PS4='+ $(date -Iseconds) ${LINENO}: '; set -x
{ date -Iseconds; stat -fc %T /sys/fs/cgroup; cat /sys/fs/cgroup/cgroup.controllers; systemctl --version | head -n 1; lscpu; free -m; swapon --show; uname -r; cat /etc/os-release; go version; tools/prometheus --version; tools/node_exporter --version; } > runs/preflight/host.txt 2>&1
python3 - <<'PY'
p='deploy/queries-red.txt'
s=open(p).read().replace('throttle_ratio      TODO','throttle_ratio      rate(cgroup_cpu_throttled_periods_total{job="enrolld"}[${window}]) / rate(cgroup_cpu_periods_total{job="enrolld"}[${window}])')
open(p,'w').write(s)
PY
cat > runs/predictions/a1.md <<'EOF'
# A1 prediction (before measurement)
0.5 core x 100 ms = 50 ms CPU budget. One busy thread runs about 50 ms and waits 50 ms; two truly concurrent busy threads each run 25 ms and wait 75 ms. GOMAXPROCS expected 2 on this two-vCPU machine due to Go minimum; shared SMT and scheduling can change wall time. Preserve this prediction unchanged.
EOF
for n in 1 2; do systemd-run --quiet --scope -p CPUQuota=50% bin/enrolld -burn "$n" -for 10s 2>&1 | tee runs/preflight/a1-burn-$n.txt; done
if ! curl -sf http://127.0.0.1:19090/-/ready; then
 taskset -c 0 tools/prometheus --config.file=deploy/prometheus.yml --storage.tsdb.path=/dev/shm/lab3-prom --web.listen-address=127.0.0.1:19090 > review/prometheus.log 2>&1 & echo $! > review/prometheus.pid
fi
stopa(){ systemctl stop lab3-a 2>/dev/null || true; systemctl reset-failed lab3-a 2>/dev/null || true; sleep 2; }
starta(){ systemd-run --unit=lab3-a "$@" "$PWD/bin/enrolld" -addr 127.0.0.1:8081 -data "$PWD/data/a" "${ARGS[@]}"; sleep 8; curl -fsS http://127.0.0.1:8081/config; }
stopa; ARGS=(-work 2000000); starta -p CPUQuota=100% -p MemoryMax=256M
scripts/run.sh a2-base -url http://127.0.0.1:8081/api/courses/1 -rates 30,60 -step 20s
R=$(python3 - <<'PY'
import csv,math,json
rs=list(csv.DictReader(open('runs/a2-base/red.csv')))
r=next(x for x in reversed(rs) if x.get('cpu_ms_per_req') and float(x['cpu_ms_per_req'])>0)
c=float(r['cpu_ms_per_req']); R=max(1,round(400/c))
json.dump({'cpu_ms_per_req':c,'R':R,'quota_fix':60},open('review/a2-calibration.json','w'),indent=2)
print(R)
PY
)
cat > runs/predictions/a2.md <<EOF
# A2 prediction (before quota change)
Measured CPU per request and chosen R: see review/a2-calibration.json. R=$R, expected mean CPU about 0.4 core. Bursts and parallel execution can exhaust 50 ms within a 100 ms period, increasing p99 despite average below 0.5 core. Throttled-period ratio is workload-dependent, plausibly 0.1-0.8; not simply mean/quota. Raising quota to 60% (ceil(0.4/0.7*100)) should reduce throttling; GOMAXPROCS=1 should spread execution but may reduce parallel capacity.
EOF
scripts/run.sh a2-q100 -url http://127.0.0.1:8081/api/courses/1 -rates "$R,$R" -step 20s
systemctl set-property --runtime lab3-a CPUQuota=50%
scripts/run.sh a2-q50 -url http://127.0.0.1:8081/api/courses/1 -rates "$R,$R" -step 20s
systemctl set-property --runtime lab3-a CPUQuota=60%
scripts/run.sh a2-q60 -url http://127.0.0.1:8081/api/courses/1 -rates "$R,$R" -step 20s
stopa; ARGS=(-work 2000000); starta -p CPUQuota=50% -p MemoryMax=256M --setenv=GOMAXPROCS=1
scripts/run.sh a2-serial -url http://127.0.0.1:8081/api/courses/1 -rates "$R,$R" -step 20s
cat > runs/predictions/a3.md <<'EOF'
# A3 prediction (before measurement)
Little's Law: 10/20/30 rps x 0.5s = 5/10/15 mean concurrent reports, 40/80/120 MiB live payload. Max concurrency exceeds the mean; no finite deterministic maximum for randomized arrivals. GOGC=100 allows heap approaching 2x live plus baseline; 200MiB may OOM at 20 or 30 rps, with transient/GC variability. RSS is not identical to cgroup memory.current. Increase limit based on measured max concurrency and GC factor plus 10%; alternatively cap concurrency conservatively at 8 (128MiB payload with 2x factor, allowing baseline under 200MiB), returning 503 on excess.
EOF
stopa; ARGS=(); starta -p MemoryMax=200M -p MemorySwapMax=0
scripts/run.sh a3-oom -url 'http://127.0.0.1:8081/api/report?mb=8&ms=500' -rates 10,20,30 -step 20s || echo 'OOM_RUN_EXIT_REVIEW'
{ systemctl show -p ActiveState,Result,ExecMainStatus lab3-a; journalctl -u lab3-a --no-pager -n 30; dmesg | grep -i -E 'oom-kill|killed process' | tail -n 8; } > runs/a3-oom/oom-evidence.txt
LIMIT=$(python3 - <<'PY'
import csv,math,json
rows=list(csv.DictReader(open('runs/a3-oom/red.csv')))
n=max([float(r['report_inflight_max']) for r in rows if r.get('report_inflight_max') and r.get('target_rps')=='20'] or [20])
limit=math.ceil((n*8*2+40)*1.1/16)*16
json.dump({'max_inflight_at_20':n,'baseline_allowance_MiB':40,'limit_MiB':limit},open('review/a3-limit.json','w'),indent=2)
print(limit)
PY
)
stopa; ARGS=(); starta -p MemoryMax=${LIMIT}M -p MemorySwapMax=0
scripts/run.sh a3-larger -url 'http://127.0.0.1:8081/api/report?mb=8&ms=500' -rates 10,20,30 -step 20s
stopa; ARGS=(-report-max 8); starta -p MemoryMax=200M -p MemorySwapMax=0
scripts/run.sh a3-bounded -url 'http://127.0.0.1:8081/api/report?mb=8&ms=500' -rates 10,20,30 -step 20s
stopa
chown -R sbse:sbse review runs deploy/queries-red.txt data
echo TASK_A_COMPLETE
