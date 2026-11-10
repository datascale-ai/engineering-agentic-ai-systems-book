# Ch14 主张与来源核验

核验日期：2026-11-09。核验者：Codex 辅助核对公开元数据与下列具体公开页面；作者技术审阅尚未完成。
文献页面、规范和数据库文档用于核对对应主张，不将整份文献视为本章程序的运行证明。

| 主张ID | 正文位置与主张 | 来源/版本 | 定位 | 适用条件与核验 |
| --- | --- | --- | --- | --- |
| Ch14-C01 | 14.2.2 工作记忆概念背景 | Baddeley与Hitch, 1974，DOI 10.1016/S0079-7421(08)60452-1 | Crossref DOI条目中的题名、作者、年、页47-89 | 已核元数据；只支持概念来源，不据此推导工程数据结构 |
| Ch14-C02 | 14.2.2 记忆、行动空间与决策的架构组织 | CoALA, arXiv:2309.02427v3 | arXiv作者、版本与摘要：modular memory / action space / decision-making | 已核公开摘要；本章状态接口为原创设计 |
| Ch14-C03 | 14.2.3 不同记忆层的数据移动与有限上下文管理 | MemGPT, arXiv:2310.08560v2 | 摘要：virtual context management / memory tiers | 已核公开摘要；不声称记忆调入构成业务授权 |
| Ch14-C04 | 14.2.3 长输入信息位置影响指定任务表现 | Lost in the Middle, arXiv:2307.03172v2 | 摘要中的multi-document QA / key-value retrieval / position effects | 已核任务与范围，不外推所有模型 |
| Ch14-C05 | 14.3.3 条件请求防止丢失更新 | RFC9110, 2022 | §8.8验证器，§13.1.1 If-Match，§13.2条件求值 | 已核规范正文；本章整数版本为教学实现 |
| Ch14-C06 | 14.3.3、14.4.2 隔离级别、事务并发 | PostgreSQL18文档 | §13.2，尤其Read Committed与Serializable | 已核官方正文；未测PostgreSQL部署 |
| Ch14-C07 | 14.3.3、14.4.2 行级锁与死锁 | PostgreSQL18文档 | §13.3.2、§13.3.4 | 已核官方正文；SQLite示例不能当成PG实测 |
| Ch14-C08 | 14.2.4、14.3.2 JSON结构与验证词汇 | JSON Schema Draft2020-12 Core与Validation | 验证词汇中的type、enum、required、组合约束 | 已核规范页面；权限和业务规则由程序检查 |
| Ch14-C09 | 14.2.5 外部数据中的行为指令与提示注入 | OWASP LLM01:2025 | 条目中直接与间接提示注入说明 | 已核官方条目；本章未开展安全攻击评测 |
| Ch14-C10 | 14.2.6 经验记录、检索与反思 | Generative Agents, arXiv:2304.03442v2 | 摘要中的experience record / reflection / retrieval | 已核公开摘要；不推导生产任务权限 |
| Ch14-C11 | 14.5.4、14.5.5 表示保留与大小数值 | 本章运行结果 | `results/representation_report.json`、两份CSV | 已执行，确定性表示测量，无模型 |
| Ch14-C12 | 14.5.6 指定状态规则与故障路径 | `tests/test_ch14_state.py`与`state_store.py` | 具名行为测试、实际本地pytest结果 | 已执行，非外部服务或生产验证 |

公开来源URL与完整元数据见正文脚注及 `references.bib`。
