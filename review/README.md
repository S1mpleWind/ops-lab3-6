# Lab3 review 与答辩资料索引

## 执行约定

- 第 6 组，仓库 https://github.com/S1mpleWind/ops-lab3-6 。由用户委托 Codex 执行，成员分工用于实际核对、分析与答辩准备，不虚构成员操作记录。
- 必做 A–E 全部结束、核查并形成 Git 提交后，才执行 O1–O7。
- 课程原始 scripts/run.sh、scripts/run3.sh 保持不变。runs 为原始输出，预测在 runs/predictions 内先写后测；失败和补测另建目录，不覆盖原数据。
- 监控 Prometheus 使用 127.0.0.1:19090；Lab3 lbd 业务入口使用 127.0.0.1:18080，管理接口保持 8090/8091。避免与仍运行的 Lab2 占用冲突。实例与压测分核仍按指导书。
- 不保存密码、密钥或公网 IP 到实验仓库。云主机日志与提交前做内容检查。
- 两个逻辑 CPU 属于同一个物理核心的 SMT，绑核不等于物理资源完全隔离；原 Lab2 进程静止时仍有监控开销，需要写入测量局限。

## 证据目录

- runs/preflight/host.txt：主机、系统、cgroup、工具版本。
- runs/preflight/a1-burn-*.txt：A1 完整原始输出。
- runs/predictions/：冻结的测量前预测。
- runs/<实验名>/：课程采集脚本原始输出。
- review/build-test.log：构建和课程测试。
- review/task-a.sh、task-bcd.sh：实验操作脚本；对应 driver.log 保存执行时刻、命令与输出。
- review/a2-calibration.json、a3-limit.json、capacity.json、c3-calibration.json：选择负载、容量线和资源限额的依据。
- LAB3.md：最终报告（仅在实测后填写实测值）。

## 成员复核与答辩分工

| GitHub 用户名 | 负责内容 | 必须检查 |
|---|---|---|
| S1mpleWind | 环境、D 发布与自愈 | 整体链路、替换时序、就绪与排空、重启与告警 |
| wgy666 | C 故障注入 | 注入时刻与判定事件、误判、慢实例与离群摘除 |
| AllenTwillight05 | B 伸缩 | 单实例容量、控制环延迟、两种信号、缺口与实例·分钟 |
| yangjunqiqq | A 配额与 OOM | 周期算术、平均与突发、内存和 GC、两种改法 |
| yollsplus | E 整合与证据核对 | 四题分析、逐项数据出处、局限、复现步骤 |

各模块负责人先检查对应分析题再交给汇总人。每个人都应能找到原始 CSV、解释整体链路，并练习至少一种现场重跑。
