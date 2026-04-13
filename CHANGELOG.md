# Changelog

All notable changes to OutlookMail Plus are documented in this file.

## [v1.15.0] - 2026-04-12

### 新功能 / New Features

- **OAuth Token 获取工具**：新增独立 Token 工具窗口，支持 Authorization Code + PKCE、手动粘贴回调 URL、Scope 校验、JWT 诊断信息展示
- **兼容账号导入模式**：OAuth Token 工具现固定面向个人 Microsoft 账号导入，要求 Public Client、`tenant=consumers`、`client_secret` 为空
- **账号一键写回**：获取到的 refresh token 可直接更新已有 Outlook 账号或创建新账号，并在写入前执行 token 有效性校验与轮换处理
- **配置持久化与环境变量开关**：支持 `oauth_tool_*` Settings 持久化、`OAUTH_TOOL_ENABLED` 总开关，以及 Client ID / Redirect URI / Scope / Tenant 的环境变量默认值

- **分层口径收敛（why）**：分组策略仅保留规则项（`verification_code_length`、`verification_code_regex`），运行期 AI 配置统一迁移到系统设置（settings Basic Tab），避免“分组配置与系统配置双口径”导致的运维混乱。
- **系统级 AI 配置闭环（why）**：`GET/PUT /api/settings` 新增并承载 `verification_ai_enabled/base_url/api_key/model`；API Key 加密存储、脱敏回显；开启 AI 时执行保存期完整性校验。
- **提取链路提速与稳定性（why）**：保持规则快路径优先，仅在低置信度场景触发 AI fallback；AI 输出异常/无效时快速回退规则结果，不阻塞主流程。
- **AI fallback 触发条件收紧（方案 A）**：`enhance_verification_with_ai_fallback()` 由"code/link 任一低置信即触发 AI"调整为"code/link 任一高置信即跳过 AI"；仅在两者均为 low 时才调用 AI，避免"验证码已高置信命中却因链接低置信而白白调用 AI"的浪费。对外仍保留 `verification_code`/`verification_link` 双字段结构不变。
- **固定 JSON 契约（why）**：新增 AI 输入/输出固定 JSON 契约（`verification_ai_v1`），并在服务端进行结构与类型校验，降低模型返回漂移风险。
- **前端迁移策略（why）**：分组弹窗移除 AI 字段，历史 group AI payload 软兼容（忽略旧字段，不硬失败），实现平滑内部切换。

- 修复 Microsoft token 端点仅返回 `error_description` 时无法命中错误引导的问题，现会同时保留 `error` 码用于稳定映射
- 修复工具关闭场景下 Blueprint 已注册但测试期望动态 404 的问题，Controller 层现统一执行开关检查
- 加固 Token 工具的 Scope Chip 渲染逻辑，改为 DOM 创建 + 事件委托，避免将动态 scope 值拼进内联 `onclick`
- 明确 `oauth_tool_client_secret` 的兼容读取策略：历史明文配置继续可读，不可解密的 `enc:` 值保持隐藏为空字符串
- 修复 Token 工具“写入账号”弹窗在校验失败或接口返回 400 时提示被主状态栏遮住、表现为“确认写入没反应”的问题，错误现已直接显示在弹窗内
- 收敛 Token 工具为兼容账号导入模式：前端禁用 `client_secret`、Tenant 固定 `consumers`、默认 Scope 切换到 IMAP 兼容预设，`prepare/config/save` 接口统一拒绝不兼容配置，避免“保存成功但运行态刷新失败”的模型错位

- 新增 `POST /api/settings/verification-ai-test`：基于**已保存**的系统级 AI 配置执行连通性与契约探测，返回结构化诊断结果（`ok/error/message/latency_ms/http_status/parsed_output`）。
- 探测口径调整为“连通性优先”：上游返回 HTTP 2xx 即判定 `ok=true`；同时暴露 `connectivity_ok` 与 `contract_ok` 区分“可连通”与“契约完全通过”。
- 前端“基础 -> 验证码 AI 增强”新增“🤖 测试 AI 配置”按钮与结果提示区，支持在页面内快速判断配置是否真正可用。
- 探测逻辑复用 `probe_verification_ai_runtime(...)`，重点覆盖：配置缺项、HTTP 错误、响应格式错误、AI 输出不符合固定 JSON 契约、探测成功。

## [v1.13.0] - 2026-04-09

### 新功能 / New Features

- **热更新双模式支持**：新增 Watchtower 和 Docker API（A2 helper 容器）两种一键更新方式，支持在设置页面切换
- **Watchtower 集成**：连通性测试、手动触发更新、已是最新版本智能检测（基于 Watchtower 同步行为）
- **Docker API 自更新**：digest 预检查避免无效更新、辅助容器（oep-updater）执行 12 步更新流程、失败自动回滚
- **GHCR 镜像支持**：白名单新增 `ghcr.io/zeropointsix/` 前缀，支持 GitHub Container Registry 镜像
- **版本检测增强**：`_version_gt()` 支持 pre-release 后缀（如 `-hotupdate-test`），自动忽略后缀仅比较语义版本号
- **部署信息 API**：`/api/system/deployment-info` 返回镜像名、标签、本地构建检测、Docker API 可用性
- **healthz 增强**：新增 `boot_id`（进程指纹）和 `version` 字段，支持前端精确检测容器重启

### 修复 / Bug Fixes

- 修复 Watchtower 连通测试 5s 超时（Watchtower 同步检查需 25-30s），增加到 35s
- 修复 Watchtower 200 响应被误判为"更新成功"（实际为"已是最新"）
- 修复 GHCR 镜像不在白名单导致 Docker API 更新被拦截
- 修复本地镜像检测 `_looks_like_local_image_ref()` 误判远程镜像
- 修复 `docker_api_available` 仅检查 Watchtower 不检查 Docker API
- 修复 Docker API 自更新同步调用导致容器停止时响应中断（改为后台线程 + 立即返回）
- 修复 `ModuleNotFoundError: outlook_web.models.AuditLog` 导致更新接口 500
- 修复前端 `waitForRestart()` 无法检测容器真正重启（新增 boot_id 变化检测）

### i18n

- 新增 emoji 前缀 i18n 变体：`🔄 一键更新配置`、`🚀 触发容器更新`
- 新增设置页 Tab 翻译：基础 / 临时邮箱 / API 安全 / 自动化
- 新增连通性/更新状态翻译：连通正常 / 检查完毕 / 测试中 / 更新失败
- `testWatchtower()` 结果文本经过 `translateAppTextLocal()` 翻译
- `manualTriggerUpdate()` 使用 `pickApiMessage()` 实现双语消息

### 安全

- 镜像白名单校验 + RepoDigests 检测双重防护，禁止本地构建镜像触发更新
- Docker API 自更新默认关闭，需显式设置 `DOCKER_SELF_UPDATE_ALLOW=true`
- 更新操作记录审计日志

---

## [v1.11.0] - 2026-04-03

### 新功能 / New Features

- **邮箱池项目隔离（PR#27）**：在 `claim-random` 时支持传入 `project_key`，同一 `caller_id + project_key` 下已使用的账号不会被重复领取（DB 迁移 v17）
- **CF Worker 临时邮箱多域支持**：可在设置页配置多个 CF Worker 域名；新增"同步域名"按钮，支持前端一键刷新域名列表
- **CF Worker Admin Key 加密存储**：`cf_worker_admin_key` 现在以 `enc:` 前缀加密写入数据库，不再以明文存储（DB 迁移 v18）
- **账号列表前端分页**：每页展示 50 条账号，大量账号时滚动加载更流畅
- **统一轮询引擎**：将标准模式与简洁模式的双轮询系统合并为单一 `poll-engine`（4 阶段重构），消除轮询竞争与状态积压

### 修复 / Bug Fixes

- **BUG-06**：生成或删除临时邮箱后，列表中已选中的邮箱状态得到正确保留，不再因刷新而丢失选中高亮
- **BUG-07**：临时邮箱面板在刷新邮件列表后，域名下拉选择不再被意外重置回默认值
- **Issue #24**：修复邮件展开/激活状态在列表重渲染后丢失、i18n 语言切换后账号列表不刷新、视口高度链路断裂、缺失翻译词条等问题
- **轮询 BUG**：修复页面初始加载时触发的批量邮件拉取、分组切换重复启动轮询、跨视图切换时轮询状态积压等问题
- **Graph API 401 静默回退**：修复 token 轮换时 Graph API 401 被静默吞掉导致的 token 丢失问题

### i18n

- 临时邮箱面板域名提示文字（`domain_hint_xxx`）新增中英双语翻译
- CF Worker 域名同步按钮 (`sync_cf_domains`)、提示文字 (`cf_domain_hint`) 新增双语支持
- 补充设置页与轮询指示器等处的缺失翻译词条

### CI / 代码质量修复

- 修复 `pool.py` 中存在的重复函数定义（`release`、`complete`、`expire_stale_claims`、`recover_cooldown`、`get_stats`）
- 修复 `pool.py` `get_stats()` 后的死代码（`return` 之后的不可达 `claim` 函数体）
- 修复 `RESULT_TO_POOL_STATUS` 中 `"success"` 映射：由旧的 `"cooldown"` 改为正确的 `"used"`
- 修复 `get_stats()` 的 `pool_counts` 字典，补充缺失的 `"used": 0` 键
- 修复 `pool.py` `claim_atomic()` 中 black 格式化问题（`cutoff`、`lease_expires_at_str` 多行表达式）
- 在 `external_api.py` 中添加 `# noqa: E203`、`# noqa: C901` 压制 flake8 误报
- 对齐 `test_pool.py` 和 `test_pool_flow_suite.py` 中的测试断言，统一期望 `success` 完成后状态为 `"used"`
- 全量 `black --line-length 127` 与 `isort --profile black` 格式化

---

## [v1.10.0] - 2026-03-26

- OAuth 回归修复与认证后工作区重构

## [v1.9.2] - 2026-03-24

- 小版本修复

## [v1.9.0] - 2026-03-20

- 双语界面、统一通知分发与演示站点保护

## [v1.7.0] - 2026-03-15

- 第二次发布：README 交付口径补全

## [v1.6.1] - 2026-03-15

- 发布质量闸门清理与发布内容精简
