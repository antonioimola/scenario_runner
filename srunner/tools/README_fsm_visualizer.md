# OpenSCENARIO FSM + Graphviz 可视化工具

## 简介

这是一个**轻量级、高性能**的可视化方案，使用 **FSM（有限状态机）+ Graphviz** 来可视化 OpenSCENARIO 场景的执行状态。

### 核心优势

- ✅ **轻量级**：无需安装 Groot2 或 BehaviorTree.CPP
- ✅ **高性能**：只在状态切换时更新，开销极小
- ✅ **易用**：自动生成 .dot 文件，一行命令生成图片
- ✅ **实时**：支持自动刷新，接近实时状态机
- ✅ **标准格式**：使用 Graphviz 标准格式，兼容性好

## 安装依赖

### 必需依赖
- Python 3.6+
- Graphviz（用于生成图片）

```bash
# Ubuntu/Debian
sudo apt install graphviz

# 或使用 pip（仅 Python 绑定）
pip install graphviz
```

### 可选依赖（用于自动刷新）
```bash
# inotify-tools（Linux 自动刷新）
sudo apt install inotify-tools
```

### 可选依赖（用于实时日志）
- ROS2 (rclpy)：用于订阅场景运行日志

## 快速开始

### 1. 基本使用（生成静态图）

```bash
# 生成初始状态图
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc

# 这会生成 xosc_fsm.dot 文件
# 然后手动生成 PNG：
dot -Tpng xosc_fsm.dot -o xosc_fsm.png
```

### 2. 实时监控（推荐）

```bash
# 终端 1: 运行场景
python scenario_runner.py --openscenario srunner/examples/CyclistCrossing.xosc

# 终端 2: 运行可视化工具（自动订阅 ROS2 日志）
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc --auto-refresh
```

### 3. 自动刷新图片（最接近实时）

```bash
# 终端 1: 运行可视化工具
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc --auto-refresh

# 终端 2: 运行自动刷新脚本（监控 .dot 文件变化并生成 PNG）
./srunner/tools/auto_refresh.sh

# 终端 3: 使用图片查看器打开 xosc_fsm.png（支持自动刷新）
# 例如：eog xosc_fsm.png 或 feh xosc_fsm.png
```

## 工作原理

### FSM 状态机

工具将 OpenSCENARIO 场景建模为有限状态机：

- **IDLE**：元素未运行（灰色）
- **RUNNING**：元素正在运行（绿色高亮）
- **COMPLETED**：元素已完成（蓝色）
- **CANCELLED**：元素被取消（红色）

### 状态转换

当收到 ROS2 日志时：

1. 解析日志消息（element_type, element_name, status）
2. 更新对应元素的状态
3. 导出新的 .dot 文件（高亮当前状态）
4. 如果启用 `--auto-refresh`，自动生成 PNG

### Graphviz 输出

生成的 .dot 文件包含：

- **节点**：每个场景元素（Story, Act, Maneuver, Event, Action）
- **边**：元素之间的层次关系
- **高亮**：当前运行的元素用绿色高亮显示

## 命令行选项

```bash
python srunner/tools/xosc_fsm_visualizer.py [选项] <xosc_file>

选项:
  -o, --output DIR     输出目录（默认：当前目录）
  --no-ros2            禁用 ROS2 日志订阅
  --auto-refresh       自动生成 PNG 图片（需要 graphviz）
```

## 使用示例

### 示例 1: 仅生成初始图

```bash
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc --no-ros2
dot -Tpng xosc_fsm.dot -o xosc_fsm.png
```

### 示例 2: 实时监控 + 自动刷新

```bash
# 终端 1: 可视化工具
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc --auto-refresh

# 终端 2: 自动刷新脚本
./srunner/tools/auto_refresh.sh

# 终端 3: 场景运行器
python scenario_runner.py --openscenario srunner/examples/CyclistCrossing.xosc
```

### 示例 3: 手动刷新

```bash
# 运行可视化工具（不自动刷新）
python srunner/tools/xosc_fsm_visualizer.py srunner/examples/CyclistCrossing.xosc

# 在另一个终端，手动刷新
watch -n 0.5 'dot -Tpng xosc_fsm.dot -o xosc_fsm.png'
```

## 输出文件

- **xosc_fsm.dot**：Graphviz 源文件（文本格式）
- **xosc_fsm.png**：生成的图片（如果使用 --auto-refresh）

## 状态高亮说明

在生成的图中：

- 🟢 **绿色高亮**：当前正在运行的元素
- 🔵 **蓝色**：已完成的元素
- 🔴 **红色**：被取消的元素
- ⚪ **灰色**：空闲的元素

## 性能特点

- **轻量级**：只在状态切换时更新，不持续绘制
- **高效**：.dot 文件生成速度极快（< 10ms）
- **低开销**：适合长时间运行

## 与 Groot2 方案对比

| 特性 | FSM + Graphviz | Groot2 + BT |
|------|----------------|-------------|
| 安装复杂度 | ⭐ 低（只需 graphviz） | ⭐⭐⭐ 高（需要 BT.CPP） |
| 性能开销 | ⭐⭐⭐ 极低 | ⭐⭐ 中等 |
| 实时性 | ⭐⭐⭐ 接近实时 | ⭐⭐⭐ 实时 |
| 可视化质量 | ⭐⭐⭐ 专业 | ⭐⭐⭐ 专业 |
| 交互性 | ⭐ 静态图片 | ⭐⭐⭐ 可编辑 |

## 故障排除

### 问题：找不到 dot 命令

```bash
# 安装 Graphviz
sudo apt install graphviz

# 验证安装
dot -V
```

### 问题：ROS2 连接失败

```bash
# 检查 ROS2 环境
source /opt/ros/humble/setup.bash  # 根据您的 ROS2 版本调整

# 或使用 --no-ros2 参数
python srunner/tools/xosc_fsm_visualizer.py <file> --no-ros2
```

### 问题：图片不自动刷新

```bash
# 确保使用 --auto-refresh 参数
python srunner/tools/xosc_fsm_visualizer.py <file> --auto-refresh

# 或使用自动刷新脚本
./srunner/tools/auto_refresh.sh
```

## 高级用法

### 自定义输出格式

```bash
# 生成 SVG（矢量图，可缩放）
dot -Tsvg xosc_fsm.dot -o xosc_fsm.svg

# 生成 PDF
dot -Tpdf xosc_fsm.dot -o xosc_fsm.pdf

# 生成其他格式
dot -Tpng -Gdpi=300 xosc_fsm.dot -o xosc_fsm_hd.png  # 高分辨率
```

### 集成到工作流

```bash
# 在脚本中使用
python srunner/tools/xosc_fsm_visualizer.py scenario.xosc --no-ros2
dot -Tpng xosc_fsm.dot -o status.png
# 然后可以在报告或文档中使用 status.png
```

## 相关资源

- Graphviz 文档: https://graphviz.org/
- Graphviz 图库: https://graphviz.org/gallery/
- ROS2 日志格式: 参考 `ros2_logger.py`

