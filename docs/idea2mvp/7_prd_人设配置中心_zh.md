# 人设配置中心（给产品经理）

## 1) 现在助手“人设”是怎么生效的

当前回复风格由三层共同决定：

1. **固定默认配置**  
   后端内置了一份默认人设参数，保证即使没有外部配置也能稳定输出。

2. **文件配置（可运营）**  
   `server/config/persona.json` 会覆盖默认值。这个文件适合版本化管理。

3. **用户偏好（个体差异）**  
   用户画像里的 `response_style` 仍会作为个体偏好拼进上下文，实现“同一人设下的个性化讲解”。

最终在每次请求时，后端会把这三部分合成系统提示词，再发给模型。

---

## 2) 已开放给 PM 的能力

新增了一个运维接口（带 token 鉴权）：

- `GET /api/ops/persona-config`：查看当前生效配置
- `POST /api/ops/persona-config`：更新配置（局部字段即可）

支持配置的核心字段：

- `assistant_name`：助手名称
- `mission`：助手目标
- `tone`：说话风格
- `response_sections`：回答结构段落（数组）
- `list_limit`：列表上限
- `markdown_features`：允许的 markdown 能力
- `table_policy`：表格输出策略
- `uncertainty_policy`：不确定场景策略
- `vision_mode`：看图问答策略

---

## 3) PM 的典型操作

### 3.1 看当前配置

```bash
curl -s http://localhost:5001/api/ops/persona-config \
  -H "X-Ops-Token: ops-secret"
```

### 3.2 调整“语气 + 结构”

```bash
curl -s -X POST http://localhost:5001/api/ops/persona-config \
  -H "Content-Type: application/json" \
  -H "X-Ops-Token: ops-secret" \
  -d '{
    "assistant_name": "教编冲刺教练",
    "tone": "更简短、更直接、先结论后行动",
    "response_sections": ["结论", "行动", "风险提醒"],
    "list_limit": 2
  }'
```

---

## 4) 风险控制（避免“改崩”）

后端已做安全兜底：

- 字段类型校验（对象/数组/整数）
- 字段长度限制
- `list_limit` 自动夹紧到 1~6
- 未提供字段保持原值，不会清空全局配置

---

## 5) 推荐上线流程（PM 可执行）

1. 在测试环境先改配置  
2. 用 10 条标准问题回归（概念题/对比题/步骤题/看图题）  
3. 观察三项指标：可读性、稳定性、幻觉率  
4. 通过后再同步到生产环境

---

## 6) 下一步可继续增强

1. 增加“配置版本管理”（草稿、发布、回滚）  
2. 增加“实验开关”（按用户比例灰度）  
3. 增加“效果看板”（不同人设版本的留存与满意度）
