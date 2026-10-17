# OpenSCENARIO HTML 可视化工具使用说明

## 简介

这是一个基于 **HTML + CSS** 的可视化工具，用于可视化 OpenSCENARIO 场景的执行状态。

### 核心特点

- ✅ **完美的纵向布局**：使用 CSS Flexbox，完全纵向排列
- ✅ **自动刷新**：每 2 秒自动刷新页面显示最新状态
- ✅ **状态高亮**：运行中的元素绿色高亮并放大显示
- ✅ **无需额外工具**：只需浏览器即可查看
- ✅ **实时更新**：支持 ROS2 日志订阅，实时更新状态

## 快速开始

### 1. 基本使用（静态查看）

```bash
# 生成 HTML 文件
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc --no-ros2

# 在浏览器中打开生成的 HTML 文件
# 文件路径会显示在输出中
```

### 2. 实时监控（推荐）

```bash
# 终端 1: 运行场景
python scenario_runner.py --openscenario srunner/examples/CyclistCrossing.xosc

# 终端 2: 运行可视化工具（自动订阅 ROS2 日志）
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc

# 工具会自动打开浏览器，页面每2秒刷新显示最新状态
```

### 3. 使用本地服务器（可选）

```bash
# 生成 HTML 文件
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc --no-ros2

# 启动本地服务器
cd /path/to/scenario_runner
python -m http.server 8000

# 在浏览器中访问
# http://localhost:8000/xosc_fsm.html
```

## 命令行选项

```bash
python srunner/tools/xosc_html_visualizer.py [选项] <xosc_file>

选项:
  -o, --output FILE    输出 HTML 文件路径（默认：xosc_fsm.html）
  --no-ros2           禁用 ROS2 日志订阅
  --no-browser        不自动打开浏览器
```

## 页面布局

生成的 HTML 页面包含两个主要部分：

### 1. 上方：OpenSCENARIO 结构图（静态参考）

- **黄色背景区域**
- 显示基于 XOSC 文件的完整结构
- 包括：Init、Story、Act、ManeuverGroup、Maneuver、Event、Action
- 显示层次关系和触发条件信息

### 2. 下方：场景执行状态图（实时更新）

- **白色背景区域**
- 显示当前场景的实际元素
- **状态颜色**：
  - 🟢 **绿色**：运行中 (RUNNING) - 高亮并放大
  - 🔵 **蓝色**：已完成 (COMPLETED)
  - 🔴 **红色**：已取消 (CANCELLED)
  - ⚪ **灰色**：空闲 (IDLE)

## 状态更新机制

### 自动刷新

页面每 2 秒自动刷新，显示最新状态。

### ROS2 日志订阅

如果启用了 ROS2 订阅（默认启用），工具会：

1. 订阅 `/scenario_runner/log` 话题
2. 解析日志消息（JSON 格式）
3. 更新对应元素的状态
4. 重新生成 HTML 文件
5. 浏览器自动刷新显示新状态

### 日志格式

工具期望接收以下 JSON 格式的日志：

```json
{
    "timestamp": 12.34,
    "element_type": "EVENT",
    "element_name": "CyclistStartsWalking",
    "status": "RUNNING"
}
```

状态值：
- `RUNNING`：元素开始运行
- `END`：元素正常结束
- `CANCEL`：元素被取消

## 使用示例

### 示例 1: 仅生成 HTML（不订阅日志）

```bash
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc --no-ros2 --no-browser
```

### 示例 2: 实时监控场景执行

```bash
# 终端 1
python scenario_runner.py --openscenario srunner/examples/CyclistCrossing.xosc

# 终端 2
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc
```

### 示例 3: 自定义输出文件

```bash
python srunner/tools/xosc_html_visualizer.py srunner/examples/CyclistCrossing.xosc -o my_scenario.html
```

## 优势对比

| 特性 | Graphviz | HTML + CSS |
|------|----------|------------|
| 布局控制 | ⚠️ 有限 | ✅ 完全控制 |
| 纵向布局 | ⚠️ 困难 | ✅ 完美 |
| 状态高亮 | ⚠️ 一般 | ✅ 清晰（绿色+放大） |
| 自动刷新 | ❌ 不支持 | ✅ 每2秒自动刷新 |
| 实时更新 | ⚠️ 需手动 | ✅ 自动更新 |
| 依赖 | 需要 graphviz | 只需浏览器 |
| 交互性 | ❌ 静态图片 | ✅ 可交互 |

## 故障排除

### 问题：浏览器无法打开文件

**解决方案**：
- 使用 `file://` 协议打开（完整路径）
- 或使用本地 HTTP 服务器

### 问题：页面不自动刷新

**解决方案**：
- 检查浏览器是否允许页面自动刷新
- 确认 HTML 文件路径正确
- 手动刷新浏览器（F5）

### 问题：状态不更新

**解决方案**：
- 检查 ROS2 是否正常运行
- 确认场景运行器正在发布日志
- 使用 `--no-ros2` 参数测试静态显示

### 问题：ROS2 连接失败

**解决方案**：
- 检查 ROS2 环境：`source /opt/ros/humble/setup.bash`
- 使用 `--no-ros2` 参数禁用订阅
- 检查话题：`ros2 topic echo /scenario_runner/log`

## 技术细节

### 布局实现

- 使用 CSS Flexbox 实现完美的纵向布局
- 每个元素垂直排列，连接线清晰
- 响应式设计，适配不同屏幕

### 状态高亮

- 运行中的元素使用绿色背景（#4CAF50）
- 添加 `transform: scale(1.05)` 放大效果
- 添加阴影效果增强视觉反馈

### 自动刷新

- JavaScript `setInterval` 每 2 秒刷新页面
- 显示最后更新时间
- 显示连接状态

## 相关文件

- `xosc_html_visualizer.py`：主程序
- `xosc_fsm_visualizer.py`：FSM 状态机实现（被 HTML 工具使用）
- `xosc_fsm.html`：生成的 HTML 文件

## 注意事项

1. **文件路径**：确保有写入权限
2. **浏览器兼容性**：推荐使用现代浏览器（Chrome、Firefox、Edge）
3. **刷新频率**：默认 2 秒，可在 HTML 中修改 JavaScript 代码调整
4. **性能**：大型场景文件可能生成较大的 HTML，但浏览器渲染速度很快

