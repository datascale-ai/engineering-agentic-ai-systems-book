# Ch15：受控长期记忆

从仓库根目录运行 `uv run --frozen python examples/ch15/run_experiment.py`。
Python 3.11+，不使用模型、网络或账户，原创教学夹具沿用 MIT。

`memory.py` 实现内存主库、元数据索引、缓存世代、快照和删除标记。
`personalization_eval.jsonl` 包含 3 用户×10 会话与三策略的逐次结果；
`results/report.json` 为运行摘要。偏好是已结构化的输入，没有自然语言提取器。
值正确、跨主体使用、陈旧使用独立计数，错误类别可能重叠。

运行 `uv run --frozen pytest tests/test_d_remaining.py` 验证身份、作用域、修订、
删除后缓存和恢复。物理备份销毁、持久删除标记和真实认证尚不在内存实现范围。
