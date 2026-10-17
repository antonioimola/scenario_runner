#!/usr/bin/env python

# Copyright (c) 2019-2020 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
OpenSCENARIO HTML + SVG 可视化工具
使用 HTML + SVG 实现精确的纵向布局和状态高亮
"""

import json
import os
import sys
import threading
import time
from typing import Dict, List, Optional
from enum import Enum

# 添加项目路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_script_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

try:
    import xml.etree.ElementTree as ET
    XML_AVAILABLE = True
except ImportError:
    XML_AVAILABLE = False

from srunner.tools.xosc_fsm_visualizer import XOSCFSM, ElementState


class ROS2LogSubscriber(Node):
    """ROS2日志订阅者"""
    
    def __init__(self, callback):
        if not ROS2_AVAILABLE:
            raise RuntimeError("ROS2不可用")
        super().__init__('xosc_html_visualizer')
        self.callback = callback
        self.subscription = self.create_subscription(
            String,
            '/scenario_runner/log',
            self.log_callback,
            10
        )
        self.get_logger().info('已订阅 /scenario_runner/log 话题')
    
    def log_callback(self, msg):
        """日志消息回调"""
        try:
            log_data = json.loads(msg.data)
            self.callback(log_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON解析失败: {e}')
        except Exception as e:
            self.get_logger().error(f'处理日志消息时出错: {e}')


class HTMLVisualizer:
    """HTML + SVG 可视化器"""
    
    def __init__(self, fsm: XOSCFSM, output_file: str = "xosc_fsm.html"):
        self.fsm = fsm
        self.output_file = output_file
        self.lock = threading.Lock()
        self.ros2_subscriber = None
        self.ros2_thread = None
        self.running = False
    
    def _get_state_color(self, state: ElementState) -> str:
        """获取状态对应的颜色"""
        color_map = {
            ElementState.IDLE: "#E0E0E0",
            ElementState.RUNNING: "#4CAF50",
            ElementState.COMPLETED: "#2196F3",
            ElementState.CANCELLED: "#F44336"
        }
        return color_map.get(state, "#E0E0E0")
    
    def _get_type_shape(self, elem_type: str) -> str:
        """获取元素类型对应的形状"""
        shape_map = {
            'STORY': 'ellipse',
            'ACT': 'rect',
            'SCENE': 'diamond',
            'MANEUVER': 'hexagon',
            'EVENT': 'parallelogram',
            'ACTION': 'rect'
        }
        return shape_map.get(elem_type, 'rect')
    
    def update_from_log(self, log_data: Dict):
        """根据日志更新状态"""
        element_type = log_data.get('element_type', '')
        element_name = log_data.get('element_name', '')
        status = log_data.get('status', '')
        timestamp = log_data.get('timestamp', 0)
        
        # 映射状态
        if status == 'RUNNING':
            new_state = ElementState.RUNNING
        elif status == 'END':
            new_state = ElementState.COMPLETED
        elif status == 'CANCEL':
            new_state = ElementState.CANCELLED
        else:
            return
        
        # 更新状态
        with self.lock:
            changed = self.fsm.transition(element_name, new_state)
            if changed:
                print(f"[{timestamp:.2f}s] {element_type}:{element_name} -> {status}")
                # 重新生成 HTML
                self.generate_html()
    
    def start_ros2_subscription(self):
        """启动 ROS2 订阅"""
        if not ROS2_AVAILABLE:
            print("警告: ROS2不可用，无法订阅日志")
            return False
        
        try:
            if not rclpy.ok():
                rclpy.init()
            
            self.ros2_subscriber = ROS2LogSubscriber(self.update_from_log)
            
            def ros2_spin():
                try:
                    rclpy.spin(self.ros2_subscriber)
                except Exception as e:
                    print(f"ROS2 spin错误: {e}")
            
            self.running = True
            self.ros2_thread = threading.Thread(target=ros2_spin, daemon=True)
            self.ros2_thread.start()
            
            time.sleep(0.5)
            print("✓ ROS2 日志订阅已启动")
            return True
        except Exception as e:
            print(f"警告: 无法启动ROS2订阅: {e}")
            return False
    
    def stop_ros2_subscription(self):
        """停止 ROS2 订阅"""
        self.running = False
        if self.ros2_subscriber:
            self.ros2_subscriber.destroy_node()
        if self.ros2_thread:
            self.ros2_thread.join(timeout=1)
    
    def generate_html(self):
        """生成 HTML 文件"""
        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenSCENARIO scenario visualization</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 100%;
            margin: 0 auto;
            background: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 28px;
        }
        .section {
            margin-bottom: 40px;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background: #fafafa;
            overflow-x: auto;
        }
        .section-title {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #555;
            border-bottom: 2px solid #ccc;
            padding-bottom: 10px;
        }
        .structure-section {
            background: #fff9e6;
            border-color: #ffd700;
        }
        .execution-section {
            background: #ffffff;
            border-color: #4CAF50;
        }
        .tree {
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            min-width: fit-content;
            padding: 20px 0;
            position: relative;
        }
        .tree-vertical {
            display: flex;
            flex-direction: column;
            align-items: stretch;
            min-width: fit-content;
            padding: 20px;
            position: relative;
        }
        .flow-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            margin: 0 15px;
            flex-shrink: 0;
        }
        .node {
            margin: 8px 0;
            padding: 15px 22px;
            border-radius: 6px;
            text-align: center;
            min-width: 180px;
            max-width: 250px;
            font-size: 16px;
            transition: all 0.3s;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12);
            position: relative;
            z-index: 2;
        }
        .nested-box {
            border: 4px solid #888;
            border-radius: 12px;
            padding: 30px;
            margin: 20px 0;
            background: rgba(255, 255, 255, 0.6);
            position: relative;
            box-shadow: 0 3px 12px rgba(0,0,0,0.15);
            min-height: 100px;
        }
        .nested-box-title {
            font-weight: bold;
            font-size: 22px;
            margin-bottom: 20px;
            color: #333;
            text-align: left;
            border-bottom: 3px solid #ccc;
            padding-bottom: 12px;
        }
        .nested-box-content {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }
        .flex-row-wrap {
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 12px;
        }
        .nested-box-inner {
            border: 2.5px dashed #aaa;
            border-radius: 10px;
            padding: 20px;
            margin: 12px 0;
            background: rgba(255, 255, 255, 0.9);
            min-height: 60px;
        }
        .nested-box-label {
            font-size: 18px;
            font-weight: 600;
            color: #444;
            margin-bottom: 12px;
        }
        .node-idle {
            background: #E0E0E0;
            color: #333;
        }
        .node-running {
            background: #4CAF50;
            color: white;
            font-weight: bold;
            box-shadow: 0 4px 10px rgba(76, 175, 80, 0.5);
            transform: scale(1.05);
        }
        .node-completed {
            background: #2196F3;
            color: white;
        }
        .node-cancelled {
            background: #F44336;
            color: white;
        }
        .node-story {
            border-radius: 50%;
            width: 150px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .node-act {
            border-radius: 5px;
        }
        .node-scene {
            clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
        }
        .node-maneuver {
            clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
        }
        .node-event {
            clip-path: polygon(20% 0%, 80% 0%, 100% 20%, 100% 80%, 80% 100%, 20% 100%, 0% 80%, 0% 20%);
        }
        .node small {
            display: block;
            margin-top: 5px;
            font-size: 13px;
        }
        .connector {
            width: 2px;
            height: 20px;
            background: #999;
            margin: 0 auto;
        }
        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 15px;
        }
        .legend-color {
            width: 24px;
            height: 24px;
            border-radius: 3px;
        }
        .auto-refresh {
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: #e3f2fd;
            border-radius: 5px;
            font-size: 15px;
        }
        .auto-refresh p {
            margin: 8px 0;
            font-size: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>OpenSCENARIO scenario visualization</h1>
        
        <!-- 结构图部分 -->
        <div class="section structure-section">
            <div class="section-title">📋 OpenSCENARIO Structure (Based on the Current File)</div>
            <div class="tree-vertical" id="structure-tree">
"""
        
        # 生成结构图
        html_content += self._generate_structure_tree()
        
        html_content += """
            </div>
        </div>
        
        <!-- 执行状态图部分 -->
        <div class="section execution-section">
            <div class="section-title">⚡ Scenario Execution Status (Real-Time Updates)</div>
            <div class="tree-vertical" id="execution-tree">
"""
        
        # 生成执行状态图
        html_content += self._generate_execution_tree()
        
        html_content += """
            </div>
        </div>
        
        <!-- 图例 -->
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #E0E0E0;"></div>
                <span>空闲 (IDLE)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #4CAF50;"></div>
                <span>运行中 (RUNNING)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #2196F3;"></div>
                <span>已完成 (COMPLETED)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #F44336;"></div>
                <span>已取消 (CANCELLED)</span>
            </div>
        </div>
        
        <div class="auto-refresh">
            <p>💡 Note: This page automatically refreshes (every 2 seconds) to display the latest status.</p>
            <p>Last Updated: <span id="last-update">-</span></p>
            <p>Status: <span id="connection-status">等待连接...</span></p>
        </div>
    </div>
    
    <script>
        // 自动刷新
        function updateTimestamp() {
            document.getElementById('last-update').textContent = new Date().toLocaleString('zh-CN');
        }
        updateTimestamp();
        
        // 每2秒自动刷新页面
        setInterval(function() {
            location.reload();
        }, 2000);
        
        // 页面加载完成提示
        window.addEventListener('load', function() {
            document.getElementById('connection-status').textContent = '已连接';
            document.getElementById('connection-status').style.color = '#4CAF50';
        });
    </script>
</body>
</html>
"""
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_structure_tree(self) -> str:
        """生成结构树 HTML（使用包围结构，内容根据实际文件动态生成）"""
        html = ""
        
        # ========== Init 部分 ==========
        if self.fsm.structure.get('init'):
            init_data = self.fsm.structure['init']
            html += '                <div class="nested-box" style="border-color: #4CAF50; margin-bottom: 20px;">\n'
            html += '                    <div class="nested-box-title">Init</div>\n'
            html += '                    <div class="nested-box-content">\n'
            html += '                        <div class="nested-box-inner">\n'
            html += '                            <div class="nested-box-label">Init Actions</div>\n'
            html += '                            <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px;">\n'
            
            # GlobalAction
            if init_data.get('global_actions'):
                for ga in init_data['global_actions']:
                    subtype = ga.get('subtype', 'GlobalAction')
                    html += f'                                <div class="node node-idle" style="font-size: 15px; border-style: dashed; min-width: 180px;">GlobalAction<br><small style="font-size: 13px;">{subtype}</small></div>\n'
            
            # UserDefinedAction
            if init_data.get('user_defined_actions'):
                for uda in init_data['user_defined_actions']:
                    name = uda.get('name', 'UserDefinedAction')
                    html += f'                                <div class="node node-idle" style="font-size: 15px; border-style: dashed; min-width: 180px;">UserDefinedAction<br><small style="font-size: 13px;">{name}</small></div>\n'
            
            # Private
            if init_data.get('private_actions'):
                for priv in init_data['private_actions']:
                    entity_ref = priv.get('entityRef', 'Unknown')
                    action_types = priv.get('actionTypes', [])
                    action_types_str = ', '.join(action_types) if action_types else 'PrivateAction'
                    html += f'                                <div class="node node-idle" style="font-size: 15px; border-style: dashed; min-width: 180px;">Private: {entity_ref}<br><small style="font-size: 13px;">{action_types_str}</small></div>\n'
            
            if not init_data.get('global_actions') and not init_data.get('user_defined_actions') and not init_data.get('private_actions'):
                html += '                                <div class="node node-idle" style="font-size: 15px; border-style: dashed; min-width: 180px;">无 Init Actions</div>\n'
            
            html += '                            </div>\n'
            html += '                        </div>\n'
            html += '                    </div>\n'
            html += '                </div>\n'
        
        # ========== Story 部分（根据实际文件动态生成）==========
        for story_idx, story_data in enumerate(self.fsm.structure.get('stories', [])):
            story_name = story_data['name']
            html += '                <div class="nested-box" style="border-color: #2196F3; margin-bottom: 20px;">\n'
            html += f'                    <div class="nested-box-title">Story: {story_name}</div>\n'
            html += '                    <div class="nested-box-content">\n'
            
            # 遍历 Act
            for act_idx, act_data in enumerate(story_data.get('acts', [])):
                act_name = act_data['name']
                html += '                        <div class="nested-box-inner" style="border-color: #2196F3;">\n'
                html += f'                            <div class="nested-box-label">Act: {act_name}</div>\n'
                # StartTrigger
                if act_data.get('has_start_trigger'):
                    html += '                            <div class="nested-box-inner" style="border-color: #9E9E9E; margin-top: 12px;">\n'
                    html += '                                <div class="nested-box-label">StartTrigger</div>\n'
                    conditions = act_data.get('start_trigger_conditions', [])
                    if conditions:
                        html += '                                <div class="flex-row-wrap">\n'
                        for cond in conditions:
                            html += f'                                    <div class="node node-idle" style="font-size: 14px; min-width: 200px;">{cond["name"]}<br><small style="font-size: 12px;">{cond["type"]} (delay: {cond["delay"]}, edge: {cond["conditionEdge"]})</small></div>\n'
                        html += '                                </div>\n'
                    else:
                        html += '                                <div class="node node-idle" style="font-size: 14px; margin-top: 10px; opacity: 0.6;">无条件</div>\n'
                    html += '                            </div>\n'
                
                # StopTrigger
                if act_data.get('has_stop_trigger'):
                    html += '                            <div class="nested-box-inner" style="border-color: #9E9E9E; margin-top: 12px;">\n'
                    html += '                                <div class="nested-box-label">StopTrigger</div>\n'
                    conditions = act_data.get('stop_trigger_conditions', [])
                    if conditions:
                        html += '                                <div class="flex-row-wrap">\n'
                        for cond in conditions:
                            html += f'                                    <div class="node node-idle" style="font-size: 14px; min-width: 200px;">{cond["name"]}<br><small style="font-size: 12px;">{cond["type"]} (delay: {cond["delay"]}, edge: {cond["conditionEdge"]})</small></div>\n'
                        html += '                                </div>\n'
                    else:
                        html += '                                <div class="node node-idle" style="font-size: 14px; margin-top: 10px; opacity: 0.6;">无条件</div>\n'
                    html += '                            </div>\n'
                
                # 遍历 ManeuverGroup
                for mg_idx, mg_data in enumerate(act_data.get('maneuver_groups', [])):
                    mg_name = mg_data['name']
                    html += '                            <div class="nested-box-inner" style="border-color: #FF9800; margin-top: 15px;">\n'
                    html += f'                                <div class="nested-box-label">ManeuverGroup: {mg_name}</div>\n'
                    html += '                                <div style="margin-top: 12px;">\n'
                    
                    # Actors 和 CatalogReference - 横向流式布局
                    if mg_data.get('actors') or mg_data.get('catalog_references'):
                        html += '                                    <div class="flex-row-wrap">\n'
                        
                        if mg_data.get('actors'):
                            for actor in mg_data['actors']:
                                html += f'                                        <div class="node node-idle" style="font-size: 15px; min-width: 150px;">Actors: {actor}</div>\n'
                        
                        if mg_data.get('catalog_references'):
                            for cr in mg_data['catalog_references']:
                                catalog_name = cr.get('catalogName', 'Catalog')
                                entry_name = cr.get('entryName', 'Entry')
                                html += f'                                        <div class="node node-idle" style="font-size: 15px; min-width: 180px;">CatalogRef: {catalog_name}/{entry_name}</div>\n'
                        
                        html += '                                    </div>\n'
                    
                        # 遍历 Maneuver - 横向流式布局
                        if mg_data.get('maneuvers'):
                            html += '                                    <div class="flex-row-wrap">\n'
                            for maneuver_idx, maneuver_data in enumerate(mg_data.get('maneuvers', [])):
                                maneuver_name = maneuver_data['name']
                                html += '                                        <div class="nested-box-inner" style="border-color: #E91E63; min-width: 200px;">\n'
                                html += f'                                            <div class="nested-box-label">Maneuver: {maneuver_name}</div>\n'
                                
                                # 遍历 Event - 横向流式布局
                                if maneuver_data.get('events'):
                                    html += '                                            <div class="flex-row-wrap" style="margin-top: 10px;">\n'
                                    for event_idx, event_data in enumerate(maneuver_data.get('events', [])):
                                        event_name = event_data['name']
                                        html += '                                                <div class="nested-box-inner" style="border-color: #00BCD4; min-width: 180px;">\n'
                                        html += f'                                                    <div class="nested-box-label">Event: {event_name}</div>\n'
                                        html += '                                                    <div style="margin-top: 10px;">\n'
                                        
                                        # StartTrigger
                                        if event_data.get('has_start_trigger'):
                                            conditions = event_data.get('start_trigger_conditions', [])
                                            if conditions:
                                                html += '                                                        <div class="nested-box-inner" style="border-color: #9E9E9E; margin-bottom: 10px;">\n'
                                                html += '                                                            <div class="nested-box-label" style="font-size: 14px;">StartTrigger</div>\n'
                                                html += '                                                            <div class="flex-row-wrap">\n'
                                                for cond in conditions:
                                                    html += f'                                                                <div class="node node-idle" style="font-size: 13px; min-width: 180px;">{cond["name"]}<br><small style="font-size: 11px;">{cond["type"]}</small></div>\n'
                                                html += '                                                            </div>\n'
                                                html += '                                                        </div>\n'
                                            else:
                                                html += '                                                        <div class="node node-idle" style="font-size: 14px; border-style: dashed; clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%); margin-bottom: 10px; min-width: 150px;">StartTrigger</div>\n'
                                        
                                        # Actions
                                        if event_data.get('actions'):
                                            html += '                                                        <div class="nested-box-inner" style="border-color: #8BC34A; margin-top: 10px;">\n'
                                            html += f'                                                            <div class="nested-box-label">Action ({len(event_data["actions"])})</div>\n'
                                            html += '                                                            <div class="flex-row-wrap">\n'
                                            for action_data in event_data['actions']:
                                                action_name = action_data['name']
                                                action_type = action_data.get('type', 'Unknown')
                                                html += f'                                                                <div class="node node-idle" style="font-size: 15px; border-style: dashed; min-width: 170px;">{action_name}<br><small style="font-size: 13px;">{action_type}</small></div>\n'
                                            html += '                                                            </div>\n'
                                            html += '                                                        </div>\n'
                                        else:
                                            html += '                                                        <div class="node node-idle" style="font-size: 15px; margin-top: 10px; min-width: 150px; opacity: 0.6;">无 Actions</div>\n'
                                        
                                        html += '                                                    </div>\n'
                                        html += '                                                </div>\n'
                                    html += '                                            </div>\n'
                                
                                html += '                                        </div>\n'
                            html += '                                    </div>\n'
                    else:
                        html += '                                    <div class="node node-idle" style="font-size: 15px; margin-top: 12px; opacity: 0.6;">无 Maneuvers</div>\n'
                    
                    html += '                                </div>\n'
                    html += '                            </div>\n'
                
                html += '                        </div>\n'
            
            html += '                    </div>\n'
            html += '                </div>\n'
        
        # ========== Stop Trigger (全局) ==========
        if self.fsm.structure.get('stop_trigger'):
            html += '                <div class="nested-box" style="border-color: #F44336;">\n'
            html += '                    <div class="nested-box-title">Stop Trigger</div>\n'
            stop_trigger = self.fsm.structure['stop_trigger']
            conditions = stop_trigger.get('conditions', [])
            if conditions:
                html += '                    <div class="nested-box-content">\n'
                html += '                        <div class="nested-box-inner">\n'
                html += '                            <div class="nested-box-label">Conditions</div>\n'
                html += '                            <div class="flex-row-wrap">\n'
                for cond in conditions:
                    html += f'                                <div class="node node-idle" style="font-size: 15px; min-width: 200px;">{cond["name"]}<br><small style="font-size: 13px;">{cond["type"]} (delay: {cond["delay"]}, edge: {cond["conditionEdge"]})</small></div>\n'
                html += '                            </div>\n'
                html += '                        </div>\n'
                html += '                    </div>\n'
            html += '                </div>\n'
        
        return html
    
    def _generate_execution_tree(self) -> str:
        """生成执行状态树 HTML（优化排版，使用嵌套结构）"""
        html = ""
        
        # 按层级组织元素
        elements_by_type = {
            'STORY': [],
            'ACT': [],
            'SCENE': [],
            'MANEUVER': [],
            'EVENT': [],
            'ACTION': []
        }
        
        for elem in self.fsm.elements:
            elem_type = elem['type']
            if elem_type in elements_by_type:
                elements_by_type[elem_type].append(elem)
        
        # 生成层级结构（使用嵌套框）
        for story in elements_by_type['STORY']:
            story_name = story['name']
            
            html += '                <div class="nested-box" style="border-color: #2196F3; margin-bottom: 15px;">\n'
            html += f'                    <div class="nested-box-title">{story_name} <span style="font-size: 16px; font-weight: normal; color: #666;">[STORY]</span></div>\n'
            html += '                    <div class="nested-box-content">\n'
            
            # 查找该 Story 下的 Act - 横向流式布局
            acts_list = [a for a in elements_by_type['ACT'] if a.get('parent') == story_name]
            if acts_list:
                html += '                    <div class="flex-row-wrap">\n'
                for act in acts_list:
                    act_name = act['name']
                    act_state = self.fsm.get_current_state(act_name)
                    act_state_class = f"node-{act_state.value.lower()}"
                    
                    html += '                        <div class="nested-box-inner" style="border-color: #4CAF50; min-width: 250px;">\n'
                    html += f'                            <div class="nested-box-label">{act_name} [ACT]<br><span class="node {act_state_class}" style="display: inline-block; padding: 4px 8px; margin-top: 5px; font-size: 12px;">{act_state.value}</span></div>\n'
                    
                    # 查找该 Act 下的 Scene - 横向流式布局
                    scenes_list = [s for s in elements_by_type['SCENE'] if s.get('parent') == act_name]
                    if scenes_list:
                        html += '                            <div class="flex-row-wrap" style="margin-top: 8px;">\n'
                        for scene in scenes_list:
                            scene_name = scene['name']
                            scene_state = self.fsm.get_current_state(scene_name)
                            scene_state_class = f"node-{scene_state.value.lower()}"
                            
                            html += '                                <div class="nested-box-inner" style="border-color: #FF9800; min-width: 220px;">\n'
                            html += f'                                    <div class="nested-box-label" style="font-size: 16px;">{scene_name} [SCENE]<br><span class="node {scene_state_class}" style="display: inline-block; padding: 4px 8px; margin-top: 5px; font-size: 12px;">{scene_state.value}</span></div>\n'
                            
                            # 查找该 Scene 下的 Maneuver - 横向流式布局
                            maneuvers_list = [m for m in elements_by_type['MANEUVER'] if m.get('parent') == scene_name]
                            if maneuvers_list:
                                html += '                                    <div class="flex-row-wrap" style="margin-top: 8px;">\n'
                                for maneuver in maneuvers_list:
                                    maneuver_name = maneuver['name']
                                    maneuver_state = self.fsm.get_current_state(maneuver_name)
                                    maneuver_state_class = f"node-{maneuver_state.value.lower()}"
                                    
                                    html += '                                    <div class="nested-box-inner" style="border-color: #E91E63; min-width: 200px;">\n'
                                    html += f'                                        <div class="nested-box-label" style="font-size: 15px;">{maneuver_name} [MANEUVER]<br><span class="node {maneuver_state_class}" style="display: inline-block; padding: 4px 8px; margin-top: 5px; font-size: 12px;">{maneuver_state.value}</span></div>\n'
                                    
                                    # 查找该 Maneuver 下的 Event - 横向流式布局
                                    events_list = [e for e in elements_by_type['EVENT'] if e.get('parent') == maneuver_name]
                                    if events_list:
                                        html += '                                        <div class="flex-row-wrap" style="margin-top: 8px;">\n'
                                        for event in events_list:
                                            event_name = event['name']
                                            event_state = self.fsm.get_current_state(event_name)
                                            event_state_class = f"node-{event_state.value.lower()}"
                                            
                                            html += '                                            <div class="nested-box-inner" style="border-color: #00BCD4; min-width: 180px;">\n'
                                            html += f'                                                <div class="nested-box-label" style="font-size: 14px;">{event_name} [EVENT]<br><span class="node {event_state_class}" style="display: inline-block; padding: 4px 8px; margin-top: 5px; font-size: 12px;">{event_state.value}</span></div>\n'
                                            
                                            # 查找该 Event 下的 Action - 横向流式布局
                                            actions_list = [a for a in elements_by_type['ACTION'] if a.get('parent') == event_name]
                                            if actions_list:
                                                html += '                                                <div class="flex-row-wrap" style="margin-top: 6px;">\n'
                                                for action in actions_list:
                                                    action_name = action['name']
                                                    action_state = self.fsm.get_current_state(action_name)
                                                    action_state_class = f"node-{action_state.value.lower()}"
                                                    
                                                    html += f'                                                    <div class="node {action_state_class}" style="font-size: 13px; min-width: 140px;">{action_name}<br><small>[ACTION] {action_state.value}</small></div>\n'
                                                html += '                                                </div>\n'
                                            
                                            html += '                                            </div>\n'
                                        html += '                                        </div>\n'
                                    
                                    html += '                                    </div>\n'
                                html += '                                </div>\n'
                            
                            html += '                                </div>\n'
                        html += '                            </div>\n'
                    
                    html += '                        </div>\n'
                html += '                    </div>\n'
            
            html += '                    </div>\n'
            html += '                </div>\n'
        
        return html


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenSCENARIO HTML 可视化工具')
    parser.add_argument('xosc_file', type=str, help='XOSC 文件路径')
    parser.add_argument('-o', '--output', type=str, default='xosc_fsm.html', help='输出 HTML 文件路径')
    parser.add_argument('--no-ros2', action='store_true', help='禁用 ROS2 日志订阅')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xosc_file):
        print(f"错误: 文件不存在: {args.xosc_file}")
        return 1
    
    try:
        print("=" * 60)
        print("OpenSCENARIO HTML 可视化工具")
        print("=" * 60)
        print(f"正在解析 XOSC 文件: {args.xosc_file}")
        
        fsm = XOSCFSM(args.xosc_file)
        visualizer = HTMLVisualizer(fsm, args.output)
        visualizer.generate_html()
        
        print(f"✓ 已生成 HTML 文件: {os.path.abspath(args.output)}")
        print(f"✓ 找到 {len(fsm.elements)} 个场景元素")
        
        # 启动 ROS2 订阅
        ros2_started = False
        if not args.no_ros2:
            ros2_started = visualizer.start_ros2_subscription()
        
        print("\n" + "=" * 60)
        print("使用说明:")
        print("=" * 60)
        print(f"1. 在浏览器中打开:")
        print(f"   file://{os.path.abspath(args.output)}")
        print(f"\n2. 或使用本地服务器:")
        print(f"   cd {os.path.dirname(os.path.abspath(args.output))}")
        print(f"   python -m http.server 8000")
        print(f"   然后访问: http://localhost:8000/{os.path.basename(args.output)}")
        print(f"\n3. 页面会自动每2秒刷新以显示最新状态")
        if ros2_started:
            print(f"4. ROS2 日志订阅已启动，状态会实时更新")
        else:
            print(f"4. ROS2 订阅未启动（使用 --no-ros2 参数）")
        print("=" * 60)
        
        # 尝试自动打开浏览器
        if not args.no_browser:
            try:
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(args.output)}")
                print("\n✓ 已尝试在默认浏览器中打开")
            except:
                pass
        
        # 保持运行（如果启用了 ROS2）
        if ros2_started:
            print("\n工具正在运行，按 Ctrl+C 退出...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n正在关闭...")
                visualizer.stop_ros2_subscription()
                print("已退出")
        
        return 0
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())

