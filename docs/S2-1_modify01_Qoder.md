# S2-1_modify01: 算法版本控制增强

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S2-1 已完成


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S2-1_modify01 |
| 任务名称 | 算法版本控制增强——公式注册表与反推验证 |
| 优先级 | P0 |
| 预估工作量 | 1天 |
| 依赖 | S2-1 已完成 |

## 二、任务背景

S2-1 已实现 `XiMingAdapter`，数据标准化时保留了 `algorithm_version` 字段。但当前实现仅记录版本号，未提供验证历史数据一致性的能力。

根据我们的架构决策：
- **慧惠侧不冗余存储公式快照**，仅保留 `algorithm_version`
- **慧惠侧维护一个公式注册表**，可通过 `dimension_scores` 反推验证 `p_zhongshu_score` 的正确性
- 当用户未来可自定义P忠恕权重时，不同版本的算法将导致事件分数不可直接比较，需通过注册表统一管理

## 三、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `memory/gateway/formula_registry.py` | **新建** | P忠恕公式注册表 + 反推验证函数 |
| `memory/gateway/__init__.py` | 修改 | 增加公式注册表相关导出（可选） |
| `memory/verify_s2_1_modify01.py` | **新建** | 算法版本控制专项验证脚本 |

**不修改的文件**：
- `memory/gateway/adapters/ximing_adapter.py` — 已有 `algorithm_version` 字段，无需修改
- `memory/verify_s2_1.py` — 原验证脚本保持不变

## 四、实现要求

### 4.1 新建 `memory/gateway/formula_registry.py`

```python
"""P忠恕算法版本注册表与反推验证"""

# 公式注册表：记录每个算法版本的权重和描述
FORMULA_REGISTRY = {
    "1.0.0": {
        "weights": {
            "temporal": 0.2,
            "spatial": 0.2,
            "wisdom": 0.3,
            "causality": 0.3
        },
        "description": "P = 0.2*T + 0.2*S + 0.3*C + 0.3*R"
    },
    # 未来版本在此注册
    # "2.0.0": {
    #     "weights": { ... },
    #     "description": "..."
    # },
}

def get_formula(version: str) -> dict | None:
    """获取指定版本的公式定义，不存在则返回 None"""
    return FORMULA_REGISTRY.get(version)

def verify_p_score(
    dimension_scores: dict,
    p_zhongshu_score: float,
    algorithm_version: str = "1.0.0",
    tolerance: float = 0.01
) -> bool:
    """
    反推验证：用公式注册表中的权重重算P忠恕分数，检查是否与原始分数一致。
    
    参数：
        dimension_scores: {"temporal": int, "spatial": int, "wisdom": int, "causality": int}
        p_zhongshu_score: 原始P忠恕分数
        algorithm_version: 算法版本号
        tolerance: 允许的浮点误差
    
    返回：
        True  — 分数一致，算法版本匹配
        False — 分数不一致，或算法版本未知
    """
    formula = get_formula(algorithm_version)
    if not formula:
        return False
    
    weights = formula["weights"]
    recalculated = sum(
        dimension_scores[dim] * weights[dim]
        for dim in ["temporal", "spatial", "wisdom", "causality"]
    )
    return abs(recalculated - p_zhongshu_score) < tolerance

def check_compatibility(version_a: str, version_b: str) -> bool:
    """
    检查两个算法版本的事件是否可比较。
    同一版本可比较；不同版本不可直接比较，需分别按各自权重解读。
    """
    return version_a == version_b

def list_versions() -> list[str]:
    """返回所有已注册的算法版本列表"""
    return sorted(FORMULA_REGISTRY.keys())
```

### 4.2 新建 `memory/verify_s2_1_modify01.py`

```python
"""S2-1_modify01 验证脚本 — 算法版本控制"""

from memory.gateway.formula_registry import (
    FORMULA_REGISTRY,
    get_formula,
    verify_p_score,
    check_compatibility,
    list_versions,
)

def main():
    # 测试 1：注册表包含默认版本
    assert "1.0.0" in FORMULA_REGISTRY
    print("[PASS] 1. FORMULA_REGISTRY 包含默认版本 1.0.0")
    
    # 测试 2：get_formula 返回正确权重
    formula = get_formula("1.0.0")
    assert formula is not None
    assert formula["weights"]["temporal"] == 0.2
    assert formula["weights"]["spatial"] == 0.2
    assert formula["weights"]["wisdom"] == 0.3
    assert formula["weights"]["causality"] == 0.3
    print("[PASS] 2. get_formula('1.0.0') 返回正确权重")
    
    # 测试 3：get_formula 对未知版本返回 None
    assert get_formula("9.9.9") is None
    print("[PASS] 3. 未知版本返回 None")
    
    # 测试 4：verify_p_score 验证正确分数通过
    scores = {"temporal": 7, "spatial": 6, "wisdom": 8, "causality": 9}
    expected = 7*0.2 + 6*0.2 + 8*0.3 + 9*0.3  # = 7.7
    assert verify_p_score(scores, expected, "1.0.0") == True
    print("[PASS] 4. 正确分数通过验证")
    
    # 测试 5：verify_p_score 拒绝错误分数
    assert verify_p_score(scores, 9.9, "1.0.0") == False
    print("[PASS] 5. 错误分数被拒绝")
    
    # 测试 6：verify_p_score 对未知版本返回 False
    assert verify_p_score(scores, 7.7, "9.9.9") == False
    print("[PASS] 6. 未知版本返回 False")
    
    # 测试 7：check_compatibility 同版本可比较
    assert check_compatibility("1.0.0", "1.0.0") == True
    print("[PASS] 7. 同版本可比较")
    
    # 测试 8：check_compatibility 不同版本不可比较
    assert check_compatibility("1.0.0", "2.0.0") == False
    print("[PASS] 8. 不同版本不可直接比较")
    
    # 测试 9：list_versions 返回版本列表
    versions = list_versions()
    assert "1.0.0" in versions
    print("[PASS] 9. list_versions() 包含 1.0.0")
    
    print("\nS2-1_modify01 ALL TESTS PASSED")

if __name__ == "__main__":
    main()
```

## 五、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | `formula_registry.py` 创建 | 文件存在，含 `FORMULA_REGISTRY` 字典 |
| 2 | `get_formula()` | 已知版本返回公式，未知版本返回 None |
| 3 | `verify_p_score()` | 正确分数通过，错误分数被拒绝 |
| 4 | `check_compatibility()` | 同版本 True，不同版本 False |
| 5 | `list_versions()` | 返回所有已注册版本 |
| 6 | 验证脚本 | `verify_s2_1_modify01.py` 全部 9 项测试通过 |
| 7 | 已有测试兼容 | `verify_s2_1.py`、`verify_soul.py` 等全部通过 |
| 8 | 不改动 XiMingAdapter | `ximing_adapter.py` 零修改 |

## 六、关键约束

- 公式注册表是慧惠侧的**单一事实来源**，不与小程序侧冗余存储
- `verify_p_score()` 的 `tolerance` 参数默认 0.01，允许合理的浮点精度误差
- 未来新增算法版本时，仅需在 `FORMULA_REGISTRY` 中注册，无需迁移历史数据
- 不修改任何已有的 S2-1 文件

---

*规格结束。请以本文档为唯一执行依据。*