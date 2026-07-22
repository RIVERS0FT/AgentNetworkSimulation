# ADR-033：Dashboard 使用 SceneListItem 字段合同

- 状态：已接受并实现
- 日期：2026-07-22
- 关联需求：SR-SCENE-05
- 扩展决策：ADR-016、ADR-029

## 背景

`GET /api/scenes` 的当前领域合同返回 `SceneListItem[]`，每项使用 `scene_key` 作为稳定剧本标识，使用 `title` 作为用户可见名称。Dashboard 仍按旧结构读取 `name` 和 `format`，导致生成的 `<option>` 值与文本均为 `undefined`，剧本下拉框表现为空，后续还会请求 `/api/scenes/undefined/panel`。

该问题不是剧本资源缺失或目录挂载失败，而是 Web 前端没有同步当前领域模型。前端必须明确区分稳定标识和显示名称，不能依赖不存在的旧字段。

## 决定

1. Dashboard 的剧本下拉框只消费当前 `SceneListItem` 字段合同：
   - `<option>.value` 使用 `scene_key`；
   - `<option>.textContent` 使用 `title`。
2. `scene_key` 继续作为后续剧本配置、启动和资源寻址的输入；`title` 只用于用户界面展示，不作为资源标识。
3. 不在后端增加 `name`、`format` 等别名，也不在前端保留字符串列表或旧对象结构的兼容分支。项目仍处于早期开发阶段，生产者与消费者应直接迁移到同一合同。
4. Dashboard 静态脚本缓存版本从 `v=12` 提升到 `v=13`，确保已打开过页面的浏览器获取修复后的脚本。
5. 增加静态前端契约测试，防止剧本选择器重新读取 `name`、`format` 或遗漏 `scene_key`、`title`。

## 影响范围与不变边界

- 影响：Dashboard 剧本列表渲染、浏览器静态资源缓存键、前端契约测试。
- 不改变：`GET /api/scenes` 的后端响应结构、剧本存储格式、剧本发现与校验规则、仿真生命周期、Agent 容器和网络通信。
- 本 ADR 只固定当前前端对稳定标识和显示名称的映射；`SR-SCENE-05` 后续增加状态、基本信息和查询条件时，仍须扩展 `SceneListItem`，不得以本次修复恢复“永久只返回两个字段”的旧目标合同。

## 被放弃方案

1. **后端补充 `name` 和 `format` 兼容字段**：放弃。该方案会形成无需求的双重字段合同，并掩盖消费者未迁移问题。
2. **前端同时兼容字符串、`name` 和 `scene_key`**：放弃。兼容分支会让错误响应静默通过，增加后续字段迁移成本。
3. **使用 `title` 作为选项值**：放弃。名称可修改且不保证唯一，不能替代稳定的 `scene_key`。

## 迁移、失败与回滚

- 迁移：无持久化数据迁移；刷新页面后浏览器通过 `v=13` 获取新脚本。
- 失败语义：如果后端不满足 `SceneListItem` 合同，列表加载进入现有错误处理路径并在浏览器控制台记录 `loadSceneList` 错误，不回退到旧字段。
- 回滚：同时回滚 Dashboard 字段映射、缓存版本、回归测试和本 ADR；不得只恢复旧字段读取而保留后端当前合同。

## 实现映射

- 前端字段映射：`web/public/dashboard.js` 的 `loadSceneList()`；
- 浏览器缓存版本：`web/public/dashboard.html`；
- 回归测试：`tests/test_dashboard_scene_contract.py`；
- 后端权威模型：`agent_network/scene_management/models.py::SceneListItem`；
- 后端列表入口：`agent_network/api/managed_simulations.py::list_scenes`；
- 相关设计：`docs/design/剧本管理设计.md`。

## 验证

预期验证：

```bash
python -m pytest tests/test_dashboard_scene_contract.py tests/test_scene_manager.py tests/test_docs_layout.py -q
python scripts/check_design_traceability.py
docker compose config
git diff --check
```

2026-07-22 实际结果：

- `python3 -m pytest tests/test_dashboard_scene_contract.py tests/test_scene_manager.py tests/test_docs_layout.py -q`：通过，13 项测试全部通过；
- `python3 scripts/check_design_traceability.py`：通过，识别到 ADR-033、ADR 索引和剧本管理设计记录；
- `node --check web/public/dashboard.js`：通过；
- `docker compose config --quiet`：通过；
- `git diff --check`：通过；
- 运行中服务验证：`/` 已引用 `/static/dashboard.js?v=13`，脚本使用 `s.scene_key` 和 `s.title`，`/api/scenes` 返回 3 个符合合同的剧本列表项。
