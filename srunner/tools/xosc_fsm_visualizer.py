#!/usr/bin/env python

# Copyright (c) 2019-2020 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
OpenSCENARIO FSM + Graphviz 可视化工具
轻量级方案：在状态切换时导出 .dot 文件，高亮当前状态
"""

import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set
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
    print("警告: ROS2不可用，将无法订阅日志。")

try:
    import xml.etree.ElementTree as ET
    XML_AVAILABLE = True
except ImportError:
    XML_AVAILABLE = False


class ElementState(Enum):
    """元素状态枚举"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class XOSCFSM:
    """OpenSCENARIO 有限状态机"""
    
    def __init__(self, xosc_file: str):
        self.xosc_file = xosc_file
        self.states = {}  # {element_name: ElementState}
        self.transitions = []  # [(from_state, to_state, element_name, timestamp)]
        self.elements = []  # 所有场景元素
        self.hierarchy = {}  # 元素层次关系
        self.current_active = set()  # 当前激活的元素名称
        self._parse_xosc()
        self._initialize_states()
    
    def _parse_xosc(self):
        """解析 XOSC 文件，提取场景结构"""
        if not XML_AVAILABLE:
            raise RuntimeError("xml.etree.ElementTree 不可用")
        
        tree = ET.parse(self.xosc_file)
        root = tree.getroot()
        storyboard = root.find("Storyboard")
        
        if storyboard is None:
            return
        
        # 存储结构信息用于静态图
        self.structure = {
            'init': None,
            'stories': [],
            'stop_trigger': None
        }
        
        # 解析 Init 部分
        init = storyboard.find("Init")
        if init is not None:
            init_data = {
                'global_actions': [],
                'user_defined_actions': [],
                'private_actions': []
            }
            actions = init.find("Actions")
            if actions is not None:
                for global_action in actions.iter("GlobalAction"):
                    # 提取 GlobalAction 的详细信息
                    action_info = {'type': 'GlobalAction'}
                    if global_action.find("EnvironmentAction") is not None:
                        action_info['subtype'] = 'EnvironmentAction'
                    elif global_action.find("TrafficAction") is not None:
                        action_info['subtype'] = 'TrafficAction'
                    else:
                        action_info['subtype'] = 'GlobalAction'
                    init_data['global_actions'].append(action_info)
                
                for user_defined in actions.iter("UserDefinedAction"):
                    action_info = {
                        'type': 'UserDefinedAction',
                        'name': user_defined.get('name', 'UserDefinedAction')
                    }
                    init_data['user_defined_actions'].append(action_info)
                
                for private in actions.iter("Private"):
                    entity_ref = private.get('entityRef', 'Unknown')
                    # 提取 Private 中的动作类型
                    action_types = []
                    for private_action in private.iter("PrivateAction"):
                        if private_action.find("TeleportAction") is not None:
                            action_types.append('TeleportAction')
                        if private_action.find("ControllerAction") is not None:
                            action_types.append('ControllerAction')
                        if private_action.find("LongitudinalAction") is not None:
                            action_types.append('LongitudinalAction')
                        if private_action.find("LateralAction") is not None:
                            action_types.append('LateralAction')
                        if private_action.find("VisibilityAction") is not None:
                            action_types.append('VisibilityAction')
                    init_data['private_actions'].append({
                        'entityRef': entity_ref,
                        'actionTypes': action_types
                    })
            self.structure['init'] = init_data
        
        # 解析 Story 结构
        for story in storyboard.findall("Story"):
            story_name = story.get('name', 'UnknownStory')
            story_data = {
                'name': story_name,
                'acts': []
            }
            
            self.elements.append({
                'name': story_name,
                'type': 'STORY',
                'parent': None
            })
            
            for act in story.iter("Act"):
                act_name = act.get('name', 'UnknownAct')
                
                # 提取 StartTrigger 条件
                start_trigger_conditions = []
                start_trigger = act.find("StartTrigger")
                if start_trigger is not None:
                    for condition_group in start_trigger.iter("ConditionGroup"):
                        for condition in condition_group.iter("Condition"):
                            cond_name = condition.get('name', 'Unknown')
                            cond_delay = condition.get('delay', '0')
                            cond_edge = condition.get('conditionEdge', 'rising')
                            
                            # 提取条件类型
                            cond_type = 'Unknown'
                            if condition.find(".//ByEntityCondition") is not None:
                                cond_type = "ByEntityCondition"
                            elif condition.find(".//ByValueCondition") is not None:
                                cond_type = "ByValueCondition"
                            
                            start_trigger_conditions.append({
                                'name': cond_name,
                                'delay': cond_delay,
                                'conditionEdge': cond_edge,
                                'type': cond_type
                            })
                
                # 提取 StopTrigger 条件
                stop_trigger_conditions = []
                stop_trigger = act.find("StopTrigger")
                if stop_trigger is not None:
                    for condition_group in stop_trigger.iter("ConditionGroup"):
                        for condition in condition_group.iter("Condition"):
                            cond_name = condition.get('name', 'Unknown')
                            cond_delay = condition.get('delay', '0')
                            cond_edge = condition.get('conditionEdge', 'rising')
                            
                            cond_type = 'Unknown'
                            if condition.find(".//ByEntityCondition") is not None:
                                cond_type = "ByEntityCondition"
                            elif condition.find(".//ByValueCondition") is not None:
                                cond_type = "ByValueCondition"
                            
                            stop_trigger_conditions.append({
                                'name': cond_name,
                                'delay': cond_delay,
                                'conditionEdge': cond_edge,
                                'type': cond_type
                            })
                
                act_data = {
                    'name': act_name,
                    'has_start_trigger': start_trigger is not None,
                    'start_trigger_conditions': start_trigger_conditions,
                    'has_stop_trigger': stop_trigger is not None,
                    'stop_trigger_conditions': stop_trigger_conditions,
                    'maneuver_groups': []
                }
                
                self.elements.append({
                    'name': act_name,
                    'type': 'ACT',
                    'parent': story_name
                })
                self.hierarchy[act_name] = story_name
                
                for mg in act.iter("ManeuverGroup"):
                    mg_name = mg.get('name', 'UnknownManeuverGroup')
                    mg_data = {
                        'name': mg_name,
                        'actors': [],
                        'catalog_references': [],
                        'maneuvers': []
                    }
                    
                    # 解析 Actors
                    for actors_elem in mg.iter("Actors"):
                        # 检查是否有 EntityRef
                        entity_refs = list(actors_elem.iter("EntityRef"))
                        if entity_refs:
                            for entity_ref in entity_refs:
                                entity_name = entity_ref.get('entityRef', 'Unknown')
                                mg_data['actors'].append(entity_name)
                        else:
                            # 如果没有 EntityRef，检查 selectTriggeringEntities 属性
                            select_triggering = actors_elem.get('selectTriggeringEntities', 'false')
                            if select_triggering == 'true':
                                mg_data['actors'].append('TriggeringEntities')
                            else:
                                mg_data['actors'].append('NoActors')
                    
                    # 解析 CatalogReference
                    for catalog_ref in mg.iter("CatalogReference"):
                        catalog_name = catalog_ref.get('catalogName', '')
                        entry_name = catalog_ref.get('entryName', '')
                        mg_data['catalog_references'].append({
                            'catalogName': catalog_name,
                            'entryName': entry_name
                        })
                    
                    self.elements.append({
                        'name': mg_name,
                        'type': 'SCENE',
                        'parent': act_name
                    })
                    self.hierarchy[mg_name] = act_name
                    
                    for maneuver in mg.iter("Maneuver"):
                        maneuver_name = maneuver.get('name', 'UnknownManeuver')
                        maneuver_data = {
                            'name': maneuver_name,
                            'events': []
                        }
                        
                        self.elements.append({
                            'name': maneuver_name,
                            'type': 'MANEUVER',
                            'parent': mg_name
                        })
                        self.hierarchy[maneuver_name] = mg_name
                        
                        for event in maneuver.iter("Event"):
                            event_name = event.get('name', 'UnknownEvent')
                            
                            # 提取 Event 的 StartTrigger 条件
                            event_start_conditions = []
                            event_start_trigger = event.find("StartTrigger")
                            if event_start_trigger is not None:
                                for condition_group in event_start_trigger.iter("ConditionGroup"):
                                    for condition in condition_group.iter("Condition"):
                                        cond_name = condition.get('name', 'Unknown')
                                        cond_delay = condition.get('delay', '0')
                                        cond_edge = condition.get('conditionEdge', 'rising')
                                        
                                        cond_type = 'Unknown'
                                        if condition.find(".//ByEntityCondition") is not None:
                                            cond_type = "ByEntityCondition"
                                        elif condition.find(".//ByValueCondition") is not None:
                                            cond_type = "ByValueCondition"
                                        
                                        event_start_conditions.append({
                                            'name': cond_name,
                                            'delay': cond_delay,
                                            'conditionEdge': cond_edge,
                                            'type': cond_type
                                        })
                            
                            event_data = {
                                'name': event_name,
                                'has_start_trigger': event_start_trigger is not None,
                                'start_trigger_conditions': event_start_conditions,
                                'actions': []
                            }
                            
                            self.elements.append({
                                'name': event_name,
                                'type': 'EVENT',
                                'parent': maneuver_name
                            })
                            self.hierarchy[event_name] = maneuver_name
                            
                            for action in event.iter("Action"):
                                action_name = action.get('name', 'UnknownAction')
                                action_type = 'Unknown'
                                
                                # 判断动作类型 - 先检查 GlobalAction
                                if action.find(".//GlobalAction") is not None:
                                    global_action = action.find(".//GlobalAction")
                                    if global_action.find(".//EnvironmentAction") is not None:
                                        action_type = "GlobalAction:EnvironmentAction"
                                    elif global_action.find(".//TrafficAction") is not None:
                                        action_type = "GlobalAction:TrafficAction"
                                    else:
                                        action_type = "GlobalAction"
                                # 检查 UserDefinedAction
                                elif action.find(".//UserDefinedAction") is not None:
                                    user_defined = action.find(".//UserDefinedAction")
                                    action_type = f"UserDefinedAction:{user_defined.get('name', 'UserDefinedAction')}"
                                # 检查 PrivateAction
                                elif action.find(".//PrivateAction") is not None:
                                    private_action = action.find(".//PrivateAction")
                                    if private_action.find(".//LongitudinalAction") is not None:
                                        action_type = "PrivateAction:LongitudinalAction"
                                    elif private_action.find(".//LateralAction") is not None:
                                        action_type = "PrivateAction:LateralAction"
                                    elif private_action.find(".//VisibilityAction") is not None:
                                        action_type = "PrivateAction:VisibilityAction"
                                    elif private_action.find(".//TeleportAction") is not None:
                                        action_type = "PrivateAction:TeleportAction"
                                    elif private_action.find(".//ControllerAction") is not None:
                                        action_type = "PrivateAction:ControllerAction"
                                    else:
                                        action_type = "PrivateAction"
                                
                                action_data = {
                                    'name': action_name,
                                    'type': action_type
                                }
                                event_data['actions'].append(action_data)
                                
                                self.elements.append({
                                    'name': action_name,
                                    'type': 'ACTION',
                                    'parent': event_name
                                })
                                self.hierarchy[action_name] = event_name
                            
                            maneuver_data['events'].append(event_data)
                        
                        mg_data['maneuvers'].append(maneuver_data)
                    
                    act_data['maneuver_groups'].append(mg_data)
                
                story_data['acts'].append(act_data)
            
            self.structure['stories'].append(story_data)
        
        # 解析全局 StopTrigger
        stop_trigger = storyboard.find("StopTrigger")
        if stop_trigger is not None:
            stop_conditions = []
            for condition_group in stop_trigger.iter("ConditionGroup"):
                for condition in condition_group.iter("Condition"):
                    cond_name = condition.get('name', 'Unknown')
                    cond_delay = condition.get('delay', '0')
                    cond_edge = condition.get('conditionEdge', 'rising')
                    
                    cond_type = 'Unknown'
                    if condition.find(".//ByEntityCondition") is not None:
                        cond_type = "ByEntityCondition"
                    elif condition.find(".//ByValueCondition") is not None:
                        cond_type = "ByValueCondition"
                    
                    stop_conditions.append({
                        'name': cond_name,
                        'delay': cond_delay,
                        'conditionEdge': cond_edge,
                        'type': cond_type
                    })
            
            self.structure['stop_trigger'] = {
                'has_conditions': len(stop_conditions) > 0,
                'conditions': stop_conditions
            }
    
    def _initialize_states(self):
        """初始化所有元素状态为 IDLE"""
        for elem in self.elements:
            self.states[elem['name']] = ElementState.IDLE
    
    def transition(self, element_name: str, new_state: ElementState):
        """状态转换"""
        if element_name not in self.states:
            # 尝试查找匹配的元素
            element_name = self._find_element(element_name)
            if element_name is None:
                return False
        
        old_state = self.states.get(element_name, ElementState.IDLE)
        
        if old_state != new_state:
            self.states[element_name] = new_state
            timestamp = time.time()
            self.transitions.append((old_state, new_state, element_name, timestamp))
            
            # 更新当前激活集合
            if new_state == ElementState.RUNNING:
                self.current_active.add(element_name)
            else:
                self.current_active.discard(element_name)
            
            return True
        return False
    
    def _find_element(self, name: str) -> Optional[str]:
        """查找匹配的元素名称"""
        # 精确匹配
        for elem in self.elements:
            if elem['name'] == name:
                return elem['name']
        
        # 部分匹配
        for elem in self.elements:
            if name in elem['name'] or elem['name'] in name:
                return elem['name']
        
        return None
    
    def _get_element_type(self, element_name: str) -> str:
        """获取元素类型"""
        for elem in self.elements:
            if elem['name'] == element_name:
                return elem['type']
        return 'UNKNOWN'
    
    def get_current_state(self, element_name: str) -> ElementState:
        """获取元素当前状态"""
        return self.states.get(element_name, ElementState.IDLE)
    
    def dump_graphviz(self, output_file: str = "xosc_fsm.dot"):
        """导出 Graphviz .dot 文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("digraph XOSC_FSM {\n")
            f.write("  rankdir=TB;  // 从上到下布局\n")
            f.write("  node [shape=box, style=rounded];\n")
            f.write("  edge [color=gray];\n")
            f.write("  compound=true;  // 允许子图之间的边\n")
            f.write("  newrank=false;   // 使用传统排名算法（更严格的纵向布局）\n")
            f.write("  size=\"8.3,11.7\";  // A4 纵向尺寸（英寸）\n")
            f.write("  ratio=fill;  // 填充整个页面\n")
            f.write("  ranksep=2.0;  // 大幅增加层级间距（纵向）\n")
            f.write("  nodesep=0.2;  // 减小节点间距（横向，强制纵向）\n")
            f.write("  orientation=portrait;  // 纵向方向\n")
            f.write("  page=\"8.3,11.7\";  // 页面尺寸\n")
            f.write("  concentrate=false;  // 不合并边\n")
            f.write("  splines=ortho;  // 使用正交边（更适合纵向布局）\n\n")
            
            # ========== 全局静态结构图（根据 XOSC 文件生成）==========
            f.write("  // ========== 全局静态结构图（基于 XOSC 文件）==========\n")
            f.write("  subgraph cluster_structure {\n")
            f.write("    label=\"OpenSCENARIO 结构 (基于当前文件)\";\n")
            f.write("    style=filled;\n")
            f.write("    fillcolor=lightyellow;\n")
            f.write("    fontsize=16;\n")
            f.write("    fontcolor=black;\n")
            f.write("    rankdir=TB;  // 子图内部也是从上到下\n")
            f.write("    ranksep=0.8;  // 层级间距\n")
            f.write("    nodesep=0.4;  // 节点间距\n\n")
            
            # Init 部分（根据实际文件内容）
            if self.structure['init']:
                init_data = self.structure['init']
                f.write("    // Init 部分\n")
                f.write("    subgraph cluster_init {\n")
                f.write("      label=\"Init (设置场景)\";\n")
                f.write("      style=filled;\n")
                f.write("      fillcolor=lightblue;\n\n")
                
                f.write("      InitActions [label=\"Init Actions\", shape=box];\n")
                
                if init_data['global_actions']:
                    for i, ga in enumerate(init_data['global_actions']):
                        node_id = f"InitGlobalAction_{i}"
                        f.write(f"      {node_id} [label=\"GlobalAction\\n{ga}\", shape=ellipse, style=dashed];\n")
                        f.write(f"      InitActions -> {node_id} [style=dashed];\n")
                
                if init_data['private_actions']:
                    for i, entity in enumerate(init_data['private_actions']):
                        node_id = f"InitPrivate_{i}"
                        f.write(f"      {node_id} [label=\"Private\\n{entity}\", shape=ellipse, style=dashed];\n")
                        f.write(f"      InitActions -> {node_id} [style=dashed];\n")
                
                f.write("    }\n\n")
            
            # Story 部分（根据实际文件内容，显示层次结构）
            for story_idx, story_data in enumerate(self.structure['stories']):
                story_name = story_data['name']
                cluster_id = f"cluster_story_{story_idx}"
                
                f.write(f"    // Story: {story_name}\n")
                f.write(f"    subgraph {cluster_id} {{\n")
                f.write(f"      label=\"Story: {story_name}\";\n")
                f.write("      style=filled;\n")
                f.write("      fillcolor=lightgreen;\n\n")
                
                story_node_id = f"Story_{story_idx}"
                f.write(f"      {story_node_id} [label=\"{story_name}\", shape=ellipse];\n\n")
                
                # 遍历 Act
                for act_idx, act_data in enumerate(story_data['acts']):
                    act_name = act_data['name']
                    act_node_id = f"Act_{story_idx}_{act_idx}"
                    
                    # Act 节点
                    trigger_info = ""
                    if act_data['has_start_trigger']:
                        trigger_info += "\\n[有StartTrigger]"
                    if act_data['has_stop_trigger']:
                        trigger_info += "\\n[有StopTrigger]"
                    
                    f.write(f"      {act_node_id} [label=\"{act_name}{trigger_info}\", shape=box];\n")
                    f.write(f"      {story_node_id} -> {act_node_id};\n\n")
                    
                    # 遍历 ManeuverGroup
                    for mg_idx, mg_data in enumerate(act_data['maneuver_groups']):
                        mg_name = mg_data['name']
                        mg_node_id = f"MG_{story_idx}_{act_idx}_{mg_idx}"
                        
                        actors_info = ""
                        if mg_data['actors']:
                            actors_info = f"\\nActors: {', '.join(mg_data['actors'][:3])}"
                            if len(mg_data['actors']) > 3:
                                actors_info += "..."
                        
                        f.write(f"      {mg_node_id} [label=\"{mg_name}{actors_info}\", shape=hexagon];\n")
                        f.write(f"      {act_node_id} -> {mg_node_id};\n\n")
                        
                        # 遍历 Maneuver
                        for maneuver_idx, maneuver_data in enumerate(mg_data['maneuvers']):
                            maneuver_name = maneuver_data['name']
                            maneuver_node_id = f"Maneuver_{story_idx}_{act_idx}_{mg_idx}_{maneuver_idx}"
                            
                            f.write(f"      {maneuver_node_id} [label=\"{maneuver_name}\", shape=hexagon];\n")
                            f.write(f"      {mg_node_id} -> {maneuver_node_id};\n\n")
                            
                            # 遍历 Event
                            for event_idx, event_data in enumerate(maneuver_data['events']):
                                event_name = event_data['name']
                                event_node_id = f"Event_{story_idx}_{act_idx}_{mg_idx}_{maneuver_idx}_{event_idx}"
                                
                                trigger_mark = " [有StartTrigger]" if event_data['has_start_trigger'] else ""
                                f.write(f"      {event_node_id} [label=\"{event_name}{trigger_mark}\", shape=parallelogram];\n")
                                f.write(f"      {maneuver_node_id} -> {event_node_id};\n\n")
                                
                                # 遍历 Action
                                for action_idx, action_data in enumerate(event_data['actions']):
                                    action_name = action_data['name']
                                    action_type = action_data['type']
                                    action_node_id = f"Action_{story_idx}_{act_idx}_{mg_idx}_{maneuver_idx}_{event_idx}_{action_idx}"
                                    
                                    action_label = f"{action_name}"
                                    if action_type != 'Unknown':
                                        action_label += f"\\n[{action_type}]"
                                    
                                    f.write(f"      {action_node_id} [label=\"{action_label}\", shape=box];\n")
                                    f.write(f"      {event_node_id} -> {action_node_id};\n")
                                
                                f.write("\n")
                
                f.write("    }\n\n")
            
            # Stop Trigger (全局)
            if self.structure['stop_trigger']:
                f.write("    // Stop Trigger (全局)\n")
                stop_label = "Stop Trigger (全局)"
                if self.structure['stop_trigger']['has_conditions']:
                    stop_label += "\\n[有条件]"
                f.write(f"    StopTriggerGlobal [label=\"{stop_label}\", shape=diamond, style=filled, fillcolor=lightcoral];\n")
            
            f.write("  }\n\n")
            
            # 添加分隔线和连接，确保上下排列
            f.write("  // ========== 分隔线 ==========\n")
            f.write("  // 上方：OpenSCENARIO 结构定义（静态）\n")
            f.write("  // 下方：实际场景执行状态（动态更新）\n\n")
            
            # 使用 rank 约束强制上下排列
            if self.structure['stories'] and self.elements:
                first_story_node = f"Story_0"
                first_exec_node = f"{self.elements[0]['type']}_{self.elements[0]['name']}"
                
                # 使用 rank 约束：结构图在上，执行图在下
                f.write("  // 使用 rank 约束强制上下顺序\n")
                f.write("  { rank=same; ")
                # 添加结构图中的关键节点
                if self.structure['init']:
                    f.write("InitActions; ")
                f.write(f"{first_story_node}; ")
                f.write("}\n")
                
                f.write("  { rank=same; ")
                f.write(f"{first_exec_node}; ")
                f.write("}\n")
                
                # 添加不可见边，确保顺序
                f.write(f"  // 强制上下顺序的连接\n")
                if self.structure['init']:
                    f.write(f"  InitActions -> {first_story_node} [style=invis, weight=100];\n")
                f.write(f"  {first_story_node} -> {first_exec_node} [style=invis, weight=100, minlen=3];\n\n")
            
            # ========== 实际场景执行状态图 ==========
            f.write("  // ========== 实际场景执行状态图 ==========\n")
            f.write("  subgraph cluster_execution {\n")
            f.write("    label=\"场景执行状态 (实时更新)\";\n")
            f.write("    style=filled;\n")
            f.write("    fillcolor=white;\n")
            f.write("    fontsize=16;\n")
            f.write("    fontcolor=black;\n")
            f.write("    rankdir=TB;  // 子图内部也是从上到下\n")
            f.write("    ranksep=0.8;  // 层级间距\n\n")
            
            # 按层次组织节点
            by_type = defaultdict(list)
            for elem in self.elements:
                by_type[elem['type']].append(elem)
            
            # 定义节点样式
            type_styles = {
                'STORY': {'shape': 'ellipse', 'color': 'blue'},
                'ACT': {'shape': 'box', 'color': 'green'},
                'SCENE': {'shape': 'diamond', 'color': 'orange'},
                'MANEUVER': {'shape': 'hexagon', 'color': 'purple'},
                'EVENT': {'shape': 'parallelogram', 'color': 'red'},
                'ACTION': {'shape': 'box', 'color': 'black'}
            }
            
            # 绘制节点（使用唯一ID避免重复）
            node_ids = {}  # {element_name: unique_id}
            for elem in self.elements:
                name = elem['name']
                elem_type = elem['type']
                
                # 生成唯一节点ID（类型+名称）
                node_id = f"{elem_type}_{name}"
                # 如果名称已存在，添加索引
                if node_id in node_ids.values():
                    idx = sum(1 for v in node_ids.values() if v.startswith(f"{elem_type}_{name}"))
                    node_id = f"{elem_type}_{name}_{idx}"
                
                node_ids[name] = node_id
                
                state = self.get_current_state(name)
                
                # 节点标签（包含类型和状态）
                label = f"{name}\\n[{elem_type}]"
                
                # 根据状态设置样式
                if state == ElementState.RUNNING:
                    # 高亮当前运行状态
                    f.write(f'    "{node_id}" [label="{label}", style="filled,bold", fillcolor="lightgreen", fontcolor="black"];\n')
                elif state == ElementState.COMPLETED:
                    f.write(f'    "{node_id}" [label="{label}", style="filled", fillcolor="lightblue", fontcolor="black"];\n')
                elif state == ElementState.CANCELLED:
                    f.write(f'    "{node_id}" [label="{label}", style="filled", fillcolor="lightcoral", fontcolor="black"];\n')
                else:
                    # IDLE 状态
                    style = type_styles.get(elem_type, {})
                    shape = style.get('shape', 'box')
                    color = style.get('color', 'black')
                    f.write(f'    "{node_id}" [label="{label}", shape={shape}, color={color}];\n')
            
            f.write("\n")
            
            # 绘制层次关系（父子关系）
            for elem in self.elements:
                parent = elem.get('parent')
                if parent:
                    parent_id = node_ids.get(parent, f"{self._get_element_type(parent)}_{parent}")
                    child_id = node_ids.get(elem['name'], f"{elem['type']}_{elem['name']}")
                    f.write(f'    "{parent_id}" -> "{child_id}" [style=solid];\n')
            
            f.write("  }\n\n")
            
            # 绘制状态转换（基于实际发生的转换）
            if self.transitions:
                f.write("  // 状态转换历史\n")
                for old_state, new_state, elem_name, timestamp in self.transitions[-20:]:  # 只显示最近20个转换
                    if old_state != ElementState.IDLE:
                        f.write(f'  // "{elem_name}": {old_state.value} -> {new_state.value} at {timestamp:.2f}s\n')
            
            f.write("}\n")
        
        return output_file


class ROS2LogSubscriber(Node):
    """ROS2日志订阅者"""
    
    def __init__(self, callback):
        if not ROS2_AVAILABLE:
            raise RuntimeError("ROS2不可用")
        super().__init__('xosc_fsm_visualizer')
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


class XOSCFSMVisualizer:
    """XOSC FSM 可视化器"""
    
    def __init__(self, xosc_file: str, output_dir: str = "."):
        self.xosc_file = xosc_file
        self.output_dir = output_dir
        self.fsm = XOSCFSM(xosc_file)
        self.dot_file = os.path.join(output_dir, "xosc_fsm.dot")
        self.png_file = os.path.join(output_dir, "xosc_fsm.png")
        
        # ROS2 相关
        self.ros2_subscriber = None
        self.ros2_thread = None
        self.running = False
        self.lock = threading.Lock()
        
        # 自动刷新
        self.auto_refresh = False
        self.refresh_interval = 0.5  # 秒
    
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
                # 导出新的 .dot 文件
                self.fsm.dump_graphviz(self.dot_file)
                
                # 如果启用自动刷新，生成 PNG
                if self.auto_refresh:
                    self._generate_png()
    
    def _generate_png(self):
        """生成 PNG 图片"""
        try:
            import subprocess
            result = subprocess.run(
                ['dot', '-Tpng', self.dot_file, '-o', self.png_file],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✓ 已更新图片: {self.png_file}")
            else:
                print(f"⚠ 生成图片失败: {result.stderr.decode()}")
        except FileNotFoundError:
            print("⚠ Graphviz 'dot' 命令未找到，请安装: sudo apt install graphviz")
        except Exception as e:
            print(f"⚠ 生成图片时出错: {e}")
    
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
    
    def generate_initial_graph(self):
        """生成初始状态图"""
        self.fsm.dump_graphviz(self.dot_file)
        print(f"✓ 已生成初始状态图: {self.dot_file}")
        
        # 尝试生成 PNG
        self._generate_png()
    
    def run(self, subscribe_ros2: bool = True, auto_refresh: bool = False):
        """运行可视化工具"""
        self.auto_refresh = auto_refresh
        
        print("=" * 60)
        print("OpenSCENARIO FSM + Graphviz 可视化工具")
        print("=" * 60)
        print(f"XOSC 文件: {self.xosc_file}")
        print(f"输出目录: {os.path.abspath(self.output_dir)}")
        print(f"元素数量: {len(self.fsm.elements)}")
        print("=" * 60)
        
        # 生成初始图
        self.generate_initial_graph()
        
        # 启动 ROS2 订阅
        ros2_started = False
        if subscribe_ros2:
            ros2_started = self.start_ros2_subscription()
        
        print("\n" + "=" * 60)
        print("工具状态:")
        print(f"  .dot 文件: {os.path.abspath(self.dot_file)}")
        if os.path.exists(self.png_file):
            print(f"  .png 文件: {os.path.abspath(self.png_file)}")
        print(f"  ROS2订阅: {'✓ 已启动' if ros2_started else '✗ 未启动'}")
        print(f"  自动刷新: {'✓ 已启用' if auto_refresh else '✗ 未启用'}")
        print("=" * 60)
        
        print("\n使用说明:")
        print("  1. 查看 .dot 文件: cat xosc_fsm.dot")
        print("  2. 生成 PNG: dot -Tpng xosc_fsm.dot -o xosc_fsm.png")
        print("  3. 自动刷新: 使用 --auto-refresh 参数")
        if ros2_started:
            print("  4. 状态变化时会自动更新 .dot 文件")
        print("\n按 Ctrl+C 退出")
        print("=" * 60)
        
        try:
            # 保持运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n正在关闭...")
            self.stop_ros2_subscription()
            print("已退出")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenSCENARIO FSM + Graphviz 可视化工具')
    parser.add_argument('xosc_file', type=str, help='XOSC 文件路径')
    parser.add_argument('-o', '--output', type=str, default='.', help='输出目录（默认：当前目录）')
    parser.add_argument('--no-ros2', action='store_true', help='禁用 ROS2 日志订阅')
    parser.add_argument('--auto-refresh', action='store_true', help='自动生成 PNG 图片（需要 graphviz）')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xosc_file):
        print(f"错误: 文件不存在: {args.xosc_file}")
        return 1
    
    try:
        visualizer = XOSCFSMVisualizer(args.xosc_file, args.output)
        visualizer.run(
            subscribe_ros2=not args.no_ros2,
            auto_refresh=args.auto_refresh
        )
        return 0
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())

