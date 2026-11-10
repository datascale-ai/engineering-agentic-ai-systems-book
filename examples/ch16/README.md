# Ch16：真实检索、确定性答案渲染

词法：`uv run --frozen python examples/ch16/run_retrieval.py`。
向量：`HF_HUB_DISABLE_IMPLICIT_TOKEN=1 uv run --frozen --with fastembed==0.7.3 python examples/ch16/run_retrieval.py --dense --cache-dir /tmp/book-embedding-cache`。
首次需下载 BGE 中文模型。私有 Hugging Face 凭据过期时可在本地命令中取消隐式凭据，代码不读取、输出或提交令牌。

公共数据在 `examples/d_shared/data/`；BM25 是中文字/双字词项实现，BGE 是真实 ONNX 编码器，
融合使用倒数排名，重排是主题元数据规则，不是神经交叉编码器。答案只渲染已知金额，未调用生成模型。

报告按 20 道有答案题算 Recall@3，按 40 题算最终正确；另记录越权片段。
`pipeline_ms` 是为同题执行全部对照的共享总耗时，不能用来宣称各策略单独延迟。
`lexical_ms` 与 `dense_and_fusion_ms` 是分阶段暖启动时间，模型初始化不计入。
`adaptive_pilot` 固定前12题，按查询是否明确含首项主题决定补检，最多2次。
