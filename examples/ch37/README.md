# Ch37 分层行为测试

唯一被测实现位于 `../ch36/src/book_reference/`。本目录只维护固定夹具、测试、受控缺陷探针和证据。MIT 许可见仓库根目录 `LICENSE`。

从仓库根目录执行（根项目测试依赖已固定）：

```powershell
uv sync --extra test --locked
uv run pytest examples/ch37/tests --junit-xml=outputs/ch37-junit.xml
uv run pytest
```

运行环境要求 Python 3.12，与 Ch36 清单保持一致；若首次安装，先确保根虚拟环境采用该版本。`fixtures/cases.jsonl` 有 **30 个唯一固定夹具**，六组各五；测试使用独立临时目录，直接读 SQLite 作用表及事件。另有 27 组三步有限序列检查和配置/回归检查。夹具数、测试项数与任务成功率不是同一指标。没有运行真实语言模型、Hypothesis、覆盖率测量或分布式并发压测。

职责映射见 `test_matrix.yaml`，端到端索引见 `e2e_scenarios.jsonl`，人可读报告见 `ci_test_report.md`。EE 场景主要从应用入口 `Engine.run` 到本地存储；另有公开 CLI 的三切片子进程检查，范围分别标明。

## 能失败的缺陷对照

下面第一条应退出 **1**，第二条应退出 **0**；各用新目录：

```powershell
uv run python examples/ch37/regression_probe.py --client buggy --output outputs/ch37-buggy
uv run python examples/ch37/regression_probe.py --client fixed --output outputs/ch37-fixed
```

故障客户端仅存在于探针脚本：每次重试换 operation ID，服务依法创建两条记录。两者都可自报 completed，独立验收分别为 false / true。正式 Engine 没有切换为该缺陷实现的配置。测试中的回归断言既检查受控缺陷确实可被捕获，也检查正常恢复只产生一个作用。

报告归档在 `reports/`，只代表 2026-11-11 同机自检。第一次克隆运行无需依赖既有报告；以本次生成输出为准。测试已加入根 `pyproject.toml` 的 testpaths，现有 CI 的 pytest 入口会收集；尚未宣称远程 CI 或其他学生已运行。

## 基础与进阶作业

| 项目切片 | 基础任务 | 进阶任务 |
| --- | --- | --- |
| PRJ-1 | 改一个政策边界，用独立预期验证允许与拒绝各一例 | 接真实模型适配器，保持审批和写入权限由受信组件控制；分开报告模型质量与控制逻辑 |
| PRJ-2 | 给研究/执行/核验职责分别列输入和业务断言 | 接入公共持久消息协议与通信预算，验证过期 epoch、重复和接管；不能只增角色标签 |
| PRJ-3 | 重现 after_commit，解释 42→0 与唯一作用 | 接真实队列和认证服务，增加撤销/查权、并发与取消竞争；再与 Ch38/39 的观测和发布演练衔接 |

提交清单、夹具、断言理由和原始报告。不要只交最终答复截图。
