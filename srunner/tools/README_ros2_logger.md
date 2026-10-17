# ROS2 日志系统使用说明

## 概述

场景运行器现在支持通过ROS2话题发布JSON格式的日志消息。系统包含两个组件：

1. **日志发布器** (`ros2_logger.py`) - 自动集成到场景运行器中，发布日志到ROS2话题
2. **日志订阅者** (`ros2_log_subscriber.py`) - 独立的订阅者节点，用于接收和打印日志

## 使用方法

### 1. 启动日志订阅者

在一个终端中运行订阅者：

```bash
# 方法1: 直接运行Python脚本
python3 srunner/tools/ros2_log_subscriber.py

# 方法2: 使用ros2 run（如果已安装为ROS2包）
ros2 run scenario_runner ros2_log_subscriber
```

### 2. 运行场景

在另一个终端中运行场景：

```bash
python3 scenario_runner.py --scenario <your_scenario>
```

订阅者将自动接收并打印所有日志消息。

## 日志格式

发布的JSON消息格式：

```json
{
  "timestamp": 123.45,
  "element_type": "ACT",
  "element_name": "场景名称",
  "status": "RUNNING"
}
```

打印输出格式：

```
[OSC][123.45s][ACT][场景名称] RUNNING
```

## 话题信息

- **话题名称**: `/scenario_runner/log`
- **消息类型**: `std_msgs/String`
- **消息内容**: JSON格式的字符串

## 使用ros2命令行工具

你也可以直接使用ROS2命令行工具查看日志：

```bash
# 查看原始JSON消息
ros2 topic echo /scenario_runner/log

# 查看话题信息
ros2 topic info /scenario_runner/log

# 查看消息频率
ros2 topic hz /scenario_runner/log
```

## 故障排除

### ROS2未安装

如果ROS2未安装，日志系统会自动回退到标准输出（print），不影响场景运行。

### 订阅者无法接收消息

1. 确保ROS2环境已正确设置（source ROS2的setup.bash）
2. 检查话题是否存在：`ros2 topic list`
3. 确认场景运行器正在运行并发布消息


