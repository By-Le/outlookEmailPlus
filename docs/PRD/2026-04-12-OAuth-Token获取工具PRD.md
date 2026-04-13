# PRD: OAuth Token 获取工具（松耦合集成）

- 文档版本: v1.3
- 创建日期: 2026-04-12
- 目标版本: v1.15.0（待定）
- 文档类型: 功能 PRD
- 优先级: P1 (高频需求)
- 当前范围: 仅讨论功能与需求,不讨论实现方式
- 关联 Issue: #38, #34, #26, #20, #18
- 关联 FD: `docs/FD/2026-04-12-OAuth-Token获取工具FD.md`
- 关联 TD: `docs/TD/2026-04-12-OAuth-Token获取工具TD.md`

> **v1.15.0 实施收口说明（兼容账号导入模式）**
>
> 当前落地实现已不再面向“任意 Azure 应用上下文导入”，而是收敛为与现有购买账号一致的兼容导入模型：
> - 仅支持个人 Microsoft 账号链路
> - Tenant 固定 `consumers`
> - 仅支持 Public Client
> - `client_secret` 不在支持范围内，页面与接口均按空值处理
> - Azure App Registration 的 Supported account types 应使用 **Accounts in any identity provider or organizational directory and personal Microsoft accounts**；仅组织目录会报 `unauthorized_client`，而 **Personal Microsoft accounts only** 会在当前 `/common` 验证链路中触发 `AADSTS9002331`
> - 若 Azure 门户在切换 Supported account types 时提示 `api.requestedAccessTokenVersion is invalid`，需先到 Manifest 将 `api.requestedAccessTokenVersion` 调整为 `2`
>
> 本文中凡是提到“可变 tenant / 可选 client_secret / 单租户或机密客户端支持”的段落，均以本说明为准视为历史设计讨论，不再作为当前实现范围。

---

## 1. 产品背景与目标

### 1.1 背景

当前系统使用 `refresh_token` + `client_id` 访问 Microsoft Graph API 读取邮件,但**没有内置获取 refresh_token 的能力**。

**用户痛点**：
1. 新导入的账号需要从外部工具获取 `refresh_token`,流程割裂（Issue #38）
2. 旧版本曾内置此功能,但因"设计过于麻烦且注册难度较大"而被废弃（Issue #34）
3. 旧版本使用内置 `client_id` 导致 `unauthorized_client` 报错,用户无法自行排查（Issue #26, #20）
4. `refresh_token` 存在 90 天未使用过期的风险,用户需要定期刷新（Issue #18）
5. 部分用户的 `refresh_token` 因密码修改、权限变更等原因失效,需要重新获取

**社区反馈**：
- Issue #38 评论区多位用户确认此功能"很实用"、"感觉还是很多人需要"
- 有用户自行使用外部 Python 脚本或 QuickMSToken 等工具获取 token,体验割裂
- 项目维护者已表态"重新评估一下这个功能"

### 1.2 产品目标

**主目标**: 在系统内提供一个独立的 OAuth Token 获取工具页面,用户可通过浏览器交互式登录 Microsoft 账号,获取 `refresh_token`,并一键写入系统账号。

**具体目标**:
1. 提供独立的 Token 获取页面,不影响主系统现有功能
2. 支持 Authorization Code + PKCE 流程（公共客户端最佳实践）
3. 支持可选的 `client_secret`（机密客户端场景）
4. 兼容多种部署场景（本地/Docker/反向代理/公网）
5. 获取到的 token 可一键写入系统账号记录
6. 可通过环境变量/设置控制是否启用此功能

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **用户自备 client_id** | 不内置任何默认 client_id,避免旧版 `unauthorized_client` 问题重现 |
| **松耦合** | 作为独立 Blueprint 模块,可启用/禁用,不影响核心功能 |
| **部署透明** | 支持手动粘贴回调 URL,解决 Docker/反代 redirect_uri 不匹配问题 |
| **安全优先** | PKCE 强制,client_secret 仅在服务端内存中保留,不写入 URL 或 Cookie |

---

## 2. 核心需求

### 2.1 功能概述

提供一个独立页面 `/token-tool`（路径待定）,包含以下能力:

1. **配置 OAuth 参数**: 用户输入 `client_id`、可选 `client_secret`、`redirect_uri`、权限 scope
2. **发起授权**: 生成 Microsoft OAuth 授权链接,用户在弹窗/新标签页中登录
3. **获取 Token**: 捕获授权码 → 自动换取 `refresh_token` + `access_token`
4. **展示结果**: 显示获取到的 token、实际授权的权限、token audience 等诊断信息
5. **一键写入**: 将 `refresh_token` + `client_id` 写入系统中的指定账号

### 2.2 用户输入表单

| 字段 | 必填 | 说明 | 默认值来源 |
|------|------|------|-----------|
| Client ID | ✅ | Azure 应用注册获取 | 环境变量 `OAUTH_CLIENT_ID` 或上次使用值 |
| Client Secret | ❌ | 机密客户端才需要 | 环境变量 `OAUTH_CLIENT_SECRET` |
| Tenant（租户） | ✅ | 账号类型决定 | 环境变量 `OAUTH_TENANT`，默认 `consumers` |
| Redirect URI | ✅ | 需与 Azure 注册一致 | 自动检测当前访问地址 |
| Scope（权限） | ✅ | 请求的 OAuth 权限列表 | `offline_access https://graph.microsoft.com/.default` |
| 强制 Consent | ❌ | 是否强制弹出权限确认页 | 否 |

**Tenant（租户）说明**:

| Tenant 值 | 适用场景 | 说明 |
|-----------|---------|------|
| `consumers` | 个人 Microsoft 账号（Outlook.com / Hotmail） | 最常见场景,推荐默认值 |
| `common` | 个人 + 组织账号 | 允许两种账号类型登录 |
| `organizations` | 仅组织账号（企业 Azure AD） | 企业/学校邮箱专用 |
| 具体租户 ID | 指定组织 | 限制为特定 Azure AD 租户 |

- UI 采用**下拉 + 可输入**模式: 预设 `consumers` / `common` / `organizations` 三个选项,同时支持手动输入具体租户 ID
- 帮助文字: "个人邮箱选 consumers,企业/学校邮箱选 organizations 或输入租户 ID"

**Scope 管理 UI 需求**:
- 支持 Chip/Tag 形式逐个添加和删除权限
- 提供常用权限预设按钮（Graph 邮件权限、IMAP 权限等）
- 支持粘贴批量导入（逗号/分号/空格/换行分隔）
- `offline_access` 自动补齐（必须有才能返回 refresh_token）

### 2.3 OAuth 授权流程

#### 2.3.1 标准流程（智能回调 + 手动复制）

**页面形态**: Token 工具以**浏览器新窗口** (`window.open`) 形式打开,独立于主页面。

1. 用户填写配置 → 点击「登录 Microsoft」
2. 系统生成 PKCE `code_verifier` + `code_challenge`
3. 系统生成随机 `state` 防 CSRF
4. 打开 Microsoft 授权页面（第二层弹窗）
5. 用户在 Microsoft 页面登录并授权
6. Microsoft 回调 `redirect_uri?code=xxx&state=xxx`
7. 回调页面显示"授权成功,请复制当前地址栏 URL"
8. 用户复制回调 URL → 粘贴到 Token 工具页面的「手动换取」区域
9. 系统校验 `state` → 用 `code` + `code_verifier` 换取 token
10. 展示结果（refresh_token、access_token、诊断信息）

#### 2.3.2 远程部署场景（Docker/反代）

当 `redirect_uri` 与实际部署地址不一致时:

1. 步骤 1-5 同上
2. Microsoft 回调到注册的 `redirect_uri`（可能是 localhost）
3. 用户**手动复制**完整的回调 URL
4. 粘贴到 Token 工具页面的「回调 URL」输入框
5. 点击「换取 Token」
6. 系统从 URL 中解析 `code` 和 `state` → 换取 token

### 2.4 Token 结果展示

获取成功后展示以下信息:

| 字段 | 说明 |
|------|------|
| Refresh Token | 主要获取目标,用于后续访问 |
| Access Token | 当前有效的访问令牌（1小时有效期） |
| Current Client ID | 本次使用的 client_id |
| Requested Scope | 请求的权限 |
| Granted Scope | 实际授权的权限（可能与请求不同） |
| Access Token Audience | token 的 audience（graph.microsoft.com 等） |

所有字段均提供**一键复制**按钮。

### 2.5 一键写入账号

获取到 token 后,提供「写入到账号」功能:

#### 场景 A: 更新已有账号的 token

1. 用户选择系统中已有的账号（下拉搜索,按邮箱匹配）
2. 系统将新的 `refresh_token` + `client_id` 更新到该账号
3. 系统自动执行一次 token 有效性验证
4. 更新成功后账号 status 恢复为 `active`（如果之前因 token 失效变为 inactive）

#### 场景 B: 创建新账号

1. 用户输入邮箱地址（或从登录信息自动提取）
2. 系统用 `refresh_token` + `client_id` 创建新账号记录
3. 自动归入默认分组

### 2.6 与现有导入功能的关系

**定位区分**:

| 功能 | Token 工具 | 账号导入 |
|------|-----------|---------|
| **场景** | 单个账号交互式获取 token | 批量导入已有 token 的账号 |
| **操作** | 浏览器登录 Microsoft 授权 | CSV/文本粘贴 |
| **适用** | 新账号首次获取 / 失效账号重新获取 | 从其他系统迁移大量账号 |
| **前提** | 只需 client_id + Azure 注册 | 需要已有 refresh_token |

**用户引导**: Token 工具页面底部提示 "已有 refresh_token？可使用「账号导入」功能批量添加"

### 2.7 常见错误与用户引导

Token 工具应对 Microsoft OAuth 返回的常见错误提供**明确的中文提示和解决建议**:

| 错误码 | 错误描述 | 常见原因 | 系统引导 |
|--------|---------|---------|---------|
| `unauthorized_client` | 客户端未授权 | Azure 未开启「允许公共客户端流」 | 提示: "请到 Azure 门户 → 身份验证 → 高级设置 → 开启『允许公共客户端流』" |
| `invalid_grant` | 授权码无效 | 授权码过期（通常 10 分钟）或已被使用 | 提示: "授权码已过期或已使用,请重新点击『登录 Microsoft』" |
| `invalid_scope` | 权限无效 | 请求的权限未在 Azure API 权限中添加 | 提示: "请到 Azure 门户 → API 权限 → 添加对应的 Microsoft Graph 委托权限" |
| `redirect_uri_mismatch` | 回调地址不匹配 | Redirect URI 与 Azure 注册的不一致 | 提示: "回调地址不匹配,请确认 Azure 门户中注册的重定向 URI 与当前填写的一致" |
| `interaction_required` | 需要用户交互 | 需要重新授权/MFA | 提示: "请勾选『强制 Consent』后重新授权" |
| `consent_required` | 需要管理员同意 | 组织账号需要管理员审批权限 | 提示: "此权限需要组织管理员同意,请联系 IT 管理员或切换为个人账号" |
| PKCE 校验失败 | code_verifier 不匹配 | 浏览器缓存或会话中断 | 提示: "校验失败,请清除浏览器缓存后重试" |
| 网络错误 | 连接超时/DNS 失败 | 服务器无法访问 Microsoft 端点 | 提示: "无法连接 Microsoft 服务器,请检查网络连接和 DNS 设置" |

### 2.8 配置与开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `OAUTH_TOOL_ENABLED` | 环境变量/设置 | `true` | 是否启用 Token 获取工具 |
| `OAUTH_CLIENT_ID` | 环境变量 | 空 | 默认的 Client ID（用户可在页面覆盖） |
| `OAUTH_CLIENT_SECRET` | 环境变量 | 空 | 默认的 Client Secret |
| `OAUTH_REDIRECT_URI` | 环境变量 | 自动检测 | 默认的 Redirect URI |
| `OAUTH_SCOPE` | 环境变量 | `offline_access https://graph.microsoft.com/.default` | 默认请求的权限 |
| `OAUTH_TENANT` | 环境变量 | `consumers` | 租户类型（consumers/common/organizations） |

**说明**:
- 所有环境变量均为**默认值**,用户可在页面上覆盖
- 用户修改的配置**持久化到服务端 Settings 表**（key 前缀 `oauth_tool_`），跨设备同步
- 配置优先级: 页面输入 > Settings 表 > 环境变量 > 硬编码默认值
- 设为 `OAUTH_TOOL_ENABLED=false` 时,Token 工具页面返回 404,导航入口隐藏

### 2.9 页面形态

**设计决策**: Token 工具以**浏览器新窗口**形式打开（`window.open`）

| 特性 | 说明 |
|------|------|
| 打开方式 | 主页面侧边栏点击 🔑 Token 工具 → `window.open('/token-tool')` |
| 独立模板 | `token_tool.html`，Jinja2 独立渲染，不依赖 index.html |
| 窗口尺寸 | 建议 720×860，可滚动 |
| 关闭影响 | 关闭窗口不影响主页面 SPA 状态 |
| 刷新通知 | 写入账号后，主页面可在下次操作时自动感知新数据 |

---

## 3. 角色与用例

### 3.1 角色定义

| 角色 | 说明 |
|------|------|
| **管理员** | 系统管理者,配置 OAuth 参数,获取 token |
| **Azure 应用持有者** | 在 Azure 门户注册应用的人（通常与管理员同一人） |

### 3.2 核心用例

#### UC-01: 首次获取账号的 Refresh Token

**优先级**: P0
**角色**: 管理员
**前置条件**: 已在 Azure 门户注册应用（获得 client_id,配置了 redirect_uri,开启了公共客户端）

**主流程**:
1. 管理员进入 Token 工具页面（`/token-tool`）
2. 填写 Client ID（如已配置环境变量则自动填充）
3. 确认 Redirect URI（自动检测或手动输入）
4. 确认请求的权限 Scope（默认已包含 Graph 邮件权限）
5. 点击「登录 Microsoft」
6. 在弹窗中使用目标 Outlook 邮箱账号登录
7. 首次使用弹出权限确认页面,点击「接受」
8. 授权成功,页面显示 `refresh_token` 等信息
9. 点击「写入到账号」→ 选择「创建新账号」→ 确认邮箱地址
10. 系统将 `refresh_token` + `client_id` 保存到 accounts 表

**结果**: 新账号入库,状态 active,可正常读取邮件

---

#### UC-02: 更新已失效账号的 Refresh Token

**优先级**: P0
**角色**: 管理员
**前置条件**: 系统中已有账号,但 token 已失效

**主流程**:
1. 管理员进入 Token 工具页面
2. 使用之前的 Client ID（自动记忆上次使用值）
3. 点击「登录 Microsoft」
4. 用目标邮箱账号重新登录授权
5. 获取到新的 `refresh_token`
6. 点击「写入到账号」→ 选择「更新已有账号」→ 搜索选择目标账号
7. 系统更新 `refresh_token`,自动验证有效性

**结果**: 账号 token 更新,状态恢复 active

---

#### UC-03: Docker 远程部署场景获取 Token

**优先级**: P1
**角色**: 管理员
**前置条件**: 系统部署在远程服务器,redirect_uri 指向 localhost

**主流程**:
1. 管理员远程访问 Token 工具页面（如 `http://server-ip:5000/token-tool`）
2. 填写配置,Redirect URI 保持 Azure 注册的 `http://localhost:5000`
3. 点击「登录 Microsoft」
4. 弹窗打开 Microsoft 登录页,完成授权
5. Microsoft 将浏览器重定向到 `http://localhost:5000?code=xxx&state=xxx`
6. 此时 localhost 无法响应（因为实际部署在远程）
7. 管理员从浏览器地址栏**复制完整的回调 URL**
8. 粘贴到 Token 工具页面的「手动换取」输入框
9. 点击「换取 Token」
10. 系统解析 URL 中的 code 和 state,服务端换取 token

**结果**: 远程部署场景也能正常获取 token

---

#### UC-04: 分别获取 Graph 和 IMAP 权限的 Token

**优先级**: P2
**角色**: 管理员
**前置条件**: 需要同时使用 Graph API 和 IMAP 协议

**主流程**:
1. 第一次:设置 Scope 为 `offline_access https://graph.microsoft.com/.default`
2. 完成授权,获取 Graph Token
3. 第二次:设置 Scope 为 `offline_access https://outlook.office.com/IMAP.AccessAsUser.All`
4. 完成授权,获取 IMAP Token

**说明**: Microsoft OAuth 每次只能针对一个资源。系统应在 UI 上明确说明此限制,并提供快捷切换按钮。

---

## 4. 功能范围

### 4.1 本期实现 (P0)

- [ ] 独立的 Token 工具页面 (`/token-tool`)
- [ ] OAuth 参数配置表单（client_id / client_secret / redirect_uri / scope）
- [ ] Authorization Code + PKCE 流程完整实现
- [ ] 弹窗授权模式
- [ ] 手动回调 URL 粘贴换取模式（兼容远程部署）
- [ ] Token 结果展示（refresh_token / access_token / 诊断信息）
- [ ] 一键复制所有结果字段
- [ ] 写入已有账号（更新 refresh_token + client_id）
- [ ] 创建新账号并写入 token
- [ ] 常用 Scope 预设按钮
- [ ] `OAUTH_TOOL_ENABLED` 环境变量开关
- [ ] 主导航栏新增入口（可通过开关隐藏）
- [ ] 常见错误中文提示与解决建议引导
- [ ] Tenant 选择器（下拉 + 可输入）

### 4.2 本期实现 (P1)

- [ ] OAuth 参数自动记忆（session 级别,下次打开自动填充上次配置）
- [ ] Scope Chip/Tag UI（逐个添加删除 + 批量粘贴）
- [ ] 强制 Consent 选项
- [ ] Token 获取后自动验证有效性
- [ ] 写入账号后自动验证邮件读取能力

### 4.3 后续考虑 (P2,不在本期)

- [ ] 批量 token 获取引导（逐个账号的向导式流程）
- [ ] Token 到期预警通知
- [ ] 与设置页面的 client_id 配置统一管理
- [ ] IMAP Token 获取快捷模式

### 4.4 明确不做

- ❌ 不内置任何默认 `client_id`（避免 Issue #26 问题重现）
- ❌ 不支持自动化批量登录（OAuth 要求交互式人工登录,无法自动化）
- ❌ 不做 Azure 应用注册代理（用户自行到 Azure 门户注册）

> **v1.2 更新说明**: `client_secret` 最终设计为**加密存储到 Settings 表**（`encrypt_data()` 加密），支持跨设备同步。早期 v1.0 中"不存储 client_secret"的约束已在 FD 设计阶段（Q4-B 决策）中被修订。

---

## 5. 安全考虑

### 5.1 OAuth 安全

| 措施 | 说明 |
|------|------|
| PKCE 强制 | 即使是公共客户端,也使用 code_challenge/code_verifier |
| State 防 CSRF | 随机生成 state 参数,回调时校验 |
| client_secret 保护 | 加密存储到 Settings 表（`encrypt_data()`），运行时仅在服务端内存中使用,不出现在 URL 或 Cookie |
| Flow TTL | 未完成的 OAuth 流程自动过期清理（默认 20 分钟） |

### 5.2 系统安全

| 措施 | 说明 |
|------|------|
| 需要系统登录 | Token 工具页面受现有登录认证保护 |
| 敏感数据加密 | 写入 accounts 表的 refresh_token 使用现有加密机制 |
| 功能开关 | 不需要时可通过 `OAUTH_TOOL_ENABLED=false` 完全禁用 |

---

## 6. UI/UX 需求

### 6.1 页面入口

- 主导航栏新增「Token 工具」入口（图标建议: 🔑 或钥匙图标）
- 仅在 `OAUTH_TOOL_ENABLED=true` 时显示

### 6.2 页面布局

**区域划分**:

```
┌─────────────────────────────────┐
│  📘 快速指引（可折叠）            │
│  Azure 应用注册 4 步指引...       │
├─────────────────────────────────┤
│  ① OAuth 配置区                  │
│  [Client ID] [Client Secret]    │
│  [Tenant ▼ ] [Redirect URI]     │
│  [Scope: chip chip chip +]      │
│  [☐ 强制 Consent]               │
│  [🔵 登录 Microsoft]             │
├─────────────────────────────────┤
│  ② 手动回调区（可折叠）           │
│  [粘贴回调 URL ___________]      │
│  [🔄 换取 Token]                 │
├─────────────────────────────────┤
│  ③ 结果展示区                    │
│  Refresh Token: ****  [📋复制]   │
│  Access Token:  ****  [📋复制]   │
│  Client ID:     ****  [📋复制]   │
│  Requested Scope: ...           │
│  Granted Scope:   ...           │
│  Audience:        ...           │
│  [💾 写入到账号]                  │
└─────────────────────────────────┘
```

### 6.3 交互细节

- 「登录 Microsoft」按钮: 打开弹窗进行授权（弹窗关闭后自动同步结果）
- 「手动回调区」默认折叠,点击展开（UI 提示: "如果弹窗授权后跳转到了 localhost,请在此手动粘贴回调 URL"）
- 「写入到账号」按钮: 弹出对话框,可选择「更新已有账号」或「创建新账号」
- 所有操作需有 loading 状态和错误提示

---

## 7. 部署与兼容性

### 7.1 部署场景兼容矩阵

| 部署方式 | 弹窗模式 | 手动粘贴模式 | 说明 |
|----------|---------|-------------|------|
| 本地直接运行 | ✅ | ✅ | redirect_uri 与访问地址一致 |
| Docker (同机访问) | ✅ | ✅ | redirect_uri 指向 localhost |
| Docker (远程访问) | ⚠️ | ✅ | redirect_uri 可能不匹配,需手动粘贴 |
| 反向代理 | ⚠️ | ✅ | 需正确配置 redirect_uri |
| 公网部署 | ✅ | ✅ | redirect_uri 使用公网地址 |

### 7.2 Azure 应用注册指引

**呈现方式**: Token 工具页面顶部提供**可折叠的「快速指引」卡片**,首次访问默认展开,关闭后记住状态。

**指引内容**（分步骤,每步配文字说明 + Azure 门户直达链接）:

**步骤 1: 注册应用**
- 进入 [Azure 门户 - 应用注册](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
- 点击「新注册」
- 名称: 自定义（如 "OutlookEmailPlus"）
- 受支持的账户类型: 选择「仅个人 Microsoft 账户」（对应 `consumers` 租户）
- 重定向 URI: 选择「Web」,填入 `http://localhost:5000/token-tool/callback`（根据实际部署调整）

**步骤 2: 开启公共客户端**
- 进入应用 →「身份验证」
- 页面底部「高级设置」→ 将「允许公共客户端流」设为「是」
- ⚠️ **这一步最容易遗漏,缺失会导致 `unauthorized_client` 错误**

**步骤 3: 配置 API 权限**
- 进入应用 →「API 权限」→「添加权限」
- 选择「Microsoft Graph」→「委托的权限」
- 添加: `offline_access`、`Mail.Read`、`User.Read`（按需添加更多）
- 对于 IMAP 场景: 选择「我的组织使用的 API」→ 搜索「Office 365 Exchange Online」→ 添加 `IMAP.AccessAsUser.All`

**步骤 4: 获取 Client ID**
- 回到应用「概述」页面
- 复制「应用程序(客户端) ID」
- 粘贴到 Token 工具的 Client ID 输入框

---

## 8. 与现有系统的交互

### 8.1 数据写入

Token 工具写入的数据使用现有 `accounts` 表结构:

| 字段 | 来源 |
|------|------|
| `email` | 用户输入或从授权信息提取 |
| `client_id` | Token 工具配置表单 |
| `refresh_token` | OAuth 流程获取（加密存储） |
| `account_type` | `outlook` |
| `status` | `active` |

### 8.2 不影响的现有功能

- ✅ 邮件读取（Graph API / IMAP）
- ✅ 定时刷新 refresh_token
- ✅ 邮箱池
- ✅ 导入导出
- ✅ 对外 API

---

## 9. 指标与验收标准

### 9.1 功能验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| A-01 | 基本流程 | 用户可通过 Token 工具获取 refresh_token |
| A-02 | 写入账号 | 获取的 token 可成功写入系统账号 |
| A-03 | Token 有效性 | 写入的 token 可正常读取邮件 |
| A-04 | 远程兼容 | Docker 部署场景可通过手动粘贴完成流程 |
| A-05 | 功能开关 | `OAUTH_TOOL_ENABLED=false` 时页面不可访问 |
| A-06 | 错误处理 | 授权失败/token 换取失败有明确中文错误提示和解决建议 |
| A-07 | Azure 指引 | 页面内嵌 Azure 注册指引,可折叠,内容完整 |
| A-08 | 多租户 | 支持 consumers/common/organizations 及自定义租户 ID |

---

## 10. 参考资料

- [Microsoft OAuth 2.0 授权码流程文档](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- Issue #38: https://github.com/ZeroPointSix/outlookEmailPlus/issues/38
- Issue #34: https://github.com/ZeroPointSix/outlookEmailPlus/issues/34
- 参考项目: [QuickMSToken](https://github.com/somnifex/QuickMSToken)
- 参考文章: [Python实现Microsoft邮件自动化：OAuth2.0认证与邮件处理详细指引](https://nblog.xxq.pp.ua/article/17938566-1c0c-80c6-96a4-d6b7b84b4461)
