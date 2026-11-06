# A：配额、节流与 OOM 复核笔记

本笔记为初步复核，最终以 LAB3.md 与 runs 原始文件为准。

## A1

- 一线程：每周期被停 51.1 ms，预测 50.0 ms，差 +1.1 ms。
- 二线程：每线程每周期被停 74.8 ms，预测 75.0 ms，差 -0.2 ms。
- 两次实际均约 0.50 核，101 个周期全部被节流，GOMAXPROCS=2。
- 证据：runs/preflight/a1-burn-1.txt、a1-burn-2.txt。调度、计数边界和两个超线程共享物理执行资源会造成偏差。

## A2

低负载基线第二阶段每请求 CPU 4.19891 ms，400 / 4.19891 ≈ 95 rps，因此选择 95 rps。四次对照发送序列相同：3791 次，全成功，便于比较。

| 条件 | 全程客户端 p99 ms | 出处 |
|---|---:|---|
| 100% | 14.09 | runs/a2-q100/steps.csv 的 all 行 |
| 50% | 37.67 | runs/a2-q50/steps.csv 的 all 行 |
| 60% | 15.03 | runs/a2-q60/steps.csv 的 all 行 |
| 50%，GOMAXPROCS=1 | 45.20 | runs/a2-serial/steps.csv 的 all 行 |

50% 下两阶段实际用核 0.412088、0.370958，均低于 0.5，节流周期比例仍为 0.307143、0.15（runs/a2-q50/red.csv）。平均量无法约束某一个 100ms 周期内的到达突发。CPUQuota=50% 是每周期合计 50ms CPU 时间，多个线程可更快耗尽预算。

提高到 60% 接近 0.4/0.7 的配额选择，减少节流并改善尾延迟；代价是增加可占用 CPU。GOMAXPROCS=1 没有改善本次 p99，不能写成成功优化：泊松突发下单线程仍可能耗尽 50ms 周期预算，串行处理还增加 Go 调度等待。其 red.csv 的调度等待 p99 第一阶段为 19.5737ms。该结论限定于本机、该负载和本次阶段，不能推出单线程永远更差。

## A3

平均在途的初始估计为 5、10、15，活跃负载为 40、80、120MiB；Go GC 和瞬时并发使峰值显著高于均值。

- 200MiB 下 Result=oom-kill、ExecMainStatus=9（runs/a3-oom/oom-evidence.txt）。进程在 20rps 阶段退出，后续指标缺样真实保留，未人工补值。
- 400MiB 下 10rps 的 182 次和 20rps 的 396 次请求全部成功；30rps 的 623 次只有 43 次成功，580 次连接错误（runs/a3-larger/steps.csv）。因此该改法只证明目标 20rps 得到改善，不能称 30rps 也安全。
- 增大配额初始使用保守并发上界 20、GC 因子 2、基线余量 40MiB：ceil((20×8×2+40)×1.1/16)×16 = 400MiB。由于原 OOM 阶段未留下有效的 20rps 峰值采样，这里的并发 20 是保守假设，不是实测值；完整计算保留在 review/a3-limit.json。
- 扩大内存后的 20rps 实测 report_inflight_max=14，cgroup memory.current 峰值 265.188MiB，RSS 峰值 268.219MiB（runs/a3-larger/red.csv 第2阶段）。RSS、heap 与 cgroup memory.current 的采样口径不同，不能互相等同。
- 200MiB 配合 report-max=8 时三阶段均完成，观测并发上限 8，最高 memory.current 133.164MiB；总发送 1201、成功 725，错误比例 39.63%，主要为主动返回 503（runs/a3-bounded/steps.csv、red.csv）。这是以拒绝超额请求来保护进程，并未增加可服务容量。
- MemorySwapMax=0 排除换出拖慢后再 OOM 的路径，使实验更接近明确的内存硬上限。

注意报表每次本身保持约500ms，客户端默认50ms SLO不适合将其判断为一般读接口性能失败；本题重点是内存、生存与拒绝率。
