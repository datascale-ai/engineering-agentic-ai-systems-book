"""Original editable vector mechanisms for chapters 15–17 and 33–35.

No raster or traced content. Node labels and directed edges remain semantic
SVG groups. Run from any directory; rendered previews are local QA assets.
"""

from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
FONT = "Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif"
BLUE = "#0072B2"
INK = "#273442"
MUTED = "#526373"
PALE = "#EDF5FA"
ORANGE = "#A95800"


class Figure:
    def __init__(self, chapter, name, width=1120, height=600, description=""):
        self.chapter = chapter
        self.name = name
        self.w = width
        self.h = height
        self.items = [
            f"<title>{escape(name)}</title><desc>{escape(description)}</desc>",
            f'<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8" fill="none" stroke="{INK}" stroke-width="1.3"/></marker></defs>',
            '<rect width="100%" height="100%" fill="white"/>',
        ]
        self.nodes = []
        self.edges = []

    def text(self, x, y, lines, size=22, color=INK, anchor="middle", weight="400"):
        if isinstance(lines, str):
            lines = lines.split("|")
        self.items.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">'
            + "".join(
                f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.45}">{escape(t)}</tspan>'
                for i, t in enumerate(lines)
            )
            + "</text>"
        )

    def box(self, key, x, y, w, h, label, authority=False, derived=False, size=22):
        color = BLUE if authority else INK
        self.items.append(
            f'<g id="{key}" data-role="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{PALE if authority else "white"}" stroke="{color}" stroke-width="2"'
            + (' stroke-dasharray="7 5"' if derived else "")
            + "/>"
        )
        lines = label.split("|")
        self.text(
            x + w / 2,
            y + h / 2 - (len(lines) - 1) * size * 0.72 + size * 0.34,
            lines,
            size,
        )
        self.items.append("</g>")
        self.nodes.append({"id": key, "label": label})

    def frame(self, x, y, w, h, label):
        self.items.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="#8B99A5" stroke-width="1.5"/>'
        )
        self.text(x + 18, y + 30, label, 19, MUTED, "start", "600")

    def arrow(self, key, points, label=None, lx=None, ly=None, dashed=False):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.items.append(
            f'<polyline id="{key}" data-role="edge" points="{pts}" fill="none" stroke="{INK}" stroke-width="1.8" marker-end="url(#arrow)"'
            + (' stroke-dasharray="6 5"' if dashed else "")
            + "/>"
        )
        if label:
            self.text(lx, ly, label, 18, MUTED)
        self.edges.append({"id": key, "points": points, "label": label})

    def save(self):
        p = ROOT / f"docs/images/ch{self.chapter}/{self.name}.svg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img">'
            + "".join(self.items)
            + "</svg>\n"
        )
        return {
            "figure_id": self.name,
            "path": str(p.relative_to(ROOT)),
            "nodes": self.nodes,
            "edges": self.edges,
            "format": "pure editable SVG",
            "license": "MIT",
            "source": "original chapter mechanism; no external artwork",
        }


manifest = []
f = Figure(
    15,
    "fig-15-01-memory-lifecycle",
    height=560,
    description="候选写入须验证来源与作用域，召回先筛选，删除反馈到派生层。",
)
f.box("candidate", 35, 170, 190, 90, "候选记忆|原句与来源", derived=True)
f.box("validation", 295, 170, 205, 90, "归属与范围确认|允许用途", True)
f.box("primary", 575, 170, 200, 90, "有效主记录|修订与期限", True)
f.box("recall", 875, 170, 205, 90, "过滤后排序|返回来源")
f.arrow("propose", [(225, 215), (295, 215)])
f.arrow("accept", [(500, 215), (575, 215)])
f.arrow("retrieve", [(775, 215), (875, 215)])
f.box("change", 575, 365, 200, 90, "纠正／删除|记录撤销", True)
f.box("derived", 875, 365, 205, 90, "索引与缓存|失效或重建", derived=True)
f.arrow("invalidate", [(775, 410), (875, 410)])
f.arrow("change-record", [(675, 365), (675, 260)])
f.arrow("clear-recall", [(975, 365), (975, 260)], dashed=True)
f.box("backup", 295, 365, 205, 90, "备份保留|恢复过滤", derived=True)
f.arrow("restore-policy", [(575, 410), (500, 410)])
f.text(
    55,
    70,
    "写入与使用共享同一组主体、范围、时间与来源约束",
    23,
    anchor="start",
    weight="600",
)
f.text(560, 520, "删除在线可读性与备份到期处理分别验收", 19, MUTED)
manifest.append(f.save())

f = Figure(
    15,
    "fig-15-02-scope-boundaries",
    height=580,
    description="组织共享、个人与会话作用域相互嵌套，另一个主体不能跨界读取。",
)
f.frame(30, 35, 1060, 490, "租户 teaching：组织规则由知识责任人维护")
f.frame(65, 100, 475, 350, "主体 u1")
f.frame(575, 100, 475, 350, "主体 u2")
f.box("u1-default", 95, 160, 415, 75, "个人默认：上午出发", True)
f.box("u1-session", 95, 300, 185, 90, "会话 s3|临时中午", derived=True)
f.box("u1-other", 325, 300, 185, 90, "会话 s4|回退默认")
f.arrow("override", [(187, 300), (187, 260), (300, 260), (300, 235)])
f.arrow("fallback", [(417, 300), (417, 235)])
f.box("u2-default", 605, 160, 415, 75, "个人默认：下午出发", True)
f.box("u2-session", 720, 300, 185, 90, "会话 s3|使用 u2 默认")
f.arrow("own-default", [(812, 300), (812, 235)])
f.text(560, 490, "相同主题与相同会话名，不产生跨主体读取权", 20, MUTED)
f.text(560, 560, "临时会话结束后退出覆盖；组织规则不被个人偏好改写", 20)
manifest.append(f.save())

f = Figure(
    16,
    "fig-16-01-permission-pipeline",
    height=620,
    description="主体和目标时间约束知识集合，再检索、重排、打包与验证主张。",
)
f.box("identity", 35, 45, 230, 80, "主体＋目标时间", True)
f.box("documents", 35, 225, 230, 105, "版本化文档|正文／附件", True)
f.box("allowed", 345, 210, 225, 120, "允许且有效集合|租户／部门／时间", True)
f.arrow("scope", [(265, 85), (455, 85), (455, 210)])
f.arrow("filter", [(265, 277), (345, 277)])
f.box("rank", 650, 210, 190, 120, "检索与重排|候选片段")
f.arrow("rank-allowed", [(570, 270), (650, 270)])
f.box("evidence", 900, 210, 185, 120, "证据包|原文与版本")
f.arrow("package", [(840, 270), (900, 270)])
f.box("verify", 650, 445, 190, 100, "主张逐条核验|支持与适用", True)
f.arrow("claim-evidence", [(992, 330), (992, 495), (840, 495)])
f.box("answer", 345, 445, 225, 100, "有依据回答|或材料不足")
f.arrow("return", [(650, 495), (570, 495)])
f.arrow(
    "recheck",
    [(455, 330), (455, 390), (745, 390), (745, 445)],
    "范围与版本复验",
    600,
    380,
    dashed=True,
)
f.text(560, 590, "缓存命中仍需核对范围、知识快照与撤销", 20, MUTED)
manifest.append(f.save())

f = Figure(
    16,
    "fig-16-02-retrieval-loop",
    height=580,
    description="固定一次取证；按需路径在材料不足且有预算时改写补检。",
)
f.frame(25, 30, 1070, 190, "固定检索")
f.box("fixed-q", 60, 100, 180, 70, "问题")
f.box("fixed-r", 330, 100, 180, 70, "一次检索")
f.box("fixed-a", 600, 100, 420, 70, "证据核验 → 回答／不足", True)
f.arrow("fixed1", [(240, 135), (330, 135)])
f.arrow("fixed2", [(510, 135), (600, 135)])
f.frame(25, 260, 1070, 280, "按需检索：访问范围保持不变")
f.box("adaptive-q", 60, 340, 180, 80, "问题与缺口")
f.box("adaptive-r", 330, 340, 180, 80, "检索")
f.box("enough", 600, 340, 180, 80, "支持充分？", True)
f.box("adaptive-a", 870, 340, 180, 80, "回答／不足")
f.arrow("adaptive1", [(240, 380), (330, 380)])
f.arrow("adaptive2", [(510, 380), (600, 380)])
f.arrow("sufficient", [(780, 380), (870, 380)], "是／预算耗尽", 825, 330)
f.arrow(
    "retry",
    [(690, 420), (690, 490), (150, 490), (150, 420)],
    "不足且仍有预算：改写或补充材料",
    430,
    480,
)
manifest.append(f.save())

f = Figure(
    17,
    "fig-17-01-update-loop",
    height=610,
    description="反馈形成诊断与候选，修复和保留集共同验证，再批准发布或拒绝。",
)
f.box("failure", 35, 70, 210, 90, "失败轨迹|目标与差异")
f.box("diagnosis", 320, 70, 210, 90, "错误诊断|新增证据")
f.box("candidate", 610, 70, 210, 90, "候选变更|范围与版本", derived=True)
f.arrow("diagnose", [(245, 115), (320, 115)])
f.arrow("propose", [(530, 115), (610, 115)])
f.box("repair", 475, 265, 210, 85, "修复集|原失败与近邻")
f.box("holdout", 785, 265, 255, 85, "保留集|旧能力与反例")
f.arrow("repair-test", [(715, 160), (715, 215), (580, 215), (580, 265)])
f.arrow("holdout-test", [(715, 215), (912, 215), (912, 265)])
f.box("acceptance", 610, 440, 210, 90, "接受决定|成本与退化", True)
f.arrow("repair-result", [(580, 350), (580, 395), (680, 395), (680, 440)])
f.arrow("holdout-result", [(912, 350), (912, 395), (750, 395), (750, 440)])
f.box("publish", 320, 440, 210, 90, "分范围发布|保留回滚", True)
f.arrow("publish-update", [(610, 485), (530, 485)], "通过", 570, 470)
f.arrow(
    "reject",
    [(715, 530), (715, 575), (140, 575), (140, 160)],
    "不通过：拒绝／预算内再提议／交接",
    425,
    565,
)
manifest.append(f.save())

f = Figure(
    17,
    "fig-17-02-adaptation-boundaries",
    height=570,
    description="当前计划、跨任务经验与离线参数训练有不同作用范围和验证。",
)
for y, title in [(35, "当前任务"), (210, "后续任务"), (385, "离线模型更新")]:
    f.frame(25, y, 1070, 145, title)
f.box("plan-input", 60, 90, 230, 65, "观察与任务反馈")
f.box("plan-change", 420, 90, 240, 65, "修订计划")
f.box("plan-check", 790, 90, 260, 65, "动作前置条件检查", True)
f.arrow("plan1", [(290, 122), (420, 122)])
f.arrow("plan2", [(660, 122), (790, 122)])
f.box("experience", 60, 265, 230, 65, "经验候选", derived=True)
f.box("experience-check", 420, 265, 240, 65, "独立验证与批准", True)
f.box("memory-release", 790, 265, 260, 65, "策略／记忆版本发布", True)
f.arrow("experience1", [(290, 297), (420, 297)])
f.arrow("experience2", [(660, 297), (790, 297)])
f.box("training-data", 60, 440, 230, 65, "数据治理与训练")
f.box("model-eval", 420, 440, 240, 65, "模型评估与回归", True)
f.box("model-release", 790, 440, 260, 65, "参数版本部署／回退", True)
f.arrow("train1", [(290, 472), (420, 472)])
f.arrow("train2", [(660, 472), (790, 472)])
manifest.append(f.save())

f = Figure(
    33,
    "fig-33-01-enterprise-integration",
    height=600,
    description="主体身份约束知识和业务，批准独立，审计串联主体、证据与结果。",
)
f.box("user", 35, 65, 205, 90, "员工请求|稳定主体")
f.box("identity", 325, 65, 220, 90, "身份与授权|角色／撤销版本", True)
f.box("assistant", 325, 265, 220, 100, "助手控制器|证据与任务")
f.box("knowledge", 650, 65, 225, 90, "企业知识库|版本与数据域", True)
f.box("approval", 650, 265, 225, 100, "批准流程|主管与申请对象", True)
f.box("business", 650, 465, 225, 90, "业务工具|查询／提交", True)
f.box("audit", 35, 465, 205, 90, "关联审计|主体与结果")
f.arrow("authenticate", [(240, 110), (325, 110)])
f.arrow("context", [(435, 155), (435, 265)])
f.arrow("knowledge-query", [(545, 290), (585, 290), (585, 110), (650, 110)])
f.arrow("approve", [(545, 315), (650, 315)])
f.arrow("execute", [(435, 365), (435, 510), (650, 510)])
f.arrow("approval-gate", [(762, 365), (762, 465)], "批准有效", 820, 425)
f.arrow("audit-flow", [(325, 330), (285, 330), (285, 510), (240, 510)], dashed=True)
f.text(140, 265, "服务账户不替代|用户与业务授权", 20, MUTED)
manifest.append(f.save())

f = Figure(
    33,
    "fig-33-02-adoption-stages",
    height=490,
    description="阶段验收决定扩大，失败回到修复，停止时保留人工服务。",
)
for i, (key, label) in enumerate(
    [
        ("discover", "发现|基线与责任"),
        ("offline", "离线|证据与权限"),
        ("shadow", "影子|不执行动作"),
        ("pilot", "受控试点|批准后行动"),
        ("scale", "扩大|分部门验证"),
    ]
):
    x = 25 + i * 220
    f.box(key, x, 115, 190, 110, label, authority=i in [1, 3])
    if i:
        f.arrow("next" + str(i), [(x - 30, 170), (x, 170)])
f.box("decision", 450, 320, 220, 90, "质量＋总成本|继续／暂停／退出", True)
f.arrow("gate", [(780, 225), (780, 365), (670, 365)])
f.arrow("repair", [(450, 365), (120, 365), (120, 225)], "修复条件后重新验证", 280, 350)
f.arrow("expand", [(670, 390), (1000, 390), (1000, 225)], "满足约定门槛", 850, 425)
f.text(560, 65, "每个阶段都有可执行验收与人工接管路径", 23, weight="600")
manifest.append(f.save())

f = Figure(
    34,
    "fig-34-01-project-progression",
    height=590,
    description="PRJ-1核心链、PRJ-2角色交接、PRJ-3持久控制逐步递进。",
)
f.frame(25, 30, 1070, 140, "PRJ-1：共同证据与业务工具")
f.box("knowledge", 70, 90, 220, 55, "知识证据", True)
f.box("controller", 420, 90, 250, 55, "单一控制器")
f.box("tools", 800, 90, 230, 55, "核验＋工单工具", True)
f.arrow("p1a", [(290, 117), (420, 117)])
f.arrow("p1b", [(670, 117), (800, 117)])
f.frame(25, 205, 1070, 140, "PRJ-2：新增角色交接，沿用同一证据和工具")
for x, key, label in [
    (70, "research", "研究"),
    (420, "verify", "核验"),
    (800, "execute", "执行"),
]:
    f.box(key, x, 265, 230, 55, label, authority=key == "verify")
f.arrow("p2a", [(300, 292), (420, 292)])
f.arrow("p2b", [(650, 292), (800, 292)])
f.frame(25, 380, 1070, 175, "PRJ-3：新增持久运行与控制面")
f.box("state", 70, 450, 230, 70, "状态与检查点", True)
f.box("events", 420, 450, 230, 70, "事件流与取消", True)
f.box("release", 800, 450, 230, 70, "权限／评测／版本", True)
f.arrow("p3a", [(300, 485), (420, 485)])
f.arrow("p3b", [(650, 485), (800, 485)])
manifest.append(f.save())

f = Figure(
    34,
    "fig-34-02-single-agent-chain",
    height=530,
    description="申请取证、验收、查询与幂等提交形成闭环，缺少条件则保留。",
)
f.box("request", 30, 100, 180, 90, "申请|类别与批准")
f.box("evidence", 290, 100, 215, 90, "当前可读政策|原文与额度", True)
f.box("verify", 585, 100, 215, 90, "独立验收|条件满足？", True)
f.box("query", 880, 100, 210, 90, "查询已有工单")
f.arrow("read", [(210, 145), (290, 145)])
f.arrow("check", [(505, 145), (585, 145)])
f.arrow("lookup", [(800, 145), (880, 145)])
f.box("hold", 585, 350, 215, 90, "保留申请|说明缺失条件")
f.box("commit", 880, 350, 210, 90, "幂等创建|事务内复验", True)
f.arrow("not-ready", [(692, 190), (692, 350)], "缺条件", 755, 280)
f.arrow("create", [(985, 190), (985, 350)], "未存在且满足", 985, 280)
f.arrow(
    "result",
    [(985, 440), (985, 480), (397, 480), (397, 190)],
    "返回证据与业务结果",
    600,
    510,
    dashed=True,
)
manifest.append(f.save())

f = Figure(
    34,
    "fig-34-03-role-handoff",
    height=620,
    description="控制器、研究、核验、执行四泳道中的可校验交接。",
)
xs = [110, 400, 690, 1000]
for x, label in zip(xs, ["控制器", "研究角色", "核验角色", "执行角色"]):
    f.text(x, 45, label, 23, weight="600")
    f.items.append(
        f'<line x1="{x}" y1="70" x2="{x}" y2="560" stroke="#A4AFB8" stroke-dasharray="5 5"/>'
    )
f.arrow("assign", [(110, 120), (400, 120)], "任务＋世代＋预算", 255, 104)
f.arrow("submit-evidence", [(400, 225), (690, 225)], "证据卡＋消息信封", 545, 209)
f.arrow("accept", [(690, 330), (1000, 330)], "核验结果＋当前版本", 845, 314)
f.arrow(
    "business-result",
    [(1000, 445), (110, 445)],
    "幂等提交后：工单结果与验收事件",
    560,
    430,
)
f.arrow(
    "late", [(400, 530), (690, 530)], "旧世代结果 → 拒绝，不提交", 545, 515, dashed=True
)
f.text(560, 595, "角色提议不产生批准；最终责任由控制器收口", 20, MUTED)
manifest.append(f.save())

f = Figure(
    34,
    "fig-34-04-platform-control",
    height=620,
    description="控制面约束执行面，持久状态与事件支持恢复和取消。",
)
f.frame(25, 25, 1070, 170, "控制面")
for x, key, label in [
    (65, "config", "配置与发布版本"),
    (420, "auth", "主体与权限"),
    (775, "evaluation", "评测／观测／回滚"),
]:
    f.box(key, x, 90, 280, 75, label, True)
f.frame(25, 250, 1070, 330, "执行面")
f.box("runtime", 65, 335, 250, 95, "任务运行时|世代与预算")
f.box("state", 420, 335, 250, 95, "持久状态|检查点与事件", True)
f.box("tool", 775, 335, 280, 95, "证据核验与工具|提交点复验", True)
f.arrow("persist", [(315, 382), (420, 382)])
f.arrow("commit", [(670, 382), (775, 382)])
f.arrow("config-binding", [(205, 165), (205, 335)])
f.arrow("auth-binding", [(560, 165), (560, 220), (915, 220), (915, 335)])
f.arrow(
    "observe",
    [(915, 430), (915, 505), (560, 505), (560, 430)],
    "恢复／流式事件／取消持久化",
    700,
    540,
)
f.arrow("telemetry", [(1055, 382), (1070, 382), (1070, 128), (1055, 128)], dashed=True)
manifest.append(f.save())

f = Figure(
    35,
    "fig-35-01-evidence-map",
    height=620,
    description="证据可复现程度与环境覆盖作为两条轴，避免用局部实验推出普遍成熟。",
)
f.arrow("x-axis", [(130, 500), (1050, 500)])
f.arrow("y-axis", [(130, 500), (130, 60)])
f.text(650, 565, "环境覆盖：固定任务 → 跨任务 → 持续真实环境", 22)
f.text(245, 48, "可重复核验的证据", 22, BLUE)
f.box("hypothesis", 190, 405, 260, 70, "E0：拟议研究问题", derived=True)
f.box("local", 300, 295, 300, 80, "E1：限定环境结果")
f.box("reproduce", 520, 185, 260, 80, "E2：可重复运行", True)
f.box("field", 790, 75, 270, 80, "E3：跨环境持续验证", True)
f.text(650, 450, "本书单机协议结果|不直接移动到“普遍自主”", 20, MUTED)
f.text(650, 610, "等级绑定具体主张；图中没有技术效果数值", 19, MUTED)
manifest.append(f.save())

f = Figure(
    35,
    "fig-35-02-long-horizon-relations",
    height=620,
    description="长程任务的目标义务、状态、学习、身份和责任共同约束行动。",
)
f.box("goals", 40, 70, 240, 90, "目标与未决义务")
f.box("state", 430, 70, 250, 90, "当前状态与来源", True)
f.box("action", 830, 70, 250, 90, "行动与结果核验", True)
f.arrow("goals-state", [(280, 115), (430, 115)])
f.arrow("state-action", [(680, 115), (830, 115)])
f.box("experience", 430, 290, 250, 100, "经验候选|验证与版本", derived=True)
f.arrow("feedback", [(955, 160), (955, 340), (680, 340)])
f.arrow("learned", [(555, 290), (555, 160)])
f.box("identity", 40, 480, 290, 85, "身份与授权变化", True)
f.box("responsibility", 790, 480, 290, 85, "责任与人工接管", True)
f.arrow("scope", [(185, 480), (185, 220), (430, 220), (430, 160)])
f.arrow("handoff", [(955, 340), (955, 480)])
f.arrow(
    "responsible-action",
    [(1080, 520), (1100, 520), (1100, 115), (1080, 115)],
    dashed=True,
)
f.text(560, 565, "经验更新不能自行扩大权限或移转责任", 20, MUTED)
manifest.append(f.save())

(ROOT / "examples/figures/d_figure_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
)
print(f"Wrote {len(manifest)} original SVG figures")
