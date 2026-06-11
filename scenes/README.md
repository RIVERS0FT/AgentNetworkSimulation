# Scenes — 剧本编译器

`scenario.py` 将自然语言想法编译为多 Agent 仿真剧本。

## 用法

### 前置条件

```bash
pip install httpx
```

环境变量 `ANTHROPIC_API_KEY` 设置为 DeepSeek API Key（`sk-` 格式）。建议写入 `.env` 文件（已在 `.gitignore` 中）。

### 命令行

```bash
python scenes/scenario.py -i "<一句话想法>" -d <输出目录>
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i` `--idea` | 剧本想法或背景描述 | 新能源项目并网审批示例 |
| `-d` `--dir` | 输出目录 | `./scenarios/energy_project_v1` |

### 示例

```bash
python scenes/scenario.py \
  -i "一个关于电信运营商市场竞争博弈及内部协作的剧本" \
  -d ./scenes/telecom_operator_v1
```

---

## 输出

每次运行生成两个目录。

### 标准包 (`<dir>/`)

| 文件 | 用途 |
|------|------|
| `meta_and_roles.json` | 元数据、角色定义、终止条件 |
| `instances_and_skills.json` | 每个角色绑定的技能列表 |
| `network_topology.json` | 子网划分与通信连线 |
| `skills.py` | 技能可执行 Python 代码 |

### 合并包 (`<dir>_merged/`)

| 文件 | 用途 |
|------|------|
| `skills.py` | 同上（复制） |
| `<name>_merged.json` | 三合一：角色 + peers + skills 合并为单文件 |

> 合并 JSON 从 3 个来源聚合：角色定义来自 `meta_and_roles`、`peers` 从拓扑 `edges` 双向推导、`skills` 提取自 `instances_and_skills`。

---

## 数据字典

### 1. meta_and_roles.json

#### `scenario_metadata`

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 剧本名称 |
| `global_rules` | string | 仿真世界规则与约束 |
| `max_rounds` | int | 硬上限轮数（3-30），到达后强制终止 |
| `stalemate_rounds` | int | 僵局阈值（2-10），连续无消息达此轮数则终止 |

#### `roles`

Key 为角色 ID，Value 对象：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 角色名称 |
| `model_backbone` | enum | 底层模型基座：`openclaw` / `claudecode` |
| `identity` | string | 角色身份与组织背景 |
| `core_goal` | string | 量化目标（含时限或指标） |
| `primary_interaction_paradigm` | enum | `INTERNAL_COLLABORATION` / `EXTERNAL_NEGOTIATION` / `ZERO_SUM_GAME` |

---

### 2. instances_and_skills.json

#### `container_instances`

Key 为角色 ID，Value 对象：

| 字段 | 类型 | 说明 |
|------|------|------|
| `skills` | string[] | 该角色绑定的技能名称列表，与 `skills.py` 中注册名一致 |

> Docker 镜像由 `model_backbone` 决定，映射见 `container_runtime.py` 的 `BACKEND_CONFIG`。

---

### 3. network_topology.json

#### 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `global_topology_type` | enum | `STAR` / `MESH` / `TREE` / `RING` / `HYBRID_MESH` |
| `sub_networks` | object[] | 子网络列表 |

#### `sub_networks` 元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `sub_id` | string | 子网唯一标识 |
| `topology_type` | enum | 局部拓扑类型 |
| `description` | string | 该层网络的业务含义 |
| `nodes` | string[] | 包含的角色 ID 数组 |
| `edges` | object[] | 连线列表 |

#### `edges` 元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 源角色 ID |
| `target` | string | 目标角色 ID |
| `paradigm` | enum | `COLLABORATION` / `NEGOTIATION` / `GAME` |
| `channel_id` | string | 通信通道标识 |

---

### 4. skills.py

可独立运行的 Python 模块。

```python
from scenes.network_collaboration_merged.skills import SkillRegistry

SkillRegistry.execute("allocate_budget", department="研发部", amount=50000)
# → {"status": "success", "result": "Budget allocated", "data": {...}}
```

| 方法 | 说明 |
|------|------|
| `register(name, func)` | 注册技能函数 |
| `execute(name, **kwargs)` | 调用技能，返回 `{"status", "result", "data"}` |
| `_skills` | 类变量 dict，存储所有已注册技能 |

返回值结构：

```json
{ "status": "success | error", "result": "<可读结果>", "data": { "<具体数据>" } }
```

每个技能函数接受 `**kwargs`，内置参数校验与仿真逻辑，文件末尾通过 `SkillRegistry.register()` 注册。

---

### 5. `<name>_merged.json`（合并包）

#### 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `scenario_metadata` | object | 同 meta_and_roles |
| `global_topology_type` | string | 同 network_topology |
| `roles` | object | 角色集合，Key 为角色 ID |

#### `roles` 元素（在原字段基础上新增）

| 字段 | 类型 | 说明 |
|------|------|------|
| `peers` | string[] | 可通信的角色 ID 列表，从拓扑 edges 双向推导 |
| `skills` | string[] | 该角色绑定的技能名称列表 |
