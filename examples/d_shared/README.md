# D组公共教学资产

代码与50份政策、40道问答、60条综合任务均为原创教学资产，沿用仓库 MIT 许可。
运行 `uv run --frozen python examples/d_shared/build_data.py` 重建。
20主题各旧/新版本共40份，A部门受限附件10份；测试日2026-11-09。
语料不存在真实员工、企业制度或私有文本。

`retrieval.py` 是词法检索与闭域答案；`projects.py` 是SQLite协议核；`project_cli.py` 是公开入口。
本地认证、批准与日期为夹具，生产系统必须接可信身份和批准服务。
`literature_registry.json` 登记核验元数据，`standards_registry.json` 保留成功及失败访问状态。
未成功读取的来源不能据登记声称正文已核验。`references.bib` 是 D 章节与附录 H 共用的规范书目，按原始署名、DOI 和官方文档核对，共 43 项资料；`examples/ch14/references.bib` 是其中的章节子集，合稿时使用公共文件以免重复。

论文登记的 `official_author_order` 保留原页面完整署名顺序，`verified_version` 与 `version_date` 标明核对版本。预印本条目以首次提交年份为年，修订日期单列；EWC 采用 2017 年 PNAS 期刊信息，同时保留 2016 年预印本标识。集体作者名称按原文完整保存。
