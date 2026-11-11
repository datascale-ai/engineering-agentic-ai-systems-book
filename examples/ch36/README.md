# Ch36 本地参考实现

版本：`ch36-local-0.1`；2026-11-11。运行核心只用 Python 标准库；无密钥、无运行期联网、无外部工单写入。原创数据和代码采用仓库根目录 MIT 许可（见 `LICENSE`）。

这是 Ch36/37 共用的教学基线。PRJ-1 展示提案、政策检查、批准范围、写入和验收；PRJ-2 增加研究证据核验事件；PRJ-3 在服务提交后结束客户端子进程，再用另一个子进程恢复。三个入口共用 `src/book_reference/`，不代表完成 Ch34 的完整综合项目。真实模型、并发多智能体、平台发布和回滚仍需后续适配。

## 从仓库根目录运行

先安装 uv；基线自检时使用 uv 0.12.8、CPython 3.12.14。锁文件限制项目依赖及 Python 允许范围；清单额外要求 Python 3.12。首次取得 Python/根项目依赖可能需要网络。示例执行阶段不需要网络。

```powershell
uv sync --project examples/ch36 --python 3.12 --locked
uv run --project examples/ch36 --python 3.12 --locked python examples/ch36/run.py reproduce --output outputs/ch36-first
```

预期最后一行为 `{"passed": true, "project_slices": 3}`。三个项目各有一个工单及一个 `created` 事件，最终状态为 `completed`。PRJ-3 中断阶段的子进程退出码 **42** 是显式故障钩子的约定；恢复阶段为 0。不要把整个命令的非零退出忽略掉。

输出目录须新建或为空。脚本不会清空已有目录。需要再次完整复现时换一个输出目录。单项目可运行：

```powershell
uv run --project examples/ch36 --python 3.12 --locked python examples/ch36/run.py run --project PRJ-1 --output outputs/ch36-single
```

只有继续同一任务和同一资产基线时使用 `--resume`。不允许在原会话下悄悄更换政策、任务修订或清单。

## 资产与结果

- `run_manifest.toml`：白名单配置；Python 原生 `tomllib` 读取。它承担任务书 `run_manifest.yaml` 的职责，避免为基础路径增加 YAML 依赖。
- `pyproject.toml` + `uv.lock`：环境声明和解析结果，承担 `environment.lock` 的职责。
- `asset_inventory.json`：`.gitattributes`、`run.py`、项目声明、锁、清单、`src/**/*.py` 和全部 fixtures 的逐字节 SHA-256。默认运行只核验，不更新。此目录固定 LF 行尾，避免 Git 在不同平台换行转换后造成摘要漂移。
- `fixtures/`：原创政策、固定任务、固定模型响应、提示接口说明、人工预期和数据卡。提示文本被记录但固定替身不会执行它。
- `resolved_manifest.json`：本次解析后的清单、资产摘要、项目、Python/SQLite/平台信息。源码摘要覆盖尚未提交的新增资产，Git HEAD 仅供定位。
- `session.sqlite`、`service.sqlite`：客户端状态与工具作用分开持久化，不跨库提交。
- `events.json`、`summary.json`：事件和独立读取存储所得的验收结果。

比较复现时核对业务状态、字段、数量和事件偏序，不比较时间戳、绝对路径或 SQLite 文件字节。`asset_inventory.json` 是漂移探测基准，不是签名或可信供应链证明。

维护者确实修改代码/配置/数据并审查后才更新摘要：

```powershell
uv run --project examples/ch36 --python 3.12 python examples/ch36/run.py seal --reason reviewed-change-description
```

不要为绕过错误直接执行 `seal`。应先定位差异，跑 Ch37 测试，核对新预期，再检查 inventory 的改动。`uv sync --locked` 验证锁是否与项目声明一致；`--frozen` 省略这项检查，不能代替验收。

## 本地边界

审批 `Approval` 是受信测试驱动构造的内存 grant，非真实身份认证。服务按可信调用者给出的 tenant 和 operation ID 去重，同键异载荷拒绝；同键旧结果允许在原 grant 过期后回查，不产生新作用。生产服务仍须单独认证每次请求并检查查询权限。

`ReplyGate` 只在当前实例内检查任务修订、assignment epoch 与重复消息，不是分布式持久收件箱。PRJ-2 是顺序角色职责切片；没有工作队列、租约或真实模型间通信。取消阻止后续新动作，不能撤销已提交工单。完成会话的再次读取返回缓存结果，不证明外部对象永远未变。连接超时保留 pending，后续查询与预算决定下一步；未确认时不声称成功。

工程测试见 `../ch37/README.md`，逐项复现检查见 `reproducibility_checklist.md`。
