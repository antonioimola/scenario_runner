#!/usr/bin/env python

# Copyright (c) 2019-2020 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
ROS2日志发布器模块，用于将场景运行日志以JSON格式发布到ROS2话题
"""

import json

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    # 创建一个虚拟的Node基类，用于ROS2不可用的情况
    class Node:
        pass


class ROS2Logger(Node):
    """
    ROS2日志发布器，将日志以JSON格式发布到/scenario_runner/log话题
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ROS2Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not ROS2Logger._initialized:
            if not ROS2_AVAILABLE:
                # ROS2不可用，使用回退模式
                self.publisher = None
                ROS2Logger._initialized = True
            else:
                try:
                    # 如果ROS2未初始化，则初始化
                    if not rclpy.ok():
                        rclpy.init()
                    super(ROS2Logger, self).__init__('scenario_runner_logger')
                    self.publisher = self.create_publisher(String, '/scenario_runner/log', 10)
                    ROS2Logger._initialized = True
                except Exception as e:
                    # 如果ROS2初始化失败，设置为None，后续会回退到print
                    print(f"Warning: ROS2初始化失败，将使用标准输出: {e}")
                    self.publisher = None
                    ROS2Logger._initialized = True
        else:
            # 如果已经初始化过，确保publisher属性存在
            if not hasattr(self, 'publisher'):
                self.publisher = None
    
    def log(self, timestamp, element_type, element_name, status):
        """
        发布日志消息到ROS2话题
        
        Args:
            timestamp: 时间戳（秒）
            element_type: 元素类型（ACT, SCENE, MANEUVER, EVENT, ACTION）
            element_name: 元素名称
            status: 状态（RUNNING, END, CANCEL等）
        """
        log_data = {
            "timestamp": timestamp,
            "element_type": element_type,
            "element_name": element_name,
            "status": status
        }
        
        json_str = json.dumps(log_data, ensure_ascii=False)

        # 始终打印到标准输出，无论ROS2是否可用——ROS2发布是附加的，不是替代品
        print(f"[OSC][{timestamp:.2f}s][{element_type}][{element_name}] {status}")

        if self.publisher is not None:
            try:
                msg = String()
                msg.data = json_str
                self.publisher.publish(msg)
            except Exception as e:
                print(f"Warning: ROS2发布失败: {e}")


def get_logger():
    """
    获取ROS2日志发布器单例
    
    Returns:
        ROS2Logger实例
    """
    try:
        return ROS2Logger()
    except Exception as e:
        print(f"Warning: 无法创建ROS2日志发布器: {e}")
        # 返回一个简单的回退对象
        class FallbackLogger:
            def log(self, timestamp, element_type, element_name, status):
                print(f"[OSC][{timestamp:.2f}s][{element_type}][{element_name}] {status}")
        return FallbackLogger()

