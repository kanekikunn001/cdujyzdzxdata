# 生成60个人员数据的脚本
import sqlite3
import random
import string
from datetime import datetime

def generate_random_student_data(count=60):
    """生成随机学生数据"""
    departments = ["技术部", "外联部", "宣传部", "活动部", "秘书处", "策划部"]
    jobs = ["干事", "副部长", "部长", "主席", "副主席"]
    names = [
        "张伟", "李娜", "王强", "刘敏", "陈杰", "杨洋", "赵丽", "黄勇", "周静", "吴涛",
        "徐娟", "孙磊", "胡芳", "郭峰", "何敏", "高翔", "林琳", "马超", "罗燕", "邓超",
        "曹阳", "彭丽", "曾伟", "肖敏", "田甜", "董浩", "袁莉", "潘勇", "蔡娟", "蒋飞",
        "丁磊", "范红", "余波", "钟艳", "熊伟", "白静", "龙飞", "石磊", "谭超", "贾敏",
        "夏磊", "邱艳", "邹洋", "韦敏", "邵军", "史丽", "万杰", "向辉", "温霞", "武杰",
        "龚燕", "孔祥", "段霞", "范霞", "方杰", "傅娟", "顾超", "韩雪", "郝杰", "洪洋"
    ]
    
    students = []
    for i in range(count):
        student_id = f"2024{random.randint(10000000, 99999999)}"  # 生成学号
        name = random.choice(names) if i < len(names) else f"用户{i+1}"
        department = random.choice(departments)
        job = random.choice(jobs)
        phone = f"1{random.randint(3000000000, 3999999999)}"  # 生成手机号
        
        students.append({
            "id": student_id,
            "name": name,
            "department": department,
            "job": job,
            "phone": phone
        })
    
    return students

def generate_free_time_data():
    """生成随机的空闲时间数据（模拟一周的空闲情况）"""
    # 生成42个时间段的空闲周数据，根据实际数据库表结构
    free_time_data = []
    for i in range(42):  # 根据实际表结构，应该是42个时间段
        # 模拟每周都有一定的空闲时间，随机选择几周作为空闲周
        weeks = random.sample(range(1, 21), random.randint(8, 15))  # 从20周中随机选择8-15周
        free_time_data.append(str(weeks))  # 转换为字符串格式存储
    return free_time_data

def get_actual_column_names():
    """获取空闲时间表的实际列名"""
    db_path = "database/data/JYZDZXdata.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取空闲时间表的列信息
        cursor.execute("PRAGMA table_info(空闲时间表)")
        columns_info = cursor.fetchall()
        
        conn.close()
        
        # 提取列名，排除第一个列（学号）
        column_names = [column[1] for column in columns_info[1:]]  # 排除学号列
        
        return column_names
    except Exception as e:
        print(f"❌ 获取列名失败: {e}")
        # 如果无法获取实际列名，返回预期的列名
        expected_columns = [
            "周一1-2节", "周一3-4节", "周一中午节", "周一5-6节", "周一7-8节", "周一9节",
            "周二1-2节", "周二3-4节", "周二中午节", "周二5-6节", "周二7-8节", "周二9节",
            "周三1-2节", "周三3-4节", "周三中午节", "周三5-6节", "周三7-8节", "周三9节",
            "周四1-2节", "周四3-4节", "周四中午节", "周四5-6节", "周四7-8节", "周四9节",
            "周五1-2节", "周五3-4节", "周五中午节", "周五5-6节", "周五7-8节", "周五9节",
            "周六1-2节", "周六3-4节", "周六中午节", "周六5-6节", "周六7-8节", "周六9节",
            "周日1-2节", "周日3-4节", "周日中午节", "周日5-6节", "周日7-8节", "周日9节"
        ]
        return expected_columns

def insert_students_to_database(students_data):
    """将学生数据插入到数据库中"""
    db_path = "database/data/JYZDZXdata.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取实际的列名
        actual_columns = get_actual_column_names()
        print(f"空闲时间表实际包含 {len(actual_columns)} 个时间段列")
        
        # 插入基础信息表数据
        basic_info_sql = '''
        INSERT OR REPLACE INTO 基础信息表 (学号, name, job, department, phone)
        VALUES (?, ?, ?, ?, ?)
        '''
        
        # 构建空闲时间表的SQL语句
        free_time_placeholders = ", ".join(["?"] * len(actual_columns))
        free_time_sql = f'''
        INSERT OR REPLACE INTO 空闲时间表 (学号, {", ".join([f'"{col}"' for col in actual_columns])})
        VALUES (?, {free_time_placeholders})
        '''
        
        success_count = 0
        
        for student in students_data:
            # 生成该学生的空闲时间数据
            free_time_data = generate_free_time_data()
            # 如果实际列数与生成的数据不匹配，则调整数据
            if len(free_time_data) > len(actual_columns):
                free_time_data = free_time_data[:len(actual_columns)]
            elif len(free_time_data) < len(actual_columns):
                # 补充数据直到匹配
                while len(free_time_data) < len(actual_columns):
                    weeks = random.sample(range(1, 21), random.randint(8, 15))
                    free_time_data.append(str(weeks))
            
            # 插入基础信息
            basic_info_values = (
                student["id"],
                student["name"],
                student["job"],
                student["department"],
                student["phone"]
            )
            
            cursor.execute(basic_info_sql, basic_info_values)
            
            # 插入空闲时间
            free_time_values = [student["id"]] + free_time_data
            cursor.execute(free_time_sql, free_time_values)
            
            # 同时插入签到表和值班表记录
            # 签到表
            signin_sql = '''
            INSERT OR REPLACE INTO 签到表 (学号, right_signin_time, Current_signin_time, right_signout_time, Current_signout_time)
            VALUES (?, NULL, NULL, NULL, NULL)
            '''
            cursor.execute(signin_sql, (student["id"],))
            
            # 值班表
            duty_sql = '''
            INSERT OR REPLACE INTO 值班表 (学号, 学期值早班数, 学期值午班数, 学期值下午班数, 学期值晚班数,
                                          本周早班数, 本周午班数, 本周下午班数, 本周晚班数)
            VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0)
            '''
            cursor.execute(duty_sql, (student["id"],))
            
            success_count += 1
            print(f"已插入第 {success_count} 个学生: {student['name']} (学号: {student['id']})")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ 成功插入 {success_count} 个学生数据到数据库!")
        print(f"   - 基础信息表: {success_count} 条记录")
        print(f"   - 空闲时间表: {success_count} 条记录")
        print(f"   - 签到表: {success_count} 条记录")
        print(f"   - 值班表: {success_count} 条记录")
        
        return True
        
    except Exception as e:
        print(f"❌ 插入数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_data_insertion():
    """验证数据插入情况"""
    db_path = "database/data/JYZDZXdata.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查基础信息表记录数
        cursor.execute("SELECT COUNT(*) FROM 基础信息表")
        basic_count = cursor.fetchone()[0]
        
        # 检查空闲时间表记录数
        cursor.execute("SELECT COUNT(*) FROM 空闲时间表")
        free_time_count = cursor.fetchone()[0]
        
        # 检查签到表记录数
        cursor.execute("SELECT COUNT(*) FROM 签到表")
        sign_in_count = cursor.fetchone()[0]
        
        # 检查值班表记录数
        cursor.execute("SELECT COUNT(*) FROM 值班表")
        duty_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n📊 数据库验证结果:")
        print(f"   - 基础信息表: {basic_count} 条记录")
        print(f"   - 空闲时间表: {free_time_count} 条记录")
        print(f"   - 签到表: {sign_in_count} 条记录")
        print(f"   - 值班表: {duty_count} 条记录")
        
        return basic_count, free_time_count, sign_in_count, duty_count
        
    except Exception as e:
        print(f"❌ 验证数据失败: {e}")
        return 0, 0, 0, 0

def main():
    """主函数"""
    print("生成60个人员数据并插入数据库")
    print("=" * 60)
    
    # 生成学生数据
    print("正在生成学生数据...")
    students = generate_random_student_data(60)
    print(f"✅ 已生成 {len(students)} 个学生的基本信息\n")
    
    # 显示前几个学生的数据样例
    print("数据样例如下:")
    for i, student in enumerate(students[:3]):
        print(f"  学号: {student['id']}, 姓名: {student['name']}, 部门: {student['department']}, "
              f"职务: {student['job']}, 电话: {student['phone']}")
    print("  ...\n")
    
    # 插入数据库
    print("正在插入数据库...")
    success = insert_students_to_database(students)
    
    if success:
        # 验证数据
        print("\n正在验证数据...")
        basic_count, free_time_count, sign_in_count, duty_count = verify_data_insertion()
        
        print(f"\n🎉 数据生成和插入完成!")
        if basic_count >= 60 and free_time_count >= 60:
            print("✅ 所有数据均已成功插入数据库")
        else:
            print("⚠️ 数据插入可能未完全成功，请检查数据库")
    else:
        print("❌ 数据插入失败")

if __name__ == "__main__":
    main()