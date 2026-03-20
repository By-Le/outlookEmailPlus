# Issue 记录

## 基本信息

- 记录日期：2026-03-20
- 状态：待修复
- 优先级：P1
- 主题：Outlook OAuth 获取 `client_id` / `refresh_token` 流程存在设计与实现问题

## 问题背景

当前项目在导入 Outlook 邮箱时，要求账号信息格式为：

- `邮箱----密码----client_id----refresh_token`

用户在使用“🔑 获取 Token”功能时，对以下问题存在明显困惑：

1. `client_id` 是什么，是否来自“正常登录微软邮箱”。
2. `refresh_token` 应该如何获取。
3. 当前页面中的“获取 Token”流程是否真的可用。

本轮代码核对后确认：当前功能说明、前端交互、后端安全校验之间存在明显脱节，导致用户即使正常登录微软账号，也很难稳定拿到可导入所需的参数。

## 正确认知

### `client_id` 不是个人邮箱登录后自动生成的

`client_id` 的本质是：

- 一个 Azure / Microsoft OAuth 应用的客户端标识

它不是用户个人 Outlook 邮箱登录后自动产生的值，也不是每个邮箱账号单独生成的值。

在当前仓库中：

- `outlook_web/config.py`
  - `get_oauth_client_id()`
- 默认会读取环境变量：
  - `OAUTH_CLIENT_ID`
- 如果未配置，则回退到仓库内默认值：
  - `24d9a0ed-8787-4584-883c-2fd79308940a`

也就是说，当前导入所需的 `client_id` 实际上是“应用级配置”，不是“用户登录微软邮箱后动态获取”的数据。

### `refresh_token` 才是通过 OAuth 授权换来的

当前设计中，`refresh_token` 的来源应该是：

1. 通过固定的 `client_id`
2. 引导用户打开微软 OAuth 授权链接
3. 用户登录微软账号并授权
4. 浏览器跳转到配置的 `redirect_uri`
5. 从回跳 URL 中取出 `code`
6. 由服务端调用微软 token 接口，把 `code` 换成 `refresh_token`

因此，用户“正常登录微软邮箱”本身并不会直接给出 `refresh_token`，必须经过 OAuth 授权码交换流程。

## 当前实现链路

### 后端

- `outlook_web/controllers/oauth.py`
  - `api_get_oauth_auth_url()`
    - 负责生成微软授权链接
  - `api_exchange_oauth_token()`
    - 负责把回跳 URL 中的 `code` 换成 `refresh_token`

### 前端

- `static/js/main.js`
  - `showGetRefreshTokenModal()`
    - 打开弹窗并请求 `/api/oauth/auth-url`
  - `openAuthUrl()`
    - 新窗口打开微软授权页
  - `exchangeToken()`
    - 读取用户手工粘贴的回跳 URL
    - 调用 `/api/oauth/exchange-token`

### 页面文案

- `templates/partials/modals.html`
  - 当前引导用户：
    - 打开授权链接
    - 手工复制回跳后的完整 URL
    - 再点击“换取 Token”

## 已确认问题

### 问题 1：前端没有传 `verify_token`，后端却强制要求二次验证

这是当前最直接的实现问题。

后端 `api_exchange_oauth_token()` 明确要求：

- 请求体中必须提供 `verify_token`

并会调用：

- `check_export_verify_token(verify_token)`
- `consume_export_verify_token(verify_token)`

如果没有 `verify_token`，后端会返回：

- `需要二次验证`

但当前前端 `exchangeToken()` 实际发送的请求体只有：

- `redirected_url`

没有任何获取 `verify_token` 或传递 `verify_token` 的流程。

这意味着当前“获取 Token”前端流程与后端接口契约不一致，属于功能级缺陷。

## 问题 2：当前交互方式过于脆弱，依赖用户手工复制回跳 URL

当前流程要求用户：

1. 点击打开授权页
2. 在微软页面登录并授权
3. 浏览器跳转到 `redirect_uri`
4. 用户自己复制地址栏完整 URL
5. 再粘贴回系统弹窗

这个方案存在多个稳定性问题：

- 用户容易复制不完整
- 用户不理解为什么要复制 URL
- 回跳地址若配置不对，会直接失败
- 用户会误以为“正常登录微软邮箱”就应该自动得到 token
- 弹窗没有解释 `client_id` 是应用配置，不是个人账号数据

## 问题 3：默认 `OAUTH_REDIRECT_URI` 为 `http://localhost:8080`，对真实部署不友好

当前配置中：

- `outlook_web/config.py`
  - `get_oauth_redirect_uri()`
- 默认值为：
  - `http://localhost:8080`

这意味着如果实际部署环境不是本机 `localhost:8080`，则：

- 微软授权回跳可能与真实访问地址不一致
- 用户看到空白页或异常页
- 即使拿到回跳 URL，也不一定符合当前部署预期

这会进一步放大用户对“获取 Token 功能坏了”的感知。

## 问题 4：产品文案没有把“应用配置”和“账号授权”区分清楚

当前 UI 与数据格式容易让用户误解：

- 以为 `client_id` 是自己登录 Outlook 后就能看到的东西
- 以为 `refresh_token` 是账号密码换出来的
- 以为只要能登录微软邮箱，就能直接拿到导入所需四段式文本

但实际不是：

- `client_id` 是应用级配置
- `refresh_token` 是 OAuth 授权结果
- 账号密码并不是 OAuth token 流程的产物

这会直接导致用户操作路径错误，增加支持成本。

## 影响

- 用户无法清晰理解 Outlook 账号导入所需参数来源
- 当前“获取 Token”功能很可能无法直接正常完成
- 就算个别情况下能完成，也依赖用户手工复制 URL，成功率低
- 用户会误判为微软登录有问题，或误以为系统支持“直接账号密码换 token”

## 建议修复方案

### 一、先修复前后端接口契约不一致

1. 明确 `api/oauth/exchange-token` 是否必须要求 `verify_token`
2. 若必须要求：
   - 前端补充完整的二次验证获取流程
   - 再把 `verify_token` 一并提交
3. 若该场景不应要求二次验证：
   - 后端应调整当前接口策略

### 二、明确区分 `client_id` 与 `refresh_token` 的来源

界面和文档都要明确说明：

1. `client_id` 来自系统配置的 OAuth 应用
2. `refresh_token` 来自用户完成微软授权后的交换结果
3. 普通邮箱登录本身不会直接产生 `refresh_token`

### 三、改造获取 Token 交互

建议从“手工复制回跳 URL”改为更稳定的方式，例如：

1. 使用专用回调页自动接收 `code`
2. 由前端或后端自动完成授权码交换
3. 用户只需完成登录授权，不再手工复制整段 URL

### 四、收紧默认配置和错误提示

1. 对 `OAUTH_REDIRECT_URI` 做部署环境校验
2. 当回调地址明显不匹配时，直接给出明确提示
3. 错误提示应区分：
   - OAuth 配置错误
   - 缺少二次验证
   - 微软授权失败
   - 回跳 URL 无法解析

## 建议验收标准

1. 用户能够在界面上明确知道：
   - `client_id` 是应用配置
   - `refresh_token` 需要通过微软 OAuth 授权获取
2. “获取 Token”功能前后端契约一致，不再出现前端漏传必填字段。
3. 用户无需手工复制整段回跳 URL，也能完成 token 获取。
4. 若配置错误，系统能给出明确可执行的提示，而不是笼统失败。

## 备注

- 本 issue 仅记录问题，不在本次操作中修复代码。
- 当前仓库还存在 Outlook 导入时的 CSRF 相关问题，已另行记录。
