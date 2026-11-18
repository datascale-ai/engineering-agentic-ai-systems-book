# D 章节的 SVG 配图

Ch14—17、Ch33—35 共 23 张 SVG：16 张机制与架构图，以及 7 张场景插画。
场景插画放在各章开头的案例附近，用工作桌、档案柜、政策书、修理台、办公室和研究旅程呈现章节主题。

在仓库根目录运行：

```bash
python3 examples/figures/build_d_figures.py
python3 examples/figures/build_d_illustrations.py
```

两份脚本只依赖 Python 标准库，分别生成 14 张机制图和 7 张场景插画；Ch14 的两张原有机制图直接维护 SVG 源文件。
`d_figure_manifest.json` 记录机制图的节点与连线，`d_illustration_manifest.json` 记录插画主题、图中文字、分组、路径和来源。

生成文件位于 `docs/images/chNN/`，正文通过相对路径引用。修改插画时优先编辑生成脚本，再重新生成；也可在矢量编辑器中直接编辑 SVG，但重新运行脚本会覆盖直接修改。

插画由原生路径、形状、可编辑文字与分组构成，无嵌入位图或外部素材，沿用仓库的 MIT 许可。
中文字体依次使用 Noto Sans CJK SC、苹方、微软雅黑和系统无衬线字体；出版导出时应统一字体并核对换字后的排版。

本地预览可用 `rsvg-convert -o preview.png 图文件.svg`，整站检查使用 `uv run --frozen mkdocs build --clean --strict`。
