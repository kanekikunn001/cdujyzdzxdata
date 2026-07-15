import os
import re
import shutil
import datetime
from pathlib import Path

import pandas as pd
import sqlite3


# ===================== 对空闲时间表的增添于,关于学号的抽取并删除,查询 =====================
class CourseSchedule:
    def __init__(self, db_name="database/data/JYZDZXdata.db"):
        self.db_name = db_name
        self.create_table()

    # ===================== 连接数据库 =====================
    def get_conn(self):
        return sqlite3.connect(self.db_name)

    # ===================== 自动创建表 =====================
    def create_table(self):
        """创建空闲时间表，成功返回True，失败返回False"""
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            columns = ["学号 INT PRIMARY KEY"]
            columns += [f"period_{i} TEXT" for i in range(1, 31)]
            sql = f'''CREATE TABLE IF NOT EXISTS 空闲时间表 ({", ".join(columns)})'''
            cursor.execute(sql)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"创建表失败：{str(e)}")
            return False

    def create_feedback_table(self):
        """创建反馈统计表"""
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS 反馈统计表 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                学号 TEXT NOT NULL,
                反馈备注 TEXT,
                处理结果 TEXT,
                审核人员 TEXT,
                上传时间 TEXT,
                反馈文件名 TEXT,
                创建时间 DATETIME DEFAULT CURRENT_TIMESTAMP
            )'''
            cursor.execute(sql)
            conn.commit()
            conn.close()
            print("✅ 反馈统计表已创建")
            return True
        except Exception as e:
            print(f"创建反馈统计表失败：{str(e)}")
            return False

    # ===================== 课表解析核心：提取课程周数 → 计算空闲周 =====================
    def extract_free_time(self, df):
        """
        从 Excel 课表中提取课程信息，解析出每个时间段的空闲周
        :param df: pandas 读取的课表 DataFrame
        :return: 所有时间段的空闲周列表，失败返回 None
        """
        try:
            value = []
            all_data = []

            # 遍历课表有效列（周一到周日）
            for l in range(4, 11):
                i = 1
                # 遍历课表有效行（课程时间段）
                for h in range(4, 14):
                    # 提取单元格内【】中的课程信息
                    def get_value(val):
                        val = str(val)
                        pattern = re.escape('【') + r'(.*?)' + re.escape('】')
                        matches = re.findall(pattern, val)
                        return ','.join(matches)

                    # 偶数行读取课程
                    if h % 2 == 0:
                        v = df.iloc[h, l]
                        value.append(get_value(v))
                    # 奇数行组合课程并计算空闲周
                    else:
                        v = df.iloc[h, l]
                        value.append(get_value(v))

                        # 解析课程周数，计算空闲周
                        def organize(val, max_weeks=20):
                            parts = [p.replace('周', '').strip() for p in re.split(r'[,，]', str(val)) if p.strip()]
                            class_weeks = set()

                            # 解析单双周、连续周、单独周
                            for part in parts:
                                nums = re.findall(r'\d+', part)
                                if not nums:
                                    continue
                                # 单/双周
                                if '(' in part or '（' in part:
                                    start, end = map(int, nums[:2])
                                    if '单' in part:
                                        weeks = [w for w in range(start, end + 1) if w % 2 == 1]
                                    else:
                                        weeks = [w for w in range(start, end + 1) if w % 2 == 0]
                                # 连续周
                                elif '-' in part:
                                    start, end = map(int, nums[:2])
                                    weeks = list(range(start, end + 1))
                                # 单独周
                                else:
                                    weeks = [int(nums[0])]
                                class_weeks.update(weeks)

                            # 总周数 - 有课周 = 空闲周
                            all_weeks = set(range(1, max_weeks + 1))
                            return sorted(all_weeks - class_weeks)

                        # 组合并处理
                        combined = ','.join(value)
                        value = organize(combined)
                        all_data.append(tuple(value))

                        i += 1
                        # 每3个时间段补一组全周空闲
                        if i == 3:
                            all_weeks = set(range(1, 21))
                            all_data.append(tuple(all_weeks))
                        value = []

            return all_data
        except Exception as e:
            print(f"解析空闲时间失败：{str(e)}")
            return None

    # ===================== 把解析好的空闲时间保存到数据库 =====================
    def save_to_db(self, stu_id, data_str):
        """
        将学生空闲时间存入 空闲时间表
        :param stu_id: 学号
        :param data_str: 42个时间段的空闲周数据
        :return: 成功 True / 失败 False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            # 先删除旧数据
            cursor.execute("DELETE FROM 空闲时间表 WHERE 学号 = ?", (stu_id,))

            # 插入语句（全部加双引号）
            sql = """
                  INSERT INTO 空闲时间表 (学号,
                                          "周一1-2节", "周一3-4节", "周一中午节", "周一5-6节", "周一7-8节", "周一9节",
                                          "周二1-2节", "周二3-4节", "周二中午节", "周二5-6节", "周二7-8节", "周二9节",
                                          "周三1-2节", "周三3-4节", "周三中午节", "周三5-6节", "周三7-8节", "周三9节",
                                          "周四1-2节", "周四3-4节", "周四中午节", "周四5-6节", "周四7-8节", "周四9节",
                                          "周五1-2节", "周五3-4节", "周五中午节", "周五5-6节", "周五7-8节", "周五9节",
                                          "周六1-2节", "周六3-4节", "周六中午节", "周六5-6节", "周六7-8节", "周六9节",
                                          "周日1-2节", "周日3-4节", "周日中午节", "周日5-6节", "周日7-8节", "周日9节")
                  VALUES (?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?) \
                  """
            cursor.execute(sql, [stu_id] + data_str)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存空闲时间失败：{str(e)}")
            return False
    # ===================== 处理单个课表Excel文件 =====================
    def process_and_save(self, file_path, stu_data):
        """
        读取单个课表 → 提取学号 → 解析空闲时间 → 保存到四张表
        :param file_path: Excel 文件路径
        :param stu_data: 学生基础信息（姓名、部门、职务、电话）
        :return: 成功 True / 失败 False
        """
        try:
            print(f"\n▶ 处理：{file_path}")
            df = pd.read_excel(file_path, header=None)

            # 从课表中提取学号
            stu_id = None
            for r in range(df.shape[0]):
                for c in range(df.shape[1]):
                    cell = str(df.iloc[r, c])
                    m = re.search(r"学号[:：\s]*(\d+)", cell)
                    if m:
                        stu_id = m.group(1)
                        break
                if stu_id:
                    break

            # 未找到学号直接失败
            if not stu_id:
                print("❌ 未提取到学号，处理失败")
                return False

            # 解析空闲时间
            all_data = self.extract_free_time(df)
            if all_data is None:
                return False

            data_str = [str(list(item)) for item in all_data]

            # 保存空闲时间
            save_ok = self.save_to_db(stu_id, data_str)
            if not save_ok:
                return False

            # 同步插入其他三张表
            stu_data["id"] = stu_id
            self.update_alldata("基础信息表", stu_data)
            self.update_alldata("签到表", stu_id)
            self.update_alldata("值班表", stu_id)

            print(f"✅ 学号 {stu_id} 已保存到 JYZDZXdata.db")
            return True

        except Exception as e:
            print(f"处理文件失败：{str(e)}")
            return False

    # ===================== 批量处理文件夹下所有课表 =====================
    def process_all(self, folder_path):
        pass

    # ===================== 数据库备份功能 =====================
    def backup_database(self, max_backups=2):
        """
        备份数据库到backup/database目录，保留指定数量的备份版本
        :param max_backups: 最大备份数量，默认保留2个版本
        :return: 备份成功返回备份文件路径，失败返回None
        """
        try:
            # 创建备份目录
            backup_dir = Path("backup/database")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成带时间戳的备份文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"JYZDZXdata_backup_{timestamp}.db"
            
            # 备份数据库文件
            shutil.copy2(self.db_name, backup_file)
            print(f"✅ 数据库备份成功：{backup_file}")
            
            # 清理旧备份，保留最新的max_backups个文件
            self._clean_old_backups(backup_dir, max_backups)
            
            return str(backup_file)
            
        except Exception as e:
            print(f"❌ 数据库备份失败：{str(e)}")
            return None

    def _clean_old_backups(self, backup_dir, max_backups):
        """
        清理旧的备份文件，保留最新的max_backups个
        """
        try:
            # 获取所有备份文件并按修改时间排序
            backup_files = list(backup_dir.glob("JYZDZXdata_backup_*.db"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 删除超出数量的旧备份
            if len(backup_files) > max_backups:
                for old_file in backup_files[max_backups:]:
                    old_file.unlink()
                    print(f"🗑️ 删除旧备份：{old_file}")
        except Exception as e:
            print(f"清理旧备份失败：{str(e)}")

    # ===================== 数据库恢复功能 =====================
    def restore_database(self, backup_file=None):
        """
        从备份文件恢复数据库
        :param backup_file: 指定备份文件路径，如果为None则使用最新的备份
        :return: 恢复成功返回True，失败返回False
        """
        try:
            backup_dir = Path("backup/database")
            
            # 如果没有指定备份文件，使用最新的备份
            if backup_file is None:
                backup_files = list(backup_dir.glob("JYZDZXdata_backup_*.db"))
                if not backup_files:
                    print("❌ 没有找到备份文件")
                    return False
                
                # 按修改时间排序，获取最新的备份
                backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                backup_file = backup_files[0]
            else:
                backup_file = Path(backup_file)
                if not backup_file.exists():
                    print(f"❌ 备份文件不存在：{backup_file}")
                    return False
            
            # 备份当前数据库（防止恢复失败）
            current_backup = self.backup_database()
            if current_backup is None:
                print("⚠️ 当前数据库备份失败，但继续恢复操作")
            
            # 恢复数据库
            shutil.copy2(backup_file, self.db_name)
            print(f"✅ 数据库恢复成功：{backup_file}")
            
            # 验证恢复是否成功
            if self._verify_database():
                print("✅ 数据库验证通过")
                return True
            else:
                print("❌ 数据库验证失败，尝试回滚")
                # 回滚到之前的备份
                if current_backup:
                    shutil.copy2(current_backup, self.db_name)
                    print("✅ 已回滚到恢复前的状态")
                return False
                
        except Exception as e:
            print(f"❌ 数据库恢复失败：{str(e)}")
            return False

    def _verify_database(self):
        """
        验证数据库是否正常可用
        :return: 验证通过返回True，失败返回False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            
            # 检查主要表是否存在
            tables_to_check = ["空闲时间表", "基础信息表", "签到表", "值班表"]
            for table in tables_to_check:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    print(f"❌ 表 {table} 不存在")
                    conn.close()
                    return False
            
            # 检查表结构是否正常
            cursor.execute("PRAGMA table_info(空闲时间表)")
            columns = [row[1] for row in cursor.fetchall()]
            if "学号" not in columns:
                print("❌ 空闲时间表结构异常")
                conn.close()
                return False
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 数据库验证失败：{str(e)}")
            return False

    def list_backups(self):
        """
        列出所有可用的备份文件
        :return: 备份文件列表，按时间倒序排列
        """
        try:
            backup_dir = Path("backup/database")
            backup_files = list(backup_dir.glob("JYZDZXdata_backup_*.db"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            print("📋 可用备份文件：")
            for i, backup_file in enumerate(backup_files, 1):
                mtime = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime)
                size = backup_file.stat().st_size / 1024  # KB
                print(f"  {i}. {backup_file.name} ({mtime.strftime('%Y-%m-%d %H:%M:%S')}, {size:.1f}KB)")
            
            return backup_files
            
        except Exception as e:
            print(f"❌ 列出备份文件失败：{str(e)}")
            return []
    # ===================== 根据学号删除学生所有信息 =====================
    def delete_by_id(self, stu_id):
        """
        从 空闲时间、基础信息、签到、值班 四张表删除该学生
        :param stu_id: 学号
        :return: 成功 True / 失败 False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM 空闲时间表 WHERE 学号 = ?", (stu_id,))
            cursor.execute("DELETE FROM 签到表 WHERE 学号 = ?", (stu_id,))
            cursor.execute("DELETE FROM 值班表 WHERE 学号 = ?", (stu_id,))
            cursor.execute("DELETE FROM 基础信息表 WHERE 学号 = ?", (stu_id,))

            conn.commit()
            conn.close()
            print(f"🗑️ 已删除学号：{stu_id}（4张表全部清除）")
            return True

        except Exception as e:
            print(f"删除失败：{str(e)}")
            return False

    # ===================== 查询任意表的所有数据并打印 =====================
    def checktable(self, table_name,stu):
        """
        查询指定表的全部数据
        :param table_name: 表名
        :return: 数据列表 / 空列表
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            tabledata = cursor.fetchall()
            for row in tabledata:
                print(row)
            conn.close()
            return tabledata
        except Exception as e:
            print(f"查询表失败：{str(e)}")
            return []

    # ===================== 统一插入/更新：基础信息/签到/值班/考勤表 =====================
    def update_alldata(self, table_name, data):
        """
        根据表名自动插入或替换学生数据
        :param table_name: 表名
        :param data: 学号 或 学生信息字典
        :return: 成功 True / 失败 False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()

            # 基础信息表
            if table_name == "基础信息表":
                keys = ["id", "name", "job", "department", "phone"]
                data_list = []
                for key in keys:
                    val = str(data.get(key, ""))
                    data_list.append(val)
                cursor.execute('''INSERT OR REPLACE INTO 基础信息表
                                (学号,name,job,department,phone) 
                                VALUES (?, ?, ?, ?, ?)''', data_list)

            # 签到表
            elif table_name == "签到表":
                cursor.execute('''INSERT OR REPLACE INTO 签到表
                                (学号,right_signin_time,Current_signin_time,right_signout_time,Current_signout_time) 
                                VALUES (?,null,null,null,null)''', (data,))

            # 值班表
            elif table_name == "值班表":
                cursor.execute('''INSERT OR REPLACE INTO 值班表
                                (学号,总值班数,学期值早班数,学期值午班数,学期值下午班数,学期值晚班数,
                                本周早班数,本周午班数,本周下午班数,本周晚班数) 
                                VALUES (?,0,0,0,0,0,0,0,0,0)''', (data,))

            # 月度考勤表
            elif "考勤表" in table_name:
                cursor.execute(f'''INSERT OR REPLACE INTO "{table_name}"
                                (学号,值早班数,值午班数,值下午班数,值晚班数,本月请假数,本月缺勤数) 
                                VALUES (?,0,0,0,0,0,0)''', (data,))
            else:
                conn.close()
                return False

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"更新{table_name}失败：{e}")
            return False

    # ===================== 考勤表自动补充学生：从基础信息表同步 =====================
    def addmessage(self, table_name):
        """
        将基础信息表中有，但考勤表中没有的学生自动添加进去
        :param table_name: 考勤表名
        :return: 成功 True / 失败 False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()

            # 获取所有学生学号
            cursor.execute("SELECT 学号 FROM 基础信息表")
            id_list_1 = [item[0] for item in cursor.fetchall()]

            # 获取考勤表已有学号
            cursor.execute(f'SELECT 学号 FROM "{table_name}"')
            id_list_2 = [item[0] for item in cursor.fetchall()]

            # 找出差集，补充缺失学生
            new_id_list = [stu_id for stu_id in id_list_1 if stu_id not in id_list_2]
            for stu_id in new_id_list:
                self.update_alldata(table_name, stu_id)

            conn.close()
            return True
        except Exception as e:
            print(f"addmessage 执行失败：{e}")
            return False

    # ===================== 修改任意表的指定学生字段 =====================
    def edittable(self, table_name, data):
        """
        通用修改方法：根据学号更新任意字段
        :param table_name: 表名
        :param data: {id:学号, data:{字段名:值}}
        :return: 成功 True / 失败 False
        """
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            stu_id = data.get("id")
            stu_data = dict(data["data"])

            # 循环更新多个字段
            for key in stu_data:
                cursor.execute(f"""
                    UPDATE {table_name}
                    SET {key} = ?
                    WHERE 学号 = ?
                """, (stu_data[key], stu_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"edittable 执行失败：{e}")
            return False

    ##########################读取###########
    def recitetable(self, table_name, data):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            pattern = data["pattern"]
            query_list = data["data"]  # 列名 或 列序号列表
            result_dict = {}

            # 第一步：获取表的所有列名 + 列数
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 1")
            columns = [desc[0] for desc in cursor.description]

            # ----------------------
            # 精准查询：按 列名 查询
            # ----------------------
            if pattern == "precise":
                # 拼接要查询的列（学号 + 指定列）
                select_columns = ["学号"] + query_list
                select_str = ", ".join([f"`{col}`" for col in select_columns])

                sql = f"SELECT {select_str} FROM `{table_name}`"
                cursor.execute(sql)
                rows = cursor.fetchall()

                # 组装成 {学号: {列名: 值}}
                for row in rows:
                    stu_id = str(row[0])
                    result_dict[stu_id] = dict(zip(query_list, row[1:]))

            # ----------------------
            # 序号查询：按 第几列 查询
            # ----------------------
            elif pattern == "order_number":
                # 根据序号拿到真实列名（序号从 1 开始算）
                selected_column_names = [columns[i] for i in query_list]
                select_str = ", ".join([f"`{columns[i]}`" for i in query_list])

                sql = f"SELECT `学号`, {select_str} FROM `{table_name}`"
                cursor.execute(sql)
                rows = cursor.fetchall()

                # 组装成 {学号: {列名: 值}}
                for row in rows:
                    stu_id = str(row[0])
                    result_dict[stu_id] = dict(zip(selected_column_names, row[1:]))

            conn.close()
            return result_dict

        except Exception as e:
            print(f"❌ 查询失败：{e}")
            return {}