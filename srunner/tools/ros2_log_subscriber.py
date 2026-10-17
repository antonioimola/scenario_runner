#!/usr/bin/env python

# Copyright (c) 2019-2020 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
ROS2日志订阅者，用于接收并解析场景运行日志
"""

import json
import sys

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except ImportError:
    print("错误: ROS2 (rclpy) 未安装。请先安装ROS2。")
    sys.exit(1)


class ROS2LogSubscriber(Node):
    """
    ROS2日志订阅者节点，订阅/scenario_runner/log话题并解析打印日志
    """
    
    def __init__(self):
        super().__init__('scenario_runner_log_subscriber')
        self.subscription = self.create_subscription(
            String,
            '/scenario_runner/log',
            self.log_callback,
            10
        )
        self.subscription  # 防止未使用变量警告
        self.get_logger().info('日志订阅者已启动，正在监听 /scenario_runner/log 话题...')
        self.get_logger().info('等待日志消息...')
    
    def log_callback(self, msg):
        """
        接收到日志消息时的回调函数
        
        Args:
            msg: String消息，包含JSON格式的日志数据
        """
        try:
            # 解析JSON消息
            log_data = json.loads(msg.data)
            
            # 提取字段
            timestamp = log_data.get('timestamp', 0)
            element_type = log_data.get('element_type', 'UNKNOWN')
            element_name = log_data.get('element_name', 'UNKNOWN')
            status = log_data.get('status', 'UNKNOWN')
            
            # 格式化输出
            print(f"[OSC][{timestamp:.2f}s][{element_type}][{element_name}] {status}")
            
            # 可选：打印完整的JSON数据（用于调试）
            # print(f"完整JSON: {json.dumps(log_data, ensure_ascii=False, indent=2)}")
            
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON解析失败: {e}')
            self.get_logger().error(f'原始消息: {msg.data}')
        except Exception as e:
            self.get_logger().error(f'处理日志消息时出错: {e}')


def main(args=None):
    """
    主函数
    """
    rclpy.init(args=args)
    
    subscriber = ROS2LogSubscriber()
    
    try:
        print("=" * 60)
        print("场景运行器日志订阅者")
        print("=" * 60)
        print("正在监听 /scenario_runner/log 话题...")
        print("按 Ctrl+C 退出")
        print("=" * 60)
        rclpy.spin(subscriber)
    except KeyboardInterrupt:
        print("\n正在关闭订阅者...")
    finally:
        subscriber.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()


