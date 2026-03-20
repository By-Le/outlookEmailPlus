# Issue 记录

## 基本信息

- 记录日期：2026-03-20
- 状态：待修复
- 优先级：P1
- 主题：Outlook 邮箱导入时报错 `The CSRF session token is missing`

## 问题描述

当前项目在 Web 界面导入 Outlook 邮箱时，用户会收到如下错误：

- 用户提示：`请求参数错误`
- 错误码：`HTTP_ERROR`
- 类型：`HttpError`
- 状态码：`400`
- 典型详情：`400 Bad Request: The CSRF session token is missing.`

同一批导入数据在另一个项目中可以正常导入，说明问题不在 Outlook 账号文本格式本身，而在当前项目的请求校验链路。

## 当前定位结论

这不是导入参数格式校验失败，而是导入接口在到达业务逻辑前，被 Flask-WTF 的 CSRF 校验拦截。

当前链路如下：

- `outlook_web/security/csrf.py`
  - 启用了 `CSRFProtect`
- `outlook_web/routes/accounts.py`
  - `POST /api/accounts` 没有豁免 CSRF
- `outlook_web/controllers/pages.py`
  - `GET /api/csrf-token` 负责生成 CSRF token
- `static/js/main.js`
  - 页面加载时先请求 `/api/csrf-token`
  - 对所有非 GET 请求自动追加 `X-CSRFToken`
- `static/js/features/accounts.js`
  - 导入账号时通过 `POST /api/accounts` 提交

## 已确认现象

本地复现结论如下：

1. 登录后直接请求 `POST /api/accounts`，不带有效 CSRF，会返回 400。
2. 先请求 `GET /api/csrf-token` 建立 token 和 session，再带 `X-CSRFToken` 调用导入接口，请求可以成功。
3. 即使请求头里带了 `X-CSRFToken`，只要它不属于当前会话，仍会返回：
   - `The CSRF session token is missing`

这说明当前错误更准确地表示为：

- 请求中的 token 与服务端当前 session 不匹配
- 或服务端当前 session 中根本没有对应的 CSRF token

## 高概率根因

### 1. 页面 token 与当前 session 已失配

典型场景：

- 页面长时间未刷新
- 登录状态变化后继续使用旧页面
- 服务端重启后，浏览器仍使用旧页面中的 token

### 2. session cookie 未稳定携带

典型场景：

- 使用 `localhost` 和 `127.0.0.1` 混用
- 访问域名、端口、反向代理入口不一致
- 代理层未正确转发或保留 cookie

### 3. `SECRET_KEY` 不稳定

当前项目要求 `SECRET_KEY` 必须固定配置。

若服务每次重启都变更 `SECRET_KEY`：

- 已有 session 会全部失效
- CSRF token 与 session 的绑定关系失效
- 页面不刷新时，导入等 POST 请求会直接触发当前错误

相关位置：

- `outlook_web/config.py`
- `.env.example`

### 4. 前端对 CSRF 初始化和失效恢复不够健壮

当前前端虽然会在页面加载时初始化 CSRF token，但还缺少针对以下场景的兜底：

- token 初始化失败后的重试
- 遇到 CSRF 400 时自动重新拉取 token 并重试一次
- 更明确提示“会话失效，请刷新页面后重试”

## 影响范围

- Outlook 邮箱导入
- 其它所有受 CSRF 保护的非 GET 接口理论上也可能受同类问题影响

具体包括但不限于：

- 新增账号
- 编辑账号
- 删除账号
- 批量操作
- 设置保存

因此这不是单一导入功能的孤立问题，而是一次会话态与前端请求恢复机制的问题暴露。

## 为什么另一个项目能正常导入

高概率有以下几种差异：

1. 对方项目未启用同样严格的 CSRF 校验。
2. 对方项目对导入接口做了 CSRF 豁免。
3. 对方项目的 `SECRET_KEY`、session、访问域名和前端请求链路更稳定。

当前仓库尚未对“另一个项目”的实现做代码级对比，但从现象判断，差异点不在导入数据本身。

## 建议修复方案

### 后端侧

1. 保持 `SECRET_KEY` 为稳定固定值，禁止随重启变化。
2. 检查部署入口、代理转发和 session cookie 行为，确保会话链路稳定。
3. 保留导入接口的 CSRF 保护，不建议直接粗暴关闭整站 CSRF。
4. 针对该类错误增加更明确的错误码或错误文案，例如：
   - `会话已失效，请刷新页面后重试`

### 前端侧

1. 页面初始化失败时，补充 CSRF token 拉取失败提示。
2. 在收到以下错误时自动尝试一次恢复：
   - `The CSRF token is missing`
   - `The CSRF session token is missing`
3. 恢复流程建议为：
   - 重新请求 `/api/csrf-token`
   - 更新内存中的 `csrfToken`
   - 对原请求自动重试一次
4. 若重试仍失败，再提示用户刷新页面重新登录。

### 验证侧

1. 补充自动化测试，覆盖：
   - 未带 CSRF token 的 POST 请求
   - token 与当前 session 不匹配的请求
   - 重新获取 token 后重试成功
2. 补充手工验证，覆盖：
   - 正常导入
   - 服务重启后旧页面导入
   - 切换 `localhost` / `127.0.0.1` 的场景
   - 代理部署场景

## 建议验收标准

满足以下条件才算该问题修复完成：

1. 正常页面流转下，Outlook 导入稳定成功。
2. 页面 token 失效时，前端可自动恢复或给出明确可操作提示。
3. 服务重启后不会出现大量“用户需手工排查参数”的误导性报错。
4. 不通过关闭全局 CSRF 的方式规避问题。

## 备注

- 本问题已于 2026-03-20 在当前仓库本地复现确认。
- 当前只完成问题记录与根因收敛，尚未开始代码修复。
- 同轮用户还提到“第二个问题”，但消息未发送完整，待补充后另行记录。
