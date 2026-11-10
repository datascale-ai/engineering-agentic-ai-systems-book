"""Build 50 original policy documents, 40 questions, and 60 integrated tasks."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOPICS = [
    ("差旅住宿", "出差酒店房费每晚能报销多少", "差旅住宿费每晚报销上限", 400, 500),
    ("市内交通", "出租车费用报销需要什么", "市内交通单次报销上限", 80, 100),
    ("业务招待", "客户餐叙能报销多少", "业务招待每人每次费用上限", 150, 180),
    ("培训报名", "参加课程允许支付多少报名费", "培训报名单次费用上限", 2000, 3000),
    ("设备采购", "买工作电脑的预算是多少", "设备采购单件预算上限", 6000, 8000),
    ("图书采购", "专业书籍能购买多少金额", "图书采购每人每月上限", 300, 400),
    ("软件订阅", "购买开发工具可以付多少钱", "软件订阅每人每月上限", 200, 300),
    ("远程办公", "居家工作配件可以报销多少", "远程办公配件年度上限", 500, 800),
    ("会议注册", "学术会议注册费额度是多少", "会议注册每次费用上限", 2000, 2500),
    ("快递寄送", "寄送项目材料可以报销多少", "快递寄送每单费用上限", 50, 80),
    ("加班餐费", "晚间工作吃饭可以领多少", "加班餐费每人每晚上限", 30, 40),
    ("夜间交通", "深夜下班打车可以领多少", "夜间交通每次报销上限", 80, 120),
    ("临时场地", "租用活动会议室允许多少钱", "临时场地每日费用上限", 1000, 1500),
    ("测试云资源", "实验服务器可花多少钱", "测试云资源每项目每月上限", 1000, 2000),
    ("数据标注", "给研究数据打标签预算多少", "数据标注每项目月度上限", 2000, 3500),
    ("打印装订", "打印项目报告允许支出多少", "打印装订每次费用上限", 100, 150),
    ("安全培训", "安全认证考试可以报销多少", "安全培训每人年度上限", 1000, 1800),
    ("出差餐补", "在外地工作每日伙食补助多少", "出差餐补每人每日上限", 80, 100),
    ("跨城交通", "乘坐城际铁路可报销多少钱", "跨城交通单程费用上限", 500, 700),
    ("资料翻译", "项目文件翻译服务预算多少", "资料翻译每项目费用上限", 1500, 2500),
]


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def build():
    docs, questions, tasks = [], [], []
    for i, (topic, paraphrase, label, old, current) in enumerate(TOPICS, 1):
        for version, limit in [(1, old), (2, current)]:
            doc_id = f"P{i:02d}"
            text = (
                f"第{i}项：{topic}管理办法。{label}为{limit}元。申请人应在费用发生前提交项目归属、"
                f"用途和金额，由所属部门负责人审批。报销时需要真实票据和对应批准记录。"
                f"超过上限的申请须进入例外审批，普通工单不得自行放宽额度。"
                f"该条款适用于部门A和部门B的在岗人员，不授权助手直接付款。"
            )
            docs.append(
                {
                    "document_id": doc_id,
                    "version": version,
                    "chunk_id": f"{doc_id}@{version}#1",
                    "topic": topic,
                    "title": f"{topic}管理办法",
                    "text": text,
                    "limit_yuan": limit,
                    "valid_from": "2026-01-01" if version == 1 else "2026-10-01",
                    "valid_to": "2026-10-01" if version == 1 else "2027-01-01",
                    "tenant_id": "teaching",
                    "departments": ["A", "B"],
                    "classification": "internal",
                }
            )
        if i <= 10:
            doc_id = f"R{i:02d}"
            docs.append(
                {
                    "document_id": doc_id,
                    "version": 1,
                    "chunk_id": f"{doc_id}@1#1",
                    "topic": topic,
                    "title": f"{topic}部门A例外附件",
                    "text": f"{topic}部门A专项例外记录。仅部门A审批人可读，专项额度为{current + 5000}元。该记录不得向部门B提供。",
                    "limit_yuan": current + 5000,
                    "valid_from": "2026-10-01",
                    "valid_to": "2027-01-01",
                    "tenant_id": "teaching",
                    "departments": ["A"],
                    "classification": "restricted",
                }
            )
        for variant in range(3):
            tasks.append(
                {
                    "task_id": f"T{i:02d}-{variant}",
                    "topic": topic,
                    "tenant_id": "teaching",
                    "department": "B",
                    "owner_id": f"user-{i % 3}",
                    "query": paraphrase,
                    "document_id": f"P{i:02d}",
                    "expected_evidence": f"P{i:02d}@2#1",
                    "amount_yuan": current - 1 if variant < 2 else current + 1,
                    "approved": variant == 1,
                    "expected_action": "create" if variant == 1 else "hold",
                }
            )
        if i <= 10:
            for kind, query in [
                ("direct", f"{topic}的当前费用上限是多少"),
                ("paraphrase", paraphrase),
            ]:
                questions.append(
                    {
                        "question_id": f"Q-{kind}-{i:02d}",
                        "kind": kind,
                        "query": query,
                        "department": "B",
                        "as_of": "2026-11-09",
                        "relevant": [f"P{i:02d}@2#1"],
                        "expected_limit_yuan": current,
                    }
                )
            questions.append(
                {
                    "question_id": f"Q-denied-{i:02d}",
                    "kind": "denied",
                    "query": f"{topic}部门A专项例外额度是多少",
                    "department": "B",
                    "as_of": "2026-11-09",
                    "relevant": [],
                    "expected_limit_yuan": None,
                    "forbidden": [f"R{i:02d}@1#1"],
                }
            )
            questions.append(
                {
                    "question_id": f"Q-unknown-{i:02d}",
                    "kind": "unanswerable",
                    "query": f"{topic}是否可以给家属申请海外商业保险",
                    "department": "B",
                    "as_of": "2026-11-09",
                    "relevant": [],
                    "expected_limit_yuan": None,
                }
            )
    target = HERE / "data"
    target.mkdir(exist_ok=True)
    write_jsonl(target / "policies.jsonl", docs)
    write_jsonl(target / "rag_eval_set.jsonl", questions)
    write_jsonl(target / "tasks.jsonl", tasks)
    for d in docs:
        p = target / "policies" / (d["chunk_id"].replace("#1", "") + ".md")
        p.parent.mkdir(exist_ok=True)
        p.write_text(
            f"# {d['title']}（版本{d['version']}）\n\n{d['text']}\n", encoding="utf-8"
        )
    print(
        f"Original teaching data: {len(docs)} documents, {len(questions)} questions, {len(tasks)} tasks"
    )


if __name__ == "__main__":
    build()
