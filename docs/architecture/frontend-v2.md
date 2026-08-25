# K-town 前端架构 v2

## 1. 目标

前端仍保持可直接打开、无需构建工具的 HTML/CSS/vanilla JS，但把“视图、网络、状态契约、动作路由”分开。这样新增章节、请求、地点或视图时，不需要把业务逻辑散落到模板 inline handler 和多个 `fetch` 调用中。

## 2. 模块边界

```text
templates/index-v2.html
  └── 静态骨架 + data-app-action 标记

static/state-contract-v2.js
  └── normalizeState / normalizeActionResult

static/api-client-v2.js
  └── REST GET/POST + WebSocket player action sender

static/campaign-view-v2.js
  └── 只渲染 campaign payload，不理解 effect

static/town-map-v2.js
  └── 地图 SVG、地点舞台、居民 token；通过 AppV2.onAgentClick 回调

static/app-v2.js
  └── 当前 UI 状态、视图编排、唯一 click router、兼容旧全局入口
```

数据流：

```text
REST / WS
   ↓
normalizeState / normalizeActionResult
   ↓
app-v2 state
   ├── pulse / campaign / today threads / requests
   ├── map stage / profile / dialogue
   └── action router → KTownApi.sendPlayerAction / REST client
```

## 3. 状态契约

`KTownContract.normalizeState(raw)` 为视图提供稳定默认值：

- `tick`：数字，默认 `0`；
- `agents/requests/crises/today_threads/events/knowledge_claims`：数组，缺失时为空数组；
- `locations/location_levels/player/campaign/campaign_markers`：对象，缺失时为空对象；
- 其他服务端字段保留，便于新视图渐进接入。

`normalizeActionResult(raw)` 统一 REST 和 WebSocket 的结果：

- `accepted/status/result/error_code`；
- `cost/hours`；
- `changes/story_beats/next_observation`；
- `details`。

服务端可增加字段，但不应改变这些字段的含义。视图不应依赖数据库列名、Python dataclass 或 effect 字符串。

## 4. 网络边界

`KTownApi` 是唯一网络适配器：

- GET：state、requests、quests、knowledge、dialogue options；
- POST：危机干预、对话执行；
- WebSocket：只发送 `{type: "player_action", action: {...}}`，接收 state、event、day summary、action result。

新增 API 时先在 `api-client-v2.js` 加方法，再由 app/view 调用。视图不得直接调用 `fetch`，主应用也不得直接调用 `ws.send`。

## 5. 事件扩展

### 5.1 静态或动态按钮

按钮声明意图，不声明实现：

```html
<button
  data-app-action="respond-request"
  data-request-id="lina_dry_wood"
  data-option-id="gather">
  去找木料
</button>
```

`setupEventListeners()` 的 click router 读取 `data-app-action` 并调用已存在的动作函数。动态 renderer 只负责生成属性，不绑定 `onclick`。

当前动作意图包括：

| data-app-action | 载荷 | 处理者 |
|---|---|---|
| `switch-tab` | `data-tab` | `switchTab` |
| `respond-request` | request/option ID | `respondRequest` |
| `intervene-crisis` | crisis/action | `interveneCrisis` |
| `context-action` | action type/agent ID | 当前地点动作 |
| `follow-thread` | thread/item index | `followThread` |
| `dialogue-option` | agent/option/text | `executeDialogue` |

### 5.2 兼容入口

地图仍通过 `window.AppV2.onAgentClick`，旧页面调用仍保留少量 `window.movePlayer` 等全局函数。这些是兼容层，不是新增 UI 的推荐入口；新代码必须使用数据属性和事件委托。

## 6. 视图扩展规则

新增章节卡、关系视图或事件册时：

1. 明确输入 payload 和空状态；
2. 放进独立 `*-view-v2.js`，只做展示和发出 data action；
3. 在 `app-v2.js` 只增加一次 render 调用或 action 分支；
4. 所有服务端文本进入 `innerHTML` 前转义，优先 `textContent`；
5. 同时验收桌面、390px 和 reduced-motion；
6. 为契约新增字段补静态/接口测试。

不要：

- 在模板或动态 HTML 中写 inline `onclick`；
- 在每个 renderer 内复制 AP、地点、章节或结局判断；
- 让新章节在 app 主逻辑中出现一串 `if (week === 2)`；
- 用隐藏侧栏解决移动端内容问题；
- 让调试字段成为首屏必需字段。

## 7. 当前已知限制

- vanilla JS 仍由 `app-v2.js` 编排较多旧视图，后续可以按“事件流 / 居民 / 请求 / 历史”继续拆 renderer；
- 目前 WebSocket 是动作通道，REST 是只读/特殊操作通道；若未来需要断线重放，应增加 action idempotency 和 server sequence；
- 视觉地图仍是单地点舞台，章节扩展先依赖侧栏和 marker，不要求马上重做 SVG 地图；
- 当前契约是运行时归一化，不替代未来 TypeScript/schema 生成。若前端复杂度继续上升，再引入编译期类型层。
