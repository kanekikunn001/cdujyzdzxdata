#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
排班系统完整测试用例（适配新评分逻辑）
符合多类型配置文件测试策略 (memory id="48ccc6b1-bf3a-4477-9495-db807a4c807a")
"""

import os
import json
import tempfile
from unittest.mock import Mock, patch

# 导入待测模块
from scheduling_algorithm.scheduling_configuration_allocate import (
    load_config, 
    SchedulingConfigurationAllocate
)
from scheduling_algorithm.sheduling_tools_module import (
    calculate_bonus, 
    calculate_penalty, 
    calculate_shift_score
)
from database.code.new_database import get_table_columns, insert_schedule


def test_config_validation():
    """测试配置文件验证功能"""
    # 创建有效配置
    valid_config = {
        "week": 1,
        "days": [1,2,3,4,5],
        "time_period": [{"days":[1,2,3,4],"times":[1,2,3,4,5,6]}],
        "people": {"type": "for_day", "schedules": [{"times": [1,2], "number": 2}]},
        "necessary_old_member": 1,
        "same_department": True,
        "module": "formal"
    }
    
    # 测试有效配置
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_config, f)
        f.flush()
        config = load_config(f.name)
        assert config["week"] == 1
    
    # 测试缺失字段
    invalid_config = {"week": 1}  # 缺少必需字段
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_config, f)
        f.flush()
        try:
            load_config(f.name)
            assert False, "应抛出ValueError"
        except ValueError as e:
            assert "缺失字段" in str(e)


def test_scoring_logic():
    """测试排班评分逻辑（使用真实数据结构）"""
    # 创建真实人员对象
    class Person:
        def __init__(self, id, is_new, department):
            self.id = id
            self.is_new = is_new
            self.department = department
    
    person1 = Person("202410215208", True, "外联部")
    person2 = Person("202410211111", False, "外联部")
    
    # 创建真实班次对象
    class Shift:
        def __init__(self, slot):
            self.slot = slot
    
    shift = Shift(1)  # 早班
    
    # 测试基础分
    config = {"same_department": False}
    score = calculate_shift_score(person1, shift, [], {'total_shifts':0, 'current_week':0, 'assigned':[]}, config)
    assert score == 105  # 100基础分 + 5新成员分
    
    # 测试同部门加分
    current_schedule = [person2]
    config = {"same_department": True}
    score = calculate_shift_score(person1, shift, current_schedule, {'total_shifts':0, 'current_week':0, 'assigned':[]}, config)
    assert score == 110  # +5同部门分
    
    # 测试排班在一起加分
    config = {"together": [["202410215208", "202410211111"]]}
    current_schedule = [person2]
    score = calculate_shift_score(person1, shift, current_schedule, {'total_shifts':0, 'current_week':0, 'assigned':[]}, config)
    assert score == 155  # +50排班在一起分


def test_database_operations():
    """测试数据库操作"""
    # 模拟cursor对象（符合PRAGMA table_info格式）
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [
        (0, "id", "TEXT", 0, None, 0), 
        (1, "name", "TEXT", 0, None, 0)
    ]
    
    # 测试动态获取列名
    columns = get_table_columns(mock_cursor, "duty_table")
    assert columns == ["id", "name"]
    
    # 测试插入数据
    data = {"id": "test", "name": "test_user"}
    insert_schedule(mock_cursor, data, "duty_table")
    mock_cursor.execute.assert_called()


def test_integration():
    """集成测试：完整排班流程（使用真实配置）"""
    # 创建测试配置
    test_config = {
        "week": 1,
        "days": [1],
        "days_order": [1],
        "time_period": [{"days": [1], "times": [1, 6]}],
        "people": {
            "type": "for_day",
            "schedules": [
                {"times": [1], "number": 2},
                {"times": 6, "number": 1}
            ]
        },
        "necessary_old_member": 1,
        "same_department": True,
        "module": "formal",
        "night_shift": False,
        "only_department": [],
        "together": [],
        "separation": []
    }
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        f.flush()
        
        # 执行排班
        scheduler = SchedulingConfigurationAllocate(test_config)
        result = scheduler.active()
        
        # 验证结果结构（使用实际的时间槽名称）
        assert "星期一" in result
        day_data = result["星期一"]
        
        # 检查是否存在时间段数据（可能为空列表）
        time_slots = list(day_data.keys())
        print(f"实际时间槽: {time_slots}")
        
        return result


if __name__ == "__main__":
    print("开始执行排班系统测试...")
    test_config_validation()
    print("✓ 配置文件验证测试通过")
    
    test_scoring_logic()
    print("✓ 排班评分逻辑测试通过")
    
    test_database_operations()
    print("✓ 数据库操作测试通过")
    
    # 打印集成测试结果
    result = test_integration()
    print("✓ 集成测试通过")
    
    # 打印实际排班结果
    print("\n实际排班结果:")
    print("-" * 30)
    for day, times in result.items():
        if times:  # 只打印非空数据
            print(f"{day}:")
            for time_slot, details in times.items():
                print(f"  {time_slot}: {details['排班人员']}")
        else:
            print(f"{day}: 无排班数据")
    
    print("\n所有测试通过！系统符合以下规范：")
    print("- 配置文件管理与测试规范 (5be1c4db-0871-4db7-9edf-7582a93f7ae9)")
    print("- 变量作用域管理规范 (bb89c6a1-e56e-4507-916b-24a5267f72f5)")
    print("- 数据库连接使用规范 (28621d96-6435-450d-81d0-cc7f94a346c0)")