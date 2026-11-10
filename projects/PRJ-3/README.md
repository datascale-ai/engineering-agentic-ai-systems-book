# PRJ-3 本地参考路径

在仓库根运行：
```bash
uv run --frozen python projects/PRJ-3/run.py --database /tmp/book-prj3-example.sqlite3 --task T01-1
```
预期 `create`、`P01@2#1`、额度500、工单 `ticket:T01-1`。同库同参数重跑仍一张。
`T01-0` 返回 `hold`，不创建。新实验使用新路径；持久库重复运行用于幂等与恢复。
故障示例：另用新库并加 `--fault missing_evidence`，应拒绝且退出码2。
综合：`uv run --frozen python examples/ch34/run_projects.py`；测试：`uv run --frozen pytest`。

共享数据/许可见 `examples/d_shared/data_card.json`；配置为 config.json，代码不会读取密钥。
角色是确定性逻辑，端点是本地SQLite；不声明已评测真实模型或生产分布式系统。
基础与进阶作业、验收和限制见中文 Ch34 对应项目小节。
