# 排班功能测试代码
import os
import json
import sys
from scheduling_algorithm.scheduling_configuration_file_module import SchedulingConfigurationFileModule
from scheduling_algorithm.scheduling_configuration_allocate import SchedulingConfigurationAllocate
from database.code.basecmd import CourseSchedule

def test_basic_components():
    """测试基本组件是否能正常工作"""
    print("=" * 60)
    print("测试基本组件...")
    print("=" * 60)
    
    # 测试1: 检查数据库文件是否存在
    db_path = "database/data/JYZDZXdata.db"
    if os.path.exists(db_path):
        print(f"✅ 数据库文件存在: {db_path}")
        db_exists = True
    else:
        print(f"❌ 数据库文件不存在: {db_path}")
        db_exists = False
        
    # 测试2: 检查配置文件是否存在
    config_path = "configuration_file/scheduling_configuration_file.json"
    if os.path.exists(config_path):
        print(f"✅ 配置文件存在: {config_path}")
        config_exists = True
    else:
        print(f"❌ 配置文件不存在: {config_path}")
        config_exists = False
    
    # 测试3: 尝试读取配置文件
    if config_exists:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            print("✅ 配置文件可正常读取")
            print(f"   - 当前周数: {config_data.get('week', '未知')}")
            print(f"   - 工作日: {config_data.get('days', [])}")
            print(f"   - 时间段配置: {len(config_data.get('time_period', []))} 条")
        except Exception as e:
            print(f"❌ 配置文件读取失败: {e}")
            config_exists = False
    
    return db_exists, config_exists

def test_scheduling_config_module():
    """测试调度配置文件模块"""
    print("\n" + "=" * 60)
    print("测试调度配置文件模块...")
    print("=" * 60)
    
    try:
        # 使用正确的配置文件路径
        from scheduling_algorithm.scheduling_configuration_file_module import SchedulingConfigurationFileModule
        module = SchedulingConfigurationFileModule(file_path="configuration_file/scheduling_configuration_file.json")
        
        print("✅ SchedulingConfigurationFileModule 初始化成功")
        print(f"   - 配置文件路径: {module.file_path}")
        print(f"   - 配置数据长度: {len(str(module.file_data)) if module.file_data else 0} 字符")
        
        # 测试临时修改功能
        temp_data = {"test_key": "test_value"}
        result = module.modify_temporary_configuration(temp_data)
        print("✅ 临时修改功能正常")
        
        return True
    except Exception as e:
        print(f"❌ SchedulingConfigurationFileModule 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def read_json_file(file_path):
    """辅助函数：读取JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def test_scheduling_allocation():
    """测试排班分配功能"""
    print("\n" + "=" * 60)
    print("测试排班分配功能...")
    print("=" * 60)
    
    # 读取配置文件
    config_path = "configuration_file/scheduling_configuration_file.json"
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 创建排班分配器
        allocator = SchedulingConfigurationAllocate(config_data)
        print("✅ SchedulingConfigurationAllocate 初始化成功")
        
        # 测试一些基本功能
        print(f"   - 当前周: {allocator.week}")
        print(f"   - 工作日: {allocator.days}")
        print(f"   - 部门限制: {'开启' if allocator.same_department else '关闭'}")
        
        # 尝试执行一次排班
        print("\n正在执行排班测试...")
        result = allocator.active()
        
        if result:
            print("✅ 排班执行成功")
            print(f"   - 排班结果天数: {len(result)}")
            
            # 显示部分结果
            for day, day_schedule in list(result.items())[:2]:  # 只显示前两天
                print(f"   - {day}: 包含 {len(day_schedule)} 个时间段")
                for time_period, info in list(day_schedule.items())[:2]:  # 只显示前两个时间段
                    print(f"     * {time_period}: 需要 {info['需要人数']} 人, 实际安排 {len(info['排班人员'])} 人")
        else:
            print("⚠️ 排班结果为空 (可能是因为数据库中没有符合条件的学生)")
        
        return True
        
    except Exception as e:
        print(f"❌ 排班分配功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_operations():
    """测试数据库操作功能"""
    print("\n" + "=" * 60)
    print("测试数据库操作功能...")
    print("=" * 60)
    
    try:
        # 创建数据库实例
        db = CourseSchedule()
        print("✅ CourseSchedule 初始化成功")
        
        # 测试数据库连接
        conn = db.get_conn()
        if conn:
            print("✅ 数据库连接成功")
            conn.close()
        else:
            print("❌ 数据库连接失败")
            return False
        
        # 检查主要表是否存在
        try:
            conn = db.get_conn()
            cursor = conn.cursor()
            
            # 检查空闲时间表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='空闲时间表'")
            if cursor.fetchone():
                print("✅ 空闲时间表存在")
            else:
                print("⚠️ 空闲时间表不存在")
                
            # 检查基础信息表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='基础信息表'")
            if cursor.fetchone():
                print("✅ 基础信息表存在")
            else:
                print("⚠️ 基础信息表不存在")
                
            # 检查签到表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='签到表'")
            if cursor.fetchone():
                print("✅ 签到表存在")
            else:
                print("⚠️ 签到表不存在")
                
            # 检查值班表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='值班表'")
            if cursor.fetchone():
                print("✅ 值班表存在")
            else:
                print("⚠️ 值班表不存在")
                
            conn.close()
        except Exception as e:
            print(f"❌ 表检查失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_scheduling_scenarios():
    """测试特定排班场景"""
    print("\n" + "=" * 60)
    print("测试特定排班场景...")
    print("=" * 60)
    
    # 读取配置文件
    config_path = "configuration_file/scheduling_configuration_file.json"
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 创建排班分配器
        allocator = SchedulingConfigurationAllocate(config_data)
        
        # 测试获取某天的时间段
        for day in allocator.days[:2]:  # 只测试前两天
            times = allocator.get_day_times(day)
            print(f"   - 第{day}天的时间段: {times}")
            
            # 测试获取需要的人数
            for time in times[:2]:  # 只测试前两个时间段
                need_num = allocator.acquire_time_period_people_number(time)
                print(f"     * 第{time}时间段需要人数: {need_num}")
                
                # 尝试获取空闲学生（这里可能因为数据库中没有数据而返回空列表）
                free_students = allocator.db.get_free_students(allocator.week, day, time)
                print(f"     * 第{day}天第{time}时间段空闲学生数: {len(free_students)}")
                
                # 尝试生成工作人员
                workers = allocator.generate_workers(need_num, day, time)
                print(f"     * 实际安排工作人员数: {len(workers)}")
        
        print("✅ 特定排班场景测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 特定排班场景测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("排班程序功能测试工具")
    print("=" * 60)
    
    # 运行各项测试
    db_exists, config_exists = test_basic_components()
    config_module_ok = test_scheduling_config_module()
    allocation_ok = test_scheduling_allocation()
    database_ok = test_database_operations()
    scenarios_ok = test_specific_scheduling_scenarios()
    
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    
    print(f"基本组件检查: {'✅ 通过' if (db_exists and config_exists) else '❌ 失败'}")
    print(f"配置模块测试: {'✅ 通过' if config_module_ok else '❌ 失败'}")
    print(f"排班分配测试: {'✅ 通过' if allocation_ok else '❌ 失败'}")
    print(f"数据库操作测试: {'✅ 通过' if database_ok else '❌ 失败'}")
    print(f"特定场景测试: {'✅ 通过' if scenarios_ok else '❌ 失败'}")
    
    # 整体评估
    overall_result = all([db_exists, config_exists, config_module_ok, allocation_ok, database_ok, scenarios_ok])
    print(f"\n整体结果: {'✅ 所有功能测试通过!' if overall_result else '❌ 部分功能存在问题!'}")
    
    # 提供建议
    if not db_exists:
        print("\n提示: 如果数据库文件不存在，您需要先创建数据库:")
        print("  - 运行相应的初始化脚本来创建数据库和表")
        print("  - 或者手动创建 database/data/JYZDZXdata.db 文件")
    
    if not config_exists:
        print("\n提示: 如果配置文件不存在，请参考示例创建配置文件")
    
    if not overall_result:
        print("\n提示: 查看上面的详细输出以了解具体问题")
    
    return overall_result

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试排班系统主流程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scheduling_algorithm.scheduling_configuration_allocate import load_config, SchedulingConfigurationAllocate

def main():
    try:
        # 加载配置文件
        config = load_config()
        print("✓ 配置文件加载成功")
        
        # 执行排班
        scheduler = SchedulingConfigurationAllocate(config)
        result = scheduler.active()
        print("✓ 排班执行完成")
        
        # 打印详细结果
        print("\n" + "="*50)
        print("详细排班结果:")
        print("="*50)
        has_data = False
        for day, times in result.items():
            if times:
                has_data = True
                print(f"\n{day}:")
                for time_slot, details in times.items():
                    workers = details["排班人员"]
                    print(f"  {time_slot}: {workers}")
        
        if not has_data:
            print("\n⚠️  无排班数据，请检查:")
            print("   1. 配置文件中的week是否有效")
            print("   2. 数据库中是否有对应周的空闲数据")
            print("   3. 空闲时间表结构是否正确")
            
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
