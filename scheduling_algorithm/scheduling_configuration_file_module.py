
# 这个是调度配置文件模块
# 导入Python内置的json模块,用于读取和写入JSON格式的配置文件
import json
import copy
from typing import Any, Dict, List, Optional, Union


# 配置文件管理类
# 作用:专门负责读取、修改、保存、验证排班系统的JSON配置文件
class SchedulingConfigurationFileModule:
    # 必需字段及其类型定义
    REQUIRED_FIELDS = {
        'week': (int, type(None)),
        'days_order': list,
        'days': list,
        'time_period': list,
        'people': dict,
        'same_department': bool,
        'night_shift': bool,
    }
    
    # 可选字段及其默认值
    OPTIONAL_FIELDS = {
        'only_department': [],
        'together': [],
        'separation': [],
    }

    # 构造函数:创建对象时自动执行
    def __init__(self, file_path: str = "configuration_file/scheduling_configuration_file.json"):
        """
        初始化配置管理器
        
        Args:
            file_path: 配置文件路径,支持相对路径和绝对路径
        """
        # 定义配置文件的存放路径
        self.file_path = file_path
        
        # 保存原始配置的副本,用于重置
        self.original_data = None
        
        # 调用外部函数,读取JSON文件内容,保存到file_data变量中
        self.file_data = read_json_file(self.file_path)

        # 如果读取文件失败(返回None),抛出异常
        if self.file_data is None:
            raise FileNotFoundError(f"Error: Failed to read configuration file: {self.file_path}")
        
        # 保存原始数据副本
        self.original_data = copy.deepcopy(self.file_data)
        
        # 验证配置文件结构
        validation_result = self.validate_configuration()
        if not validation_result['valid']:
            print(f"Warning: Configuration validation failed:")
            for error in validation_result['errors']:
                print(f"  - {error}")

    def validate_configuration(self) -> Dict[str, Any]:
        """
        验证配置文件的完整性和正确性
        
        Returns:
            包含验证结果的字典: {'valid': bool, 'errors': list}
        """
        errors = []
        
        # 检查必需字段是否存在
        for field, expected_type in self.REQUIRED_FIELDS.items():
            if field not in self.file_data:
                errors.append(f"Missing required field: '{field}'")
            elif not isinstance(self.file_data[field], expected_type):
                errors.append(f"Field '{field}' has invalid type. Expected {expected_type}, got {type(self.file_data[field])}")
        
        # 验证 days_order 和 days 的值范围(1-7)
        if 'days_order' in self.file_data:
            for day in self.file_data['days_order']:
                if not (1 <= day <= 7):
                    errors.append(f"days_order contains invalid day value: {day} (must be 1-7)")
        
        if 'days' in self.file_data:
            for day in self.file_data['days']:
                if isinstance(day, int) and not (-7 <= day <= 7):
                    errors.append(f"days contains invalid day value: {day} (must be -7 to 7)")
        
        # 验证 people 配置
        if 'people' in self.file_data:
            people_config = self.file_data['people']
            if 'type' not in people_config:
                errors.append("Missing 'type' field in 'people' configuration")
            elif people_config['type'] not in ['for_day', 'for_time_period']:
                errors.append(f"Invalid people type: {people_config['type']} (must be 'for_day' or 'for_time_period')")
            
            if 'schedules' not in people_config:
                errors.append("Missing 'schedules' field in 'people' configuration")
            elif not isinstance(people_config['schedules'], list):
                errors.append("'schedules' must be a list")
            else:
                for i, schedule in enumerate(people_config['schedules']):
                    if 'times' not in schedule:
                        errors.append(f"Schedule {i} missing 'times' field")
                    if 'number' not in schedule:
                        errors.append(f"Schedule {i} missing 'number' field")
                    elif not isinstance(schedule['number'], int) or schedule['number'] <= 0:
                        errors.append(f"Schedule {i} has invalid 'number': {schedule['number']}")
        
        # 验证 time_period 配置
        if 'time_period' in self.file_data:
            if not isinstance(self.file_data['time_period'], list):
                errors.append("'time_period' must be a list")
            else:
                for i, period in enumerate(self.file_data['time_period']):
                    if 'days' not in period:
                        errors.append(f"time_period[{i}] missing 'days' field")
                    if 'times' not in period:
                        errors.append(f"time_period[{i}] missing 'times' field")
        
        # 验证 only_department 配置
        if 'only_department' in self.file_data:
            if not isinstance(self.file_data['only_department'], list):
                errors.append("'only_department' must be a list")
            else:
                for i, dept in enumerate(self.file_data['only_department']):
                    if not isinstance(dept, dict):
                        errors.append(f"only_department[{i}] must be a dictionary")
                    else:
                        if 'department' not in dept:
                            errors.append(f"only_department[{i}] missing 'department' field")
                        if 'day' not in dept:
                            errors.append(f"only_department[{i}] missing 'day' field")
                        if 'time_period' not in dept:
                            errors.append(f"only_department[{i}] missing 'time_period' field")
        
        # 验证 together 和 separation 配置
        for field in ['together', 'separation']:
            if field in self.file_data:
                if not isinstance(self.file_data[field], list):
                    errors.append(f"'{field}' must be a list")
                else:
                    for i, group in enumerate(self.file_data[field]):
                        if not isinstance(group, list):
                            errors.append(f"{field}[{i}] must be a list")
                        elif len(group) < 2:
                            errors.append(f"{field}[{i}] must contain at least 2 people")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def get_configuration(self, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置项的值
        
        Args:
            key: 配置键名,如果为None则返回整个配置
            default: 当键不存在时的默认值
            
        Returns:
            配置项的值或整个配置字典
        """
        if key is None:
            return copy.deepcopy(self.file_data)
        return self.file_data.get(key, default)

    def set_configuration(self, key: str, value: Any) -> bool:
        """
        设置配置项的值(仅内存,不保存到文件)
        
        Args:
            key: 配置键名
            value: 配置值
            
        Returns:
            是否设置成功
        """
        try:
            self.file_data[key] = value
            return True
        except Exception as e:
            print(f"Error setting configuration '{key}': {e}")
            return False

    def modify_temporary_configuration(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        临时修改配置(只改内存,不写入文件,重启程序就失效)
        
        Args:
            new_data: 要修改的配置数据字典
            
        Returns:
            修改后的配置字典
            
        Raises:
            ValueError: 当新数据为空时
        """
        # 如果传入的新数据为空,抛出异常
        if new_data is None:
            raise ValueError("Error: New data is None.")

        # 遍历要修改的新数据
        for key, value in new_data.items():
            # 如果配置里已有这个键,就更新它的值
            if key in self.file_data:
                self.file_data[key] = value
            else:
                # 如果键不存在,打印警告,并新增这个键值对
                print(f"Warning: Key '{key}' not found in existing data. Adding new key.")
                self.file_data[key] = value

        # 返回修改后的配置(仅内存中)
        return copy.deepcopy(self.file_data)

    def modify_local_configuration(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        永久修改配置(改内存 + 写入文件,永久保存)
        
        Args:
            new_data: 要修改的配置数据字典
            
        Returns:
            修改后的配置字典
            
        Raises:
            ValueError: 当新数据为空时
            IOError: 当写入文件失败时
        """
        # 如果传入的新数据为空,抛出异常
        if new_data is None:
            raise ValueError("Error: New data is None.")

        # 遍历要修改的新数据(逻辑同上)
        for key, value in new_data.items():
            if key in self.file_data:
                self.file_data[key] = value
            else:
                print(f"Warning: Key '{key}' not found in existing data. Adding new key.")
                self.file_data[key] = value

        # 关键:将修改后的配置写入文件,保存到硬盘
        if not write_json_file(self.file_path, self.file_data):
            raise IOError(f"Error: Failed to write to file: {self.file_path}")

        # 更新原始数据副本
        self.original_data = copy.deepcopy(self.file_data)
        
        # 返回最终配置
        return copy.deepcopy(self.file_data)

    def reset_to_original(self) -> Dict[str, Any]:
        """
        重置配置到初始状态(从文件重新加载)
        
        Returns:
            重置后的配置字典
        """
        self.file_data = read_json_file(self.file_path)
        if self.file_data is None:
            raise FileNotFoundError(f"Error: Failed to read configuration file during reset: {self.file_path}")
        self.original_data = copy.deepcopy(self.file_data)
        return copy.deepcopy(self.file_data)

    def reset_to_defaults(self) -> Dict[str, Any]:
        """
        重置配置到默认值(使用内存中的原始副本)
        
        Returns:
            重置后的配置字典
        """
        if self.original_data is None:
            raise RuntimeError("Error: Original data not available.")
        self.file_data = copy.deepcopy(self.original_data)
        return copy.deepcopy(self.file_data)

    def add_time_period(self, days: Union[int, List[int]], times: Union[int, List[int]]) -> bool:
        """
        添加时间段配置
        
        Args:
            days: 适用的日期(1-7或带负数表示上周)
            times: 适用的时间段
            
        Returns:
            是否添加成功
        """
        if 'time_period' not in self.file_data:
            self.file_data['time_period'] = []
        
        new_period = {
            'days': days if isinstance(days, list) else [days],
            'times': times if isinstance(times, list) else [times]
        }
        
        self.file_data['time_period'].append(new_period)
        return True

    def add_schedule(self, times: Union[int, List[int]], number: int) -> bool:
        """
        添加排班计划
        
        Args:
            times: 时间段
            number: 人数
            
        Returns:
            是否添加成功
        """
        if 'people' not in self.file_data:
            self.file_data['people'] = {'type': 'for_day', 'schedules': []}
        
        if 'schedules' not in self.file_data['people']:
            self.file_data['people']['schedules'] = []
        
        new_schedule = {
            'times': times,
            'number': number
        }
        
        self.file_data['people']['schedules'].append(new_schedule)
        return True

    def add_together_group(self, people_ids: List[str]) -> bool:
        """
        添加必须一起排班的人员组
        
        Args:
            people_ids: 人员ID列表
            
        Returns:
            是否添加成功
        """
        if 'together' not in self.file_data:
            self.file_data['together'] = []
        
        if len(people_ids) < 2:
            print("Warning: together group must contain at least 2 people")
            return False
        
        self.file_data['together'].append(people_ids)
        return True

    def add_separation_group(self, people_ids: List[str]) -> bool:
        """
        添加必须分开排班的人员组
        
        Args:
            people_ids: 人员ID列表
            
        Returns:
            是否添加成功
        """
        if 'separation' not in self.file_data:
            self.file_data['separation'] = []
        
        if len(people_ids) < 2:
            print("Warning: separation group must contain at least 2 people")
            return False
        
        self.file_data['separation'].append(people_ids)
        return True

    def add_only_department(self, department: str, day: int, time_period: Union[int, List[int]]) -> bool:
        """
        添加指定部门排班限制
        
        Args:
            department: 部门名称
            day: 日期(1-7)
            time_period: 时间段
            
        Returns:
            是否添加成功
        """
        if 'only_department' not in self.file_data:
            self.file_data['only_department'] = []
        
        new_dept = {
            'department': department,
            'day': day,
            'time_period': time_period if isinstance(time_period, list) else [time_period]
        }
        
        self.file_data['only_department'].append(new_dept)
        return True

    def remove_together_group(self, index: int) -> bool:
        """
        删除指定索引的必须一起排班组
        
        Args:
            index: 组索引
            
        Returns:
            是否删除成功
        """
        if 'together' not in self.file_data or index >= len(self.file_data['together']):
            return False
        
        self.file_data['together'].pop(index)
        return True

    def remove_separation_group(self, index: int) -> bool:
        """
        删除指定索引的必须分开排班组
        
        Args:
            index: 组索引
            
        Returns:
            是否删除成功
        """
        if 'separation' not in self.file_data or index >= len(self.file_data['separation']):
            return False
        
        self.file_data['separation'].pop(index)
        return True

    def get_summary(self) -> Dict[str, Any]:
        """
        获取配置摘要信息
        
        Returns:
            配置摘要字典
        """
        summary = {
            'week': self.file_data.get('week'),
            'days_count': len(self.file_data.get('days', [])),
            'days_order': self.file_data.get('days_order', []),
            'time_periods_count': len(self.file_data.get('time_period', [])),
            'people_type': self.file_data.get('people', {}).get('type'),
            'schedules_count': len(self.file_data.get('people', {}).get('schedules', [])),
            'same_department': self.file_data.get('same_department'),
            'night_shift': self.file_data.get('night_shift'),
            'only_department_count': len(self.file_data.get('only_department', [])),
            'together_groups_count': len(self.file_data.get('together', [])),
            'separation_groups_count': len(self.file_data.get('separation', [])),
        }
        return summary

    def __str__(self) -> str:
        """
        返回配置的可读字符串表示
        
        Returns:
            配置信息的字符串
        """
        summary = self.get_summary()
        lines = [
            "=== 排班配置摘要 ===",
            f"周数: {summary['week']}",
            f"天数: {summary['days_count']}",
            f"天数顺序: {summary['days_order']}",
            f"时间段数量: {summary['time_periods_count']}",
            f"排班类型: {summary['people_type']}",
            f"排班计划数量: {summary['schedules_count']}",
            f"同部门排班: {summary['same_department']}",
            f"夜班: {summary['night_shift']}",
            f"指定部门限制数量: {summary['only_department_count']}",
            f"必须一起排班组数: {summary['together_groups_count']}",
            f"必须分开排班组数: {summary['separation_groups_count']}",
        ]
        return '\n'.join(lines)


# 工具函数:读取JSON文件
# 输入:文件路径
# 输出:Python字典(配置数据),失败返回None
def read_json_file(file_path: str) -> Optional[Dict]:
    """
    读取JSON文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        解析后的字典数据,失败返回None
    """
    try:
        # 这里加上 encoding='utf-8' 就好了!
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in file: {e}")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None


# 工具函数:写入JSON文件
# 输入:文件路径 + 要保存的数据(字典)
# 输出:成功True,失败False
def write_json_file(file_path: str, data: Dict) -> bool:
    """
    写入JSON文件
    
    Args:
        file_path: 文件路径
        data: 要保存的字典数据
        
    Returns:
        成功返回True,失败返回False
    """
    try:
        # 打开文件,写入模式
        with open(file_path, 'w', encoding='utf-8') as file:
            # 将Python字典转为格式化的JSON字符串并保存
            # indent=4 让文件排版整齐,方便人阅读
            # ensure_ascii=False 保证中文正常显示
            json.dump(data, file, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing to file: {e}")
        return False
