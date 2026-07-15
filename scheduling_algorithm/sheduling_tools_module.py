def calculate_bonus(person, shift, current_schedule, config):
    """
    计算加分项（根据排班规则动态计算）
    """
    bonus = 0
    
    # 新成员基础加分（符合排班需求）
    if hasattr(person, 'is_new') and person.is_new:
        bonus += 5
    
    # 同部门加分（需开启同部门优先）
    if config.get('same_department') and current_schedule:
        # 注意：这里假设 current_schedule 非空且第一个元素有 department 属性
        first_dept = current_schedule[0].department
        if hasattr(person, 'department') and person.department == first_dept:
            bonus += 5
    
    # 排班在一起加分
    for group in config.get('together', []):
        if person.id in group:
            if any(m.id in group for m in current_schedule):
                bonus += 50
    
    return bonus


def calculate_penalty(person, shift, weekly_stats, config):
    """
    计算扣分项（根据排班规则动态计算）
    """
    penalty = 0
    
    # 每周排班次数惩罚
    penalty += weekly_stats.get('total_shifts', 0)
    
    # 特殊班次惩罚（早/晚班）
    if hasattr(shift, 'slot') and shift.slot in [1, 6]:  # 1=早班, 6=晚班
        penalty += weekly_stats.get(f"{shift.slot}_shifts", 0)
    
    # 本周已排班惩罚
    if weekly_stats.get('current_week', 0) > 0:
        penalty += weekly_stats['current_week'] * 2
    
    # 排班分开惩罚
    for group in config.get('separation', []):
        if person.id in group:
            assigned_persons = weekly_stats.get('assigned', [])
            if any(m.id in group for m in assigned_persons):
                penalty += 50
    
    return penalty


def calculate_shift_score(person, shift, current_schedule, weekly_stats, config):
    """
    计算最终排班分数
    """
    base_score = 100  # 基础分为100
    # 计算加分项
    bonus = calculate_bonus(person, shift, current_schedule, config)
    # 计算扣分项
    penalty = calculate_penalty(person, shift, weekly_stats, config)
    # 确保分数不低于0
    final_score = max(0, base_score + bonus - penalty)
    
    return final_score


# 主排班循环示例（需根据实际结构调整）
def schedule_shifts(time_period, eligible_persons, config):
    """
    示例排班主循环
    """
    current_schedule = []
    # 初始化统计信息，实际使用中可能需要按人或按周更复杂的结构
    weekly_stats = {
        'total_shifts': 0, 
        'current_week': 0, 
        'assigned': []
    }
    
    for shift in time_period:
        best_person = None
        best_score = -1
        
        for person in eligible_persons:
            # 计算每个人的得分
            score = calculate_shift_score(person, shift, current_schedule, weekly_stats, config)
            
            # 简单的择优逻辑：分数越高越优先
            if score > best_score:
                best_score = score
                best_person = person
        
        if best_person:
            # 更新排班结果和统计信息
            current_schedule.append(best_person)
            weekly_stats['assigned'].append(best_person)
            weekly_stats['total_shifts'] += 1
            # 这里需要根据实际日期逻辑更新 current_week 等
            
    return current_schedule
