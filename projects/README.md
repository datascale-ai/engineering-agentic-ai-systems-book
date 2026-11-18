# 三项目共同入口

PRJ-1 验证单控制器闭环；PRJ-2 增加研究/核验/执行逻辑交接；PRJ-3 增加持久检查点与JSON事件流。
三者复用同一数据、证据、工单和接口1.0。配置清单分别位于项目目录。
`uv sync --frozen --extra test` 后按各README运行。
综合报告入口 `examples/ch34/run_projects.py`，实际结果在 `examples/ch34/results/report.json`。

本地路径为D的整合参考，C/E/F正式模块尚待接入；每项目外部学生独立运行仍待安排，不能以自检替代。
