"""Build evidence tables after all mandatory experiments; prose is reviewed separately."""
from pathlib import Path
import csv,json,subprocess,re,datetime,shutil
root=Path('/home/sbse/lab3');review=root/'review'
def table(name,cols):
 return subprocess.check_output(['bash','scripts/table.sh','runs/'+name,*cols],cwd=root,text=True)
def text(p):return (root/p).read_text()
def block(s):return '```text\n'+s.strip()+'\n```\n'
def prediction(name):return f'预测原文（在测量前保存，保持不变）：`runs/predictions/{name}`。\n\n'+text('runs/predictions/'+name)+'\n'
der=json.loads(text('review/mandatory-derived.json'))
assert not der['issues'],der['issues']
r=der['results'];cap=json.loads(text('review/capacity.json'))
alert=json.loads(text('runs/d2-heal/restart-query.json'))
alert_value=alert['data']['result'][0]['value'][1] if alert['data']['result'] else '空结果，需核查'
parts=['# 实验 3 记录：第 6 组\n\n仓库：https://github.com/S1mpleWind/ops-lab3-6\n\n由用户委托 Codex 在小组真实 Linux 云主机执行。原始输出未编辑；预测原文件与执行时刻保留，最终报告整理时引用。成员负责实际核对、复现与讲解，不虚构个人执行记录。原始证据索引见 `review/README.md`。\n',
'''## 1. 基本信息

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
''',prediction('a1.md')]
for n in [1,2]:parts.append(f'原始输出：`runs/preflight/a1-burn-{n}.txt`\n\n'+block(text(f'runs/preflight/a1-burn-{n}.txt')))
parts += ['### 2.2 A2 节流与p99\n\n',prediction('a2.md'),'每请求CPU与到达率的计算见 `review/a2-calibration.json`。本组查询：\n\n```promql\nrate(cgroup_cpu_throttled_periods_total{job="enrolld"}[${window}]) / rate(cgroup_cpu_periods_total{job="enrolld"}[${window}])\n```\n']
for name in ['a2-base','a2-q100','a2-q50','a2-q60','a2-serial']:
 parts.append(f'\n#### {name}\n\n出处：`runs/{name}/steps.csv`、`red.csv`；由 `scripts/table.sh` 生成。\n\n'+table(name,['ok_rps','p50_ms','p99_ms','server_p99_ms','gomaxprocs','cg_limit_cores','cg_cpu_cores','throttle_ratio','throttled_s_per_s']))
parts+=['### 2.3 A3 OOM\n\n',prediction('a3.md')]
for name in ['a3-oom','a3-larger','a3-bounded']:
 parts.append(f'\n#### {name}\n\n'+table(name,['ok_rps','error_rate','p99_ms','inflight_avg','report_inflight_max','rss_max_mb','heap_max_mb','mem_current_max_mb','mem_limit_mb']))
parts+=['\nOOM证据：`runs/a3-oom/oom-evidence.txt`\n\n'+block(text('runs/a3-oom/oom-evidence.txt')),'\n400MiB来自保守并发上界20、8MiB/请求、GC因子2、基线余量40MiB、10%余量并向16MiB取整，详见 `review/a3-limit.json`。20是原阶段已OOM、缺样时的保守假设，不是原OOM阶段的实测峰值。扩大限额后的20rps峰值并发14，可用于后续复核。400MiB只保护本次20rps，30rps仍失败。有界并发取8，在200MiB下保留运行时余量，超出立即503。完整差异见 `review/A-review.md`。\n',
'## 3. 任务 B：伸缩控制环\n\n### 3.1 B0 单实例容量\n\n']
for name in ['b0-one','b0-confirm']:parts.append(f'\n{name}（出处 `runs/{name}/steps.csv`）：\n\n'+table(name,['ok_rps','error_rate','p99_ms','timeout','codes']))
parts+=['\n校准过程及边界说明见 `review/B0-review.md`；参数见 `review/capacity.json`。\n\n',prediction('b-confirm.md'),'### 3.2 四次对照\n\n| 方案 | runs目录 | 缺口秒 | 全程错误 | 峰值p99 ms | 实例·分钟 |\n|---|---|---:|---:|---:|---:|\n']
for name in ['b1-fixed','b2-cpu','b2-qps','b3-sched']:
 q=r[name];parts.append(f'| {name} | `runs/{name}/` | {q["gap_seconds"]} | {q["timeline_errors"]} | {q["peak_phase"]["p99_ms"]} | {q["instance_minutes"]} |\n')
parts+=['\n各数值来源：对应 `summary.md` 缺口、实例表，以及 `steps.csv` 第3阶段。各次完整630s计划相同；`meta.txt` 保存参数，`decisions.csv` 保存信号与动作。\n\n### 3.3 控制环原始汇总\n\n']
events=list(csv.DictReader((root/'runs/b2-cpu/instances.csv').open()))
base_ms=r['b2-cpu']['start']*1000
created=next(e for e in events if e['event']=='created' and int(e['unix_ms'])>=base_ms+120000)
started=next(e for e in events if e['event']=='started' and e['instance']==created['instance'] and int(e['unix_ms'])>=int(created['unix_ms']))
ready=next(e for e in events if e['event']=='ready' and e['instance']==created['instance'] and int(e['unix_ms'])>=int(started['unix_ms']))
decision=(int(created['unix_ms'])-base_ms)/1000-120
pull=(int(started['unix_ms'])-int(created['unix_ms']))/1000
warm=(int(ready['unix_ms'])-int(started['unix_ms']))/1000
parts.append(f'| 段 | 本组实测秒 | 出处 |\n|---|---:|---|\n| 爬升到首次扩容决策 | {decision:.1f} | decisions.csv及instances.csv |\n| 创建到启动（拉镜像） | {pull:.1f} | instances.csv |\n| 启动到首次就绪 | {warm:.1f} | instances.csv |\n| 爬升到首个新增实例首次就绪 | {decision+pull+warm:.1f} | 上述三段相加 |\n\n首次就绪可能之后又变为不健康，完整恢复需对照lbd-events与timeline。\n')
for name in ['b2-cpu','b2-qps','b3-sched']:
 parts.append(f'\n#### {name}\n\n以下复制 `runs/{name}/summary.md`，包含决策与创建、启动、就绪时间：\n\n'+text(f'runs/{name}/summary.md').replace('# '+name,'##### '+name,1))
parts+=['## 4. 任务 C：故障注入\n\n',prediction('c.md')]
for name in ['c1-stop','c2-default','c2-sensitive','c3-slow','c3-outlier']:
 parts.append(f'\n### {name}\n\n'+table(name,['ok_rps','error_rate','p99_ms','http_err','timeout','net_err','codes'])+'\n'+text(f'runs/{name}/summary.md').replace('# '+name,'#### '+name,1))
parts+=['\nC3参数来源：`review/c1-baseline-cpu.json` 是C1前60秒内的原始Prometheus查询；`review/c3-calibration.json` 保存U和round(U/0.85×100)的配额选择。每个实例的CPU和按backend的p99保存在对应 `runs/<名字>/prometheus/`。\n',
'## 5. 任务 D：发布与自愈\n\n',prediction('d.md'),prediction('d2-detail.md')]
for name in ['d1-naive','d1-graceful','d2-heal']:
 parts.append(f'\n### {name}\n\n'+table(name,['ok_rps','error_rate','p99_ms','http_err','timeout','net_err','codes'])+'\n'+text(f'runs/{name}/summary.md').replace('# '+name,'#### '+name,1))
parts+=['\nD2进程管理器重启计数（依次对应8101、8102、8103，顺序见执行脚本）：\n\n'+block(text('runs/d2-heal/systemd-restarts.txt')),
f'\n告警表达式本次查询值：**{alert_value}**，原始返回值见 `runs/d2-heal/restart-query.json`。\n',
'''\nD2告警查询：

```promql
sum(changes(process_start_time_seconds{job="instances"}[10m]))
```

原始返回值：`runs/d2-heal/restart-query.json`。重启时间与缺口分别在 `instances.csv` 和 `timeline.csv`，按同一时间窗对照；`changes`在采样遗漏时可能少计，需与systemd计数交叉检查。

## 6. 分析问题

分析正文见后续审核后的四题答案；本生成步骤仅整理表格，不自动猜测未测结果。

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
''']
old=root/'LAB3.md'
shutil.copy2(old,review/'LAB3-before-final.md')
old.write_text('\n'.join(parts))
print('Evidence tables written; analysis prose still requires review')
