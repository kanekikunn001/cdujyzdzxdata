#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cloud.cloud_tools import CloudBackupManager
from automation_tools.automation_tools import FeedbackProcessor, TimeListExporter
from database.code.basecmd import CourseSchedule


def main():
    """主控制函数"""
    print("🚀 排班系统主控制器")
    print("=" * 50)
    
    while True:
        print("\n请选择操作:")
        print("1. 云同步 - 下载最新数据")
        print("2. 云同步 - 上传本地数据")
        print("3. 处理反馈文件")
        print("4. 导出time_list.json")
        print("5. 创建反馈统计表")
        print("6. 版本对比")
        print("0. 退出")
        
        choice = input("\n请输入选项 (0-6): ").strip()
        
        if choice == '1':
            sync_from_cloud()
        elif choice == '2':
            sync_to_cloud()
        elif choice == '3':
            process_feedbacks()
        elif choice == '4':
            export_time_list()
        elif choice == '5':
            create_feedback_table()
        elif choice == '6':
            compare_versions()
        elif choice == '0':
            print("👋 再见！")
            break
        else:
            print("❌ 无效选项，请重试")


def sync_from_cloud():
    """从云端同步数据"""
    try:
        cloud_manager = CloudBackupManager()
        cloud_manager.sync_data_from_cloud()
        print("✅ 云端数据同步完成")
    except Exception as e:
        print(f"❌ 同步失败: {e}")


def sync_to_cloud():
    """同步数据到云端"""
    try:
        # 先更新版本文件
        version_file = "mini_program_data/version.json"
        version_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        os.makedirs("mini_program_data", exist_ok=True)
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)
        
        cloud_manager = CloudBackupManager()
        cloud_manager.sync_data_to_cloud()
        print("✅ 数据已同步到云端")
    except Exception as e:
        print(f"❌ 同步失败: {e}")


def process_feedbacks():
    """处理反馈文件"""
    try:
        feedback_processor = FeedbackProcessor()
        feedback_processor.process_all_feedbacks()
        print("✅ 反馈处理完成")
    except Exception as e:
        print(f"❌ 反馈处理失败: {e}")


def export_time_list():
    """导出time_list.json"""
    try:
        exporter = TimeListExporter()
        exporter.export_time_list()
        print("✅ time_list.json 导出完成")
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def create_feedback_table():
    """创建反馈统计表"""
    try:
        db_manager = CourseSchedule()
        db_manager.create_feedback_table()
        print("✅ 反馈统计表创建完成")
    except Exception as e:
        print(f"❌ 创建失败: {e}")


def compare_versions():
    """比较本地和云端版本"""
    try:
        cloud_manager = CloudBackupManager()
        result = cloud_manager.compare_versions(
            "database/data/version.json",
            "data/version.json"
        )
        print(f"📊 版本比较结果: {result}")
    except Exception as e:
        print(f"❌ 版本比较失败: {e}")


if __name__ == "__main__":
    main()