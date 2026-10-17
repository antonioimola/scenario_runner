# OpenSCENARIO 可视化方案对比

## 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **HTML + CSS** | ✅ 精确控制布局<br>✅ 自动刷新<br>✅ 浏览器查看<br>✅ 状态高亮清晰 | ⚠️ 需要浏览器 | **推荐** - 最灵活 |
| **Mermaid** | ✅ 语法简洁<br>✅ 自动布局<br>✅ 支持多种格式 | ⚠️ 布局控制有限 | 简单场景 |
| **文本树** | ✅ 极轻量<br>✅ 无依赖<br>✅ 终端查看 | ⚠️ 视觉效果一般 | 快速查看 |
| **Graphviz** | ✅ 标准工具<br>✅ 多种输出格式 | ⚠️ 复杂布局困难 | 简单流程图 |

## 方案 1: HTML + CSS（推荐）⭐

**特点**：精确控制、自动刷新、状态高亮

```bash
# 生成 HTML 文件
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc

# 在浏览器中打开
# 文件会自动每2秒刷新一次
```

**优点**：
- ✅ 完美的纵向布局
- ✅ 状态高亮清晰（绿色=运行中）
- ✅ 自动刷新（无需手动）
- ✅ 响应式设计
- ✅ 无外部依赖（只需浏览器）

## 方案 2: Mermaid 图表

**特点**：简洁语法、自动布局

```bash
# 生成 Mermaid 代码
python srunner/tools/xosc_mermaid_visualizer.py srunner/examples/CyclistCrossing.xosc

# 在 https://mermaid.live 查看
# 或使用 VS Code 的 Mermaid 插件
```

## 方案 3: 文本树形结构

**特点**：极轻量、终端查看

```bash
# 生成文本树
python srunner/tools/xosc_text_visualizer.py srunner/examples/CyclistCrossing.xosc

# 输出示例：
# MyStory
#   └─ Behavior
#       └─ ManeuverSequence
#           └─ CyclistCrossingManeuver
#               └─ CyclistStartsWalking [RUNNING] ⬢
```

## 方案 4: 改进的 Graphviz（当前）

**特点**：标准工具、多种格式

```bash
# 生成 .dot 文件
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc

# 生成图片
dot -Tpng xosc_fsm.dot -o xosc_fsm.png
```

## 推荐使用

**首选：HTML + CSS 方案**
- 布局完美控制
- 自动刷新
- 状态高亮清晰
- 无需安装额外工具

**备选：文本树方案**
- 极轻量
- 终端直接查看
- 适合快速调试

## 快速开始

### HTML 方案（推荐）

```bash
# 1. 生成 HTML
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc

# 2. 打开浏览器查看
# 文件路径会显示在输出中

# 3. 实时更新（如果启用 ROS2）
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc
# HTML 会自动每2秒刷新
```

