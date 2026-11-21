# 学生 E 项目与实验报告

日期：2026-11-20。数据、源码和参数按 `asset_inventory.json` 冻结；源清单摘要为 `0dcbd7899ccf30aeee29f7e7315814ec1bc9c3432ac1cc09653b0d460954d33c`。原始结果在 [归档入口](reports/study_20261120/report.json)，各项均是实际本地运行，未调用真实模型或生产服务。

| 项目 | 实际结果 | 原始记录 |
| --- | --- | --- |
| PRJ-2 | 8任务、24角色工作关闭、3工单；RPC73/240；首项42→0，唯一作用不增加 | [项目报告](reports/study_20261120/project2/report.json)、[事件](reports/study_20261120/project2/events.json) |
| Ch19 | 协议18/20合格完成，1取消、1升级；简化组8/20合格，4未收口；协议RPC83/240 | [20任务及对照](reports/study_20261120/ch19/report.json)、[事件](reports/study_20261120/ch19/events.json) |
| Ch20 | 20题×5种子×3组=300条；标签相符70/78/100，证据同时合格66/74/100；脚本规则审查不代表模型能力 | [组汇总](reports/study_20261120/ch20/report.json)、[逐调用与评分](reports/study_20261120/ch20/trials.jsonl)、[主张矩阵](reports/study_20261120/ch20/claim_evidence_matrix.jsonl) |
| Ch21 | 200试次；表单O/C成功5/40，网格15/40，各分母50；4组约束均50/50；错误作用均0 | [汇总](reports/study_20261120/ch21/report.json)、[逐试次](reports/study_20261120/ch21/trials.jsonl)、[事件](reports/study_20261120/ch21/events.jsonl) |
| 附录D | 上线、灰度错配阻断、配置路由回滚、退役4条实际记录均通过预设检查 | [生命周期记录](reports/study_20261120/deploy/report.json) |
| 测试 | 根98项通过，含原77项与新增21项；无失败、错误或跳过 | [JUnit](../ch37/reports/student-e-20261120-junit.xml) |

运行命令见 [STUDIES.md](STUDIES.md)。`all` 最后输出 passed=true，退出0。源码位置、夹具与许可见 [证据索引](evidence_index.md)。SQLite原始状态由同版命令重建。五种子重复不等于扩大独立任务数，不作总体显著性/性能结论。

Ch20的相关错误和强审查均由脚本公开构造，24,000字节上限不是token预算；实际token和金额未测量。Ch21使用受限结构化视图及预知静态地图，未测浏览器视觉或机器人；保护停止、未知与业务完成分开记录。PRJ-2为本地最小实现，团队schema/正式数据/真实端点与独立学生复现待完成；附录D不是生产发布批准。

## 同机分发副本验证

复制全部已跟踪和未忽略的新交付文件后，新建项目与根依赖虚拟环境，使用缓存离线重建。环境安装、全部项目/实验、根98项测试和MkDocs严格构建五步均退出0；[副本记录](reports/study_20261120/clean_copy.json)与本报告使用同一源清单摘要，[副本JUnit](../ch37/reports/student-e-20261120-clean-junit.xml)保存98项无失败、错误或跳过的结果。另检查七个中文网页的1,283个本地链接/锚点、38个源码/输入摘要；205个其他既有文件保持不变。

这是作者同机的干净副本自检，副本包含本次尚未提交的新文件。它不是已发布Git树或其他学生独立复现；不能据此填写F签认或团队公共接口已冻结。
