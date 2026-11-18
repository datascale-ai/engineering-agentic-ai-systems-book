# Ch14 任务状态与工作记忆

配套中文正文：`docs/zh/part4/ch14_state_working_memory_context.md`。

本目录提供原创合成长会话、状态规范、SQLite 状态实现和确定性表示实验。
运行环境为 Python 3.11+，只使用 Python 标准库；测试使用仓库的 pytest 依赖。
代码与原创数据沿用仓库 MIT 许可证，无需外部模型账号。

## 运行

从仓库根目录执行：

```bash
uv sync --frozen --extra test --python 3.12
uv run python examples/ch14/build_cases.py
uv run python examples/ch14/representation_experiment.py \
  --output examples/ch14/results/representation_report.json
uv run pytest tests/test_ch14_state.py
uv run mkdocs build --clean --strict
```

预期生成 10 条、每条 60 轮的会话；实验得到 50 个检查点、每项对照 200 个当前事实项。
默认对照的正确保留数依次为 200、10、200，详细结果见 JSON。

容量对照与 UTF-8 表格导出：

```bash
uv run python examples/ch14/export_results.py
```

## 文件与责任

| 文件 | 内容 |
| --- | --- |
| `state_store.py` | 接受条件、来源角色、版本、事务内去重与行动前检查 |
| `agent_state_schema.json` | Draft 2020-12 状态模式草案 |
| `build_cases.py` | 原创会话生成器 |
| `state_update_cases.jsonl` | 已生成会话及事实标注 |
| `representation_experiment.py` | 表示保留与序列化开销测量 |
| `export_results.py` | 固定容量对照与 CSV 汇总 |
| `results/representation_report.json` | 主实验逐检查点原始结果 |
| `results/representation_summary.csv` | 正文表14-03对应数据 |
| `results/summary_capacity.csv` | 正文表14-04对应数据 |
| `experiment_card.md` | 输入、对照、指标、命令和结果解释范围 |
| `claim_sources.md` | 主张、公开来源、定位和核验记录 |
| `references.bib` | 本章参考文献元数据 |
| `figure_manifest.csv`、`figure_labels.csv` | SVG 图源、许可、引用位置与图中文字 |

`Principal` 必须由应用认证层构造，不能直接接受模型提供的身份。
示例没有身份认证服务，也没有完整的任务级服务授权策略。
`authorize` 返回检查时刻的决定，不执行外部操作或预留额度。
事件去重表不等于完整审计与会话事件流，过期判断也不等于数据删除。

表示实验的事实标注由生成器提供，结构化状态直接使用这些更新。
它衡量确定性表示规则，没有调用模型，不包含自然语言事实抽取准确率、模型 token 或模型性能数据。
