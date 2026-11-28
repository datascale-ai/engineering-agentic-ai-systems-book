---
title: "第九篇：工程实践、可运行代码与测试"
owner: "F"
status: zh-draft
version: zh-draft-0.3
updated: 2026-11-27
---

# 第九篇：工程实践、可运行代码与测试

**Engineering Practice, Runnable Code, and Testing**

> **范围与扩展声明**：Springer 提案原始目录包含前八篇共 35 章；本篇 Ch36 至 Ch39 预算 112 个等效出版页，是本书团队为打通“从架构概念到可检出、可测试、可回归、可发布代码”的实训路径而保留的工程实践扩展，不能标注为原提案已包含部分。本篇由学生 F 统筹，学生 E 执笔 Ch36 与 Ch37，学生 F 执笔 Ch38 与 Ch39，Ch38 与 Ch39 由学生 A 独立审稿。

## 把全书架构落到同一套可运行参考底座

[Ch34 综合项目与参考架构](../part8/ch34_capstone_reference_architectures.md) 阐述了单智能体知识工具助手 PRJ-1、多智能体协作系统 PRJ-2 与生产级智能体平台 PRJ-3 的设计取舍。第九篇不再重复前文原理与项目叙事，而是复用唯一一套共享参考实现 `examples/ch36/src/book_reference/` 与统一原创夹具，带领读者依次完成四个工程里程碑：

1. **搭环境与锁基线（Ch36）**：用运行清单、依赖锁与内容摘要消除配置漂移，确保干净检出后得到同一可核验结果。
2. **写分层行为测试（Ch37）**：用确定性单元测试、集成测试与本地端到端断言守住幂等、授权与状态恢复不变量。
3. **建回归门禁与故障注入（Ch38）**：将黄金风险切片、OpenTelemetry GenAI 风格轨迹断言与 9 类沙箱故障注入接入自动质量门禁。
4. **跑预发布演练与五要素回滚（Ch39）**：把构建、测试、回归、安全扫描、审批、预发布冒烟以及覆盖代码、配置、数据、权限与缓存的五要素回滚贯通为持续交付流水线与 100 分工程综合实践。

## 章节与工程产物地图

| 章节 | 预算 | 执笔 | 工程核心与必须交付的可运行产物 | 代码与报告入口 |
| --- | ---: | :---: | --- | --- |
| [Ch36 参考实现架构、配置与可复现环境](ch36_reference_implementation.md) | 26 页 | E | 共享核心 `book_reference/`、运行清单、依赖锁、内容摘要与三项目最小切片 | `examples/ch36/` |
| [Ch37 智能体单元测试、集成测试与端到端测试](ch37_agent_testing.md) | 28 页 | E | 30 项固定行为夹具、分层测试套件、可失败缺陷探针与 CI 测试报告 | `examples/ch37/` |
| [Ch38 评估回归、故障注入与可观测测试](ch38_regression_fault_injection.md) | 28 页 | F | 黄金风险切片、三类受控变更拦截、9 类沙箱故障注入、轨迹断言与回归报告 | `examples/ch38/` |
| [Ch39 部署演练、持续交付与工程综合实践](ch39_deployment_continuous_delivery.md) | 30 页 | F | 三档部署配置、七阶段持续交付门禁、四项预发布回滚演练与 100 分综合评分标准 | `examples/ch39/` |

## 离线稳定入口与基础/扩展边界

本篇全部基础实训路径均采用无密钥、可离线运行的确定性模拟端点与原创夹具，不依赖任何付费账号或专有平台。接入真实外部模型端点属于扩展路径，必须单独记录模型端点、价格日期、预算与重复波动，严禁把确定性控制逻辑门禁通过宣称为真实模型能力或生产集群容量验证。

读者可在仓库根目录按以下顺序运行完整验证链：

```powershell
# 1. 结构与公共契约校验
python -m pytest tests/test_book_structure.py -q
# 2. Ch37 分层行为测试
python -m pytest examples/ch37/tests/test_behaviour.py -q
# 3. Ch38 评估回归、轨迹断言与 9 类沙箱故障注入
python examples/ch38/regression_runner/runner.py
# 4. Ch39 预发布发布、故障注入、五要素回滚与 PRJ-3 综合演练
python examples/ch39/drill_runner.py
# 5. 第六篇与第九篇全量自动化断言
python -m pytest tests/ch22_25/ tests/ch38_39/ -q
```

## 跨章与附录回链

异步运行时、持久会话与流式打断基线见 [第六篇](../part6/index.md)；评估方法论、故障分类、安全威胁与生产治理原理见 [第七篇](../part7/index.md)；公共接口模式、部署档位模板与安全清单分别集中维护于 [附录 C](../appendix_c_schemas.md)、[附录 D](../appendix_d_deployment.md) 与 [附录 F](../appendix_f_security.md)。
