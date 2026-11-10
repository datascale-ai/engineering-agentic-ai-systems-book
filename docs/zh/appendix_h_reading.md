# 附录 H：参考文献与延伸阅读

本附录按问题组织阅读入口。正式参考文献保留在使用它的章节，下面强调每项资料适合回答什么问题、阅读时检查什么条件。资料核验截至 2026-11-09；源码中的题名、作者与版本登记位于 `examples/d_shared/literature_registry.json`，规范访问状态位于 `standards_registry.json`。

## H.1 状态、记忆与跨会话能力

| 阅读 ID | 原始资料 | 阅读问题 | 正文回链 |
| --- | --- | --- | --- |
| H-M01 | Sumers 等，2023，[CoALA](https://arxiv.org/abs/2309.02427) | 记忆、行动与决策怎样组织为架构？哪些对象只是分类框架？ | [Ch14](part4/ch14_state_working_memory_context.md)、[Ch15](part4/ch15_long_term_memory.md) |
| H-M02 | Park 等，2023，[Generative Agents](https://arxiv.org/abs/2304.03442) | 经验、反思与相关性检索怎样影响模拟行为？评估与企业任务有什么差别？ | [Ch15](part4/ch15_long_term_memory.md) |
| H-M03 | Packer 等，2023，[MemGPT](https://arxiv.org/abs/2310.08560) | 记忆层之间怎样移动内容？“存得下”与“用得对”怎样区分？ | [Ch14](part4/ch14_state_working_memory_context.md)、[Ch15](part4/ch15_long_term_memory.md) |
| H-M04 | Zhong 等，2023，[MemoryBank](https://arxiv.org/abs/2305.10250) | 个性化信息怎样形成与保留？偏好变化如何评价？ | [Ch15](part4/ch15_long_term_memory.md) |
| H-M05 | Liu 等，2023，[Lost in the Middle](https://arxiv.org/abs/2307.03172) | 上下文位置怎样改变证据利用？长输入为何不等于稳定利用？ | [Ch14](part4/ch14_state_working_memory_context.md)、[Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-M06 | Maharana 等，2024，[LoCoMo](https://arxiv.org/abs/2402.17753) | 跨会话记忆的任务与标注怎样组织？ | [Ch15](part4/ch15_long_term_memory.md)、[Ch35](part8/ch35_open_problems.md) |
| H-M07 | Wu 等，2024，[LongMemEval](https://arxiv.org/abs/2410.10813) | 信息更新、时间与拒答怎样成为长期记忆评价的一部分？ | [Ch15](part4/ch15_long_term_memory.md)、[Ch35](part8/ch35_open_problems.md) |

建议先运行本书的结构化记忆选择，再阅读开放对话评测。前者隔离身份、时效和删除规则，后者增加抽取、时间推理和生成。比较结果时先统一任务分母与判定方式。

## H.2 知识检索与证据

| 阅读 ID | 原始资料 | 阅读问题 | 正文回链 |
| --- | --- | --- | --- |
| H-K01 | Robertson、Zaragoza，2009，[BM25 and Beyond](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf) | 词频饱和与长度归一化有什么作用？中文词项方案怎样影响匹配？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K02 | Karpukhin 等，2020，[DPR](https://arxiv.org/abs/2004.04906) | 双编码器怎样训练、检索与评价？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K03 | Lewis 等，2020，[RAG](https://arxiv.org/abs/2005.11401) | 检索与生成如何结合？回答正确与证据支持是否同一指标？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K04 | Khattab、Zaharia，2020，[ColBERT](https://arxiv.org/abs/2004.12832) | 晚交互如何权衡表示能力和检索效率？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K05 | Asai 等，2023，[Self-RAG](https://arxiv.org/abs/2310.11511) | 检索、生成与批评如何联合学习？与简单循环有什么区别？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K06 | Yan 等，2024，[Corrective RAG](https://arxiv.org/abs/2401.15884) | 检索质量判断如何影响后续取证？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K07 | Edge 等，2024，[GraphRAG](https://arxiv.org/abs/2404.16130) | 全局总结与局部事实查找有什么差别？图构建增加哪些证据责任？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |
| H-K08 | BAAI，[BGE 中文模型卡](https://huggingface.co/BAAI/bge-small-zh-v1.5) | 查询/片段编码接口、向量使用和模型版本怎样固定？ | [Ch16](part4/ch16_retrieval_knowledge_agents.md) |

阅读检索论文时分开看候选召回、排序、最终生成和计算成本。权限过滤、制度生效与组织发布属于额外工程约束，不能从开放域问答成绩直接推定已经满足。

## H.3 反馈、经验与持续学习

| 阅读 ID | 原始资料 | 阅读问题 | 正文回链 |
| --- | --- | --- | --- |
| H-L01 | Madaan 等，2023，[Self-Refine](https://arxiv.org/abs/2303.17651) | 自反馈怎样产生候选修订？收益依赖哪些任务与停止条件？ | [Ch17](part4/ch17_reflection_adaptation.md) |
| H-L02 | Shinn 等，2023，[Reflexion](https://arxiv.org/abs/2303.11366) | 语言反馈如何作为经验影响后续尝试？ | [Ch17](part4/ch17_reflection_adaptation.md) |
| H-L03 | Huang 等，2023，[自纠错局限](https://arxiv.org/abs/2310.01798) | 没有外部反馈时，推理修订为什么可能退化？ | [Ch17](part4/ch17_reflection_adaptation.md) |
| H-L04 | Kirkpatrick 等，2017，[EWC，PNAS 期刊版](https://doi.org/10.1073/pnas.1611835114)（预印本初版 2016） | 参数持续学习怎样保留旧任务？与应用记忆有何区别？ | [Ch17](part4/ch17_reflection_adaptation.md)、[Ch35](part8/ch35_open_problems.md) |
| H-L05 | Wang 等，2023，[Voyager](https://arxiv.org/abs/2305.16291) | 课程、技能库与反馈怎样组合？Minecraft 证据如何约束迁移主张？ | [Ch35](part8/ch35_open_problems.md) |

把有效研究与负面研究成对阅读：先查反馈来源、候选选择和预算，再比较效果。参数不变的经验积累可以改善行为，但不应称为每次交互都在训练模型。

## H.4 交互环境、评估与迁移

| 阅读 ID | 原始资料 | 重点 | 正文回链 |
| --- | --- | --- | --- |
| H-E01 | Liu 等，2023，[AgentBench](https://arxiv.org/abs/2308.03688) | 多环境任务、行动与失败类型 | [Ch35](part8/ch35_open_problems.md) |
| H-E02 | Zhou 等，2023，[WebArena](https://arxiv.org/abs/2307.13854) | 网页状态、动作空间、任务验收 | [Ch35](part8/ch35_open_problems.md) |
| H-E03 | Jimenez 等，2023，[SWE-bench](https://arxiv.org/abs/2310.06770) | 真实问题、代码修改、测试判定与数据划分 | [Ch35](part8/ch35_open_problems.md) |
| H-E04 | Xie 等，2024，[OSWorld](https://arxiv.org/abs/2404.07972) | 桌面观测、跨应用操作与执行评估 | [Ch35](part8/ch35_open_problems.md) |
| H-E05 | Open X-Embodiment Collaboration，2023，[OXE/RT-X](https://arxiv.org/abs/2310.08864) | 跨机器人数据、正迁移及目标平台条件 | [Ch35](part8/ch35_open_problems.md) |

上述论文会持续修订，榜单和模型能力也会变化。本书引用其问题设置与机制，未把论文首次发布时的得分写成当前模型排名。使用数据时另查所用版本与许可。

## H.5 身份、来源、采用与工程规范

| 阅读 ID | 原始资料 | 本书用途 | 正文回链 |
| --- | --- | --- | --- |
| H-G01 | IETF，2025，[RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | OAuth 授权安全实践 | [Ch33](part8/ch33_enterprise_adoption.md) |
| H-G02 | IETF，2013，[RFC 7009](https://www.rfc-editor.org/rfc/rfc7009.html) | 令牌撤销 | [Ch33](part8/ch33_enterprise_adoption.md) |
| H-G03 | IETF，2015，[RFC 7662](https://www.rfc-editor.org/rfc/rfc7662.html) | 令牌状态查询 | [Ch33](part8/ch33_enterprise_adoption.md) |
| H-G04 | W3C，2013，[PROV-DM](https://www.w3.org/TR/prov-dm/) | 实体、活动、参与者及来源关系 | [Ch33](part8/ch33_enterprise_adoption.md) |
| H-G05 | SQLite，[事务文档](https://www.sqlite.org/lang_transaction.html) | 本地事务的范围与限制 | [Ch34](part8/ch34_capstone_reference_architectures.md) |
| H-G06 | Brynjolfsson、Li、Raymond，[Generative AI at Work](https://www.nber.org/papers/w31161) | 工作场景与效果异质性，不移植收益率 | [Ch33](part8/ch33_enterprise_adoption.md) |
| H-G07 | OWASP，[LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) | 外部内容与指令来源区分 | [Ch15](part4/ch15_long_term_memory.md) |

规范给出接口与机制，业务组织仍需定义批准、责任、数据用途与申诉。将规范名称写进架构图不等于已经完成相应集成，应保留实际配置与测试证据。

## H.6 架构、推理、工具与运行时的基础导航

| 阅读 ID | 原始资料 | 阅读问题 | 对应篇 |
| --- | --- | --- | --- |
| H-F01 | Wei 等，2022，[Chain-of-Thought](https://arxiv.org/abs/2201.11903) | 推理提示的效果依赖什么任务与规模？推理文字与可核验行动有什么差别？ | 第二篇 |
| H-F02 | Yao 等，2022，[ReAct](https://arxiv.org/abs/2210.03629) | 推理与行动如何交替？观测如何改变下一步？ | 第一、三篇 |
| H-F03 | Schick 等，2023，[Toolformer](https://arxiv.org/abs/2302.04761) | 模型怎样学习调用工具？训练机制与运行时授权怎样分开？ | 第三篇 |
| H-F04 | Bai 等，2022，[Constitutional AI](https://arxiv.org/abs/2212.08073) | AI反馈用于什么训练过程？与运行时业务批准有什么区别？ | 第二、七篇 |
| H-F05 | CNCF，[CloudEvents 1.0.2](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md) | 事件身份、来源与类型怎样标准化？标准信封不提供哪些业务保证？ | 第六篇 |

基础导航先提供经核验入口；各章负责人在合稿时结合实际正文补充引用支持关系。标准事件格式有助于互操作，租约、幂等、取消与业务验收仍由系统协议定义。第九篇可沿 Ch34 的实际代码检查这些区别。

## H.7 资料登记样例与索引入口

完整条目样例：`H-L02`，题名 *Reflexion: Language Agents with Verbal Reinforcement Learning*，Shinn 等，2023，原始标识 `arXiv:2303.11366`，核验日期 2026-11-09；用于 Ch17 的语言反馈与经验机制；不作为本书脚本修复率的来源。登记将书目存在、内容支持与本地实验三个证据层分开。

补充导航：[主题索引](topic_index.md)、[人名与机构索引](name_index.md)、[版本与补充材料](afterword.md)。其他篇的正式书目由相应章节负责人随合稿补入，本附录的主题导航结构可以直接扩展。
