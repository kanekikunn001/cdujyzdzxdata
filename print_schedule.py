#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
排班结果打印示例
展示符合要求的scheduling_data.json和scheduling_list.json格式
"""

import json
from datetime import datetime

def generate_sample_schedule():
    """生成示例排班数据"""
    # 模拟配置
    config = {
        "week": 8,
        "days_order": [1,2,3,4,5],
        "days": [1,2,3,4,5],
        "time_period": [
            {"days":[1,2,3,4],"times":[1,2,3,4,5,6]},
            {"days":[5],"times":[1,2,3]}
        ]
    }
    
    # 示例排班结果 (scheduling_data.json 格式)
    scheduling_data = {
        "_metadata": {
            "week": config["week"],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "data": [
            {"周一1-2节": ["202311202305", "202511608121", "202511001218", "202410811201"]},
            {"周一3-4节": ["202410215208", "202410211111", "202310212401"]},
            {"周二1-2节": ["202511608121", "202410811201", "202310212401"]},
            {"周三中午节": ["202410215208", "202511001218"]},
            {"周四9节": ["202311202305", "202410211111"]}
        ]
    }
    
    # 示例人员统计 (scheduling_list.json 格式)
    scheduling_list = {
        "_metadata": {
            "week": config["week"],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "data": [
            {
                "id": "202310212401",
                "week_times": 2,
                "day_times": 2,
                "morning_times": 1,
                "night_times": 0,
                "all_morning_times": 2,
                "all_night_times": 0
            },
            {
                "id": "202410215208",
                "week_times": 2,
                "day_times": 2,
                "morning_times": 1,
                "night_times": 0,
                "all_morning_times": 3,
                "all_night_times": 1
            },
            {
                "id": "202511608121",
                "week_times": 2,
                "day_times": 2,
                "morning_times": 2,
                "night_times": 0,
                "all_morning_times": 5,
                "all_night_times": 0
            }
        ]
    }
    
    return scheduling_data, scheduling_list

def print_schedule():
    """打印排班结果"""
    scheduling_data, scheduling_list = generate_sample_schedule()
    
    print("="*50)
    print("排班数据 (scheduling_data.json 格式):")
    print("="*50)
    print(json.dumps(scheduling_data, ensure_ascii=False, indent=2))
    
    print("\n" + "="*50)
    print("人员统计 (scheduling_list.json 格式):")
    print("="*50)
    print(json.dumps(scheduling_list, ensure_ascii=False, indent=2))
    
    # 验证格式合规性
    validate_format(scheduling_data, scheduling_list)

def validate_format(data, stats):
    """验证输出格式是否符合要求"""
    # 验证 metadata
    assert "week" in data["_metadata"]
    assert "last_updated" in data["_metadata"]
    
    # 验证数据结构
    for entry in data["data"]:
        assert len(entry) == 1  # 每个条目只有一个时间槽键
        
    for person in stats["data"]:
        required_fields = ["week_times", "day_times", "morning_times", "night_times", 
                          "all_morning_times", "all_night_times"]
        assert all(field in person for field in required_fields)
    
    print("\n✓ 输出格式验证通过！")

if __name__ == "__main__":
    print_schedule()