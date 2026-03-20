# BUG 记录

## 基本信息

- 记录日期：2026-03-20
- 状态：待修复
- 优先级：P1
- 主题：IMAP 邮箱错误参与微软 Refresh Token 刷新流程

## 问题描述

当前项目中，`Refresh Token` 刷新能力在设计上应仅适用于 `Outlook / OAuth` 邮箱。

但是实际实现里，手动刷新相关的部分接口仍会把 `IMAP` 邮箱一起带入微软 `refresh token` 刷新逻辑，导致行为与产品语义不一致，也会产生错误的刷新日志和无意义的请求。

## 正确预期

- 只有 `account_type = 'outlook'` 的账号允许执行 Token 刷新。
- `account_type = 'imap'` 的账号不应参与：
  - 单个账号手动刷新
  - 手动刷新全部账号
  - 手动触发定时刷新
- IMAP 账号也不应更新 `refresh_token` 字段，不应写入对应的微软 token 刷新结果。

## 当前核对结论

### 已正确的路径

- `outlook_web/services/scheduler.py`
  - `scheduled_refresh_task(...)`
  - 当前已只处理 `account_type = 'outlook'` 的账号

### 存在 BUG 的路径

- `outlook_web/controllers/accounts.py`
  - `api_refresh_account(...)`
- `outlook_web/services/refresh.py`
  - `stream_refresh_all_accounts(...)`
- `outlook_web/services/refresh.py`
  - `stream_trigger_scheduled_refresh(...)`

上述路径当前仍会把 `status = 'active'` 的账号整体取出，而没有统一过滤掉 `IMAP` 账号。

## 影响

- IMAP 邮箱会错误进入微软 OAuth token 刷新逻辑。
- 会产生无意义的 Graph token 请求。
- 会导致刷新行为在“后台自动刷新”和“前台手动刷新”之间不一致。
- 会污染刷新日志，增加排查成本。

## 建议修复方案

1. 后端统一收口刷新规则，只允许 `Outlook` 账号进入 token 刷新链路。
2. 将手动刷新相关查询条件统一改为仅筛选 `account_type = 'outlook'`。
3. 单个账号刷新接口增加硬校验：
   - 若账号为 `IMAP`，直接返回“该账号类型不支持 Token 刷新”。
4. 前端同步收口：
   - IMAP 账号不显示“刷新 Token”按钮，或点击时直接提示不适用。
5. 补充回归测试，覆盖：
   - 单个刷新跳过 IMAP
   - 全量刷新跳过 IMAP
   - 手动触发定时刷新跳过 IMAP

## 备注

这是一个“实现不一致”问题，不是全链路都错误：

- 后台自动定时刷新已经做了正确过滤
- 但手动刷新相关入口没有统一遵守同一规则

因此需要统一产品规则和后端实现，避免后续继续出现同类偏差。

---

## 同轮新增确认问题一：Email 自动转发当前不会执行

### 问题描述

当前“新邮件自动通知”在产品预期上应支持：

- Telegram 通知
- Email 自动转发
- 两边同时发送
- 也允许只启用其中一个渠道

但是当前实际运行状态下，账号开启推送后，Telegram 可以正常收到，新邮件的 Email 自动转发却不会执行。

### 根因

当前调度器已被切换为只运行 Telegram 推送 Job：

- `outlook_web/services/scheduler.py`
  - `configure_scheduler_jobs(...)`
  - 当前调用 `_configure_telegram_push_job(...)`
- `_configure_telegram_push_job(...)`
  - 会主动移除 `email_notification_job`

因此当前后台不会再执行 Email 自动转发所依赖的统一通知分发 Job。

### 当前代码层面的真实状态

- Telegram：
  - 账号级开关生效
  - 自动轮询正常
  - 可成功推送
- Email：
  - 发送能力代码存在
  - 但自动通知 Job 当前未运行
  - 因此不会自动转发

### 影响

- 用户看到“邮箱通知/Email 通知”相关配置已保存，但新邮件到达后实际收不到自动转发。
- 产品行为与用户预期不一致，容易被误判为 SMTP、邮箱服务商或配置问题。

### 建议修复方案

1. 恢复统一通知分发 Job，不再只跑 Telegram 单通道 Job。
2. 在统一通知分发中保留 Telegram 与 Email 两类渠道投递能力。
3. 将“是否发送 Email 自动转发”改为按账号级渠道选择决定，而不是简单依赖旧的全局调度切换。

---

## 同轮新增确认问题二：通知模型设计与文案表达不符合真实需求

### 当前问题

当前系统中的通知配置语义混乱，把“渠道配置”和“账号是否启用通知”混在了一起：

- 设置页中存在“启用邮件通知”等全局表达
- 账号侧目前主要体现的是 Telegram 推送开关
- 文案容易让用户理解成：
  - 只要启用了 Email 通知，全体邮箱都会自动发送
  - 或者 Telegram 与 Email 只能二选一

但本轮已确认的真实需求不是这样。

### 正确需求模型

通知模型应拆成两层，但账号侧只保留一个统一通知开关，不再让用户在每个邮箱上分别选择 Telegram / Email 渠道。

#### 1. 渠道层

- Telegram 通知通道
- Email 通知通道
- 两个通道都可以配置可用，也可以只配置其中一个
- 渠道是否真正发送，统一由“用户设置页”决定

#### 2. 账号层

每个邮箱只负责一个问题：

- 是否开启通知

也就是：

- 开启通知：该邮箱允许参与通知
- 关闭通知：该邮箱无论什么渠道都不发送

### 正确触发规则

实际发送条件应为：

- 该邮箱已开启通知
- 且某通知渠道在用户设置页中已启用并配置可用

例如：

- 邮箱开启通知，设置页只启用 Telegram，则只发 Telegram
- 邮箱开启通知，设置页只启用 Email，则只发 Email
- 邮箱开启通知，设置页同时启用 Telegram 和 Email，则双发
- 邮箱未开启通知，则所有渠道都不发

### 当前代码不一致点

- `outlook_web/services/notification_dispatch.py`
  - `_is_email_channel_enabled()` 仍基于全局 `email_notification_enabled`
- `_build_active_channels_for_source(...)`
  - 当前 Email channel 仍是“全局开启就对所有 source 生效”
  - 没有像 Telegram 一样按账号级开关过滤

### 文案问题

当前中英文描述也未对齐真实产品语义，容易误导：

- 设置页文案更像“启用后全局自动发”
- 账号页文案更像“只有 Telegram 这一种通知”
- 也容易让用户误解为“每个邮箱需要分别设置每一种渠道”

### 建议的文案方向

#### 设置页

- 中文：
  - `Telegram 通知`
  - `Email 通知`
- 英文：
  - `Telegram Notifications`
  - `Email Notifications`
- 辅助说明：
  - `这里只配置通知渠道，不代表所有邮箱都会发送通知`
  - `This section configures notification channels only. It does not mean every mailbox will send notifications.`

#### 账号页

- 中文：`开启通知`
- 英文：`Enable Notifications`
- 辅助说明：
  - `邮箱页只控制该邮箱是否参与通知；具体发送到哪些渠道，由当前用户设置决定。`
  - `The mailbox page only controls whether this mailbox participates in notifications. Delivery channels are determined by the current user settings.`

### 建议修复方案

1. 重构通知配置模型，分清“渠道配置”和“邮箱是否参与通知”。
2. 账号页只保留统一通知开关，不再逐邮箱配置渠道组合。
3. 设置页负责渠道级开关与配置，支持 Telegram / Email 独立启用，也支持双通道同时启用。
4. 统一通知分发逻辑按“邮箱通知开关 + 用户设置中的渠道可用性”决定最终投递渠道。
5. 调整设置页与账号页中英文描述，使其与真实行为一致。
6. 清理旧的“全局邮件通知”误导性表述，避免后续继续造成理解偏差。
