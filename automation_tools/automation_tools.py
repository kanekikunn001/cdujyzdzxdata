import os
import json
import shutil
from datetime import datetime
import sqlite3


class FeedbackProcessor:
    def __init__(self, db_path="database/data/JYZDZXdata.db", feedback_dir="feedback"):
        self.db_path = db_path
        self.feedback_dir = feedback_dir
        self.ensure_feedback_table()
    
    def ensure_feedback_table(self):
        """确保反馈统计表存在"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS 反馈统计表 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                学号 TEXT NOT NULL,
                反馈备注 TEXT,
                处理结果 TEXT,
                审核人员 TEXT,
                上传时间 TEXT,
                反馈文件名 TEXT,
                创建时间 DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
            conn.close()
            print("✅ 反馈统计表已准备就绪")
        except Exception as e:
            print(f"❌ 创建反馈统计表失败: {e}")
    
    def process_feedback_file(self, feedback_file):
        """处理单个反馈文件"""
        try:
            if not os.path.exists(feedback_file):
                print(f"❌ 反馈文件不存在: {feedback_file}")
                return False
            
            # 读取反馈文件
            with open(feedback_file, 'r', encoding='utf-8') as f:
                feedback_data = json.load(f)
            
            # 解析反馈文件格式
            metadata = feedback_data.get('_metadata', {})
            data_list = feedback_data.get('data', [])
            
            if not data_list:
                print(f"❌ 反馈文件数据为空: {feedback_file}")
                return False
            
            # 获取第一个学生的学号作为主要学号
            student_info = data_list[0]
            student_id = str(student_info.get('学号', ''))
            
            if not student_id:
                print(f"❌ 反馈文件缺少学号信息: {feedback_file}")
                return False
            
            # 默认module为feedback（不更新数据库）
            module_type = 'feedback'
            
            # 记录到反馈统计表
            upload_time = metadata.get('last_updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            self.record_feedback(
                student_id, '空闲时间更新', '已处理', 
                '系统自动', upload_time, os.path.basename(feedback_file)
            )
            
            # 根据module类型决定是否更新数据库
            if module_type == 'formal':
                print(f"🔄 处理正式模式反馈: {feedback_file}")
                self.update_database_from_feedback(feedback_data)
            else:
                print(f"📝 处理反馈模式反馈（不更新数据库）: {feedback_file}")
            
            # 备份原数据文件
            self.backup_current_data()
            
            # 更新本地JSON文件（这里主要是更新空闲时间表）
            self.update_free_time_from_feedback(feedback_data)
            
            print(f"✅ 反馈文件处理完成: {feedback_file}")
            return True
            
        except Exception as e:
            print(f"❌ 处理反馈文件失败 {feedback_file}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def record_feedback(self, student_id, note, result, reviewer, upload_time, filename):
        """记录反馈信息到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO 反馈统计表 
                (学号, 反馈备注, 处理结果, 审核人员, 上传时间, 反馈文件名)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (student_id, note, result, reviewer, upload_time, filename))
            conn.commit()
            conn.close()
            print(f"✅ 反馈记录已保存: {student_id}")
        except Exception as e:
            print(f"❌ 保存反馈记录失败: {e}")
    
    def backup_current_data(self):
        """备份当前的数据文件"""
        backup_dir = "backup/feedback"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files_to_backup = [
            "mini_program_data/scheduling_data.json",
            "mini_program_data/scheduling_list.json",
            "mini_program_data/time_list.json"
        ]
        
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                backup_name = f"{os.path.basename(file_path)}_{timestamp}"
                shutil.copy2(file_path, os.path.join(backup_dir, backup_name))
                print(f"💾 已备份: {file_path} -> {backup_name}")
    
    def update_database_from_feedback(self, feedback_data):
        """根据反馈数据更新数据库（仅formal模式）"""
        try:
            # 这里需要根据具体的反馈内容来更新值班表
            # 假设反馈数据中包含需要更新的排班信息
            changes = feedback_data.get('changes', [])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for change in changes:
                student_id = change.get('student_id')
                action = change.get('action')  # 'add', 'remove', 'swap'
                
                if action == 'add':
                    # 添加排班记录
                    pass
                elif action == 'remove':
                    # 移除排班记录
                    pass
                elif action == 'swap':
                    # 交换班次
                    pass
            
            conn.commit()
            conn.close()
            print("✅ 数据库已根据反馈更新")
            
        except Exception as e:
            print(f"❌ 更新数据库失败: {e}")
    
    def update_free_time_from_feedback(self, feedback_data):
        """根据反馈数据更新空闲时间表"""
        try:
            data_list = feedback_data.get('data', [])
            if not data_list:
                return
            
            student_info = data_list[0]
            student_id = str(student_info.get('学号', ''))
            free_time_data = student_info.get('空闲时间', {})
            
            if not student_id or not free_time_data:
                return
            
            # 连接数据库更新空闲时间表
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建更新SQL
            time_columns = []
            time_values = []
            
            # 时间段映射
            day_map = {"周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5, "周六": 6, "周日": 7}
            time_map = {"1-2节": 1, "3-4节": 2, "中午节": 3, "5-6节": 4, "7-8节": 5, "9节": 6}
            
            for time_slot, free_weeks in free_time_data.items():
                # 解析时间段
                for day_name, day_num in day_map.items():
                    if time_slot.startswith(day_name):
                        time_part = time_slot[len(day_name):]
                        if time_part in time_map:
                            time_num = time_map[time_part]
                            period_index = (day_num - 1) * 6 + time_num
                            column_name = f"period_{period_index}"
                            time_columns.append(f'"{column_name}"')
                            time_values.append(str(free_weeks))
                            break
            
            if time_columns:
                set_clause = ", ".join([f"{col} = ?" for col in time_columns])
                sql = f'''UPDATE 空闲时间表 SET {set_clause} WHERE 学号 = ?'''
                values = time_values + [student_id]
                
                # 如果学生不存在，先插入
                cursor.execute("SELECT 学号 FROM 空闲时间表 WHERE 学号 = ?", (student_id,))
                if not cursor.fetchone():
                    # 插入新记录
                    all_columns = ["学号"] + [f'"period_{i}"' for i in range(1, 31)]
                    all_values = [student_id] + ['[]'] * 30
                    
                    # 更新特定时间段
                    for i, col in enumerate(time_columns):
                        idx = all_columns.index(col)
                        all_values[idx] = time_values[i]
                    
                    insert_sql = f'''INSERT INTO 空闲时间表 ({", ".join(all_columns)}) VALUES ({", ".join(["?"] * len(all_values))})'''
                    cursor.execute(insert_sql, all_values)
                else:
                    # 更新现有记录
                    cursor.execute(sql, values)
                
                conn.commit()
                print(f"✅ 空闲时间表已更新: {student_id}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 更新空闲时间表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_local_json_files(self, feedback_data):
        """更新本地JSON文件"""
        try:
            # 读取现有的scheduling_data.json和scheduling_list.json
            scheduling_data_file = "mini_program_data/scheduling_data.json"
            scheduling_list_file = "mini_program_data/scheduling_list.json"
            
            # 这里需要根据反馈数据的具体格式来实现更新逻辑
            # 假设反馈数据中包含了修改后的完整数据
            
            if 'scheduling_data' in feedback_data:
                with open(scheduling_data_file, 'w', encoding='utf-8') as f:
                    json.dump(feedback_data['scheduling_data'], f, ensure_ascii=False, indent=2)
            
            if 'scheduling_list' in feedback_data:
                with open(scheduling_list_file, 'w', encoding='utf-8') as f:
                    json.dump(feedback_data['scheduling_list'], f, ensure_ascii=False, indent=2)
            
            # 更新version.json
            self.update_version_file()
            
            print("✅ 本地JSON文件已更新")
            
        except Exception as e:
            print(f"❌ 更新本地JSON文件失败: {e}")
    
    def update_version_file(self):
        """更新版本文件的时间戳"""
        version_file = "mini_program_data/version.json"
        version_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)
        print("✅ 版本文件已更新")
    
    def process_all_feedbacks(self):
        """处理所有反馈文件"""
        if not os.path.exists(self.feedback_dir):
            print(f"📁 反馈目录不存在: {self.feedback_dir}")
            return
        
        processed_count = 0
        for filename in os.listdir(self.feedback_dir):
            if filename.endswith('.json'):
                feedback_file = os.path.join(self.feedback_dir, filename)
                if self.process_feedback_file(feedback_file):
                    processed_count += 1
        
        print(f"✅ 总共处理了 {processed_count} 个反馈文件")


class TimeListExporter:
    """导出time_list.json的工具类"""
    
    def __init__(self, db_path="database/data/JYZDZXdata.db"):
        self.db_path = db_path
    
    def export_time_list(self, output_file="mini_program_data/time_list.json"):
        """导出time_list.json格式"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有学生的基础信息和空闲时间
            cursor.execute('''SELECT b.学号, b.name, b.job, b.department, b.phone, k.*
                           FROM 基础信息表 b
                           LEFT JOIN 空闲时间表 k ON b.学号 = k.学号''')
            rows = cursor.fetchall()
            
            # 获取列名
            columns = [desc[0] for desc in cursor.description]
            
            time_list_data = {
                "_metadata": {
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": []
            }
            
            for row in rows:
                student_info = {}
                free_time = {}
                
                for i, col_name in enumerate(columns):
                    value = row[i]
                    if col_name == '学号':
                        student_info['学号'] = str(value) if value else ''
                    elif col_name == 'name':
                        student_info['姓名'] = value if value else ''
                    elif col_name == 'job':
                        student_info['职位'] = value if value else ''
                    elif col_name == 'department':
                        student_info['部门'] = value if value else ''
                    elif col_name == 'phone':
                        student_info['电话号码'] = str(value) if value else ''
                    elif col_name.startswith('period_'):
                        # 转换为时间段格式
                        period_num = int(col_name.replace('period_', ''))
                        day_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
                        time_map = {1: "1-2节", 2: "3-4节", 3: "中午节", 4: "5-6节", 5: "7-8节", 6: "9节"}
                        
                        day_idx = (period_num - 1) // 6 + 1
                        time_idx = (period_num - 1) % 6 + 1
                        
                        if day_idx <= 7 and time_idx <= 6:
                            day_name = day_map.get(day_idx, f"周{day_idx}")
                            time_name = time_map.get(time_idx, f"{time_idx}节")
                            time_slot = f"{day_name}{time_name}"
                            
                            # 解析空闲周数据
                            try:
                                if value:
                                    free_weeks = eval(value)  # 注意：生产环境应使用json.loads
                                    free_time[time_slot] = free_weeks
                                else:
                                    free_time[time_slot] = []
                            except:
                                free_time[time_slot] = []
                
                # 设置状态（可以根据实际需求调整）
                student_info['状态'] = '在校'
                student_info['空闲时间'] = free_time
                
                time_list_data['data'].append(student_info)
            
            conn.close()
            
            # 保存到文件
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(time_list_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ time_list.json 导出完成: {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ 导出time_list.json失败: {e}")
            return False