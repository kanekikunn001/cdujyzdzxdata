#获取到配置文件后，根据配置文件中的信息，分配资源


import sys
import os
import sqlite3
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduling_algorithm.sheduling_tools_module import calculate_shift_score
from scheduling_algorithm.operations_research_scheduler import OperationsResearchScheduler

# 数据库操作类：专门和数据库打交道，查空闲、查部门
class SchedulingDB:
    # 初始化：指定数据库文件路径
    def __init__(self, db_path="database/data/JYZDZXdata.db"):
        self.db_path = db_path  # 数据库文件名

    # 核心功能：查询【某一周、某一天、某一节】空闲的学生
    def get_free_students(self, schedule_week, day, time):
        week_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
        time_map = {1: "1-2节", 2: "3-4节", 3: "中午节", 4: "5-6节", 5: "7-8节", 6: "9节"}

        col_name = f"{week_map[day]}{time_map[time]}"
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            # 修正查询逻辑：检查空闲周列表是否包含目标周
            sql = f"SELECT 学号 FROM 空闲时间表 WHERE 学号 IS NOT NULL"
            cur.execute(sql)
            all_students = cur.fetchall()
            
            free_list = []
            for row in all_students:
                stu_id = row[0]
                # 获取该学生的空闲周数据
                cur.execute(f"SELECT `{col_name}` FROM 空闲时间表 WHERE 学号 = ?", (stu_id,))
                result = cur.fetchone()
                if result and result[0]:
                    # 解析存储的字符串为列表
                    try:
                        free_weeks = eval(result[0])  # 安全性注意：生产环境应使用json.loads
                        if schedule_week in free_weeks:
                            free_list.append(str(stu_id))
                    except:
                        continue
            
            conn.close()
            return free_list
        except Exception as e:
            print(f"查询空闲学生失败: {e}")
            return []

    # 根据学号，查询学生所属部门
    def get_student_department(self, student_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT department FROM 基础信息表 WHERE 学号 = ?', (student_id,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else "未知部门"
        except:
            return "未知部门"

    # 把一批学生，按【部门】分组
    def group_by_department(self, student_id_list):
        try:
            dept_group = {}
            for sid in student_id_list:
                dept = self.get_student_department(sid)
                if dept not in dept_group:
                    dept_group[dept] = []
                dept_group[dept].append(sid)
            return dept_group
        except:
            return {}


# 排班核心类：所有规则来自JSON，只负责排班
class SchedulingConfigurationAllocate:
    # 初始化：传入JSON配置
    def __init__(self, scheduling_configuration_file):
        self.scheduling_configuration_file = scheduling_configuration_file
        self.allocate()
        self.schedule_result = {}
        self.db = SchedulingDB()

        self.week_name_map = {1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五"}
        # 修正时间槽名称，与数据库列名保持一致
        self.time_name_map = {
            1: "1-2节",
            2: "3-4节",
            3: "中午节",
            4: "5-6节",
            5: "7-8节",
            6: "9节"
        }

    def allocate(self):
        try:
            self.week = self.scheduling_configuration_file["week"]
            self.days = self.scheduling_configuration_file["days"]
            self.days_order = self.scheduling_configuration_file["days_order"]
            self.time_period = self.scheduling_configuration_file["time_period"]
            self.people = self.scheduling_configuration_file["people"]
            self.same_department = self.scheduling_configuration_file["same_department"]
            self.night_shift = self.scheduling_configuration_file["night_shift"]
            self.only_department = self.scheduling_configuration_file["only_department"]
            self.together = self.scheduling_configuration_file["together"]
            self.separation = self.scheduling_configuration_file["separation"]
            return True
        except:
            return False

    def get_current_day_shifts(self, student_id, current_day_schedule):
        """获取学生当天已排班次数（基于当前排班进度）"""
        count = 0
        for day_name, times in current_day_schedule.items():
            for time_slot, details in times.items():
                if student_id in details.get("排班人员", []):
                    count += 1
        return count

    def is_new_member(self, student_id):
        try:
            conn = sqlite3.connect(self.db.db_path)
            cur = conn.cursor()
            cur.execute('SELECT job FROM 基础信息表 WHERE 学号 = ?', (student_id,))
            row = cur.fetchone()
            conn.close()
            # 如果职务不是"新成员"，则为老成员
            return row and row[0] == "新成员"
        except:
            return True  # 默认视为新成员

    def is_old_member(self, student_id):
        """判断是否为老成员"""
        return not self.is_new_member(student_id)
    
    def get_current_week_shifts_from_db(self, student_id):
        """从数据库获取学生本周已排班次数"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cur = conn.cursor()
            cur.execute('''SELECT 本周早班数, 本周午班数, 本周下午班数, 本周晚班数 
                          FROM 值班表 WHERE 学号 = ?''', (student_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return sum(row) if row else 0
            return 0
        except:
            return 0

    def get_current_week_shifts(self, student_id):
        """获取学生本周已排班次数 (保留以兼容其他可能调用，内部调用新函数)"""
        return self.get_current_week_shifts_from_db(student_id)

    # 获取周统计信息（完整实现）
    def get_weekly_stats(self, student_ids):
        """
        获取每个学生的周统计信息
        返回字典：{student_id: stats_dict}
        """
        stats = {}
        try:
            conn = sqlite3.connect(self.db.db_path)
            cur = conn.cursor()
            
            for sid in student_ids:
                # 查询值班表中的统计数据
                cur.execute('''SELECT 总值班数, 学期值早班数, 学期值午班数, 学期值下午班数, 学期值晚班数,
                              本周早班数, 本周午班数, 本周下午班数, 本周晚班数 
                              FROM 值班表 WHERE 学号 = ?''', (sid,))
                row = cur.fetchone()
                
                if row:
                    total_shifts = row[0] or 0
                    # 早班(slot=1)对应学期值早班数和本周早班数
                    slot_1_shifts = (row[1] or 0) + (row[5] or 0)
                    # 晚班(slot=6)对应学期值晚班数和本周晚班数  
                    slot_6_shifts = (row[4] or 0) + (row[8] or 0)
                    # 本周总值班数
                    current_week = sum(row[5:9]) if row[5:9] else 0
                    
                    stats[sid] = {
                        'total_shifts': total_shifts,
                        '1_shifts': slot_1_shifts,  # 早班次数
                        '6_shifts': slot_6_shifts,  # 晚班次数
                        'current_week': current_week,
                        'assigned': []  # 当前排班轮次中已分配的人员对象（动态更新）
                    }
                else:
                    # 如果没有记录，初始化为0
                    stats[sid] = {
                        'total_shifts': 0,
                        '1_shifts': 0,
                        '6_shifts': 0,
                        'current_week': 0,
                        'assigned': []
                    }
            
            conn.close()
            return stats
        except Exception as e:
            print(f"获取周统计信息失败: {e}")
            # 返回默认值
            return {sid: {
                'total_shifts': 0,
                '1_shifts': 0,
                '6_shifts': 0,
                'current_week': 0,
                'assigned': []
            } for sid in student_ids}

    # 核心排班算法（使用评分逻辑）
    def generate_workers(self, need_num, day, time, current_day_assigned=None, current_week_assigned=None):
        """current_day_assigned: 当天已分配的人员列表
           current_week_assigned: 本周已分配的人员统计字典 {student_id: count}"""
        if current_day_assigned is None:
            current_day_assigned = []
        if current_week_assigned is None:
            current_week_assigned = {}
            
        try:
            free_list = self.db.get_free_students(self.week, day, time)
            if not free_list:
                return []
            
            # 创建人员对象列表
            eligible_persons = []
            for sid in free_list:
                person = type('Person', (), {
                    'id': sid,
                    'is_new': self.is_new_member(sid),
                    'department': self.db.get_student_department(sid)
                })
                eligible_persons.append(person)
            
            # 硬性过滤：应用周和日限制
            filtered_persons = []
            for person in eligible_persons:
                # 获取数据库中的本周排班次数
                db_week_shifts = self.get_current_week_shifts_from_db(person.id)
                # 获取本次排班中本周已分配次数
                current_week_count = current_week_assigned.get(person.id, 0)
                total_week_shifts = db_week_shifts + current_week_count
                
                # 检查当天是否已排班
                current_day_count = 1 if person.id in current_day_assigned else 0
                
                # 应用约束：每周最多2次，每天最多1次
                if total_week_shifts < 2 and current_day_count < 1:
                    filtered_persons.append(person)
                else:
                    if total_week_shifts >= 2:
                        print(f"排除 {person.id}：总周排班次数{total_week_shifts}次")
                    if current_day_count >= 1:
                        print(f"排除 {person.id}：今天已排班")
            
            if not filtered_persons:
                # 如果都超限，尝试只放宽天限制（但保持周限制）
                filtered_persons = []
                for person in eligible_persons:
                    db_week_shifts = self.get_current_week_shifts_from_db(person.id)
                    current_week_count = current_week_assigned.get(person.id, 0)
                    total_week_shifts = db_week_shifts + current_week_count
                    if total_week_shifts < 2:
                        filtered_persons.append(person)
                if not filtered_persons:
                    filtered_persons = eligible_persons  # 最后手段
            
            # 分离新老成员
            new_members = [p for p in filtered_persons if p.is_new]
            old_members = [p for p in filtered_persons if not p.is_new]
            
            # 初始化统计信息
            all_ids = [p.id for p in filtered_persons]
            weekly_stats_dict = self.get_weekly_stats(all_ids)
            current_schedule = []
            selected = []
            
            # 强制保证必要老成员数量
            necessary_old = self.scheduling_configuration_file.get('necessary_old_member', 0)
            old_selected = 0
            
            # 先选择必要的老成员
            if necessary_old > 0 and old_members:
                temp_schedule = []
                temp_selected = []
                temp_stats = {sid: weekly_stats_dict[sid].copy() if sid in weekly_stats_dict else {
                    'total_shifts': 0, '1_shifts': 0, '6_shifts': 0, 'current_week': 0, 'assigned': []
                } for sid in [p.id for p in old_members]}
                
                for _ in range(min(necessary_old, len(old_members), need_num)):
                    best_person = None
                    best_score = -1
                    
                    for person in old_members:
                        if person.id in [p.id for p in temp_selected]:
                            continue
                        
                        person_stats = temp_stats.get(person.id, {
                            'total_shifts': 0, '1_shifts': 0, '6_shifts': 0, 'current_week': 0, 'assigned': temp_schedule.copy()
                        })
                        
                        score = calculate_shift_score(
                            person, 
                            type('Shift', (), {'slot': time}), 
                            temp_schedule, 
                            person_stats, 
                            self.scheduling_configuration_file
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_person = person
                    
                    if best_person:
                        temp_selected.append(best_person)
                        temp_schedule.append(best_person)
                        old_selected += 1
                        # 更新统计
                        if best_person.id in temp_stats:
                            temp_stats[best_person.id]['total_shifts'] += 1
                            temp_stats[best_person.id]['current_week'] += 1
                            if time == 1:
                                temp_stats[best_person.id]['1_shifts'] += 1
                            elif time == 6:
                                temp_stats[best_person.id]['6_shifts'] += 1
                            temp_stats[best_person.id]['assigned'] = temp_schedule.copy()
                
                selected.extend(temp_selected)
                current_schedule.extend(temp_selected)
                # 更新主统计信息
                for person in temp_selected:
                    if person.id in weekly_stats_dict:
                        weekly_stats_dict[person.id]['total_shifts'] += 1
                        weekly_stats_dict[person.id]['current_week'] += 1
                        if time == 1:
                            weekly_stats_dict[person.id]['1_shifts'] += 1
                        elif time == 6:
                            weekly_stats_dict[person.id]['6_shifts'] += 1
                        weekly_stats_dict[person.id]['assigned'] = current_schedule.copy()
            
            # 选择剩余人员
            remaining_needed = need_num - len(selected)
            if remaining_needed > 0:
                all_candidates = filtered_persons
                for _ in range(remaining_needed):
                    best_person = None
                    best_score = -1
                    
                    for person in all_candidates:
                        if person.id in [p.id for p in selected]:
                            continue
                        
                        person_stats = weekly_stats_dict.get(person.id, {
                            'total_shifts': 0, '1_shifts': 0, '6_shifts': 0, 'current_week': 0, 'assigned': current_schedule.copy()
                        })
                        
                        score = calculate_shift_score(
                            person, 
                            type('Shift', (), {'slot': time}), 
                            current_schedule, 
                            person_stats, 
                            self.scheduling_configuration_file
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_person = person
                    
                    if best_person:
                        selected.append(best_person)
                        current_schedule.append(best_person)
                        # 更新统计信息
                        if best_person.id in weekly_stats_dict:
                            weekly_stats_dict[best_person.id]['total_shifts'] += 1
                            weekly_stats_dict[best_person.id]['current_week'] += 1
                            if time == 1:
                                weekly_stats_dict[best_person.id]['1_shifts'] += 1
                            elif time == 6:
                                weekly_stats_dict[best_person.id]['6_shifts'] += 1
                            weekly_stats_dict[best_person.id]['assigned'] = current_schedule.copy()
                        
                        # 更新其他人员的assigned列表
                        for sid in all_ids:
                            if sid != best_person.id and sid in weekly_stats_dict:
                                weekly_stats_dict[sid]['assigned'] = current_schedule.copy()
                    else:
                        break
            
            return [p.id for p in selected]
        except Exception as e:
            print(f"排班错误: {e}")
            import traceback
            traceback.print_exc()
            return []

    def update_duty_table(self, schedule_result):
        """将排班结果更新到值班表"""
        if self.scheduling_configuration_file.get('module') != 'formal':
            return True
            
        try:
            conn = sqlite3.connect(self.db.db_path)
            cur = conn.cursor()
            
            # 统计每个学生的排班情况
            student_shifts = {}
            for day_name, times in schedule_result.items():
                for time_slot, details in times.items():
                    workers = details.get("排班人员", [])
                    for worker_id in workers:
                        if worker_id not in student_shifts:
                            student_shifts[worker_id] = {'total': 0, 'early': 0, 'late': 0}
                        
                        student_shifts[worker_id]['total'] += 1
                        # 根据时间槽判断早班/晚班
                        if time_slot == "1-2节":  # 早班
                            student_shifts[worker_id]['early'] += 1
                        elif time_slot == "9节":  # 晚班
                            student_shifts[worker_id]['late'] += 1
            
            # 更新数据库
            for student_id, shifts in student_shifts.items():
                cur.execute('''UPDATE 值班表 SET 
                              总值班数 = 总值班数 + ?,
                              学期值早班数 = 学期值早班数 + ?,
                              学期值晚班数 = 学期值晚班数 + ?,
                              本周早班数 = 本周早班数 + ?,
                              本周晚班数 = 本周晚班数 + ?
                              WHERE 学号 = ?''',
                           (shifts['total'], shifts['early'], shifts['late'], 
                            shifts['early'], shifts['late'], student_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新值班表失败: {e}")
            return False

    def save_to_json_files(self, schedule_result):
        """保存排班结果到JSON文件"""
        try:
            # 准备元数据
            metadata = {
                "week": self.week,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 1. 生成 scheduling_list.json - 按时间段分组
            scheduling_list_data = []
            for day_name, times in schedule_result.items():
                for time_slot, details in times.items():
                    time_key = f"{day_name}{time_slot}"
                    workers = details.get("排班人员", [])
                    scheduling_list_data.append({time_key: workers})
            
            scheduling_list = {
                "_metadata": metadata,
                "data": scheduling_list_data
            }
            
            # 2. 生成 scheduling_data.json - 按人员统计
            # 先从数据库获取学期总排班数
            conn = sqlite3.connect(self.db.db_path)
            cur = conn.cursor()
            
            student_stats = {}
            daily_counts = {}  # {student_id: {day: count}}
            
            for day_name, times in schedule_result.items():
                for time_slot, details in times.items():
                    workers = details.get("排班人员", [])
                    for worker_id in workers:
                        if worker_id not in student_stats:
                            # 从数据库获取学期各时段排班数并计算总和
                            cur.execute('''SELECT "学期值早班数", "学期值午班数", "学期值下午班数", "学期值晚班数" 
                                         FROM 值班表 WHERE 学号 = ?''', (worker_id,))
                            db_counts = cur.fetchone()
                            if db_counts:
                                early, noon, afternoon, night = db_counts
                                all_times = (early or 0) + (noon or 0) + (afternoon or 0) + (night or 0)
                            else:
                                all_times = 0
                            
                            student_stats[worker_id] = {
                                "week_times": 0,
                                "morning_times": 0,
                                "night_times": 0,
                                "all_morning_times": 0,
                                "all_night_times": 0,
                                "all_times": all_times  # 学期总排班数
                            }
                        if worker_id not in daily_counts:
                            daily_counts[worker_id] = {}
                        if day_name not in daily_counts[worker_id]:
                            daily_counts[worker_id][day_name] = 0
                        
                        student_stats[worker_id]["week_times"] += 1
                        daily_counts[worker_id][day_name] += 1
                        
                        # 判断早班/晚班
                        if time_slot == "1-2节":  # 早班
                            student_stats[worker_id]["morning_times"] += 1
                            student_stats[worker_id]["all_morning_times"] += 1
                        elif time_slot == "9节":  # 晚班
                            student_stats[worker_id]["night_times"] += 1
                            student_stats[worker_id]["all_night_times"] += 1
            
            # 计算每个学生的单日最大排班次数
            for student_id in student_stats:
                max_daily = max(daily_counts[student_id].values()) if daily_counts[student_id] else 0
                student_stats[student_id]["day_times"] = max_daily
            
            conn.close()
            
            scheduling_data = {
                "_metadata": metadata,
                "data": []
            }
            
            for student_id, stats in student_stats.items():
                student_record = {"id": student_id}
                student_record.update(stats)
                scheduling_data["data"].append(student_record)
            
            # 保存到文件
            mini_program_dir = "mini_program_data"
            os.makedirs(mini_program_dir, exist_ok=True)
            
            with open(f"{mini_program_dir}/scheduling_list.json", "w", encoding="utf-8") as f:
                json.dump(scheduling_list, f, ensure_ascii=False, indent=2)
            
            with open(f"{mini_program_dir}/scheduling_data.json", "w", encoding="utf-8") as f:
                json.dump(scheduling_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 排班结果已保存到 {mini_program_dir}/")
            return True
            
        except Exception as e:
            print(f"保存JSON文件失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================================================================
    # 运筹学目标规划排班入口（新算法）
    # ==================================================================
    def active_or(self, only_days=None):
        """
        使用运筹学目标规划算法进行全局排班
        
        与 active() 相比的改进:
        - 全局视角求解，非逐班次贪心
        - 工作量方差最小化为最高优先级目标
        - 模拟退火局部搜索避免局部最优
        - 数学化的代价函数替代人工打分

        Args:
            only_days: 只排某些天，格式同 active()
        
        Returns:
            schedule_result (与 active() 格式兼容)
        """
        try:
            print("\n" + "=" * 60)
            print("🧠 启动运筹学目标规划排班模式")
            print("=" * 60)

            # 创建 OR 调度器
            or_scheduler = OperationsResearchScheduler(
                self.scheduling_configuration_file,
                self.db.db_path
            )

            # 求解
            raw_result = or_scheduler.solve()
            # raw_result 格式: {"星期一_1-2节": ["sid1", "sid2"], ...}

            if not raw_result:
                print("❌ OR 调度器未产生结果，回退到原始算法")
                return self.active(only_days)

            # 格式转换: OR结果 → active() 兼容格式
            self.schedule_result = {}
            day_filter = set(only_days) if only_days else None

            for day in self.days:
                if day_filter is not None and day not in day_filter:
                    continue

                day_name = self.week_name_map[day]
                day_res = {}
                today_times = self.get_day_times(day)

                for time_slot in today_times:
                    time_name = self.time_name_map[time_slot]
                    or_key = f"{day_name}_{time_name}"
                    workers = raw_result.get(or_key, [])

                    limit_dept = self.acquire_time_period_only_department(day, time_slot)
                    need = self.acquire_time_period_people_number(time_slot)

                    day_res[time_name] = {
                        "需要人数": need,
                        "排班人员": workers,
                        "限定部门": limit_dept or "无"
                    }

                    if len(workers) < need:
                        print(f"  ⚠️ {or_key}: 人员不足 ({len(workers)}/{need})")

                self.schedule_result[day_name] = day_res

            print("\n✅ 运筹学排班完成")

            # 正式模式下更新数据库
            if self.scheduling_configuration_file.get('module') == 'formal':
                if self.update_duty_table(self.schedule_result):
                    print("✅ 值班表已更新")
                else:
                    print("❌ 值班表更新失败")

            # 保存到JSON文件
            self.save_to_json_files(self.schedule_result)

            return self.schedule_result

        except Exception as e:
            print(f"❌ OR 排班出错: {e}, 回退到原始算法")
            import traceback
            traceback.print_exc()
            return self.active(only_days)

    # 排班总入口（原始贪心算法）
    def active(self, only_days=None):
        try:
            print("开始排班...")
            self.schedule_result = {}
            day_filter = {}

            if isinstance(only_days, list):
                for d in only_days:
                    day_filter[d] = []
            elif isinstance(only_days, dict):
                day_filter = only_days

            # 跟踪本周排班状态 {student_id: count}
            current_week_assigned = {}
            
            for day in self.days:
                if only_days is not None and day not in day_filter:
                    continue

                # 为每一天创建独立的已分配人员集合
                day_assigned = set()
                
                today_times = self.get_day_times(day)
                if day in day_filter and day_filter[day]:
                    today_times = [t for t in today_times if t in day_filter[day]]

                day_res = {}
                for time in today_times:
                    free_list = self.db.get_free_students(self.week, day, time)
                    if not free_list:
                        continue

                    need = self.acquire_time_period_people_number(time)
                    
                    # 过滤掉今天已经排班的人员和本周超限的人员
                    available_list = []
                    for sid in free_list:
                        # 检查今天是否已排班
                        if sid in day_assigned:
                            continue
                        # 检查本周是否超限（数据库 + 当前排班）
                        db_week_count = self.get_current_week_shifts_from_db(sid)
                        current_week_count = current_week_assigned.get(sid, 0)
                        total_week_count = db_week_count + current_week_count
                        if total_week_count >= 2:
                            continue
                        available_list.append(sid)
                    
                    if not available_list:
                        # 如果没有可用人员，尝试只放宽天限制（但保持周限制）
                        available_list = []
                        for sid in free_list:
                            db_week_count = self.get_current_week_shifts_from_db(sid)
                            current_week_count = current_week_assigned.get(sid, 0)
                            total_week_count = db_week_count + current_week_count
                            if total_week_count < 2:
                                available_list.append(sid)
                        if not available_list:
                            available_list = free_list
                    
                    # 创建人员对象
                    eligible_persons = []
                    for sid in available_list:
                        person = type('Person', (), {
                            'id': sid,
                            'is_new': self.is_new_member(sid),
                            'department': self.db.get_student_department(sid)
                        })
                        eligible_persons.append(person)
                    
                    # 分离新老成员
                    new_members = [p for p in eligible_persons if p.is_new]
                    old_members = [p for p in eligible_persons if not p.is_new]
                    
                    workers = []
                    selected_count = 0
                    
                    # 强制选择必要老成员
                    necessary_old = self.scheduling_configuration_file.get('necessary_old_member', 0)
                    # 特殊处理晚班：如果允许新成员值晚班，则晚班不需要强制老成员
                    if time == 6 and self.night_shift:
                        necessary_old = 0
                    
                    if necessary_old > 0 and old_members:
                        # 从老成员中选择
                        temp_selected = []
                        for _ in range(min(necessary_old, len(old_members), need)):
                            best_person = None
                            best_score = -1
                            for person in old_members:
                                if person.id in [p.id for p in temp_selected]:
                                    continue
                                # 使用简化的统计（因为我们已经过滤了超限人员）
                                stats = {'total_shifts': 0, '1_shifts': 0, '6_shifts': 0, 'current_week': 0, 'assigned': []}
                                score = calculate_shift_score(
                                    person, 
                                    type('Shift', (), {'slot': time}), 
                                    [], 
                                    stats, 
                                    self.scheduling_configuration_file
                                )
                                if score > best_score:
                                    best_score = score
                                    best_person = person
                            if best_person:
                                temp_selected.append(best_person)
                        
                        workers.extend([p.id for p in temp_selected])
                        selected_count = len(temp_selected)
                    
                    # 选择剩余人员
                    if selected_count < need:
                        remaining_candidates = [p for p in eligible_persons if p.id not in workers]
                        remaining_needed = need - selected_count
                        temp_selected = []
                        for _ in range(remaining_needed):
                            best_person = None
                            best_score = -1
                            for person in remaining_candidates:
                                if person.id in workers or person.id in [x for x in temp_selected]:
                                    continue
                                stats = {'total_shifts': 0, '1_shifts': 0, '6_shifts': 0, 'current_week': 0, 'assigned': []}
                                score = calculate_shift_score(
                                    person, 
                                    type('Shift', (), {'slot': time}), 
                                    [], 
                                    stats, 
                                    self.scheduling_configuration_file
                                )
                                if score > best_score:
                                    best_score = score
                                    best_person = person
                            if best_person:
                                temp_selected.append(best_person.id)
                                # 立即从候选列表中移除，避免重复选择
                                remaining_candidates = [p for p in remaining_candidates if p.id != best_person.id]
                            else:
                                break
                        workers.extend(temp_selected)
                    
                    limit_dept = self.acquire_time_period_only_department(day, time)
                    time_label = self.time_name_map[time]
                    day_res[time_label] = {
                        "需要人数": need,
                        "排班人员": workers,
                        "限定部门": limit_dept or "无"
                    }

                    # 更新当天和本周的分配状态
                    for worker_id in workers:
                        day_assigned.add(worker_id)
                        current_week_assigned[worker_id] = current_week_assigned.get(worker_id, 0) + 1

                week_label = self.week_name_map[day]
                self.schedule_result[week_label] = day_res

            print("排班完成")
            
            # 正式模式下更新数据库
            if self.scheduling_configuration_file.get('module') == 'formal':
                if self.update_duty_table(self.schedule_result):
                    print("✅ 值班表已更新")
                else:
                    print("❌ 值班表更新失败")
            
            # 保存到JSON文件
            self.save_to_json_files(self.schedule_result)
            
            return self.schedule_result
        except Exception as e:
            print(f"排班总入口错误: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # 获取时段需要人数
    def acquire_time_period_people_number(self, time):
        try:
            for item in self.people["schedules"]:
                ts = item["times"]
                if isinstance(ts, list):
                    if time in ts:
                        return item["number"]
                else:
                    if time == ts:
                        return item["number"]
            return 0
        except:
            return 0

    # 获取某天时段
    def get_day_times(self, day):
        try:
            for item in self.time_period:
                if day in item["days"]:
                    return item["times"]
            return []
        except:
            return []

    # 获取时段限定部门
    def acquire_time_period_only_department(self, day, time):
        try:
            for item in self.only_department:
                if item["day"] == day and time in item["time_period"]:
                    return item["department"]
            return None
        except:
            return None


def load_config(config_path="configuration_file/scheduling_configuration_file.json"):
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # 验证必需字段（符合配置文件测试规范）
    required_fields = ["week", "days", "time_period", "people"]
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise ValueError(f"配置文件缺失字段: {', '.join(missing)}")
    
    return config


if __name__ == "__main__":
    config = load_config()
    schedule = SchedulingConfigurationAllocate(config)
    result = schedule.active()
    
    # 打印详细排班结果
    print("\n" + "="*50)
    print("详细排班结果:")
    print("="*50)
    for day, times in result.items():
        if times:  # 只打印有排班数据的日期
            print(f"\n{day}:")
            for time_slot, details in times.items():
                workers = details["排班人员"]
                print(f"  {time_slot}: {workers}")
        else:
            print(f"\n{day}: 无排班数据")
