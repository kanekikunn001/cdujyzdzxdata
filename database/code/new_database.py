import sqlite3

class creattable:
    def __init__(self):
        self.db_name = "database/data/JYZDZXdata.db"

    def get_conn(self):
        return sqlite3.connect(self.db_name)

    def createtimetable(self):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS 空闲时间表")

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS 空闲时间表
                           (
                               学号 INT PRIMARY KEY,
                               "周一1-2节" TEXT,
                               "周一3-4节" TEXT,
                               "周一中午节" TEXT,
                               "周一5-6节" TEXT,
                               "周一7-8节" TEXT,
                               "周一9节" TEXT,
                               "周二1-2节" TEXT,
                               "周二3-4节" TEXT,
                               "周二中午节" TEXT,
                               "周二5-6节" TEXT,
                               "周二7-8节" TEXT,
                               "周二9节" TEXT,
                               "周三1-2节" TEXT,
                               "周三3-4节" TEXT,
                               "周三中午节" TEXT,
                               "周三5-6节" TEXT,
                               "周三7-8节" TEXT,
                               "周三9节" TEXT,
                               "周四1-2节" TEXT,
                               "周四3-4节" TEXT,
                               "周四中午节" TEXT,
                               "周四5-6节" TEXT,
                               "周四7-8节" TEXT,
                               "周四9节" TEXT,
                               "周五1-2节" TEXT,
                               "周五3-4节" TEXT,
                               "周五中午节" TEXT,
                               "周五5-6节" TEXT,
                               "周五7-8节" TEXT,
                               "周五9节" TEXT,
                               "周六1-2节" TEXT,
                               "周六3-4节" TEXT,
                               "周六中午节" TEXT,
                               "周六5-6节" TEXT,
                               "周六7-8节" TEXT,
                               "周六9节" TEXT,
                               "周日1-2节" TEXT,
                               "周日3-4节" TEXT,
                               "周日中午节" TEXT,
                               "周日5-6节" TEXT,
                               "周日7-8节" TEXT,
                               "周日9节" TEXT
                           )
                           ''')

            conn.commit()
            conn.close()
            print("✅ 空闲时间表创建成功！")
            return True
        except Exception as e:
            print(f"❌ 创建空闲时间表失败：{e}")
            return False

    def createmessagetable(self):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS 基础信息表(
                学号 INT PRIMARY KEY,
                name TEXT,
                job TEXT,
                department TEXT,
                phone INT)
                ''')
            conn.commit()
            conn.close()
            print("✅ 表 基础信息表 已创建成功！")
            return True
        except Exception as e:
            print(f"❌ 创建基础信息表失败：{e}")
            return False

    def createsightable(self):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS 签到表(
                学号 INT PRIMARY KEY,
                right_signin_time TEXT,
                Current_signin_time TEXT,
                right_signout_time TEXT,
                Current_signout_time TEXT)
            ''')
            conn.commit()
            conn.close()
            print("✅ 表 签到表已创建成功！")
            return True
        except Exception as e:
            print(f"❌ 创建签到表失败：{e}")
            return False

    def createdutytable(self):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS 值班表(
                学号 INT PRIMARY KEY,
                总值班数 INT,
                学期值早班数 INT,
                学期值午班数 INT,
                学期值下午班数 INT,
                学期值晚班数 INT,
                本周早班数 INT,
                本周午班数 INT,
                本周下午班数 INT,
                本周晚班数 INT)
                ''')
            conn.commit()
            conn.close()
            print("✅ 表 值班表已创建成功！")
            return True
        except Exception as e:
            print(f"❌ 创建值班表失败：{e}")
            return False

    def createset(self, year, month):
        try:
            table_name = f'"{year}{month}月考勤表"'
            conn = self.get_conn()
            cursor = conn.cursor()
            create_sql = f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                学号 INT PRIMARY KEY,
                值早班数 INT,
                值午班数 INT,
                值下午班数 INT,
                值晚班数 INT,
                本月请假数 INT,
                本月缺勤数 INT)
                '''
            cursor.execute(create_sql)
            conn.commit()
            conn.close()
            print("✅ 已完成", table_name, "表")
            return True
        except Exception as e:
            print(f"❌ 创建{table_name}失败：{e}")
            return False


def get_table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [col[1] for col in cursor.fetchall()]

def insert_schedule(cursor, data, table_name="duty_table"):
    columns = get_table_columns(cursor, table_name)
    placeholders = ', '.join(['?'] * len(columns))
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    cursor.execute(sql, [data.get(col) for col in columns])
