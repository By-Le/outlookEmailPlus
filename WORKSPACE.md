# WORKSPACE — 工作区操作记录

> 本文档记录项目开发过程中的操作日志，按日期倒序排列。

---

## 2026-04-09

### 操作记录

#### 7. CF临时邮箱接入邮箱池：Phase 1-3 实现 + 部分测试通过

**时间**：2026-04-09

**目标**：实现 CF 临时邮箱接入邮箱池的核心链路（动态创建 claim + 智能删除 complete）。

**实际完成内容**：

**Phase 1: DB Schema v19** ✅
- `outlook_web/db.py`：`DB_SCHEMA_VERSION = 19`，新增 `temp_mail_meta TEXT` 列
- 迁移幂等：重复启动不报错
- 新增唯一索引 `idx_pool_claim_token`、`idx_pool_tasks_unique`

**Phase 2: Pool - claim 动态创建** ✅
- `outlook_web/repositories/pool.py`：
  - 新增 `insert_claimed_account()` — 纯 DB 写入（INSERT accounts + claim_log + project_usage）
  - 移除了对 `services.temp_mail_provider_cf` 的违规导入（架构修复）
- `outlook_web/services/pool.py`：
  - 新增 `_create_cf_mailbox_for_pool()` — 调用 CF Provider 创建邮箱
  - 新增 `_delete_cf_mailbox_nonblocking()` — 非阻塞删除远程 CF 邮箱
  - `claim_random()` 增强：池空且 provider=cloudflare_temp_mail 时动态创建
  - Provider 白名单校验：None/'' + 现有 provider + cloudflare_temp_mail

**Phase 3: Pool - complete 智能删除** ✅
- `services/pool.py` `complete_claim()` 增强：
  - 事务提交后判断 `result in ('success', 'credential_invalid')` 才调用远程删除
  - 删除失败非阻塞：仅 warning 日志，不影响本地状态流转
  - 其他 result（timeout/network_error/provider_blocked）不触发删除

**Phase 5 部分测试** ✅
- `tests/test_module_boundaries.py`：3/3 通过（验证 repositories 不依赖 services）
- `tests/test_pool_cf_integration_tdd_skeleton.py`：18/18 通过
- `tests/test_pool.py`：全部通过（Repository + Service + API）
- `tests/test_pool_flow_suite.py`：全部通过
- Pool 相关 70 测试总耗时 4.4s，0 failures
- 全量测试套件无 FAIL、无 ERROR

**修改文件清单**：
- `outlook_web/db.py` — Schema v19 迁移（+143 行）
- `outlook_web/repositories/pool.py` — 新增 `insert_claimed_account()`，移除 CF 导入（+155 行）
- `outlook_web/services/pool.py` — CF 动态创建/删除逻辑（+219 行）
- `tests/test_db_migration_task_token_unique.py` — 适配新迁移
- `tests/test_pool.py` — 新增 CF 相关 Service/Repository 测试（+153 行）
- `tests/test_pool_flow_suite.py` — 适配增强逻辑（+51 行）
- `tests/test_pool_cf_integration_tdd_skeleton.py` — **新增** 18 个 TDD 骨架测试

**架构约束验证**：
- Route → Controller → Service → Repository 分层严格保持
- Repository 层不依赖任何 Service（包括 temp_mail_provider_cf）
- CF 上游调用（create_mailbox / delete_mailbox）全部在 Service 层

**待完成**：
- ~~Phase 0: 文档对齐收尾（PRD/FD/TD 接口名/schema 版本）~~ ✅ 已完成
- ~~Phase 4: external 读信链路适配（mailbox_resolver 识别 CF pool 账号）~~ ✅ 已完成
- Phase 5: 补充 external 读信链路测试、DB v19 迁移测试
- Phase 6: 联调与验收

#### 7b. Phase 0 文档对齐收尾

**时间**：2026-04-09

**操作内容**：
- PRD：6 处修改
  - `§2.4.1` 标题和所有 `/claim` 引用 → `claim-random`
  - "加密存储" → "明文 JSON 存储"（JWT 已签名，本期不额外加密）
- FD：3 处修改
  - 数据流图和参考资料中 `/claim` → `claim-random`
- TD：4 处修改
  - `Schema v18` → `Schema v19`
  - 所有 `/claim` 引用 → `claim-random`
- TODO：Phase 0 任务全部标记为 `[x]`

#### 7c. Phase 4 读信链路适配 + 真实 E2E 测试

**时间**：2026-04-09

**操作内容**：

1. **mailbox_resolver.py 适配**：
   - CF pool 账号（`provider='cloudflare_temp_mail'`）→ 返回 `kind='temp'`
   - meta 从 `accounts.temp_mail_meta` 解析，包含 `provider_jwt`
   - 外部读信链路自动走 `TempMailService → CF Provider → 真实 CF Worker API`

2. **真实 CF Worker E2E 测试**（`tests/test_pool_cf_real_e2e.py`）：
   - CF Worker: `https://temp.zerodotsix.top` + 真实 admin key
   - E2E-01: claim-random → 真实创建 CF 邮箱 ✅
   - E2E-02: 读取邮件列表（新邮箱为空，正确返回 404）✅
   - E2E-03: complete(success) → 远程 CF 邮箱已删除 ✅
   - E2E-04: complete(verification_timeout) → 远程邮箱保留 ✅
   - 4/4 全部通过（11.961s）

3. **测试结果汇总**：
   - Pool 相关 70 测试（含 TDD 骨架）：0 failures, 1 skipped
   - 真实 E2E 4 测试：0 failures
   - 模块边界测试 3/3 通过

**修改文件**：
- `outlook_web/services/mailbox_resolver.py` — 新增 CF pool 账号 → `kind='temp'` 逻辑
- `outlook_web/services/refresh.py` — 排除 CF pool 账号进入 OAuth 刷新链路（`provider='cloudflare_temp_mail'`）
- `tests/test_pool_cf_real_e2e.py` — **新增** 真实 CF Worker E2E 测试（4 个用例）
- `tests/test_pool_cf_integration_tdd_skeleton.py` — E2E mock 测试 skip（已由真实 E2E 替代）

#### 7d. Phase 6 风险修复 + 联调验收

**时间**：2026-04-09

**发现并修复的风险**：
- CF pool 账号（account_type='outlook'）会被 `refresh.py` 误选入 OAuth token 刷新链路
- 修复：`is_refreshable_outlook_account()` 新增 `provider` 参数，排除 `cloudflare_temp_mail`
- 修复：`build_refreshable_outlook_account_where()` SQL 新增 `provider != 'cloudflare_temp_mail'` 条件
- 验证：refresh 测试 7/7 通过

**Phase 6 进度**：
- ✅ Task 6.1: 本地联调脚本（已被真实 E2E 覆盖）
- ✅ Task 6.3: 日志与审计（claim/complete audit 有 provider、account_id、result）
- ✅ Task 6.4: 风险清单复核（refresh 排除 + 缓存依赖已通过 E2E 验证）
- ✅ Task 6.5: 验收清单（claim → read → complete 全链路真实验证通过）

#### 7e. Phase 6.2 前端 UI 保护 + 后端删除/编辑守卫

**时间**：2026-04-09

**操作内容**：

1. **前端 UI 保护**（`static/js/features/groups.js`）：
   - `getProviderLabel()` 新增 `cloudflare_temp_mail: 'CF 临时邮箱'` 标签
   - 新增 `isCfPoolAccount` 变量，识别 CF pool 账号
   - CF pool 账号的编辑和删除按钮设为 `disabled` + `opacity:0.3` + 提示文案

2. **后端删除保护**（`outlook_web/controllers/accounts.py`）：
   - `api_delete_account()` 新增 CF pool 检查，返回 403
   - `api_delete_account_by_email()` 新增 CF pool 检查，返回 403
   - `api_batch_delete_accounts()` 新增 CF pool 跳过逻辑
   - `api_update_account()` 新增 CF pool 检查，返回 403

3. **全量测试**：917 测试通过，0 failures

**修改文件**：
- `static/js/features/groups.js` — CF provider 标签 + 编辑/删除按钮禁用
- `outlook_web/controllers/accounts.py` — 删除/编辑 CF pool 账号保护（4 处）

#### 7f. 临时邮箱页面 CF 域名下拉不显示：BUG 确认 + 方案 A 选定 + 文档对齐更新

**时间**：2026-04-09

**背景**：在验收 CF Worker 临时邮箱/邮箱池接入时发现一个前端体验 BUG —— 设置页已同步的 CF 域名在「⚡ 临时邮箱」页选择 `cloudflare_temp_mail` provider 后，域名下拉不展示。

**根因结论**（已记录到 BUG 文档）：
- `/api/temp-emails/options` 当前不支持按 provider 返回（始终按全局 runtime provider 返回 options）
- `CloudflareTempMailProvider.get_options()` 读取的是 `temp_mail_*` key，但设置页同步写入的是 `cf_worker_*` key，导致 domains 为空

**本次决策**：确认采用 **修复方案 A（推荐）**
- options API 支持 `provider_name` 参数（后端按 provider 返回 options）
- CF provider 的 options 读取口径切换为 `cf_worker_*`
- 前端请求 options 时携带当前选择的 provider

**本次实际操作**（按“以代码为准”修正文档）：
- 更新/对齐文档：
  - `docs/FD/2026-04-09-CF临时邮箱接入邮箱池FD.md`（修正“读信无需改动/解析返回 kind=account/account_type=temp_mail”等不准确描述；强调 resolver 返回 `kind='temp'`）
  - `docs/TD/2026-04-09-CF临时邮箱接入邮箱池TD.md`（修正“Repository 层进行网络调用”的伪代码与函数命名；对齐实际实现：网络调用在 Service，Repository 仅 DB 写入）
  - `docs/TODO/2026-04-09-CF临时邮箱接入邮箱池TODO.md`（补齐 Phase 4/6 的已完成勾选，保持与 WORKSPACE 的真实进度一致）
  - `docs/BUG/2026-04-09-临时邮箱-CF域名配置不生效-Options口径不一致BUG.md`（状态更新为“已确认方案 A，待实施”）

#### 7g. BUG 修复实施完成 + 人工验收通过（含一次配置值误报排查）

**时间**：2026-04-09

**实施内容**：

1. **方案 A 落地**：
   - `/api/temp-emails/options` 支持 `provider_name` 参数（后端按 provider 返回 options）
   - `TempMailService.get_options(provider_name=...)` 支持按 provider 取配置
   - 前端 `loadTempEmailOptions()` 带 provider 查询参数

2. **v0.3.1 快速修复**：
   - `CloudflareTempMailProvider.get_options()` 增加自动同步逻辑：
     - 当 `cf_worker_domains` 为空且 `cf_worker_base_url` 已配置时，自动请求 `GET {base_url}/open_api/settings`
     - 成功后写回 `cf_worker_domains` / `cf_worker_default_domain`
     - 失败非阻塞（warning）

3. **人工验收（真实环境）**：
   - provider=CF 后域名下拉可见（`zerodotsix.top`, `outlookmailplus.tech`）
   - 指定域名创建邮箱成功

4. **现场故障排查记录**：
   - 现象：创建时报 `UNAUTHORIZED` / 502
   - 根因：`cf_worker_admin_key` 配置值错误（写入了 `admin123`，实际应为 `1234567890-=`）
   - 结论：非代码保存链路缺陷，修正配置值后恢复

#### 7h. 文档二次对齐收尾（按“代码与测试结果为准”）

**时间**：2026-04-09

**目标**：将 `FD/TD/TODO/BUG` 与当前实现、真实人工验收、全量测试结果一致化，清理历史“计划态/样例态”描述。

**本次对齐动作**：

1. `docs/TODO/2026-04-09-CF临时邮箱接入邮箱池TODO.md`
   - 将全量测试从 `917/917` 更新为 `919/919`
   - 明确 claim/complete audit 当前字段覆盖现状（claim-complete 额外 provider 标为后续增强）
   - 明确 `mailbox_resolver` + external read 最小链路已由真实 E2E 覆盖
   - 文末声明更新为“已持续回填，默认以代码和测试为准”

2. `docs/FD/2026-04-09-CF临时邮箱接入邮箱池FD.md`
   - 修正测试文件引用：去除不存在的 `test_pool_cf_integration.py / test_external_pool_cf_e2e.py / test_pool_cf_contract.py`
   - 对齐当前实际测试文件：`test_pool_cf_integration_tdd_skeleton.py`、`test_pool_cf_real_e2e.py`、`test_temp_emails_api_regression.py`、`test_temp_mail_provider_cf.py`
   - 调整“文档更新”章节为当前仓库状态描述（CHANGELOG/API 文档按可选同步）

3. `docs/TD/2026-04-09-CF临时邮箱接入邮箱池TD.md`
   - 将“动态创建在 claim_atomic 中调用 `_create_cf_temp_email_for_pool()`”改为真实实现：Service 层 `_create_cf_mailbox_for_pool()` + Repository `insert_claimed_account()`
   - 将 external claim-random 示例对齐为当前 controller 结构（返回字段以当前实现为准）
   - 修正里程碑与验收项：标注已完成项、待发布项、测试结果（919/919）
   - 将不存在测试文件替换为当前真实文件

4. `docs/BUG/2026-04-09-临时邮箱-CF域名配置不生效-Options口径不一致BUG.md`
   - 状态改为“已修复”
   - 补充 v0.3.1 自动同步实现与人工验收结论
   - 补充“UNAUTHORIZED 为配置值错误而非保存链路缺陷”的排查记录

**验证**：
- 重点回归：`tests.test_temp_mail_provider_cf` + `tests.test_temp_emails_api_regression` 通过
- 全量测试：`python -m unittest discover -s tests -v` → `Ran 919 tests ... OK (skipped=7)`

#### 7i. README 与对外接口文档同步更新（面向接入方）

**时间**：2026-04-09

**背景**：在完成 CF 临时邮箱接入池能力与人工验收后，补齐对外可见文档，避免接入方沿用旧字段/旧错误码。

**本次更新文件**：

1. `README.md`
   - 补充 CF 临时邮箱最近更新：
     - options 支持 `provider_name`（前端切换 provider 时域名下拉正确联动）
     - v0.3.1 自动同步 domains（`cf_worker_domains` 为空时自动回源）
     - `cf_worker_admin_key` 配置不一致会导致 `UNAUTHORIZED` 的注意事项
   - 在核心能力中补充 `provider=cloudflare_temp_mail` 且池空动态创建
   - 在环境变量说明中补充 CF Worker 对应项（并注明设置页 key 名）

2. `注册与邮箱池接口文档.md`
   - `claim-random` 的 `provider` 可选值补全：`outlook/imap/custom/cloudflare_temp_mail`
   - 明确 `provider=cloudflare_temp_mail` 且池空时会动态创建
   - 成功返回字段补全：`email_domain`、`claimed_at`
   - 错误码对齐：`NO_AVAILABLE_ACCOUNT` → `no_available_account`
   - 补充 `claim-complete` 下 CF 删除策略（success/credential_invalid 删除，失败非阻塞）

3. `registration-mail-pool-api.en.md`
   - 与中文接口文档做同口径同步（provider 枚举、动态创建行为、返回字段、错误码大小写、CF 删除策略）

**结果**：
- 接入方文档与当前实现保持一致，减少对接歧义和现场排障成本。

---

#### 4. CF临时邮箱接入邮箱池：文档补齐 + TDD 编写

**时间**：2026-04-09

**目标**：按“文档先行”流程补齐该功能的文档链路，并在进入实现前完成 TDD（测试设计文档）。

**本次实际操作**：

- 确认 PRD 已存在：`docs/PRD/2026-04-09-CF临时邮箱接入邮箱池PRD.md`
- 编写/补齐（当前工作区内为未提交状态）：
  - `docs/FD/2026-04-09-CF临时邮箱接入邮箱池FD.md`
  - `docs/TD/2026-04-09-CF临时邮箱接入邮箱池TD.md`
  - `docs/TDD/2026-04-09-CF临时邮箱接入邮箱池-TDD.md`

**关键内容**：

- 明确测试目标：动态创建、智能删除、兼容不破坏、外部 API 契约稳定
- 明确测试分层：Repository → Service → Controller →（可选）external 读信链路
- 明确 Mock 策略：禁止真实网络，统一 patch `CloudflareTempMailProvider.*`

**对话规范**：后续需求确认/方案选择/完成前反馈，统一通过“寸止 MCP”进行。

#### 5. 文档与代码现状对齐：schema 版本与项目地图修正

**时间**：2026-04-09

**目标**：在“充分阅读源代码”后，将仓库内关键说明文档与代码现状对齐，并记录本次操作。

**本次实际操作**：

- 对照源码确认：
  - `outlook_web/__init__.py` 版本号为 `1.13.0`
  - `outlook_web/db.py` 当前 `DB_SCHEMA_VERSION = 19`（含 v18: accounts 新增 `temp_mail_meta`）
- 修正文档不一致处：
  - `CLAUDE.md`：
    - `outlook_web/__init__.py` 版本号注释 `v1.12.0` → `v1.13.0`
    - `db.py` schema 注释 `v18` → `v19`
    - Database 章节 `schema v18` → `schema v19`
  - `docs/项目地图.md`：
    - “凭据加密（schema v18）” → “（schema v19）”
    - “数据库迁移框架（v18）” → “（v19）”

**说明**：本次仅做“事实对齐”的最小改动，不调整原有结构与叙事。

#### 6. 深读主链路源码并对齐 CF 邮箱池文档（external_pool 路由实际为 claim-random/claim-complete）

**时间**：2026-04-09

**目标**：按“以源码为准”的原则深读邮箱池/CF Provider/外部 API 安全链路，并将 FD/TD 文档中的接口路径与行为描述对齐到当前实现。

**本次实际操作（可核对点）**：

- 深读源码文件（节选）：
  - `outlook_web/routes/external_pool.py`：外部邮箱池路由实际为
    - `POST /api/external/pool/claim-random`
    - `POST /api/external/pool/claim-release`
    - `POST /api/external/pool/claim-complete`
    - `GET  /api/external/pool/stats`
  - `outlook_web/controllers/external_pool.py`：claim-random/complete/release 的参数透传与 audit 逻辑
  - `outlook_web/security/external_api_guard.py`：公网模式下的 IP 白名单、限流、功能开关（feature 禁用）
  - `outlook_web/repositories/pool.py`：provider=cloudflare_temp_mail 时无可用邮箱会动态创建；complete 后按结果非阻塞删除远程 CF 邮箱
  - `outlook_web/services/temp_mail_provider_cf.py`：CF Worker API 适配（x-admin-auth / Bearer jwt），meta 标准化（provider_jwt/provider_mailbox_id/provider_capabilities）

- 文档对齐改动：
  - `docs/FD/2026-04-09-CF临时邮箱接入邮箱池FD.md`
    - 将 `/api/external/pool/claim` 对齐为实际路由 `/api/external/pool/claim-random`
    - 将 `/api/external/pool/complete` 对齐为实际路由 `/api/external/pool/claim-complete`
    - 修正“邮件读取已支持无需改动”的表述，避免与当前 resolver 行为产生误导
  - `docs/TD/2026-04-09-CF临时邮箱接入邮箱池TD.md`
    - 将 external pool 章节中的 `/claim`、`/complete` 路由对齐为 `/claim-random`、`/claim-complete`
    - 将 complete 响应示例调整为“以 controller 实现为准”的兼容表述

**说明**：本次仍坚持“最小必要改动”，只修正与源码不一致的接口路径与高风险误导点。

#### 3. 分支同步与联系方式添加

**时间**：2026-04-09

**分支同步**：
- `Buggithubissue`、`dev`、`feature` 三个分支均已落后 main，无独立提交
- 使用 `git branch -f` + `git push --force` 将所有分支 fast-forward 到 main（`7952820`）
- 注意：三个分支被 worktree 占用（`E:/hushaokang/Data-code/EnsoAi/outlookEmail/` 下），无法 checkout，改用 `git branch -f` 直接重置
- `feature` 无远程分支，仅本地同步

**联系方式**：
- `README.md`：新增"联系方式"章节 → `outlookmailplus@163.com`
- `README.en.md`：新增"Contact"章节 → `outlookmailplus@163.com`

**修改文件**：
- `README.md`：末尾新增联系方式
- `README.en.md`：末尾新增 Contact 章节

**Commits**：
- `301b122`：fix: 移除 sonar-project.properties 中已删除的 fix_format.py 引用
- `7952820`：docs: 添加联系邮箱，同步所有分支到 main

---

#### 2. v1.13.0 发布与 SonarCloud 修复

**时间**：2026-04-09

**版本发布**：
- 版本号：`1.12.0` → `1.13.0`（`outlook_web/__init__.py`）
- 更新 CHANGELOG.md、DEVLOG.md、README.md、README.en.md 版本引用
- 更新 `tests/test_version_update.py` 中所有版本断言和 mock 数据
- 本地 893 测试全部通过（0 failures, 6 skipped）
- CI 全量通过（Python Tests / Code Quality / Docker Build）
- Git Tag `v1.13.0` → 触发 `create-github-release.yml` 自动创建 GitHub Release
- Docker 镜像双仓库推送成功：
  - GHCR: `ghcr.io/zeropointsix/outlook-email-plus:v1.13.0` / `:latest`
  - Docker Hub: `guangshanshui/outlook-email-plus:v1.13.0` / `:latest`
  - Digest: `sha256:8909cf0300c956d2db803157dfdeced2a24e6b6c09c149509f87ae6025ff086d`
  - 架构: `linux/amd64` + `linux/arm64`

**SonarCloud 失败修复**：
- 根因：`sonar-project.properties` 中 `sonar.sources` / `sonar.inclusions` / `sonar.coverage.exclusions` 引用了已删除的 `fix_format.py`
- 该文件在 commit `04824bc` 已删除，但 SonarCloud 配置未同步清理
- 修复：从 3 处配置项中移除 `fix_format.py` 引用
- 同步清理：`docs/项目地图.md` 中可清理项目列表移除 `fix_format.py`

**修改文件**：
- `outlook_web/__init__.py`：版本号 → `1.13.0`
- `tests/test_version_update.py`：版本断言 + mock tag_name
- `CHANGELOG.md`：新增 `[v1.13.0]` 段落
- `docs/DEVLOG.md`：新增 `v1.13.0` 段落
- `README.md` / `README.en.md`：版本引用更新
- `sonar-project.properties`：移除 `fix_format.py` 引用（3 处）
- `docs/项目地图.md`：移除已删除文件记录

---

#### 1. hotupdate-test 分支端到端测试与合并

**时间**：2026-04-09

**背景**：`hotupdate-test` 分支在 `main` 基础上新增 24 个提交，用于热更新功能的端到端验证（Watchtower + Docker API 双模式）。分支使用 GHCR 远程镜像（`ghcr.io/zeropointsix/outlook-email-plus:hotupdate-test`）进行了完整的两种更新方式的实际测试。

**测试环境**：
- 端口 5002：Watchtower 模式（`docker-compose.hotupdate-test.yml`，含 Watchtower sidecar）
- 端口 5003：Docker API 模式（`docker-compose.docker-api-test.yml`，挂载 docker.sock）
- 镜像：`ghcr.io/zeropointsix/outlook-email-plus:hotupdate-test`

**发现并修复的问题**：

| # | 问题 | 修复 | Commit |
|---|------|------|--------|
| 1 | GHCR 镜像不在白名单 | 添加 `ghcr.io/zeropointsix/` 到 ALLOWED_IMAGE_PREFIXES | 早期提交 |
| 2 | 本地镜像检测误判 | 重写 `_looks_like_local_image_ref()` 为 namespace 白名单 | 早期提交 |
| 3 | 版本比较 pre-release 后缀问题 | `_version_gt()` 忽略 `-hotupdate-test` 等后缀 | 早期提交 |
| 4 | Watchtower 连通测试超时 (5s) | 增加到 35s，添加详细注释说明 Watchtower 同步行为 | `6441de2` |
| 5 | Emoji 前缀 i18n 翻译匹配失败 | 在 exactMap 中添加 `🔄`/`🚀` 前缀变体 | `6441de2` |
| 6 | 设置页 Tab 标签缺少翻译 | 添加 基础/临时邮箱/API 安全/自动化 翻译 | `6441de2` |
| 7 | Watchtower 200 响应误判为"更新成功" | 改为 `already_latest: true`（Watchtower 同步完成 → 未更新我们） | `2b49547` |
| 8 | 连通性/更新结果 i18n 缺失 | 添加 连通正常/检查完毕/测试中/更新失败 等翻译 | `2b49547` |
| 9 | 测试断言不匹配 | 更新 `test_watchtower_success` 断言 `already_latest` + `"检查完毕"` | `3672888` |

**合并过程**：

1. 版本号从 `1.12.8-hotupdate-test` 回退至 `1.12.0`（与 main 一致）
2. 删除测试专用 compose 文件（`docker-compose.hotupdate-test.yml`、`docker-compose.docker-api-test.yml`）
3. 移除 CI docker-build-push 中 `hotupdate-test` 分支触发
4. 清理 `start.py` 测试注释、恢复 `WORKSPACE.md`
5. Fast-forward 合并到 main（`6f5c707`）
6. 推送 main、删除远程和本地 `hotupdate-test` 分支
7. 停止并删除所有测试容器和 volume

**Watchtower 同步行为关键发现**：

Watchtower `POST /v1/update` 是**同步接口**——完整执行镜像拉取和 digest 比对后才返回 200。如果我们的容器需要更新，Watchtower 会在返回前 kill 旧容器并启动新容器，因此**我们永远收不到 200 响应**。反过来，如果收到了 200 响应，说明 Watchtower 判定当前已是最新版本，无需更新。

**Watchtower DNS 问题**：

测试环境中 Watchtower 将 `ghcr.io` 解析为 `198.18.2.198`（VPN/代理干扰），导致 HEAD 请求失败，fallback 到完整 pull（需 25-30s），这是连通测试超时需要从 5s 增加到 35s 的根本原因。

---

## 2026-04-07

### 操作记录

#### 7. Docker API 自更新安全策略强化（策略A）

**时间**：2026-04-07 下午

**背景**：原有 Docker API 自更新功能存在安全隐患——本地构建镜像可能误触发更新，导致不可预期的行为。

**目标**：实施策略A（彻底禁止本地构建镜像触发 Docker API 更新），确保只有官方远程镜像才能触发更新。

**实施内容**：

1. **镜像白名单收紧**：
   - 移除 `outlook-email-plus`（无 namespace）白名单项
   - 仅保留 `guangshanshui/outlook-email-plus`官方镜像前缀
   
2. **新增本地构建检测**：
   - `validate_image_for_update()`：镜像白名单 + RepoDigests 检测双重校验
   - `_looks_like_local_image_ref()`：基于 namespace 的启发式本地镜像检测（修复 bug：改为 namespace 白名单判断）
   - `_has_repo_digests()`：通过 Docker API 检查镜像 RepoDigests（本地 build 镜像为空）
   
3. **API 层前置校验**：
   - `_trigger_docker_api_update()` 在触发阶段就获取容器镜像并校验
   - 校验失败返回 403/500，避免等到 spawn updater 内部才失败
   
4. **部署信息展示优化**：
   - `api_deployment_info()` 不再依赖 `DOCKER_SELF_UPDATE_ALLOW` 环境变量
   - 只要 docker.sock 可用就通过 Docker API 获取真实镜像名（更准确）
   
5. **测试用例调整**：
   - `docker-compose.docker-api-test.yml` 镜像改为 `guangshanshui/outlook-email-plus:latest`（形成负向用例：本地 build 但伪装官方名也会被 RepoDigests 检测拦截）

**修改文件**：
- `outlook_web/services/docker_update.py`：
  - 白名单收紧
  - 新增 `validate_image_for_update()`, `_looks_like_local_image_ref()`, `_has_repo_digests()`
  - `get_container_info()` 通过 `client.images.get()` 获取 RepoDigests
  - `spawn_update_helper_container()` 和 `self_update()` 调用新校验函数
  - Bug修复：`_looks_like_local_image_ref()` 改为 namespace 白名单判断（`guangshanshui`, `docker.io/guangshanshui`, `ghcr.io/guangshanshui`）
- `outlook_web/controllers/system.py`：
  - `_trigger_docker_api_update()` API 层镜像校验
  - `api_deployment_info()` 获取镜像名逻辑优化
- `docker-compose.docker-api-test.yml`：测试镜像名调整

**代码逻辑测试结果**（PowerShell环境）：
```
=== 白名单校验 ===
guangshanshui/outlook-email-plus:latest  → ✅ 通过
guangshanshui/outlook-email-plus:test    → ✅ 通过
outlook-email-plus:latest                → ❌ 拦截（无 namespace）
myregistry/outlook-email-plus:latest     → ❌ 拦截（非官方 namespace）

=== 启发式检测 ===
guangshanshui/outlook-email-plus:*       → False（正确识别为官方）
outlook-email-plus:*                     → True（正确识别为本地）
其他namespace/*                          → True（正确识别为非官方）
```

**文档产出**：
- `docs/DEV/manual-acceptance-checklist.md`：人工验收清单（4 个测试用例 + 验收标准 + 快速测试脚本）

**待验收项（当时）**：
- [ ] 负向用例1：本地构建镜像触发更新被拦截
- [ ] 负向用例2：本地构建伪装官方名触发更新被拦截
- [ ] 正向用例3：官方远程镜像成功触发更新流程
- [ ] 部署信息准确性验证

**端到端实际测试记录（Docker Desktop / Windows）**：

环境：
- Docker Desktop 4.43.2（Engine 28.3.2，Context: desktop-linux）
- Docker Compose v2.38.2

执行：
1) 启动负向用例（本地 build + 伪装官方镜像名）：
   - 命令：`docker compose -f docker-compose.docker-api-test.yml up -d --build`
   - 容器：`outlook-dockerapi-test`（端口 5003→5000）
   - 镜像：`guangshanshui/outlook-email-plus:latest`（本地 build）
   - 镜像 RepoDigests：`[]`（确认本地 build 特征）

2) 通过脚本模拟前端触发更新（含 CSRF）：
   - `POST /login` → ✅ success
   - `GET /api/csrf-token` → ✅ 返回 csrf_token
   - `POST /api/system/trigger-update?method=docker_api` + `X-CSRFToken` → ✅ 返回 403
     - message：`检测到本地构建镜像（RepoDigests 为空），已按安全策略禁止 Docker API 一键更新...`
   - 结论：策略A拦截生效；未创建 updater 容器；旧容器未被 stop

3) 正向用例尝试（远程拉取官方镜像）被环境网络阻塞：
   - `docker pull guangshanshui/outlook-email-plus:v1.11.0` → ❌ 超时
   - 错误：`Client.Timeout exceeded while awaiting headers`（auth.docker.io token 请求超时）
   - 影响：无法在当前环境完成“远程镜像 RepoDigests 非空 → 允许触发 updater → self_update 跑完”的正向验收

**结论（阶段性）**：负向端到端已通过；正向端到端当时受 DockerHub 网络访问影响未完成。

---

#### 13. 策略A 正向端到端验收补全：真实“热更新切换”演示（A2 + 远程镜像 tag 变更）

**时间**：2026-04-07 晚

**目标**：补齐策略A的正向端到端验收，验证当远程镜像 tag 指向新 digest 时，A2 updater 能完成完整切换流程：

- pull 最新镜像
- digest 不同 → create 新容器
- stop 旧容器释放端口
- start 新容器 + health
- rename（新容器接管原名称）
- 旧容器保留为 backup（remove_old=false）

**验收环境/对象**：

- 镜像 tag：`guangshanshui/outlook-email-plus:a2-strategyA-canary`
- 初始运行容器：`outlook-canary`（端口 `5005 -> 5000`，挂载 `/var/run/docker.sock`）
- 触发更新方式：应用内接口 `POST /api/system/trigger-update?method=docker_api`（登录 + CSRF）

**关键证据（更新前）**：

- 运行中容器：`outlook-canary`
- 容器使用的 image id（旧）：`sha256:056f69613d8dac7a486ed77a32c8041fb522c4f63d0fad8f6d0149078190e84e`
- 容器镜像引用仍为 tag：`guangshanshui/outlook-email-plus:a2-strategyA-canary`
- 本地同 tag 已被重新打到新镜像（新 image id）：`sha256:21aba8bda26d893f59af319eaeb5a72d06eedfd3b4f521a0d004e2bd9503b2fb`

说明：容器创建时记录的是当时 tag 对应的镜像 ID；后续重新 push 同 tag 后，容器仍显示原 tag，但 image id 不会自动变化，因此能触发“digest 不同 → 更新”。

**触发更新（PowerShell / Invoke-RestMethod，带 session cookie 与 CSRF）**：

```powershell
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) 登录（写入 session cookie）
$loginBody = @{ password = 'admin123' } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://localhost:5005/login' -Method Post -ContentType 'application/json' -Body $loginBody -WebSession $session

# 2) 获取 CSRF token
$csrf = (Invoke-RestMethod -Uri 'http://localhost:5005/api/csrf-token' -Method Get -WebSession $session).csrf_token

# 3) 触发 Docker API 更新（A2 helper）
Invoke-RestMethod -Uri 'http://localhost:5005/api/system/trigger-update?method=docker_api' -Method Post -Headers @{ 'X-CSRFToken' = $csrf } -WebSession $session
```

接口返回（关键字段）：

```json
{"success": true, "message": "更新任务已启动: oep-updater-1775571256 (e21bf4afbbdb)"}
```

**关键证据（更新后）**：

1) `outlook-canary` 名称仍存在，且重新变为运行态并健康：

- 新容器 ID（short）：`e0ba3c44dcc9`
- 新容器 image id：`sha256:21aba8bda26d893f59af319eaeb5a72d06eedfd3b4f521a0d004e2bd9503b2fb`
- 端口仍为：`0.0.0.0:5005->5000/tcp`

2) 旧容器被 rename 为 backup 并退出（符合 A2 设计：保留旧容器便于回滚）：

- 旧容器名称：`outlook-canary_backup_1775571270`
- 旧容器 image id：`sha256:056f69613d8dac7a486ed77a32c8041fb522c4f63d0fad8f6d0149078190e84e`
- 状态：Exited(0)

3) `/healthz` 访问正常（证明新容器已接管服务）：

```json
{"status":"ok","version":"1.12.0","boot_id":"1775571264516-7"}
```

**结论**：策略A + A2 helper 的“正向端到端热更新切换”已完成，验证了 digest 变化场景下的 stop/start/rename/backup 全链路行为。

**关联 Issue/PR**：待 Docker 容器内实际验收通过后提交

---

#### 1. mystatus 插件状态确认

**背景**：尝试使用 `mystatus` 工具查询 AI 账户配额使用情况。

**实际情况**：

| 项目 | 状态 |
|------|------|
| 插件安装 | `opencode-mystatus@1.2.4` 已安装于全局 `~/.config/opencode/node_modules/` |
| 全局配置 | `~/.config/opencode/opencode.json` 已注册 `plugin` 和 `command` |
| 项目配置 | 项目级 `opencode.json` 未单独配置 mystatus 插件（使用全局配置） |
| 工具可用性 | 当前会话工具列表中**未注册** `mystatus` 工具，无法直接调用 |

**配置位置**：

- 全局插件配置：`C:\Users\PLA30\.config\opencode\opencode.json`
  ```json
  "plugin": ["opencode-mystatus"],
  "command": {
    "mystatus": {
      "description": "Query quota usage for all AI accounts",
      "template": "Use the mystatus tool to query quota usage. Return the result as-is without modification."
    }
  }
  ```
- 插件源码位置：`C:\Users\PLA30\.config\opencode\node_modules\opencode-mystatus\`

**支持平台**：

| Platform | Account Type |
|----------|-------------|
| OpenAI | Plus / Team / Pro |
| Zhipu AI | Coding Plan |
| Z.ai | Coding Plan |
| GitHub Copilot | Individual / Business |
| Google Cloud | Antigravity |

**结论**：`mystatus` 作为 opencode 插件需要在 opencode 运行时环境中通过 `/mystatus` 命令或自然语言触发，当前通过外部 Agent 调用时无法直接使用该工具。

#### 2. 热更新功能开发状态确认

**关联文档**：
- AI 提示词：`docs/DEV/hot-update-ai-prompt.md`
- 基线记录：`docs/DEV/hot-update-baseline.md`

**功能概述**：为 Outlook Email Plus 实现 Docker 部署环境下的一键更新功能，支持 Watchtower 和 Docker API 两种更新方式。

**实施进度（全部已完成）**：

| 阶段 | 内容 | 状态 | Commit |
|------|------|------|--------|
| Phase 1 | BUG 修复（Token 为空启动失败、浏览器缓存旧 JS） | ✅ | 91a8f35 |
| Phase 2 | UI 提示优化（镜像标签/构建模式检测） | ✅ | 91a8f35 |
| Phase 3 | 内置 Docker API 自更新 | ✅ | 91a8f35 |
| P0 | BUG-006 GitHub 仓库地址修复 | ✅ | e6d27b6 |

**核心产出**：
- 新增：`outlook_web/services/docker_update.py`（591 行，经代码验证 2026-04-07，原文档记录 839 行已修正）
- 新增 API：`/api/system/version-check`、`/api/system/trigger-update`、`/api/system/test-watchtower`、`/api/system/deployment-info`
- 新增设置项：`watchtower_url`、`watchtower_token`（加密存储）、`update_method`
- 前端：版本更新 Banner、Watchtower 配置 UI、Docker API 更新方式选择
- 前端补齐：设置页一键更新区域的部署信息警告（`/api/system/deployment-info` → `#deploymentWarnings`）
- 安全：默认关闭 Docker API 自更新、镜像白名单校验、审计日志

**当前版本**：v1.12.0，热更新验证已通过（v1.12.0 → v1.12.1）

#### 3. 文档更新

- 创建 `WORKSPACE.md` 工作区操作记录文档
- 确认项目结构：项目级 `opencode.json` 仅配置了子代理（context-retriever, small-task-executor），mystatus 依赖全局配置
- 记录热更新功能完整实施状态

#### 4. 热更新文档代码验证与清理

**操作内容**：

1. **代码验证**：逐一对比 `hot-update-ai-prompt.md` 中的描述与实际代码
   - ✅ 4 个 API 端点全部存在且已注册路由
   - ✅ `update_method` 设置项 GET/PUT 支持
   - ✅ 静态文件缓存控制 `set_static_cache_control()` 
   - ✅ GitHub 仓库地址 `ZeroPointSix/outlookEmailPlus`
   - ✅ `docker-compose.yml` 配置完整（Token 默认值、docker.sock 注释、DOCKER_SELF_UPDATE_ALLOW）
   - ✅ `.env.example` 模板完整
   - ⚠️ **发现差异**：`docker_update.py` 实际 591 行，文档记录为 839 行 → **已修正**

2. **文档清理**：清理 `hot-update-ai-prompt.md`
   - 删除"待实施任务 (可选扩展)"部分（第 154-318 行），该部分重复了已完成的 Phase 1-3 任务描述
   - 新增"代码验证记录"表格，记录 13 项验证结果
   - 修正 `docker_update.py` 行数为实际值 591
   - 保留"参考文件清单"和"注意事项"部分

**已修改文件**：
- `docs/DEV/hot-update-ai-prompt.md` — 删除冗余内容，新增验证记录，修正数据

#### 5. README 生产配置更新

**操作内容**：
- 更新 `README.md` 中 docker-compose 生产配置示例，同步 Phase 3 新功能
  - 新增 `DOCKER_SELF_UPDATE_ALLOW` 环境变量（注释状态）
  - 新增 docker.sock 挂载选项（注释状态）
  - 新增"更新方式"说明段落，指导用户如何切换 Watchtower/Docker API 模式
- 修正 README "最近更新"版本号：v1.11.0 → v1.12.0
- 新增"一键更新"功能说明段落

**已修改文件**：
- `README.md` — 版本号更新、docker-compose 示例更新、功能说明补充

#### 6. 热更新功能完整性详细分析

**结论：功能已完整实现**，所有文档描述的功能点均在代码中找到对应实现。

**后端功能验证（全部 ✅）**：

| 功能 | 位置 | 状态 |
|------|------|------|
| 版本检测 API（10 分钟缓存） | system.py:353 | ✅ |
| 更新触发 API（双模式） | system.py:402 | ✅ |
| Watchtower 更新（DB→env fallback + 加密 Token） | system.py:438 | ✅ |
| Docker API 更新（安全检查→socket→白名单→12 步流程） | system.py:500 + docker_update.py | ✅ |
| 部署信息检测（镜像/标签/本地构建/Watchtower 连通性） | system.py:561 | ✅ |
| Watchtower 连通性测试 | system.py:732 | ✅ |
| 设置项 update_method（GET/PUT） | settings.py:351/1013 | ✅ |
| 静态文件缓存控制 | app.py:124 | ✅ |

**前端功能验证（全部 ✅）**：

| 功能 | 位置 | 状态 |
|------|------|------|
| 页面加载版本检查 | main.js:3763 `checkVersionUpdate()` | ✅ |
| 双模式触发更新 + 差异化超时 | main.js:3790 `triggerUpdate()` (120s/10s) | ✅ |
| 重启轮询等待 | main.js:3880 `waitForRestart()` | ✅ |
| 部署信息警告渲染（设置页） | main.js: `loadDeploymentInfo()` / `renderDeploymentWarnings()` | ✅ |
| Watchtower 连通性测试 | main.js:2169 `testWatchtower()` | ✅ |
| 设置加载/保存 update_method | main.js:1743/2100 | ✅ |

**Docker API 自更新 12 步流程（docker_update.py）**：

| 步骤 | 函数 | 状态 |
|------|------|------|
| 1. 启用开关检查 | `is_docker_api_enabled()` | ✅ |
| 2. Socket 可访问性 | `check_docker_socket()` | ✅ |
| 3. 获取当前容器信息 | `get_current_container_info()` | ✅ |
| 4. 镜像名白名单校验 | `validate_image_name()` | ✅ |
| 5. 拉取最新镜像 | `pull_latest_image()` | ✅ |
| 6. Digest 比较 | `compare_image_digest()` | ✅ |
| 7. 创建新容器（复制配置） | `create_new_container()` + `_parse_volumes()` + `_parse_ports()` | ✅ |
| 8. 启动新容器 | `start_new_container()` | ✅ |
| 9. 健康检查 | `health_check_new_container()` | ✅ |
| 10. 停止旧容器 | `stop_old_container()` | ✅ |
| 11. 重命名容器 | `rename_containers()` | ✅ |
| 12. 清理/保留旧容器 | `cleanup_old_container()` | ✅ |

**发现的问题（非阻塞）**：

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | `can_auto_update` 未考虑 Docker API 模式 | 低 | `api_deployment_info()` 中 `can_auto_update` 仅检查 Watchtower 连通性，用户选 Docker API 模式且无 Watchtower 时会误报为不可更新 |
| 2 | `self_update()` 同步调用风险 | 低 | system.py:531 注释说明同步调用可能中断响应，但 Docker API 模式下前端有 120s 超时 + `waitForRestart()` 轮询兜底 |
| 3 | `docker-compose.hotupdate-test.yml` 含硬编码密钥 | 低 | 测试专用文件，不影响生产安全 |

#### 7. 热更新功能非阻塞问题修复

**修复 #1：`can_auto_update` 逻辑支持 Docker API 模式**

- **文件**：`outlook_web/controllers/system.py`
- **问题**：`api_deployment_info()` 中 `can_auto_update` 仅检查 Watchtower 连通性
- **修复**：新增 `docker_api_available` 检测（检查 `DOCKER_SELF_UPDATE_ALLOW` + socket 可用性），`can_auto_update` 逻辑改为 `watchtower_reachable or docker_api_available`
- **新增返回字段**：`deployment.docker_api_available`（布尔值）

**修复 #2：`self_update()` 同步→异步**

- **文件**：`outlook_web/controllers/system.py`
- **问题**：`_trigger_docker_api_update()` 同步调用 `self_update()`，旧容器被停止时响应无法到达客户端
- **修复**：使用 `threading.Thread(daemon=True)` 在后台线程执行自更新，主线程立即返回 `{"success": True, "message": "Docker API 自更新已启动，容器即将重启"}`
- **审计日志**：移入后台线程，确保更新结果被记录
- **前端兼容**：前端已有 `waitForRestart()` 轮询 `/healthz` 等待新容器启动，无需修改

**修复 #3：清理测试配置硬编码密钥**

- **文件**：`docker-compose.hotupdate-test.yml`
- **问题**：SECRET_KEY 和 WATCHTOWER_HTTP_API_TOKEN 为硬编码明文值
- **修复**：改为 `${SECRET_KEY:-please-change-this-secret-key-for-testing}` 和 `${WATCHTOWER_HTTP_API_TOKEN:-test-hotupdate-token}` 格式，支持 `.env` 文件注入
- **附加**：更新文件头注释（移除版本号引用，添加使用方式说明）

**已修改文件汇总**：
- `outlook_web/controllers/system.py` — can_auto_update 逻辑 + self_update 异步化
- `docker-compose.hotupdate-test.yml` — 密钥环境变量化

#### 8. README 环境变量补充

**操作内容**：
- 在 `README.md` 的"常用环境变量"部分新增"一键更新相关"小节
- 补充环境变量说明：
  - `WATCHTOWER_HTTP_API_TOKEN` — Watchtower API 鉴权令牌
  - `WATCHTOWER_API_URL` — Watchtower API 地址
  - `DOCKER_SELF_UPDATE_ALLOW` — 是否启用 Docker API 自更新
  - `DOCKER_IMAGE` — 当前容器镜像名（可选）
- 添加安全提示说明 Docker API 自更新的风险

**已修改文件**：
- `README.md` — 新增一键更新相关环境变量说明

#### 9. 一键更新功能人工验收 BUG 分析

**分析范围**：dev 分支相对于 main 分支新增的一键更新功能

**功能概述**：
- 版本检测：GET `/api/system/version-check`，对比 GitHub 最新 release 与本地版本
- 触发更新：POST `/api/system/trigger-update?method=watchtower|docker_api`
- Watchtower 配置：设置页可配置 URL + Token（加密存储）
- Docker API 自更新：12 步流程（拉取镜像→创建容器→健康检查→切换）

**潜在 BUG 分析**：

| # | 问题描述 | 严重度 | 复现条件 | 影响 | 建议处理 |
|---|---------|--------|----------|------|----------|
| 1 | **镜像名检测依赖 DOCKER_IMAGE 环境变量** | 低 | 未设置 DOCKER_IMAGE 时 | `api_deployment_info()` 无法准确获取镜像名，可能显示 `unknown` | 可接受，用户可手动设置 |
| 2 | **容器名冲突风险** | 低 | Docker API 自更新失败后重试 | 新容器使用 `{name}_new` 临时名称，若上次失败未清理可能冲突 | 代码中已有 force 删除逻辑，风险较低 |
| 3 | **审计日志在后台线程中记录** | 低 | Docker API 自更新 | 若新容器启动后旧容器被停止，审计日志写入数据库时机可能不稳定 | 非阻塞，日志可能丢失但不影响功能 |
| 4 | **前端超时固定 120s** | 信息 | Docker API 大镜像拉取 | 若镜像很大，拉取时间超过 120s，前端可能误报超时（但后台仍在执行） | 可接受，前端会继续轮询 `/healthz` |

**健康检查说明**：
- `docker_update.py` 中的 `health_check_new_container()` 检查的是 Docker 容器状态和 Docker 原生 healthcheck
- 前端 `waitForRestart()` 轮询的 `/healthz` 端点是应用级健康检查（已存在于 `system.py:39`）
- 两者是独立的：容器启动后，后端健康检查通过 → 前端轮询 `/healthz` 确认应用可用

**验收建议**：

1. **Watchtower 模式验收**：
   - [ ] 部署 docker-compose（含 watchtower 服务）
   - [ ] 在设置页配置 Watchtower URL + Token
   - [ ] 点击"测试连通性"按钮，确认返回成功
   - [ ] 触发版本检测，确认 Banner 显示
   - [ ] 点击"立即更新"，确认容器重启

2. **Docker API 模式验收**：
   - [ ] 修改 docker-compose 启用 `DOCKER_SELF_UPDATE_ALLOW=true`
   - [ ] 挂载 `/var/run/docker.sock`
   - [ ] 在设置页切换"更新方式"为 Docker API
   - [ ] 确认部署信息显示 `docker_api_available: true`
   - [ ] 触发更新，确认 12 步流程正常执行

3. **边界条件验收**：
   - [ ] 使用固定版本标签（如 `:v1.12.0`），确认 UI 警告正确
   - [ ] 本地构建镜像，确认 UI 警告正确
   - [ ] 未配置 Watchtower Token，确认错误提示

**结论**：一键更新功能已基本完整，无阻塞性 BUG。建议按上述验收清单进行人工测试。

#### 10. Docker API 自更新实测发现阻塞 BUG 并修复（dev 分支）

**实测背景**：尝试在 Docker 容器中调用 `/api/system/trigger-update?method=docker_api` 做完整 12 步自更新模拟。

**实际问题**：接口直接返回 500。

- 容器日志报错：`ModuleNotFoundError: No module named 'outlook_web.models'`
- 根因：`outlook_web/controllers/system.py::_trigger_docker_api_update()` 中错误引用 `from outlook_web.models import AuditLog`，但项目不存在 `outlook_web/models.py` 以及 `AuditLog` 类

**修复策略（方案 A）**：移除 `AuditLog` 依赖。

- 主线程：使用现有 `outlook_web.audit.log_audit()` 记录一次 `trigger_docker_api_update_start`（含 method/remove_old/username）
- 后台线程：仅执行 `docker_update.self_update()` 并写入应用日志（logger），避免后台线程依赖 Flask request context / DB 连接

**修改文件**：
- `outlook_web/controllers/system.py` — 移除 `outlook_web.models.AuditLog` 引用，改用 `log_audit`

---

#### 11. A2 方案实现：按需 helper job 容器（避免"自杀"问题）

**背景问题**：Docker API 模式实测发现核心阻塞——容器无法在内部 stop 自己后继续执行后续步骤（进程被杀死）。原始方案使用 daemon 线程在后台执行 self_update()，但旧容器被 stop 的瞬间后台线程也会被杀死，导致"create 新容器→stop 旧→rename→cleanup"流程中断。

**方案选型**：

| 方案 | 描述 | 优势 | 劣势 |
|------|------|------|------|
| A1: 两阶段脚本 | app 容器内写脚本→nohup 后台执行→exit | 最简单 | 可靠性差，进程管理困难 |
| **A2: 按需 helper job 容器** | app 通过 Docker API 临时创建 updater 容器 | 可靠、隔离、auto_remove 自动清理 | 短暂 2 容器并存 |
| A3: 外部 updater 服务 | 额外部署常驻 updater 容器 | 最稳 | 增加部署复杂度 |

**选定方案**：A2（按需 helper job 容器）

**架构设计**：

```
┌─────────────────────────────┐
│  App 容器（用户请求）          │
│                             │
│  1. 鉴权 + 安全校验            │
│  2. 记录审计日志（主线程）       │
│  3. Docker API 创建 updater 容器│
│  4. 立即返回 HTTP 响应          │
└─────────────┬───────────────┘
              │ docker.sock
              ▼
┌─────────────────────────────┐
│  Updater 容器（短生命周期）     │
│                             │
│  1. sleep(2) 等 HTTP 响应     │
│  2. pull 最新镜像              │
│  3. create 新容器（复制配置）   │
│  4. stop 旧容器（释放端口）     │
│  5. start 新容器               │
│  6. healthcheck 新容器         │
│  7. rename 容器                │
│  8. cleanup 旧容器             │
│  9. 退出 → auto_remove 自动清理 │
└─────────────────────────────┘
```

**关键设计决策**：

1. **start_delay_seconds=2**：updater 容器启动后延迟 2 秒再执行更新操作，给 app 容器的 HTTP 响应留出到达客户端的时间
2. **先 stop 旧容器再 start 新容器**：解决 host port 映射场景下端口冲突问题（docker-compose 常见 5000:5000 映射）
3. **auto_remove=True**：updater 容器退出后自动删除，保持"单容器部署体验"
4. **失败回滚**：新容器启动失败或健康检查失败时，尝试恢复旧容器
5. **透传 Docker 凭证**：支持 DOCKER_AUTH_CONFIG / DOCKER_CONFIG 环境变量，确保 updater 可拉取私有镜像
6. **Watchtower 排除**：updater 容器添加 `com.centurylinklabs.watchtower.enable=false` 标签

**新增/修改文件清单**：

| 文件 | 操作 | 说明 |
|------|------|------|
| `outlook_web/services/docker_update_helper.py` | **新增**（69 行） | updater 容器入口模块，读取环境变量调用 `self_update()` |
| `outlook_web/services/docker_update.py` | 修改 | 新增 `get_container_info()`、`spawn_update_helper_container()`；增强 `validate_image_name()` 支持 digest 和 registry port；增强 volumes 解析支持 named volume；`self_update()` 新增 `target_container_id` 参数；调整步骤顺序（先 stop 旧再 start 新）；失败时尝试恢复旧容器 |
| `outlook_web/controllers/system.py` | 修改 | `healthz()` 新增 `boot_id` 和 `version` 字段；`_trigger_docker_api_update()` 改为调用 `spawn_update_helper_container()`；`api_deployment_info()` 增强 Docker API 检测和上下文感知警告 |
| `static/js/main.js` | 修改 | `waitForRestart()` 增加 boot_id 变化检测；Docker API 模式超时放宽到 180s；`triggerUpdate()` 统一走 waitForRestart 逻辑；`loadSettings()` 触发部署信息加载；新增 `loadDeploymentInfo()` / `renderDeploymentWarnings()`；语言切换时重渲染部署警告 |
| `templates/index.html` | 修改 | 新增 `#deploymentWarnings` 容器；微调缩进格式 |
| `tests/test_error_and_trace.py` | 修改 | 适配 healthz 新增 `boot_id` / `version` 字段 |
| `tests/test_smoke_contract.py` | 修改 | 适配 healthz 新增字段 |
| `docker-compose.docker-api-test.yml` | **新增**（45 行） | Docker API 模式专用测试 compose 配置 |
| `docker-compose.hotupdate-test.yml` | 修改 | 新增 DOCKER_IMAGE 环境变量 |

**self_update() 步骤顺序调整**：

原方案（先 start 新再 stop 旧）在 host port 映射场景下会产生端口冲突：

```
原: pull → compare → get_info → validate → pull_image → compare_digest → create → start_new → health_check → stop_old → rename → cleanup
新: pull → compare → get_info → validate → pull_image → compare_digest → create → stop_old → start_new → health_check → rename → cleanup
```

**前端轮询优化**：

通过 `boot_id`（`{timestamp}-{pid}`）判断容器是否发生了真正的进程重启：
- 首次轮询前记录 `initialBootId`
- 后续轮询中检测 `boot_id` 是否变化
- `boot_id` 变化 或 `seenDown`（曾看到服务不可用）时判定为重启完成

#### 12. A2 方案本地 Docker 验证（dev 分支）

**验证环境**：
- Docker Desktop 4.43.2 (Engine 28.3.2)
- 本地构建镜像 `outlook-email-a2-test:latest`（基于 dev 分支源码）
- 容器名 `outlook-dockerapi-test`，端口映射 5003:5000
- 挂载 docker.sock，DOCKER_SELF_UPDATE_ALLOW=true

**验证步骤与结果**：

| # | 测试项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | `healthz` 返回 `boot_id` + `version` | ✅ | `{"status":"ok","boot_id":"1775563642828-8","version":"1.12.0"}` — A2 代码已生效 |
| 2 | 登录 + CSRF token 获取 | ✅ | Cookie-based session + X-CSRFToken |
| 3 | 部署信息 API | ✅ | `docker_api_available:true`，`is_local_build:true`，警告正确 |
| 4 | 触发更新 API（白名单校验） | ✅ | 返回 `"镜像名不在白名单内: outlook-email-a2-test:latest"` — 正确拦截 |
| 5 | Docker socket 连通性 | ✅ | `check_docker_socket()` 返回可用 |
| 6 | 容器内省 `get_container_info()` | ✅ | 返回完整容器信息（name/image/volumes/networks/restart_policy） |
| 7 | updater 容器创建 + 运行 + auto_remove | ✅ | 容器创建成功 → 正常运行 → 退出后自动删除 |
| 8 | 完整 helper 流程 (`python -m docker_update_helper`) | ✅ | 步骤 1-3 通过（权限/socket/容器信息），步骤 4 白名单拦截（本地构建镜像），原容器完好 |

**关键发现**：

1. **A2 核心逻辑完全通过**：updater 容器可以由 app 容器通过 docker.sock 创建、运行、自动清理
2. **白名单机制正常**：本地构建镜像被正确拦截，不会误更新
3. **auto_remove 有效**：updater 容器退出后自动删除，保持"单容器体验"
4. **原容器保护有效**：即使更新流程被拦截，原容器状态不受影响（status=running）
5. **无法端到端验证 pull→create→stop→start→rename**：因为本地构建镜像无法从远程 registry pull；完整流程需在真实远程镜像环境下验证

**清理**：
- 停止并删除测试容器和 volume
- 删除临时测试脚本 `test_a2_spawn.py` / `test_a2_helper.py`
- 删除本地测试镜像 `outlook-email-a2-test:latest`

**结论**：A2 方案的核心逻辑（updater 容器创建、运行、自动清理、白名单保护）已全部验证通过。完整端到端测试（含 pull→create→stop→start→rename）需在远程镜像环境下进行。

---

### 待办：本地端到端测试指南

> 以下是用户自行在本地进行端到端测试的完整步骤，覆盖 Watchtower 模式和 Docker API 模式。

#### 前提条件

1. Docker Desktop 运行中（Engine 28.x+）
2. dev 分支最新代码
3. 端口 5002、5003 未被占用

#### 方式一：Docker API 模式测试（A2 方案核心验证）

```bash
# 1. 构建本地镜像（含 A2 代码改动）
docker compose -f docker-compose.docker-api-test.yml up -d --build

# 2. 等待容器启动（约 20 秒）
# 查看健康状态
docker ps --filter "name=outlook-dockerapi-test"

# 3. 浏览器访问
# 打开 http://localhost:5003
# 使用密码 admin123 登录

# 4. 测试验证项
# 4a. 访问 /healthz 确认 boot_id 和 version 字段
#     浏览器直接访问 http://localhost:5003/healthz
#     期望: {"status":"ok","boot_id":"...","version":"1.12.0"}

# 4b. 进入"设置"→"自动化"→"一键更新"
#     - 切换更新方式为"Docker API"
#     - 确认看到部署信息警告（本地构建提示/Docker API 可用提示）
#     - 点击"立即更新"按钮
#     期望: 弹出"镜像名不在白名单内"错误（本地构建镜像无法自动更新，这是正确行为）

# 5. 测试完毕后清理
docker compose -f docker-compose.docker-api-test.yml down -v
docker rmi outlook-email-a2-test:latest  # 清理本地测试镜像
```

**注意**：本地构建镜像无法完成完整 pull→create→stop→start→rename 流程，因为远程 registry 没有 `outlook-email-a2-test` 镜像。白名单校验会正确拦截。

#### 方式二：Watchtower 模式测试（原有功能回归验证）

```bash
# 1. 启动 app + watchtower 双容器
docker compose -f docker-compose.hotupdate-test.yml up -d

# 2. 等待容器启动（约 20 秒）
docker ps --filter "name=outlook-hotupdate-test"

# 3. 浏览器访问 http://localhost:5002
# 使用密码 admin123 登录

# 4. 测试验证项
# 4a. 进入"设置"→"自动化"→"一键更新"
#     - 确认 Watchtower 配置显示
#     - 点击"测试连通性"
#     期望: 返回"连接成功"

# 4b. 点击"检查更新"（页面顶部或设置页）
#     期望: 显示当前版本和最新版本信息

# 4c. 点击"立即更新"
#     期望: 按钮变为"等待容器重启..."，前端轮询 /healthz
#     注意: 如果已是最新版本，Watchtower 不会触发容器重建

# 5. 测试完毕后清理
docker compose -f docker-compose.hotupdate-test.yml down -v
```

#### 方式三：远程镜像 + Docker API 端到端测试（最完整，需发布新版本）

```bash
# 1. 先提交 A2 代码到 dev 分支
# 2. 合并到 main 并发布新版本（如 v1.13.0）
# 3. 等待 Docker Hub 镜像发布
# 4. 使用远程镜像启动容器

docker run -d \
  --name oep-e2e-test \
  -p 5004:5000 \
  -e SECRET_KEY=test-secret-key \
  -e LOGIN_PASSWORD=admin123 \
  -e DOCKER_SELF_UPDATE_ALLOW=true \
  -e SCHEDULER_AUTOSTART=true \
  -v /var/run/docker.sock:/var/run/docker.sock \
  guangshanshui/outlook-email-plus:v1.13.0

# 5. 浏览器访问 http://localhost:5004，登录
# 6. 设置 → 自动化 → 一键更新 → 切换到 Docker API 模式
# 7. 点击"立即更新"
#    期望:
#    - 后端创建 updater 容器 (oep-updater-xxxxx)
#    - updater 容器 pull 最新镜像
#    - 如果有新版本：stop 旧容器 → create/start 新容器 → rename → cleanup
#    - 如果已是最新：返回"镜像已是最新，无需更新"
#    - 前端检测到 boot_id 变化 → 刷新页面

# 8. 清理
docker rm -f oep-e2e-test
```

#### 关键验证检查清单

- [ ] `GET /healthz` 返回 `boot_id` + `version`
- [ ] `GET /api/system/deployment-info` 返回正确的部署信息
- [ ] `docker_api_available` 在挂载 docker.sock 时为 true
- [ ] 更新方式切换 UI 正常（Watchtower ↔ Docker API）
- [ ] 部署警告根据更新方式动态变化（Watchtower 不可达时 info vs error）
- [ ] 触发更新时 CSRF 保护正常
- [ ] 白名单校验正确拦截非白名单镜像
- [ ] updater 容器创建成功并正确退出
- [ ] 前端 waitForRestart 轮询正常（boot_id 变化检测）
- [ ] 语言切换时部署警告重渲染

#### 13. 生成功能验证提示词（给其他 AI 审查用）

**操作内容**：
- 创建 `VERIFICATION_PROMPT.md`，包含 A2 方案的完整功能验证提示词
- 覆盖 5 大类验证点（后端 API / Docker 服务 / 前端 / 安全 / 边界条件），共 30+ 个具体检查项
- 附带改动文件清单和已知限制说明
- 用于交给其他 AI 审查代码变更的完整性和正确性

**已新增文件**：
- `VERIFICATION_PROMPT.md` — 功能验证提示词

---

### 待办：项目文件归类清理（暂缓，提交后执行）

> 以下为扫描项目结构后的清理建议，待 dev 分支提交后再执行。

#### 需删除的文件

| 文件 | 原因 |
|------|------|
| `fix_format.py` | 一次性格式修复脚本，已完成使命 |
| `NUL` | Windows 空文件，已在 .gitignore |
| `EhushaokangData-codeoutlookEmailserver.log` | 日志文件（文件名异常），已在 .gitignore |
| `-p/` 空目录 | 空目录，无内容 |
| `.ruff_cache/` | Linter 缓存目录 |

#### 需移动归类的文件

| 文件 | 目标位置 |
|------|---------|
| `注册与邮箱池接口文档.md` | → `docs/API/注册与邮箱池接口文档.md` |
| `registration-mail-pool-api.en.md` | → `docs/API/registration-mail-pool-api.en.md` |
| `VERIFICATION_PROMPT.md` | → `docs/DEV/VERIFICATION_PROMPT.md` |
| `docs/2026-04-05-设置页面重构-AI执行提示词.md` | → `docs/DEV/` 或删除 |

#### .gitignore 需补充

```
.ruff_cache/
-p/
```

**执行结果**（Commit: `04824bc`）：
- ✅ 删除 `fix_format.py`
- ✅ 移动 `注册与邮箱池接口文档.md` → `docs/API/`
- ✅ 移动 `registration-mail-pool-api.en.md` → `docs/API/`
- ✅ 移动 `VERIFICATION_PROMPT.md` → `docs/DEV/`
- ✅ 移动 `设置页面重构-AI执行提示词.md` → `docs/DEV/`
- ✅ `.gitignore` 补充 `.ruff_cache/` 和 `-p/`
- 注：`NUL`、`-p/`、`.ruff_cache/`、`Ehushaokang...server.log` 已在 .gitignore 中，物理文件已被清理

---

### 历史记录：A2 方案开发期间的修改清单（已合并至 main）

> 以下修改已通过 `hotupdate-test` 分支合并到 main（2026-04-09），此处仅作历史参考。

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `outlook_web/services/docker_update_helper.py` | **新增** | updater 容器入口模块 |
| `outlook_web/services/docker_update.py` | Modified | helper 容器创建、步骤顺序调整、失败回滚 |
| `outlook_web/controllers/system.py` | Modified | A2 触发逻辑、healthz 增强、部署信息增强 |
| `static/js/main.js` | Modified | boot_id 检测、部署警告渲染、超时优化 |
| `templates/index.html` | Modified | deploymentWarnings 容器 |
| `tests/test_error_and_trace.py` | Modified | 适配 healthz 新字段 |
| `tests/test_smoke_contract.py` | Modified | 适配 healthz 新字段 |
| `docs/DEV/hot-update-ai-prompt.md` | Modified | 文档清理 + 补充 |
| `docs/DEV/hot-update-baseline.md` | Modified | 文档补充 |
