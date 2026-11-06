# 实验 3 记录：第 6 组

仓库：https://github.com/S1mpleWind/ops-lab3-6

由用户委托 Codex 在小组真实 Linux 云主机执行。原始输出未编辑；预测原文件与执行时刻保留，最终报告整理时引用。成员负责实际核对、复现与讲解，不虚构个人执行记录。原始证据索引见 `review/README.md`。

## 1. 基本信息

| 项 | 内容 |
|---|---|
| 小组 | 第6组 |
| 主机 | 华为云；2vCPU、3719MiB；云商品规格名尚未从控制台核实 |
| CPU | Intel Xeon Platinum 8378C @2.80GHz；两个逻辑CPU属于同一物理核心的SMT |
| 内存与swap | total3719MiB；无swap |
| 操作系统、内核、systemd | Ubuntu22.04.5 LTS；5.15.0-186-generic；systemd249 |
| cgroup | cgroup2fs；cpu、memory控制器可用 |
| 工具 | Go1.26.0；Prometheus3.13.4；node_exporter1.12.1 |
| 分核 | 实例CPU1；loadgen、lbd、scaler、Prometheus CPU0；A2实例使用CPU0/1，按指导书记录共核局限 |
| 端口差异 | Lab3业务入口18080，Prometheus19090；实例8081/8101起、管理8090/8091。避免冲突，不改变实验机制 |

上述系统读数出处：`runs/preflight/host.txt`；构建与课程测试：`review/build-test.log`。Lab2服务与监控保留，存在少量后台开销；绑逻辑CPU不能完全隔离SMT共享资源。

## 2. 任务 A：配额、节流与OOM

### 2.1 A1 配额算术

预测原文（在测量前保存，保持不变）：`runs/predictions/a1.md`。

# A1 prediction (before measurement)
0.5 core x 100 ms = 50 ms CPU budget. One busy thread runs about 50 ms and waits 50 ms; two truly concurrent busy threads each run 25 ms and wait 75 ms. GOMAXPROCS expected 2 on this two-vCPU machine due to Go minimum; shared SMT and scheduling can change wall time. Preserve this prediction unchanged.


原始输出：`runs/preflight/a1-burn-1.txt`

```text
cgroup：/sys/fs/cgroup/system.slice/run-r4ba783c8c367443abaf78f4c8936539e.scope
cpu.max：配额 0.50 核，周期 100ms（每个周期最多 50 ms CPU 时间）
GOMAXPROCS=2，忙线程 1 个，计数 10.0 秒
实际用核 0.50；周期 101 个，被节流 101 个（100%）；被停共 5.16 秒（按 CPU 累计）
每个线程每个周期被停：实测 51.1 ms，算术 50.0 ms
```

原始输出：`runs/preflight/a1-burn-2.txt`

```text
cgroup：/sys/fs/cgroup/system.slice/run-rf55e5095ba2d4f3bad13e311befcc3d3.scope
cpu.max：配额 0.50 核，周期 100ms（每个周期最多 50 ms CPU 时间）
GOMAXPROCS=2，忙线程 2 个，计数 10.1 秒
实际用核 0.50；周期 101 个，被节流 101 个（100%）；被停共 15.12 秒（按 CPU 累计）
每个线程每个周期被停：实测 74.8 ms，算术 75.0 ms
```

### 2.2 A2 节流与p99


预测原文（在测量前保存，保持不变）：`runs/predictions/a2.md`。

# A2 prediction (before quota change)
Measured CPU per request and chosen R: see review/a2-calibration.json. R=95, expected mean CPU about 0.4 core. Bursts and parallel execution can exhaust 50 ms within a 100 ms period, increasing p99 despite average below 0.5 core. Throttled-period ratio is workload-dependent, plausibly 0.1-0.8; not simply mean/quota. Raising quota to 60% (ceil(0.4/0.7*100)) should reduce throttling; GOMAXPROCS=1 should spread execution but may reduce parallel capacity.


每请求CPU与到达率的计算见 `review/a2-calibration.json`。本组查询：

```promql
rate(cgroup_cpu_throttled_periods_total{job="enrolld"}[${window}]) / rate(cgroup_cpu_periods_total{job="enrolld"}[${window}])
```


#### a2-base

出处：`runs/a2-base/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。

| step | target_rps | ok_rps | p50_ms | p99_ms | server_p99_ms | gomaxprocs | cg_limit_cores | cg_cpu_cores | throttle_ratio | throttled_s_per_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 30 | 28.8 | 6.89 | 9.69 | 9.96216 | 2 | 1 | 0.125123 | 0 | 0 |
| 2 | 60 | 63.5 | 6.92 | 12.00 | 9.9949 | 2 | 1 | 0.26693 | 0 | 0 |
| all | - | 46.1 | 6.91 | 11.51 | - | - | - | - | - | - |


#### a2-q100

出处：`runs/a2-q100/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。

| step | target_rps | ok_rps | p50_ms | p99_ms | server_p99_ms | gomaxprocs | cg_limit_cores | cg_cpu_cores | throttle_ratio | throttled_s_per_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 95 | 98.0 | 7.01 | 14.50 | 11.2375 | 2 | 1 | 0.413752 | 0 | 0 |
| 2 | 95 | 91.6 | 6.99 | 13.67 | 12.9944 | 2 | 1 | 0.373398 | 0 | 0 |
| all | - | 94.8 | 7.01 | 14.09 | - | - | - | - | - | - |


#### a2-q50

出处：`runs/a2-q50/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。

| step | target_rps | ok_rps | p50_ms | p99_ms | server_p99_ms | gomaxprocs | cg_limit_cores | cg_cpu_cores | throttle_ratio | throttled_s_per_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 95 | 98.0 | 7.06 | 37.41 | 36.6333 | 2 | 0.5 | 0.412088 | 0.307143 | 0.0679659 |
| 2 | 95 | 91.6 | 7.04 | 39.46 | 32.3833 | 2 | 0.5 | 0.370958 | 0.15 | 0.0368498 |
| all | - | 94.8 | 7.05 | 37.67 | - | - | - | - | - | - |


#### a2-q60

出处：`runs/a2-q60/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。

| step | target_rps | ok_rps | p50_ms | p99_ms | server_p99_ms | gomaxprocs | cg_limit_cores | cg_cpu_cores | throttle_ratio | throttled_s_per_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 95 | 98.0 | 6.99 | 17.11 | 15.5259 | 2 | 0.6 | 0.41557 | 0.0785714 | 0.00919307 |
| 2 | 95 | 91.6 | 7.00 | 14.00 | 13.3937 | 2 | 0.6 | 0.371934 | 0.0428571 | 0.00594007 |
| all | - | 94.8 | 7.00 | 15.03 | - | - | - | - | - | - |


#### a2-serial

出处：`runs/a2-serial/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。

| step | target_rps | ok_rps | p50_ms | p99_ms | server_p99_ms | gomaxprocs | cg_limit_cores | cg_cpu_cores | throttle_ratio | throttled_s_per_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 95 | 98.0 | 8.52 | 48.32 | 41.9882 | 1 | 0.5 | 0.405613 | 0.307143 | 0.0639928 |
| 2 | 95 | 91.6 | 8.43 | 42.08 | 32.3167 | 1 | 0.5 | 0.364992 | 0.164286 | 0.0284445 |
| all | - | 94.8 | 8.48 | 45.20 | - | - | - | - | - | - |

### 2.3 A3 OOM


预测原文（在测量前保存，保持不变）：`runs/predictions/a3.md`。

# A3 prediction (before measurement)
Little's Law: 10/20/30 rps x 0.5s = 5/10/15 mean concurrent reports, 40/80/120 MiB live payload. Max concurrency exceeds the mean; no finite deterministic maximum for randomized arrivals. GOGC=100 allows heap approaching 2x live plus baseline; 200MiB may OOM at 20 or 30 rps, with transient/GC variability. RSS is not identical to cgroup memory.current. Increase limit based on measured max concurrency and GC factor plus 10%; alternatively cap concurrency conservatively at 8 (128MiB payload with 2x factor, allowing baseline under 200MiB), returning 503 on excess.



#### a3-oom

| step | target_rps | ok_rps | error_rate | p99_ms | inflight_avg | report_inflight_max | rss_max_mb | heap_max_mb | mem_current_max_mb | mem_limit_mb |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10 | 9.1 | 0.0000 | 504.98 | 4.6 | 8 | 136.684 | 113.379 | 132.812 | 200 |
| 2 | 20 | 1.8 | 0.9091 | 504.98 | - | - | - | - | - | - |
| all | - | 5.5 | 0.6228 | 504.98 | - | - | - | - | - | - |


#### a3-larger

| step | target_rps | ok_rps | error_rate | p99_ms | inflight_avg | report_inflight_max | rss_max_mb | heap_max_mb | mem_current_max_mb | mem_limit_mb |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10 | 9.1 | 0.0000 | 505.42 | 4.2 | 9 | 135.812 | 97.3613 | 131.672 | 400 |
| 2 | 20 | 19.8 | 0.0000 | 504.98 | 8.93333 | 14 | 268.219 | 265.518 | 265.188 | 400 |
| 3 | 30 | 2.1 | 0.9310 | 506.71 | - | - | - | - | - | - |
| all | - | 10.3 | 0.4829 | 505.37 | - | - | - | - | - | - |


#### a3-bounded

| step | target_rps | ok_rps | error_rate | p99_ms | inflight_avg | report_inflight_max | rss_max_mb | heap_max_mb | mem_current_max_mb | mem_limit_mb |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10 | 8.7 | 0.0495 | 505.55 | 4.13333 | 8 | 121.516 | 89.3348 | 116.738 | 200 |
| 2 | 20 | 13.2 | 0.3359 | 504.88 | 6.06667 | 8 | 137.535 | 121.358 | 132.938 | 200 |
| 3 | 30 | 14.4 | 0.5361 | 505.02 | 7.26667 | 8 | 137.734 | 121.384 | 133.164 | 200 |
| all | - | 12.1 | 0.3963 | 505.11 | - | - | - | - | - | - |


OOM证据：`runs/a3-oom/oom-evidence.txt`

```text
Result=oom-kill
ExecMainStatus=9
ActiveState=failed
Nov 06 17:30:41 master-server1 systemd[1]: Started /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000.
Nov 06 17:30:41 master-server1 enrolld[1557488]: 2026/11/06 17:30:41 enrolld v1 监听 127.0.0.1:8081；GOMAXPROCS=2；cgroup /sys/fs/cgroup/system.slice/lab3-a.service；预热 0s；读：work=2000000、pool=32、db-ms=2；写：sync=each
Nov 06 17:33:34 master-server1 systemd[1]: Stopping /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000...
Nov 06 17:33:34 master-server1 enrolld[1557488]: 2026/11/06 17:33:34 收到停止信号：/readyz 改为 503，2s 后停止接收新请求
Nov 06 17:33:36 master-server1 enrolld[1557488]: 2026/11/06 17:33:36 已停止
Nov 06 17:33:36 master-server1 systemd[1]: lab3-a.service: Deactivated successfully.
Nov 06 17:33:36 master-server1 systemd[1]: Stopped /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000.
Nov 06 17:33:36 master-server1 systemd[1]: lab3-a.service: Consumed 54.846s CPU time.
Nov 06 17:33:38 master-server1 systemd[1]: Started /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000.
Nov 06 17:33:38 master-server1 enrolld[1558563]: 2026/11/06 17:33:38 enrolld v1 监听 127.0.0.1:8081；GOMAXPROCS=1；cgroup /sys/fs/cgroup/system.slice/lab3-a.service；预热 0s；读：work=2000000、pool=32、db-ms=2；写：sync=each
Nov 06 17:34:27 master-server1 systemd[1]: Stopping /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000...
Nov 06 17:34:27 master-server1 enrolld[1558563]: 2026/11/06 17:34:27 收到停止信号：/readyz 改为 503，2s 后停止接收新请求
Nov 06 17:34:29 master-server1 enrolld[1558563]: 2026/11/06 17:34:29 已停止
Nov 06 17:34:29 master-server1 systemd[1]: lab3-a.service: Deactivated successfully.
Nov 06 17:34:29 master-server1 systemd[1]: Stopped /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a -work 2000000.
Nov 06 17:34:29 master-server1 systemd[1]: lab3-a.service: Consumed 15.344s CPU time.
Nov 06 17:34:31 master-server1 systemd[1]: Started /home/sbse/lab3/bin/enrolld -addr 127.0.0.1:8081 -data /home/sbse/lab3/data/a.
Nov 06 17:34:31 master-server1 enrolld[1558949]: 2026/11/06 17:34:31 enrolld v1 监听 127.0.0.1:8081；GOMAXPROCS=2；cgroup /sys/fs/cgroup/system.slice/lab3-a.service；预热 0s；读：work=200000、pool=32、db-ms=2；写：sync=each
Nov 06 17:35:01 master-server1 systemd[1]: lab3-a.service: A process of this unit has been killed by the OOM killer.
Nov 06 17:35:01 master-server1 systemd[1]: lab3-a.service: Main process exited, code=killed, status=9/KILL
Nov 06 17:35:01 master-server1 systemd[1]: lab3-a.service: Failed with result 'oom-kill'.
[1885703.268859] enrolld invoked oom-killer: gfp_mask=0xcc0(GFP_KERNEL), order=0, oom_score_adj=0
[1885703.268946] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=lab3-a.service,mems_allowed=0,oom_memcg=/system.slice/lab3-a.service,task_memcg=/system.slice/lab3-a.service,task=enrolld,pid=1558949,uid=0
[1885703.268965] Memory cgroup out of memory: Killed process 1558949 (enrolld) total-vm:1462872kB, anon-rss:203556kB, file-rss:5836kB, shmem-rss:0kB, UID:0 pgtables:496kB oom_score_adj:0
```


400MiB来自保守并发上界20、8MiB/请求、GC因子2、基线余量40MiB、10%余量并向16MiB取整，详见 `review/a3-limit.json`。20是原阶段已OOM、缺样时的保守假设，不是原OOM阶段的实测峰值。扩大限额后的20rps峰值并发14，可用于后续复核。400MiB只保护本次20rps，30rps仍失败。有界并发取8，在200MiB下保留运行时余量，超出立即503。完整差异见 `review/A-review.md`。

## 3. 任务 B：伸缩控制环

### 3.1 B0 单实例容量



b0-one（出处 `runs/b0-one/steps.csv`）：

| step | target_rps | ok_rps | error_rate | p99_ms | timeout | codes |
|---|---|---|---|---|---|---|
| 1 | 20 | 18.6 | 0.0000 | 7.45 | 0 | - |
| 2 | 40 | 41.5 | 0.0000 | 8.22 | 0 | - |
| 3 | 60 | 63.3 | 0.0000 | 9.27 | 0 | - |
| 4 | 80 | 76.3 | 0.0000 | 30.19 | 0 | - |
| 5 | 100 | 99.8 | 0.0000 | 65.74 | 0 | - |
| all | - | 59.9 | 0.0000 | 46.52 | 0 | - |


b0-confirm（出处 `runs/b0-confirm/steps.csv`）：

| step | target_rps | ok_rps | error_rate | p99_ms | timeout | codes |
|---|---|---|---|---|---|---|
| 1 | 80 | 81.7 | 0.0000 | 34.26 | 0 | - |
| 2 | 100 | 98.3 | 0.0000 | 69.88 | 0 | - |
| 3 | 120 | 119.3 | 0.0000 | 196.83 | 0 | - |
| 4 | 140 | 116.0 | 0.1603 | 1813.14 | 23 | 502:1 503:419 |
| 5 | 160 | 112.2 | 0.3009 | 1921.62 | 60 | 502:8 503:898 |
| 6 | 180 | 107.0 | 0.4156 | 1963.62 | 180 | 502:23 503:1318 |
| all | - | 105.8 | 0.1876 | 1831.63 | 263 | 502:32 503:2635 |


校准过程及边界说明见 `review/B0-review.md`；参数见 `review/capacity.json`。


预测原文（在测量前保存，保持不变）：`runs/predictions/b-confirm.md`。

# B prediction before B1-B3
B0 calibration: review/capacity.json. Plan: 33@120s,33~330@30s,330@300s,330~33@60s,33@120s. Peak needs ceil(P/C) about 4 instances. Reactive metric/decision delay about 0-35s plus 20s pull plus 60-65s readiness; total about 85-120s after rise starts. Deficit roughly 60-120s, depends on headroom and health failures. Scheduled increase at +20s gives about 100s before ramp at +120s. Constant four instances should minimize deficit but cost ~42 instance-min; reactive costs less but catches up late. Compare both CPU and per-instance arrival signal on identical plan. Prediction is approximate, frozen before measurement.


### 3.2 四次对照

| 方案 | runs目录 | 缺口秒 | 全程错误 | 峰值p99 ms | 实例·分钟 |
|---|---|---:|---:|---:|---:|

| b1-fixed | `runs/b1-fixed/` | 0 | 0 | 35.30 | 42.0 |

| b2-cpu | `runs/b2-cpu/` | 100 | 18309 | 1638.26 | 37.0 |

| b2-qps | `runs/b2-qps/` | 114 | 24048 | 1651.14 | 36.5 |

| b3-sched | `runs/b3-sched/` | 0 | 0 | 35.14 | 41.3 |


各数值来源：对应 `summary.md` 缺口、实例表，以及 `steps.csv` 第3阶段。各次完整630s计划相同；`meta.txt` 保存参数，`decisions.csv` 保存信号与动作。

### 3.3 控制环原始汇总


| 段 | 本组实测秒 | 出处 |
|---|---:|---|
| 爬升到首次扩容决策 | 22.2 | decisions.csv及instances.csv |
| 创建到启动（拉镜像） | 21.0 | instances.csv |
| 启动到首次就绪 | 63.0 | instances.csv |
| 爬升到首个新增实例首次就绪 | 106.2 | 上述三段相加 |

首次就绪可能之后又变为不健康，完整恢复需对照lbd-events与timeline。


#### b2-cpu

以下复制 `runs/b2-cpu/summary.md`，包含决策与创建、启动、就绪时间：

##### b2-cpu

负载共 630 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 142 | 242 | 100 | 32813 | 18309 | 9678 |

缺口共 100 秒；第一段从第 142 秒到第 242 秒。
全程发出 123254 个请求，错误 18309 个（14.85%），成功但超过阈值 9678 个（7.85%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：37.0；同时存在的实例最多 4 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -82.8 | -61.8 | 1.2 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8102 | v1 | -82.8 | -61.8 | 1.2 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | 142.2 | 163.2 | 226.2 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8104 | v1 | 157.2 | 178.2 | 241.2 | - | 21.0 | 63.0 | 84.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|
| 142 | 0.817 | 2 | 2 | 2 | 3 | 3 | create 1 |
| 157 | 0.960 | 3 | 2 | 2 | 4 | 4 | create 1 |



#### b2-qps

以下复制 `runs/b2-qps/summary.md`，包含决策与创建、启动、就绪时间：

##### b2-qps

负载共 630 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 142 | 256 | 114 | 37394 | 24048 | 8745 |

缺口共 114 秒；第一段从第 142 秒到第 256 秒。
全程发出 123254 个请求，错误 24048 个（19.51%），成功但超过阈值 8746 个（7.10%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：36.5；同时存在的实例最多 4 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -83.0 | -61.9 | 0.1 | - | 21.0 | 62.0 | 83.0 | 0 |
| 127.0.0.1:8102 | v1 | -83.0 | -61.9 | 1.1 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | 157.1 | 178.1 | 241.1 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8104 | v1 | 172.1 | 193.1 | 256.1 | - | 21.0 | 63.0 | 84.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|
| 157 | 117.714 | 2 | 2 | 2 | 3 | 3 | create 1 |
| 172 | 123.643 | 3 | 0 | 2 | 4 | 4 | create 1 |



#### b3-sched

以下复制 `runs/b3-sched/summary.md`，包含决策与创建、启动、就绪时间：

##### b3-sched

负载共 630 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

没有缺口。
全程发出 123254 个请求，错误 0 个（0.00%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：41.3；同时存在的实例最多 4 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -83.1 | -62.1 | 0.9 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8102 | v1 | -83.1 | -62.0 | 0.9 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | 21.9 | 43.0 | 105.9 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8104 | v1 | 21.9 | 43.0 | 105.9 | - | 21.0 | 63.0 | 84.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|
| 22 | 0.155 | 2 | 2 | 4 | 4 | 4 | create 2 |


## 4. 任务 C：故障注入


预测原文（在测量前保存，保持不变）：`runs/predictions/c.md`。

# C prediction before injection
Constant arrival 167 ~2C, 3 replicas. Kill may be discovered by scaler and removed before health failure threshold. Pause 20s should fail 3 checks roughly 2-4.5s after injection; errors roughly arrival/3 x detection latency, plus timeouts already in flight. Pausing all 2s may be tolerated by fall=3 but fall=1/500ms/200ms can remove all and cause 503; faster detection can increase false positives. Slow instance around 85% CPU should increase latency while lightweight readiness passes; passive ejection can reduce p99 but reduces capacity and may oscillate.



### c1-stop

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 167.0 | 0.0045 | 15.61 | 27 | 155 | 0 | 502:27 |
| all | - | 167.0 | 0.0045 | 15.61 | 27 | 155 | 0 | 502:27 |

#### c1-stop

负载共 240 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 59 | 61 | 2 | 344 | 16 | 0 |
| 159 | 163 | 4 | 691 | 166 | 0 |

缺口共 6 秒；第一段从第 59 秒到第 61 秒。
全程发出 40264 个请求，错误 182 个（0.45%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：12.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -83.2 | -62.2 | -0.2 | - | 21.0 | 62.0 | 83.0 | 0 |
| 127.0.0.1:8102 | v1 | -83.2 | -62.1 | 0.8 | 60.8 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | -83.2 | -62.1 | 0.8 | - | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8102 | v1 | 60.9 | 81.9 | 144.9 | - | 21.0 | 63.0 | 84.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|

## 注入

| 时刻 | 注入 | 对象 | lbd 判定 | 判定用时 s | 恢复 | 恢复用时 s | 注入到判定之间的错误 |
|---|---|---|---|---|---|---|---|
| 60.6 | kill | 127.0.0.1:8102 | removed 127.0.0.1:8102 | 0.2 | up 127.0.0.1:8102 | 83.2 | 15 |
| 160.6 | pause | 127.0.0.1:8103 | down 127.0.0.1:8103 | 2.7 | up 127.0.0.1:8103 | 21.3 | 165 |
| 180.6 | resume | 127.0.0.1:8103 | - | - | - | - | - |



### c2-default

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 168.1 | 0.0041 | 1371.60 | 3 | 80 | 0 | 502:3 |
| all | - | 168.1 | 0.0041 | 1371.60 | 3 | 80 | 0 | 502:3 |

#### c2-default

负载共 120 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 39 | 46 | 7 | 1199 | 83 | 677 |

缺口共 7 秒；第一段从第 39 秒到第 46 秒。
全程发出 20252 个请求，错误 83 个（0.41%），成功但超过阈值 677 个（3.34%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：6.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -97.2 | -76.2 | -10.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8102 | v1 | -97.2 | -76.2 | -10.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8103 | v1 | -97.2 | -76.2 | -10.2 | - | 21.0 | 66.0 | 87.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|

## 注入

| 时刻 | 注入 | 对象 | lbd 判定 | 判定用时 s | 恢复 | 恢复用时 s | 注入到判定之间的错误 |
|---|---|---|---|---|---|---|---|
| 40.6 | pause | * | down 等 3 台 | 2.7 | 3 台都恢复 | 7.2 | 79 |
| 42.6 | resume | * | - | - | - | - | - |



### c2-sensitive

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 165.3 | 0.0205 | 15.63 | 408 | 8 | 0 | 502:1 503:407 |
| all | - | 165.3 | 0.0205 | 15.63 | 408 | 8 | 0 | 502:1 503:407 |

#### c2-sensitive

负载共 120 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 39 | 43 | 4 | 714 | 416 | 29 |

缺口共 4 秒；第一段从第 39 秒到第 43 秒。
全程发出 20252 个请求，错误 416 个（2.05%），成功但超过阈值 29 个（0.14%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：6.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -233.2 | -212.2 | -146.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8102 | v1 | -233.2 | -212.2 | -146.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8103 | v1 | -233.2 | -212.2 | -146.2 | - | 21.0 | 66.0 | 87.0 | 0 |

## 伸缩决策（有动作的）

| 时刻 | 信号 | 当前 | 就绪 | 最少 | 计算 | 期望 | 动作 |
|---|---|---|---|---|---|---|---|

## 注入

| 时刻 | 注入 | 对象 | lbd 判定 | 判定用时 s | 恢复 | 恢复用时 s | 注入到判定之间的错误 |
|---|---|---|---|---|---|---|---|
| 40.7 | pause | * | down 等 3 台 | 0.3 | 3 台都恢复 | 2.6 | 126 |
| 42.7 | resume | * | - | - | - | - | - |



### c3-slow

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 167.8 | 0.0000 | 17.54 | 0 | 0 | 0 | - |
| all | - | 167.8 | 0.0000 | 17.54 | 0 | 0 | 0 | - |

#### c3-slow

负载共 240 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

没有缺口。
全程发出 40264 个请求，错误 0 个（0.00%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：12.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -369.2 | -348.2 | -282.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8102 | v1 | -369.2 | -348.2 | -282.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8103 | v1 | -369.2 | -348.2 | -282.2 | - | 21.0 | 66.0 | 87.0 | 0 |

## 注入

| 时刻 | 注入 | 对象 | lbd 判定 | 判定用时 s | 恢复 | 恢复用时 s | 注入到判定之间的错误 |
|---|---|---|---|---|---|---|---|
| 60.7 | slow | 127.0.0.1:8102 | - | - | - | - | 0 |
| 180.8 | restore | 127.0.0.1:8102 | - | - | - | - | - |



### c3-outlier

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 167.8 | 0.0000 | 16.50 | 0 | 0 | 0 | - |
| all | - | 167.8 | 0.0000 | 16.50 | 0 | 0 | 0 | - |

#### c3-outlier

负载共 240 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

没有缺口。
全程发出 40264 个请求，错误 0 个（0.00%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：12.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -625.2 | -604.2 | -538.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8102 | v1 | -625.2 | -604.2 | -538.2 | - | 21.0 | 66.0 | 87.0 | 0 |
| 127.0.0.1:8103 | v1 | -625.2 | -604.2 | -538.2 | - | 21.0 | 66.0 | 87.0 | 0 |

## 注入

| 时刻 | 注入 | 对象 | lbd 判定 | 判定用时 s | 恢复 | 恢复用时 s | 注入到判定之间的错误 |
|---|---|---|---|---|---|---|---|
| 60.8 | slow | 127.0.0.1:8102 | ejected 127.0.0.1:8102，共 2 次 | 69.0 | restored 127.0.0.1:8102 | 99.0 | 0 |
| 180.8 | restore | 127.0.0.1:8102 | - | - | - | - | - |



C3参数来源：`review/c1-baseline-cpu.json` 是C1前60秒内的原始Prometheus查询；`review/c3-calibration.json` 保存U和round(U/0.85×100)的配额选择。每个实例的CPU和按backend的p99保存在对应 `runs/<名字>/prometheus/`。

## 5. 任务 D：发布与自愈


预测原文（在测量前保存，保持不变）：`runs/predictions/d.md`。

# D prediction before rollout and leak runs
Three serial graceful replacements: roughly 3 x (20s pull+60s warmup+2-5s readiness+2s drain) ~252-270s; naive starts replacement every 5s and does not wait readiness, likely loses capacity of all replicas for ~60s, with 503 and connections reset. Graceful temporarily uses a fourth replica and takes longer but preserves ready capacity. D2 arrival 167, each replica leaks LOAD/3*16 KiB/s. Approximate OOM time (64MiB-baseline-GC transient)/(LOAD/3*16KiB/s), likely tens of seconds; GC cannot free intentional retained leak. Similar arrival per instance may synchronize OOM and invalidate independent-failure assumptions. Alert on changes(process_start_time_seconds[10m]), cross-check NRestarts and instances.csv; scrape can miss fast restarts.


预测原文（在测量前保存，保持不变）：`runs/predictions/d2-detail.md`。

# D2 自愈补充预测（D2 运行前保存）

B0 补测确定故障/发布负载为167rps。轮询均分时每个实例约55.667请求/秒，每请求永久保留16KiB，因此每实例泄漏约890.667KiB/s，即0.86979MiB/s。

忽略一切基线时，64MiB/0.86979MiB/s≈73.58s；扣除约10–20MiB初始进程、运行时和GC空间后，预计约50.59–62.08s触顶。实际还受瞬时GC堆、cgroup统计、重启预热期间负载重分配影响。

三个实例创建时间接近、分流接近、限额相同，可能在接近时刻OOM。即使剩余两实例的稳态CPU容量足够，相关性重启和预热仍可能造成阶段性缺口。自动重启清理泄漏堆，但不修复泄漏代码；应以重启/异常退出次数告警，同时观察可用实例、错误和缺口。

预先写明：上面10–20MiB只是基线假设，后续与实测对照，不把实测值回填成预测。



### d1-naive

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 117.0 | 0.3057 | 1147.82 | 9234 | 35 | 0 | 502:159 503:9075 |
| all | - | 117.0 | 0.3057 | 1147.82 | 9234 | 35 | 0 | 502:159 503:9075 |

#### d1-naive

负载共 180 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 29 | 33 | 4 | 683 | 129 | 0 |
| 34 | 98 | 64 | 10733 | 9140 | 608 |

缺口共 68 秒；第一段从第 29 秒到第 33 秒。
全程发出 30320 个请求，错误 9269 个（30.57%），成功但超过阈值 608 个（2.01%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：9.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -83.1 | -62.1 | 0.9 | 30.7 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8102 | v1 | -83.1 | -62.1 | 0.9 | 35.7 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | -83.1 | -62.0 | 0.9 | 40.8 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8101 | v2 | 30.7 | 30.7 | 92.9 | - | 0.0 | 62.2 | 62.2 | 0 |
| 127.0.0.1:8102 | v2 | 35.7 | 35.7 | 97.9 | - | 0.0 | 62.2 | 62.2 | 0 |
| 127.0.0.1:8103 | v2 | 40.8 | 40.8 | 102.9 | - | 0.0 | 62.1 | 62.1 | 0 |



### d1-graceful

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 167.4 | 0.0000 | 14.89 | 0 | 0 | 0 | - |
| all | - | 167.4 | 0.0000 | 14.89 | 0 | 0 | 0 | - |

#### d1-graceful

负载共 420 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

没有缺口。
全程发出 70298 个请求，错误 0 个（0.00%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：25.3；同时存在的实例最多 4 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8101 | v1 | -83.2 | -62.2 | 0.8 | 116.2 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8102 | v1 | -83.2 | -62.2 | 0.8 | 202.3 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8103 | v1 | -83.2 | -62.2 | 0.8 | 288.1 | 21.0 | 63.0 | 84.0 | 0 |
| 127.0.0.1:8104 | v3 | 30.6 | 50.8 | 113.8 | - | 20.2 | 63.0 | 83.2 | 0 |
| 127.0.0.1:8101 | v3 | 116.2 | 136.8 | 199.8 | - | 20.6 | 63.0 | 83.6 | 0 |
| 127.0.0.1:8102 | v3 | 202.3 | 222.8 | 285.8 | - | 20.5 | 63.0 | 83.5 | 0 |



### d2-heal

| step | target_rps | ok_rps | error_rate | p99_ms | http_err | timeout | net_err | codes |
|---|---|---|---|---|---|---|---|---|
| 1 | 167 | 139.8 | 0.1647 | 15.05 | 13227 | 0 | 0 | 502:2583 503:10644 |
| all | - | 139.8 | 0.1647 | 15.05 | 13227 | 0 | 0 | 502:2583 503:10644 |

#### d2-heal

负载共 480 秒；时间都是负载开始后的秒数。

## 缺口（出错，或 p99 > 200 ms 的秒）

| 起 | 止 | 秒数 | 发出 | 错误 | 慢（成功但超过阈值） |
|---|---|---|---|---|---|
| 63 | 78 | 15 | 2512 | 2244 | 0 |
| 139 | 154 | 15 | 2604 | 2326 | 0 |
| 216 | 231 | 15 | 2496 | 2224 | 0 |
| 294 | 308 | 14 | 2408 | 2236 | 0 |
| 370 | 385 | 15 | 2549 | 2137 | 0 |
| 446 | 461 | 15 | 2436 | 2060 | 0 |

缺口共 89 秒；第一段从第 63 秒到第 78 秒。
全程发出 80316 个请求，错误 13227 个（16.47%），成功但超过阈值 0 个（0.00%）。

## 实例

实例·分钟（从创建算起，只计负载期间）：24.0；同时存在的实例最多 3 个。

| 实例 | 版本 | 创建 | 启动 | 就绪 | 结束 | 拉镜像 s | 启动到就绪 s | 创建到就绪 s | 重启 |
|---|---|---|---|---|---|---|---|---|---|
| 127.0.0.1:8104 | v3 | -426.4 | -406.2 | -343.2 | -34.3 | 20.2 | 63.0 | 83.2 | 0 |
| 127.0.0.1:8101 | v3 | -340.8 | -320.2 | -257.2 | -34.3 | 20.6 | 63.0 | 83.6 | 0 |
| 127.0.0.1:8102 | v3 | -254.7 | -234.2 | -171.2 | -34.3 | 20.5 | 63.0 | 83.5 | 0 |
| 127.0.0.1:8101 | v1 | -33.3 | -12.3 | 0.7 | - | 21.0 | 13.0 | 34.0 | 6 |
| 127.0.0.1:8102 | v1 | -33.3 | -12.3 | 0.7 | - | 21.0 | 13.0 | 34.0 | 6 |
| 127.0.0.1:8103 | v1 | -33.3 | -12.3 | 0.7 | - | 21.0 | 13.0 | 34.0 | 6 |



D2进程管理器重启计数（依次对应8101、8102、8103，顺序见执行脚本）：

```text
NRestarts=6
NRestarts=6
NRestarts=6
```


告警表达式本次查询值：**20**，原始返回值见 `runs/d2-heal/restart-query.json`。


D2告警查询：

```promql
sum(changes(process_start_time_seconds{job="instances"}[10m]))
```

原始返回值：`runs/d2-heal/restart-query.json`。重启时间与缺口分别在 `instances.csv` 和 `timeline.csv`，按同一时间窗对照；`changes`在采样遗漏时可能少计，需与systemd计数交叉检查。

## 6. 分析问题

### 问题 1：配额

证据见第2节、`runs/a2-q50/red.csv`、`runs/a3-oom/oom-evidence.txt`。A1单线程每周期被停51.1ms，对照50ms；双线程每线程74.8ms，对照75ms。差异与调度、测量周期边界及SMT共享有关。A2在平均0.37～0.41核低于0.5核时，节流周期仍约15%～31%，全程客户端p99从14.09升至37.67ms：平均值掩盖了单个100ms周期内配额提前耗尽。提高配额到60%后p99为15.03ms，代价是预留更多CPU；限制GOMAXPROCS为1后p99为45.20ms，本次没有改善，串行排队与突发仍会发生。A3按平均在途数乘8MiB只估计存活负载，瞬时并发和GC余量会抬高RSS；200MiB下观察到oom-kill。400MiB在20rps成功，但30rps仍失败；并发限制8保护内存，却返回503。MemorySwapMax=0排除换出导致的长时间变慢。前者适合有可预测峰值和足够内存，后者适合可接受拒绝及上游退避的情况。

### 问题 2：控制环

证据见第3节和各次`summary.md`。CPU反应式从爬升到首次决策22.2s、拉镜像21.0s、启动到首次就绪63.0s，合计106.2s；最长的是模拟预热和健康检查。理想情况下消除决策等待及拉镜像也仍要等约63s，实际能否压缩预热取决于应用。常驻、CPU反应式、到达率反应式和定时预热的缺口分别为0、100、114、0秒，实例·分钟分别为42.0、37.0、36.5、41.3。到达率信号在142秒为85.607，距目标83.51不足10%，容差使其等到157秒才扩容；本次较CPU信号晚一个决策周期。CPU方案有8185个超时和8129个503，过载也使健康检查失败，摘除后剩余实例承担更多负载，可能加重缺口。已知开放日且本次容量、启动和负载条件成立时可选定时预热；其缩容稳定窗口使节省有限。实际镜像、下游和云主机干扰会改变结论。

### 问题 3：健康检查

证据见第4节各注入表与`lbd-events.csv`。C1停止后scaler在0.2s移除实例，卡住时进程仍在，健康检查2.7s判down；进程管理无法单独发现不响应的存活进程。C2暂停2s时，默认组2.7s判定、7.2s全部恢复，产生83个错误；灵敏组0.3s判定、2.6s恢复，错误416个。灵敏检查缩短缺口，却更快把短暂扰动转化为无可用后端的503；两次均是实际短暂停顿，并非证明探针本身报告了虚假状态。C3将实例8102从25%降至15%，依据正常CPU用量0.125211核；轻量检查未将其判down。离群检测在注入后69s摘除该实例，共摘除两次，但两次全站均无超过200ms的缺口，不能声称消除了已有缺口。被动摘除可识别业务变慢，也可能误摘、减少容量或反复摘除；限制同时摘除比例是为了避免健康容量被一次性移空，效果取决于剩余容量。

### 问题 4：发布与自愈

证据见第5节实例表、`runs/d2-heal/instances.csv`和重启查询。直接替换在30.7、35.7、40.8秒杀掉旧实例，新版本到92.9、97.9、102.9秒才就绪，期间连接中断、未就绪及无可用后端导致9269个错误、68秒缺口。排空加就绪先增加新实例并等其就绪，再等待旧实例的在途请求；本次零错误，但从30.6秒首次创建到288.1秒最后旧实例停止约257.5秒，最多同时占用4个实例。D2每个实例均重启6次，共出现89秒缺口、13227个错误，重启集中反复发生，不能假定冗余实例的故障独立。自动重启恢复进程但没有修复持续泄漏，应同时告警重启频率、可用实例及错误。`changes(process_start_time_seconds[10m])`结果20，systemd的三个NRestarts合计18；查询覆盖窗口、抓取及生命周期统计不同，不能直接视作相同计数，应按时间戳交叉核对。

## 7. 选做记录

必做提交时O1–O7尚未执行；以必做完成的Git提交和 mandatory-complete 标记为分界，随后追加独立预测、数据与分析。

## 8. 成员分工

| GitHub用户名 | 负责核对与答辩的内容 |
|---|---|
| S1mpleWind | 环境与D发布、自愈；整体链路 |
| wgy666 | C故障注入、健康检查与离群摘除 |
| AllenTwillight05 | B容量校准、伸缩信号与控制环 |
| yangjunqiqq | A配额、节流、OOM与GC |
| yollsplus | E四题整合、数据出处与归档核对 |

每位成员需实际核对本模块、练习复现、理解关键代码，并能解释整体链路。答辩材料不替代成员理解。

## 9. 测量局限与review入口

单机、SMT共享、云邻居、低样本逐秒p99、模拟拉镜像与预热、采样周期、成功请求分位数和缺口阈值均影响结论。不能平均不同阶段/实例的p99，也不能将p99代入Little定律。OOM后服务缺样原样保留。各结论限定于本次配置和本组实测。

完整过程与参数：review目录；原始数据：runs；校验和：review/raw-sha256.txt；独立一致性核对：review/mandatory-derived.json。正式复现命令与答辩分工另附review材料。
