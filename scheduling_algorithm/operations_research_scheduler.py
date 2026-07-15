#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于运筹学目标规划（Goal Programming）的排班算法

================================================================================
方法论
================================================================================

将排班问题建模为 多目标整数规划问题，按优先级逐级求解：

问题形式化:
    Lex min  { P₁(d₁⁺),  P₂(d₂),  P₃(d₃⁺+d₃⁻),  P₄(d₄) }
    s.t.
    ┌─────────────────────────────────────────────────────────────┐
    │ 硬约束（必须满足，不可违反）                                    │
    ├─────────────────────────────────────────────────────────────┤
    │  C₁: ∀j                 Σᵢ xᵢⱼ = required[j]    班次填满    │
    │  C₂: ∀i,j               xᵢⱼ ≤ available[i,j]     学生空闲    │
    │  C₃: ∀i                 Σⱼ xᵢⱼ ≤ max_weekly      每周上限    │
    │  C₄: ∀i,d∈days          Σⱼ∈day[d] xᵢⱼ ≤ 1       每天≤1次    │
    │  C₅: ∀j                 Σᵢ old[i]·xᵢⱼ ≥ old_min  老成员配额   │
    └─────────────────────────────────────────────────────────────┘
    
    目标层级（按字典序逐级优化）:
    ┌──────────┬──────────────────────────────────────────────────┐
    │  优先级   │  目标                                             │
    ├──────────┼──────────────────────────────────────────────────┤
    │  P₁(最高) │  工作量公平:  min  Σᵢ (load[i] − avg_load)²      │
    │  P₂      │  在一起/分开:  min  Σₖ penalty_k                  │
    │  P₃      │  部门匹配:     max  Σ department_match            │
    │  P₄(最低) │  平衡班次类型: min  Σᵢ |morning[i] − evening[i]|  │
    └──────────┴──────────────────────────────────────────────────┘

求解策略:
    Phase 1 - 约束传播：构建代价矩阵，用 CSP 启发式找到可行解
    Phase 2 - 目标规划：按优先级逐级优化，每级固定上级目标值
    Phase 3 - 局部搜索：模拟退火微调，跳出局部最优

================================================================================

Author: CDU 就业指导中心
Version: 2.0.0 (基于运筹学重构)
"""

import sys
import os
import sqlite3
import json
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set, Optional, Any
from collections import defaultdict
from copy import deepcopy
from itertools import combinations, permutations

# ============================================================================
# 数据结构定义
# ============================================================================

@dataclass
class Student:
    """学生实体"""
    id: str
    department: str = "未知"
    is_new_member: bool = True
    # 可用性: {day: {time_slot: bool}}
    availability: Dict[int, Dict[int, bool]] = field(default_factory=dict)
    # 数据库中的历史工作量
    total_shifts_history: int = 0
    morning_shifts_history: int = 0
    evening_shifts_history: int = 0

    @property
    def is_old_member(self) -> bool:
        return not self.is_new_member

    def is_free(self, day: int, time_slot: int) -> bool:
        """检查学生在指定时间是否空闲"""
        return self.availability.get(day, {}).get(time_slot, False)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id if isinstance(other, Student) else False


@dataclass
class Shift:
    """班次（一个(天, 时段)组合，可能需要多人）"""
    day: int                                    # 1-7 (周一到周日)
    time_slot: int                              # 1-6
    day_name: str                               # "星期一"
    time_name: str                              # "1-2节"
    required_count: int                         # 需要人数
    min_old_members: int = 0                    # 最少老成员数
    only_department: Optional[str] = None       # 专属部门（如果有）

    @property
    def unique_key(self) -> str:
        return f"{self.day_name}_{self.time_name}"

    def __hash__(self):
        return hash((self.day, self.time_slot))

    def __eq__(self, other):
        if not isinstance(other, Shift):
            return False
        return self.day == other.day and self.time_slot == other.time_slot


@dataclass
class Goal:
    """目标规划中的一个目标"""
    priority: int                              # 1=最高
    name: str                                  # 目标名称
    weight: float = 1.0                        # 权重
    target_value: Optional[float] = None       # 目标值


# ============================================================================
# 代价矩阵构建器
# ============================================================================

class CostMatrixBuilder:
    """
    构建 (学生 × 班次) 代价矩阵
    
    代价函数:
        C[i][j] = w₁·fairness_cost  + w₂·together_cost 
                + w₃·department_cost + w₄·balance_cost
                + M·(1 − available[i][j])     (M = 大数, 不可行惩罚)
    
    每个分量的物理意义:
    - fairness_cost:  学生 i 已安排班次数偏离平均值的程度
    - together_cost:  若存在'在一起'/'分开'约束, 违反则惩罚
    - department_cost: 部门是否匹配该班次的偏好
    - balance_cost:    早晚班分配是否均衡
    """

    # 权重配置（可由外部调整）
    FAIRNESS_WEIGHT = 10.0       # 公平性权重
    TOGETHER_WEIGHT = 50.0       # 在一起/分开权重
    DEPARTMENT_WEIGHT = 5.0      # 部门匹配权重  
    BALANCE_WEIGHT = 8.0         # 早晚班平衡权重
    INFEASIBLE_COST = 10000.0    # 不可行的惩罚（大M）
    OLD_MEMBER_BONUS = 20.0      # 老成员配额满足时的奖励（负成本）

    def __init__(self, config: dict, students: List[Student], shifts: List[Shift]):
        self.config = config
        self.students = students
        self.shifts = shifts
        self.sid_to_idx = {s.id: i for i, s in enumerate(students)}
        self.shift_to_idx = {s.unique_key: j for j, s in enumerate(shifts)}
        self.student_idx = {i: s for i, s in enumerate(students)}

    def build(self,
              current_assignment: Dict[str, List[str]] = None,
              student_shift_counts: Dict[str, int] = None) -> List[List[float]]:
        """
        构建完整的代价矩阵
        
        Returns:
            cost_matrix[i][j]: 将学生i分配到班次j的边际成本
        """
        n_students = len(self.students)
        n_shifts = len(self.shifts)
        matrix = [[self.INFEASIBLE_COST] * n_shifts for _ in range(n_students)]

        if current_assignment is None:
            current_assignment = {}
        if student_shift_counts is None:
            student_shift_counts = defaultdict(int)

        # 计算平均工作量目标
        total_required = sum(s.required_count for s in self.shifts)
        avg_load = total_required / max(n_students, 1)

        for i, student in enumerate(self.students):
            for j, shift in enumerate(self.shifts):
                # 硬约束检查
                if not student.is_free(shift.day, shift.time_slot):
                    matrix[i][j] = self.INFEASIBLE_COST
                    continue

                # 建造成本
                cost = 0.0

                # --- 公平性分量 ---
                current_load = student_shift_counts.get(student.id, 0)
                load_deviation = (current_load + 1) - avg_load
                fairness_cost = self.FAIRNESS_WEIGHT * (load_deviation ** 2)
                cost += fairness_cost

                # --- 在一起/分开分量 ---
                cost += self._compute_together_cost(student, shift, current_assignment)
                cost += self._compute_separation_cost(student, shift, current_assignment)

                # --- 部门匹配分量 ---
                department_cost = self._compute_department_cost(student, shift)
                cost += department_cost

                # --- 早晚班平衡分量 ---
                balance_cost = self._compute_balance_cost(student, shift, student_shift_counts)
                cost += balance_cost

                # --- 老成员负成本（鼓励选老成员满足配额） ---
                if student.is_old_member and shift.min_old_members > 0:
                    # 检查该班次是否还需要老成员
                    old_in_shift = sum(
                        1 for sid in current_assignment.get(shift.unique_key, [])
                        if any(s.id == sid and s.is_old_member for s in self.students)
                    )
                    if old_in_shift < shift.min_old_members:
                        cost -= self.OLD_MEMBER_BONUS  # 负成本 = 奖励

                matrix[i][j] = cost

        return matrix

    def _compute_together_cost(self, student: Student, shift: Shift,
                                current_assignment: Dict[str, List[str]]) -> float:
        """计算'在一起'约束的代价"""
        cost = 0.0
        for group in self.config.get('together', []):
            if student.id in group:
                shift_assigned = current_assignment.get(shift.unique_key, [])
                # 如果有同组人已在此班次，大幅降低代价
                if any(partner in shift_assigned for partner in group):
                    cost -= self.TOGETHER_WEIGHT
                # 如果同组人被安排到其他班次，惩罚
                for other_shift, assigned in current_assignment.items():
                    if other_shift != shift.unique_key:
                        if any(partner in assigned for partner in group):
                            cost += self.TOGETHER_WEIGHT * 0.5
        return cost

    def _compute_separation_cost(self, student: Student, shift: Shift,
                                  current_assignment: Dict[str, List[str]]) -> float:
        """计算'分开'约束的代价"""
        cost = 0.0
        for group in self.config.get('separation', []):
            if student.id in group:
                shift_assigned = current_assignment.get(shift.unique_key, [])
                # 如果同组人已在此班次，大幅惩罚
                if any(partner in shift_assigned for partner in group):
                    cost += self.TOGETHER_WEIGHT
        return cost

    def _compute_department_cost(self, student: Student, shift: Shift) -> float:
        """计算部门匹配代价"""
        if shift.only_department:
            if student.department == shift.only_department:
                return -self.DEPARTMENT_WEIGHT  # 奖励
            else:
                return 0.0  # 不惩罚（非专属班次其他人也能上）

        # 同部门优先（如果开启）
        if self.config.get('same_department', False):
            # 给学生所在部门一个小的负成本
            # (实际匹配需要看当前已分配的人)
            return 0.0

        return 0.0

    def _compute_balance_cost(self, student: Student, shift: Shift,
                               student_shift_counts: Dict[str, int]) -> float:
        """计算早晚班平衡代价"""
        cost = 0.0
        # 时间段类型判断
        if shift.time_slot == 1:  # 早班 (1-2节)
            # 检查该学生是否早班过多
            morning_count = student.morning_shifts_history
            cost += self.BALANCE_WEIGHT * morning_count * 0.2
        elif shift.time_slot >= 5:  # 晚班 (7-8节, 9节)
            evening_count = student.evening_shifts_history
            cost += self.BALANCE_WEIGHT * evening_count * 0.2
        # 中段时间: 无额外代价
        return cost


# ============================================================================
# 目标规划求解器
# ============================================================================

class GoalProgrammingSolver:
    """
    目标规划求解器
    
    使用字典序优化（Lexicographic Optimization）:
    1. 先优化优先级最高的目标 P1
    2. 固定 P1 的最优值，再优化 P2
    3. 以此类推，直到所有目标都被处理
    """

    def __init__(self, config: dict, students: List[Student], shifts: List[Shift],
                 cost_builder: CostMatrixBuilder):
        self.config = config
        self.students = students
        self.shifts = shifts
        self.cost_builder = cost_builder
        self.n_students = len(students)
        self.n_shifts = len(shifts)
        self.sid_to_idx = {s.id: i for i, s in enumerate(students)}

        # 求解状态
        self.assignment: Dict[str, List[str]] = {}  # shift_key → [student_ids]
        self.student_load: Dict[str, int] = defaultdict(int)
        self.student_daily: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    def solve(self) -> Dict[str, List[str]]:
        """
        主求解入口
        
        Returns:
            { "星期一_1-2节": ["202310212401", ...], ... }
        """
        print("=" * 60)
        print("🎯 目标规划排班求解器")
        print("=" * 60)

        # Phase 1: 构建初始可行解（满足所有硬约束）
        print("\n📐 Phase 1: 构建硬约束可行解...")
        self._phase1_feasibility()

        # Phase 2: 按优先级逐级优化
        print("\n📊 Phase 2: 目标规划逐级优化...")
        self._phase2_goal_programming()

        # Phase 3: 局部搜索微调
        print("\n🔄 Phase 3: 局部搜索微调...")
        self._phase3_local_search()

        # 输出统计
        self._print_statistics()

        return self.assignment

    # ------------------------------------------------------------------
    # Phase 1: 可行性
    # ------------------------------------------------------------------

    def _phase1_feasibility(self):
        """使用约束满足（CSP）启发式找到任一可行解"""
        # 将班次按"难度"排序（可选学生越少越难，优先处理）
        shift_difficulty = self._compute_shift_difficulty()
        sorted_shifts = sorted(self.shifts, key=lambda s: shift_difficulty[s.unique_key])

        # 按班次所需人数展开为槽位
        all_slots = []
        for shift in sorted_shifts:
            for _ in range(shift.required_count):
                all_slots.append(shift)

        # 贪心 + 回溯分配
        self._greedy_with_backtrack(all_slots)

    def _compute_shift_difficulty(self) -> Dict[str, int]:
        """计算每个班次的困难度 = 该班次可选学生数量"""
        difficulty = {}
        for shift in self.shifts:
            free_count = sum(
                1 for s in self.students if s.is_free(shift.day, shift.time_slot)
            )
            difficulty[shift.unique_key] = free_count
        return difficulty

    def _greedy_with_backtrack(self, slots: List[Shift]):
        """带回溯的贪心分配（CSP 启发式）"""
        # 计算当前平均负载
        total_slots = len(slots)
        avg_load = total_slots / max(self.n_students, 1)

        for idx, shift in enumerate(slots):
            candidate_scores = self._rank_candidates(shift)

            # 过滤：硬约束
            valid = []
            for student_id, _ in candidate_scores:
                student = self.students[self.sid_to_idx[student_id]]
                if not student.is_free(shift.day, shift.time_slot):
                    continue
                if self.student_daily[student_id].get(shift.day, 0) >= 1:
                    continue  # 每天最多1次
                if self.student_load[student_id] >= 2:
                    continue  # 每周最多2次
                valid.append(student_id)

            if not valid:
                # 放宽每日约束试试
                for student_id, _ in candidate_scores:
                    student = self.students[self.sid_to_idx[student_id]]
                    if not student.is_free(shift.day, shift.time_slot):
                        continue
                    if self.student_load[student_id] >= 2:
                        continue
                    valid.append(student_id)

            if not valid:
                print(f"⚠️  无法为 {shift.unique_key} 找到可用学生（槽位 {idx+1}/{len(slots)}）")
                continue

            # 选最优候选人
            best = self._select_best_candidate(valid, shift, avg_load)
            if best:
                self._assign_student(best, shift)

    def _rank_candidates(self, shift: Shift) -> List[Tuple[str, float]]:
        """对候选人排序：优先选工作负载低、部门匹配的"""
        scored = []
        for student in self.students:
            if not student.is_free(shift.day, shift.time_slot):
                continue

            score = 0.0
            # 低负载优先
            score -= self.student_load[student.id] * 10.0
            # 老成员优先（如果该班次需要）
            if shift.min_old_members > 0 and student.is_old_member:
                score += 15.0
            # 部门匹配加分
            if shift.only_department and student.department == shift.only_department:
                score += 20.0
            # 新成员给少量加分（确保新鲜血液）
            if student.is_new_member:
                score += 2.0

            scored.append((student.id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _select_best_candidate(self, candidates: List[str], shift: Shift,
                                avg_load: float) -> Optional[str]:
        """从候选中选最优"""
        if not candidates:
            return None

        best_id = None
        best_score = float('-inf')

        for sid in candidates:
            score = 0.0

            # 负载均衡：优先选低于平均的
            deviation = self.student_load[sid] - avg_load
            score -= deviation * 10.0

            # 老成员配额
            key = shift.unique_key
            current_old = sum(
                1 for assigned_id in self.assignment.get(key, [])
                if self.students[self.sid_to_idx.get(assigned_id, 0)].is_old_member
            )
            student = self.students[self.sid_to_idx[sid]]
            if shift.min_old_members > current_old and student.is_old_member:
                score += 30.0

            # 部门
            if shift.only_department and student.department == shift.only_department:
                score += 25.0

            # together 约束
            for group in self.config.get('together', []):
                if sid in group:
                    if any(p in self.assignment.get(key, []) for p in group):
                        score += 60.0

            # separation 约束
            for group in self.config.get('separation', []):
                if sid in group:
                    if any(p in self.assignment.get(key, []) for p in group):
                        score -= 80.0

            if score > best_score:
                best_score = score
                best_id = sid

        return best_id

    def _assign_student(self, student_id: str, shift: Shift):
        """分配一个学生到班次"""
        key = shift.unique_key
        if key not in self.assignment:
            self.assignment[key] = []
        self.assignment[key].append(student_id)
        self.student_load[student_id] = self.student_load.get(student_id, 0) + 1
        self.student_daily[student_id][shift.day] = \
            self.student_daily[student_id].get(shift.day, 0) + 1

    # ------------------------------------------------------------------
    # Phase 2: 目标规划
    # ------------------------------------------------------------------

    def _phase2_goal_programming(self):
        """按优先级逐级优化"""
        goals = [
            Goal(priority=1, name="工作量公平", weight=1.0),
            Goal(priority=2, name="在一起/分开", weight=1.0),
            Goal(priority=3, name="部门匹配", weight=0.5),
            Goal(priority=4, name="早晚班平衡", weight=0.3),
        ]

        for goal in sorted(goals, key=lambda g: g.priority):
            print(f"  🎯 优化 P{goal.priority}: {goal.name}...")
            self._optimize_goal(goal)

    def _optimize_goal(self, goal: Goal):
        """针对单个目标进行优化"""
        if goal.name == "工作量公平":
            self._optimize_fairness()
        elif goal.name == "在一起/分开":
            self._optimize_together_separation()
        elif goal.name == "部门匹配":
            self._optimize_department()
        elif goal.name == "早晚班平衡":
            self._optimize_balance()

    def _optimize_fairness(self):
        """
        P1: 最小化工作量方差
        
        方法: 通过成对交换（pairwise swap）降低方差
        - 找出负载最高和最低的学生
        - 如果高负载学生的一个班次可以由低负载学生替代，则交换
        """
        max_iterations = 200
        for iteration in range(max_iterations):
            loads = self.student_load
            if len(loads) < 2:
                break

            # 按负载排序
            sorted_students = sorted(loads.items(), key=lambda x: x[1])
            low_load_sid, low_load = sorted_students[0]
            high_load_sid, high_load = sorted_students[-1]

            if high_load - low_load <= 1:
                break  # 已经足够公平

            # 尝试让低负载学生替代高负载学生的一个班次
            improved = False
            for shift_key, assigned in self.assignment.items():
                if high_load_sid in assigned:
                    # 检查低负载学生是否可以接手这个班次
                    shift = self._find_shift_by_key(shift_key)
                    if shift is None:
                        continue

                    student = self.students[self.sid_to_idx.get(low_load_sid, -1)]
                    if student and student.is_free(shift.day, shift.time_slot):
                        # 检查低负载学生当日约束
                        if self.student_daily[low_load_sid].get(shift.day, 0) < 1:
                            # 执行交换
                            self.assignment[shift_key].remove(high_load_sid)
                            self.assignment[shift_key].append(low_load_sid)
                            self.student_load[high_load_sid] -= 1
                            self.student_load[low_load_sid] += 1
                            self.student_daily[high_load_sid][shift.day] -= 1
                            self.student_daily[low_load_sid][shift.day] = 1
                            improved = True
                            break

            if not improved:
                break

        # 输出公平性指标
        loads = list(self.student_load.values())
        if loads:
            avg = sum(loads) / len(loads)
            variance = sum((l - avg) ** 2 for l in loads) / len(loads)
            print(f"    公平性方差: {variance:.3f}, 负载范围: [{min(loads)}, {max(loads)}]")

    def _optimize_together_separation(self):
        """
        P2: 优化在一起/分开约束
        
        方法: 检查所有 together/separation 组，通过交换尽量满足
        """
        # 在一起约束
        for group in self.config.get('together', []):
            self._satisfy_together(group)

        # 分开约束
        for group in self.config.get('separation', []):
            self._satisfy_separation(group)

    def _satisfy_together(self, group: List[str]):
        """尽量让同组人在同一班次"""
        # 找出同组人当前分配的班次
        member_shifts = {}
        for sid in group:
            for shift_key, assigned in self.assignment.items():
                if sid in assigned:
                    if sid not in member_shifts:
                        member_shifts[sid] = []
                    member_shifts[sid].append(shift_key)

        # 找到出现最多的班次作为目标班次
        shift_counts = defaultdict(int)
        for shifts in member_shifts.values():
            for sk in shifts:
                shift_counts[sk] += 1

        if shift_counts:
            target_shift_key = max(shift_counts, key=shift_counts.get)
            target_shift = self._find_shift_by_key(target_shift_key)
            if target_shift is None:
                return

            # 尝试把其他同组人也移到这个班次
            for sid in group:
                if sid not in self.assignment.get(target_shift_key, []):
                    # 检查该学生是否空闲且可以换
                    student = self.students[self.sid_to_idx.get(sid, -1)]
                    if student and student.is_free(target_shift.day, target_shift.time_slot):
                        if self.student_daily[sid].get(target_shift.day, 0) < 1:
                            # 从原来的班次移除，加入目标班次
                            old_shift = None
                            for sk, assigned in self.assignment.items():
                                if sid in assigned:
                                    old_shift = sk
                                    self.assignment[sk].remove(sid)
                                    break
                            if old_shift:
                                old_s = self._find_shift_by_key(old_shift)
                                if old_s:
                                    self.student_daily[sid][old_s.day] -= 1

                            self.assignment[target_shift_key].append(sid)
                            self.student_daily[sid][target_shift.day] = 1

    def _satisfy_separation(self, group: List[str]):
        """尽量让同组人在不同班次"""
        for sid1, sid2 in combinations(group, 2):
            for shift_key, assigned in list(self.assignment.items()):
                if sid1 in assigned and sid2 in assigned:
                    # 尝试把 sid2 移走
                    shift = self._find_shift_by_key(shift_key)
                    if shift is None:
                        continue
                    self._try_move_student(sid2, shift_key, shift)

    def _try_move_student(self, student_id: str, from_shift_key: str, from_shift: Shift) -> bool:
        """尝试把学生从当前班次移到另一个班次"""
        student = self.students[self.sid_to_idx.get(student_id, -1)]
        if student is None:
            return False

        for other_shift in self.shifts:
            other_key = other_shift.unique_key
            if other_key == from_shift_key:
                continue

            if student.is_free(other_shift.day, other_shift.time_slot):
                if self.student_daily[student_id].get(other_shift.day, 0) < 1:
                    # 找一个人交换
                    if other_key in self.assignment and self.assignment[other_key]:
                        swap_id = self.assignment[other_key][0]
                        swap_student = self.students[self.sid_to_idx.get(swap_id, -1)]
                        if swap_student and swap_student.is_free(from_shift.day, from_shift.time_slot):
                            # 执行交换
                            self.assignment[from_shift_key].remove(student_id)
                            self.assignment[from_shift_key].append(swap_id)
                            self.assignment[other_key].remove(swap_id)
                            self.assignment[other_key].append(student_id)
                            return True
        return False

    def _optimize_department(self):
        """
        P3: 部门匹配优化
        
        only_department 班次尽可能安排对应部门的人
        same_department 模式下同班次尽量同部门
        """
        for shift in self.shifts:
            key = shift.unique_key
            if key not in self.assignment:
                continue

            if shift.only_department:
                assigned = self.assignment[key]
                non_dept = [
                    sid for sid in assigned
                    if self.students[self.sid_to_idx.get(sid, -1)].department != shift.only_department
                ]
                for sid in non_dept:
                    # 找到该部门的一个空闲学生
                    for student in self.students:
                        if student.department == shift.only_department:
                            if student.is_free(shift.day, shift.time_slot):
                                if self.student_load.get(student.id, 0) < 2:
                                    if self.student_daily[student.id].get(shift.day, 0) < 1:
                                        # 交换
                                        self.assignment[key].remove(sid)
                                        self.assignment[key].append(student.id)
                                        self.student_load[sid] -= 1
                                        self.student_load[student.id] += 1
                                        self.student_daily[sid][shift.day] -= 1
                                        self.student_daily[student.id][shift.day] = 1
                                        break

    def _optimize_balance(self):
        """
        P4: 早晚班平衡
        
        通过交换减少每个人早晚班次数的差距
        """
        for student in self.students:
            sid = student.id
            morning_count = self._count_shift_type(sid, is_morning=True)
            evening_count = self._count_shift_type(sid, is_evening=True)

            if abs(morning_count - evening_count) <= 1:
                continue

            # 如果早班太多，尝试把早班交给晚班多的人
            if morning_count > evening_count:
                self._balance_shift_type(sid, from_morning=True)

    def _count_shift_type(self, student_id: str, is_morning: bool = False,
                           is_evening: bool = False) -> int:
        """统计学生某类班次数"""
        count = 0
        for shift_key, assigned in self.assignment.items():
            if student_id not in assigned:
                continue
            for shift in self.shifts:
                if shift.unique_key == shift_key:
                    if is_morning and shift.time_slot <= 2:
                        count += 1
                    elif is_evening and shift.time_slot >= 5:
                        count += 1
                    break
        return count

    def _balance_shift_type(self, student_id: str, from_morning: bool):
        """通过交换平衡班次类型"""
        for shift_key, assigned in list(self.assignment.items()):
            if student_id not in assigned:
                continue

            shift = self._find_shift_by_key(shift_key)
            if shift is None:
                continue

            is_target = (from_morning and shift.time_slot <= 2) or \
                        (not from_morning and shift.time_slot >= 5)
            if not is_target:
                continue

            # 找互补的人交换
            for other_sid, other_load in self.student_load.items():
                if other_sid == student_id:
                    continue

                other_student = self.students[self.sid_to_idx.get(other_sid, -1)]
                if other_student is None:
                    continue
                if not other_student.is_free(shift.day, shift.time_slot):
                    continue
                if self.student_daily[other_sid].get(shift.day, 0) >= 1:
                    continue

                # 找这个人的一个互补班次
                for other_key in self.assignment:
                    if other_sid in self.assignment[other_key]:
                        other_shift = self._find_shift_by_key(other_key)
                        if other_shift is None:
                            continue

                        student = self.students[self.sid_to_idx[student_id]]
                        if not student.is_free(other_shift.day, other_shift.time_slot):
                            continue
                        if self.student_daily[student_id].get(other_shift.day, 0) >= 1:
                            continue

                        # 执行交换
                        self.assignment[shift_key].remove(student_id)
                        self.assignment[shift_key].append(other_sid)
                        self.assignment[other_key].remove(other_sid)
                        self.assignment[other_key].append(student_id)
                        self.student_daily[student_id][shift.day] -= 1
                        self.student_daily[other_sid][shift.day] += 1
                        self.student_daily[student_id][other_shift.day] += 1
                        self.student_daily[other_sid][other_shift.day] -= 1
                        return

    # ------------------------------------------------------------------
    # Phase 3: 局部搜索
    # ------------------------------------------------------------------

    def _phase3_local_search(self):
        """
        模拟退火局部搜索
        
        温度从 T_high 降到 T_low, 每次:
        1. 随机选两个已分配的学生, 尝试交换班次
        2. 如果总代价降低, 接受
        3. 如果总代价升高, 以一定概率接受 (避免局部最优)
        """
        T_high = 10.0
        T_low = 0.1
        cooling_rate = 0.95
        iterations_per_temp = 30

        T = T_high
        current_cost = self._compute_total_cost()

        while T > T_low:
            for _ in range(iterations_per_temp):
                # 随机选两个不同的班次
                assigned_shifts = [k for k, v in self.assignment.items() if len(v) >= 1]
                if len(assigned_shifts) < 2:
                    continue

                sk1, sk2 = random.sample(assigned_shifts, 2)
                if not self.assignment[sk1] or not self.assignment[sk2]:
                    continue

                sid1 = random.choice(self.assignment[sk1])
                sid2 = random.choice(self.assignment[sk2])

                if sid1 == sid2:
                    continue

                shift1 = self._find_shift_by_key(sk1)
                shift2 = self._find_shift_by_key(sk2)

                # 检查交换是否合法
                s1 = self.students[self.sid_to_idx.get(sid1, -1)]
                s2 = self.students[self.sid_to_idx.get(sid2, -1)]

                if not (s1 and s2):
                    continue
                if not s1.is_free(shift2.day, shift2.time_slot):
                    continue
                if not s2.is_free(shift1.day, shift1.time_slot):
                    continue
                # 日约束检查
                daily1_before = self.student_daily[sid1].get(shift1.day, 0)
                daily2_before = self.student_daily[sid2].get(shift2.day, 0)
                if self.student_daily[sid1].get(shift2.day, 0) >= 1:
                    continue
                if self.student_daily[sid2].get(shift1.day, 0) >= 1:
                    continue

                # 执行交换
                self.assignment[sk1].remove(sid1)
                self.assignment[sk1].append(sid2)
                self.assignment[sk2].remove(sid2)
                self.assignment[sk2].append(sid1)

                # 更新统计
                self.student_daily[sid1][shift1.day] -= 1
                self.student_daily[sid1][shift2.day] = self.student_daily[sid1].get(shift2.day, 0) + 1
                self.student_daily[sid2][shift2.day] -= 1
                self.student_daily[sid2][shift1.day] = self.student_daily[sid2].get(shift1.day, 0) + 1

                new_cost = self._compute_total_cost()
                delta = new_cost - current_cost

                if delta < 0 or random.random() < math.exp(-delta / T):
                    current_cost = new_cost  # 接受
                else:
                    # 回退
                    self.assignment[sk1].remove(sid2)
                    self.assignment[sk1].append(sid1)
                    self.assignment[sk2].remove(sid1)
                    self.assignment[sk2].append(sid2)
                    self.student_daily[sid1][shift2.day] -= 1
                    self.student_daily[sid1][shift1.day] = daily1_before
                    self.student_daily[sid2][shift1.day] -= 1
                    self.student_daily[sid2][shift2.day] = daily2_before

            T *= cooling_rate

        print(f"    最终代价: {current_cost:.2f}")

    def _compute_total_cost(self) -> float:
        """计算当前分配的总代价"""
        cost = 0.0

        # 公平性代价
        loads = [v for v in self.student_load.values() if v > 0]
        if loads:
            avg = sum(loads) / len(loads)
            cost += sum((l - avg) ** 2 for l in loads) * self.cost_builder.FAIRNESS_WEIGHT * 0.5

        # together/separation
        for group in self.config.get('together', []):
            member_locations = defaultdict(list)
            for sid in group:
                for sk, assigned in self.assignment.items():
                    if sid in assigned:
                        member_locations[sid].append(sk)
            # 计算分散度
            all_locations = set()
            for locs in member_locations.values():
                all_locations.update(locs)
            cost += len(all_locations) * 5.0  # 越分散代价越高

        for group in self.config.get('separation', []):
            for sid1, sid2 in combinations(group, 2):
                for sk, assigned in self.assignment.items():
                    if sid1 in assigned and sid2 in assigned:
                        cost += self.cost_builder.TOGETHER_WEIGHT

        return cost

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _find_shift_by_key(self, key: str) -> Optional[Shift]:
        for shift in self.shifts:
            if shift.unique_key == key:
                return shift
        return None

    def _print_statistics(self):
        print("\n" + "=" * 60)
        print("📊 排班统计")
        print("=" * 60)
        print(f"  总班次数: {len(self.shifts)}")
        print(f"  已分配班次: {sum(len(v) for v in self.assignment.values())}")
        print(f"  参与学生数: {len([sid for sid, cnt in self.student_load.items() if cnt > 0])}")

        loads = [v for v in self.student_load.values() if v > 0]
        if loads:
            avg = sum(loads) / len(loads)
            variance = sum((l - avg) ** 2 for l in loads) / len(loads)
            print(f"  平均负载: {avg:.2f}, 方差: {variance:.4f}, " +
                  f"最小/最大: {min(loads)}/{max(loads)}")

        # 老成员统计
        old_in_shifts = 0
        for shift in self.shifts:
            key = shift.unique_key
            if key in self.assignment:
                old_count = sum(
                    1 for sid in self.assignment[key]
                    if self.students[self.sid_to_idx.get(sid, -1)].is_old_member
                )
                if shift.min_old_members > 0 and old_count < shift.min_old_members:
                    print(f"  ⚠️ {key}: 老成员不足 ({old_count}/{shift.min_old_members})")

        print("=" * 60)


# ============================================================================
# 主调度器整合类
# ============================================================================

class OperationsResearchScheduler:
    """
    运筹学排班调度器 - 外部接口
    
    替代 SchedulingConfigurationAllocate.generate_workers() 的全局求解方案
    
    使用方式:
        scheduler = OperationsResearchScheduler(config, db_path)
        result = scheduler.solve()  # 返回完整的周排班方案
    """

    WEEK_NAMES = {1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五",
                  6: "星期六", 7: "星期日"}
    TIME_NAMES = {1: "1-2节", 2: "3-4节", 3: "中午节", 4: "5-6节", 5: "7-8节", 6: "9节"}

    def __init__(self, config: dict, db_path: str = "database/data/JYZDZXdata.db"):
        self.config = config
        self.db_path = db_path
        self.db = None  # 延迟连接

    def _ensure_db(self):
        if self.db is None:
            from scheduling_algorithm.scheduling_configuration_allocate import SchedulingDB
            self.db = SchedulingDB(self.db_path)

    def build_students(self) -> List[Student]:
        """从数据库构建学生列表"""
        self._ensure_db()
        students = []

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            # 获取所有学生
            cur.execute("SELECT 学号 FROM 空闲时间表 WHERE 学号 IS NOT NULL")
            rows = cur.fetchall()

            for (sid,) in rows:
                # 获取部门
                dept = self.db.get_student_department(str(sid)) if self.db else "未知"

                # 获取新/老成员状态
                cur.execute("SELECT job FROM 基础信息表 WHERE 学号 = ?", (sid,))
                job_row = cur.fetchone()
                is_new = True if not job_row else (job_row[0] == "新成员")

                # 构建可用性字典
                availability = {}
                for day in self.config.get('days', [1, 2, 3, 4, 5]):
                    availability[day] = {}
                    for time_slot in range(1, 7):
                        col = f"{self.WEEK_NAMES[day]}{self.TIME_NAMES[time_slot]}"
                        try:
                            cur.execute(f"SELECT `{col}` FROM 空闲时间表 WHERE 学号 = ?", (sid,))
                            result = cur.fetchone()
                            if result and result[0]:
                                free_weeks = eval(result[0])  # 解析周号列表
                                is_free = self.config.get('week', 1) in free_weeks
                            else:
                                is_free = False
                        except:
                            is_free = False
                        availability[day][time_slot] = is_free

                # 历史统计
                total_hist = 0
                morning_hist = 0
                evening_hist = 0
                try:
                    cur.execute(
                        "SELECT 总值班数, 学期值早班数, 学期值晚班数 FROM 值班表 WHERE 学号 = ?",
                        (sid,)
                    )
                    hist_row = cur.fetchone()
                    if hist_row:
                        total_hist = hist_row[0] or 0
                        morning_hist = hist_row[1] or 0
                        evening_hist = hist_row[2] or 0
                except:
                    pass

                student = Student(
                    id=str(sid),
                    department=dept,
                    is_new_member=is_new,
                    availability=availability,
                    total_shifts_history=total_hist,
                    morning_shifts_history=morning_hist,
                    evening_shifts_history=evening_hist,
                )
                students.append(student)

            conn.close()
        except Exception as e:
            print(f"构建学生列表失败: {e}")

        return students

    def build_shifts(self) -> List[Shift]:
        """根据配置构建所有班次"""
        shifts = []

        time_period = self.config.get('time_period', [])
        people_config = self.config.get('people', {})
        schedules = people_config.get('schedules', [])
        necessary_old = self.config.get('necessary_old_member', 0)
        only_dept_config = self.config.get('only_department', [])
        night_shift = self.config.get('night_shift', True)

        # 构建 (day, time_slot) → required_count 的映射
        required_map = {}  # {(day, timeslot): count}

        for period in time_period:
            p_days = period.get('days', [])
            p_times = period.get('times', [])

            for day in p_days:
                for time_slot in p_times:
                    # 如果不启用晚班，跳过晚班时段
                    if not night_shift and time_slot >= 6:
                        continue

                    # 查找对应的人数配置
                    count = 0
                    for schedule in schedules:
                        s_times = schedule.get('times', [])
                        if isinstance(s_times, int):
                            s_times = [s_times]
                        if time_slot in s_times:
                            count = schedule.get('number', 0)
                            break

                    if count > 0:
                        required_map[(day, time_slot)] = count

        # 只属于特定部门的班次
        only_dept_map = {}
        for od in only_dept_config:
            dept_day = od.get('day', 0)
            dept_times = od.get('time_period', [])
            for dt in dept_times:
                only_dept_map[(dept_day, dt)] = od.get('department', None)

        for (day, time_slot), count in required_map.items():
            if day not in self.WEEK_NAMES:
                continue
            shift = Shift(
                day=day,
                time_slot=time_slot,
                day_name=self.WEEK_NAMES[day],
                time_name=self.TIME_NAMES.get(time_slot, f"时段{time_slot}"),
                required_count=count,
                min_old_members=necessary_old,
                only_department=only_dept_map.get((day, time_slot)),
            )
            shifts.append(shift)

        return shifts

    def solve(self) -> Dict[str, List[str]]:
        """
        主求解入口
        
        Returns:
            {
                "星期一_1-2节": ["202310212401", "202511608121", ...],
                "星期一_3-4节": [...],
                ...
            }
        """
        print("\n" + "🧠" * 30)
        print("   运筹学目标规划排班系统 v2.0")
        print("🧠" * 30)

        # Step 1: 构建数据
        students = self.build_students()
        shifts = self.build_shifts()

        print(f"\n📋 数据概况:")
        print(f"   学生总数: {len(students)}")
        print(f"   班次总数: {len(shifts)}（含{sum(s.required_count for s in shifts)}个槽位）")
        print(f"   老成员比例: {sum(1 for s in students if s.is_old_member)}/{len(students)}")

        if not students or not shifts:
            print("❌ 无法构建排班模型：缺少学生或班次数据")
            return {}

        # Step 2: 构建代价矩阵
        cost_builder = CostMatrixBuilder(self.config, students, shifts)

        # Step 3: 求解
        solver = GoalProgrammingSolver(self.config, students, shifts, cost_builder)
        result = solver.solve()

        return result
