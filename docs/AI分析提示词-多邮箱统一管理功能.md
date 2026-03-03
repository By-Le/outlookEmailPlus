# 多邮箱统一管理功能 - AI 深度分析提示词

## 📋 项目背景

### 当前项目：outlookEmail
- **技术栈**：Flask + SQLite + Graph API/IMAP
- **主要功能**：Outlook 邮箱管理工具，支持多账号管理、邮件读取、标签分组
- **架构特点**：
  - 模块化设计（outlook_web/）
  - 已支持多账号存储（accounts 表）
  - 使用 Graph API 和 IMAP 两种方式读取邮件
  - 有定时任务调度器（scheduler）
  - 邮件可能是实时获取，缺少本地持久化存储

### 参考项目：MailAggregator_Pro
- **技术栈**：FastAPI + SQLAlchemy（异步）+ SQLite + React
- **核心功能**：
  - 多邮箱 IMAP 聚合（Gmail、QQ、163、Yahoo、阿里邮箱等）
  - 统一邮件存储和查询
  - 规则引擎自动打标签
  - 后台轮询任务
  - Telegram 推送 + Webhook 通知
  - 每个账号独立轮询间隔控制

## 🎯 需求目标

在当前 outlookEmail 项目中，实现类似 MailAggregator_Pro 的多邮箱统一管理功能：

1. **支持多种邮箱提供商**：Gmail、QQ邮箱、163邮箱、126邮箱、Outlook、Yahoo、阿里邮箱等
2. **统一 IMAP 接口**：通过 IMAP 协议统一拉取所有邮箱的邮件
3. **本地邮件存储**：将所有邮箱的邮件存储到本地数据库
4. **后台自动轮询**：定时拉取所有活跃账号的新邮件
5. **统一查询界面**：在一个界面查看所有邮箱的邮件
6. **可选高级功能**：规则引擎、推送通知、Webhook

## 📊 关键架构对比

### 当前项目架构
```
outlookEmail/
├── outlook_web/
│   ├── app.py                    # Flask 应用入口
│   ├── db.py                     # 数据库初始化和连接
│   ├── repositories/             # 数据访问层
│   │   ├── accounts.py           # 账号管理（已支持多账号）
│   │   ├── groups.py             # 分组管理
│   │   └── tags.py               # 标签管理
│   ├── services/                 # 业务逻辑层
│   │   ├── graph.py              # Graph API 服务
│   │   ├── imap.py               # IMAP 服务
│   │   └── scheduler.py          # 定时任务
│   ├── routes/                   # API 路由
│   └── security/                 # 安全模块（加密、认证）
└── data/                         # SQLite 数据库

数据库表：
- accounts: 邮箱账号（email, password, client_id, refresh_token, group_id, remark, status）
- groups: 账号分组
- tags: 标签
- account_tags: 账号标签关联
- settings: 系统设置
- temp_emails: 临时邮件（可能用于缓存）
```

### 参考项目架构
```
MailAggregator_Pro/
├── app/
│   ├── api/                      # FastAPI 路由
│   │   ├── accounts.py           # 账号管理 API
│   │   ├── emails.py             # 邮件查询 API
│   │   ├── rules.py              # 规则管理 API
│   │   └── settings.py           # 系统设置 API
│   ├── models/                   # SQLAlchemy 模型
│   │   ├── email.py              # EmailAccount + EmailRecord
│   │   ├── poll_status.py        # AccountPollStatus
│   │   └── mail_rule.py          # MailRule
│   ├── services/                 # 业务逻辑
│   │   ├── fetcher.py            # 邮件拉取服务（核心）
│   │   ├── rules_engine.py       # 规则引擎
│   │   ├── telegram.py           # Telegram 推送
│   │   └── webhook.py            # Webhook 通知
│   ├── worker/                   # 后台任务
│   │   └── poller.py             # 轮询循环（核心）
│   └── core/                     # 核心模块
│       ├── database.py           # 异步数据库
│       └── encryption.py         # 加密服务
└── frontend/
    └── src/
        └── config/
            └── mailProviders.ts  # 邮箱提供商配置（核心）

数据库表：
- accounts: 邮箱账号（email, provider, encrypted_pwd, host, port, is_active, sort_order, telegram_push_enabled, push_template, poll_interval_seconds）
- emails: 统一邮件存储（message_id, account_id, subject, sender, content_summary, body_text, body_html, received_at, is_read, labels）
- account_poll_status: 轮询状态（account_id, last_started_at, last_finished_at, last_success_at, last_error）
- mail_rules: 邮件规则
- telegram_filter_rules: Telegram 推送规则
```

## 🔑 核心实现要点

### 1. 邮箱提供商配置（mailProviders.ts）
```typescript
export const MAIL_PROVIDERS: MailProviderPreset[] = [
  {
    key: "gmail",
    label: "Gmail",
    host: "imap.gmail.com",
    port: 993,
    note: "需要在账户中开启 IMAP，并使用应用专用密码"
  },
  {
    key: "qq",
    label: "QQ 邮箱",
    host: "imap.qq.com",
    port: 993,
    note: "需要在 QQ 邮箱中开启 IMAP，并使用授权码"
  },
  // ... 更多提供商
];
```

### 2. 邮件拉取服务（fetcher.py）
- 使用 `imap_tools` 库统一处理所有 IMAP 邮箱
- 通过 `message_id` 去重，避免重复入库
- 首次同步：拉取历史邮件，不推送通知
- 增量同步：只拉取新邮件，推送通知

### 3. 后台轮询任务（poller.py）
- 全局轮询循环，每 5 秒检查一次
- 遍历所有 `is_active=True` 的账号
- 每个账号有独立的轮询间隔
- 记录轮询状态和错误信息

### 4. 统一邮件存储
- 所有邮箱的邮件存储在同一个 `emails` 表
- 通过 `account_id` 外键关联账号
- 支持跨账号查询和筛选

## 📝 需要深度分析的问题

### 1. 架构设计
- **问题**：如何在 Flask 同步架构中实现高效的多账号轮询？
- **考虑**：
  - 是否需要改造为异步架构（FastAPI + asyncio）？
  - 如何避免轮询任务阻塞主线程？
  - 如何处理大量账号的并发拉取？

### 2. 数据库设计
- **问题**：如何设计邮件存储表以支持高效查询？
- **考虑**：
  - 索引策略（account_id, received_at, message_id）
  - 邮件正文存储（body_text, body_html）的性能影响
  - 如何处理大量邮件的存储和查询性能？
  - 是否需要分表或归档策略？

### 3. IMAP 兼容性
- **问题**：不同邮箱提供商的 IMAP 实现差异如何处理？
- **考虑**：
  - Gmail 的特殊标签系统
  - QQ/163 邮箱的中文编码问题
  - Outlook 的文件夹结构差异
  - 错误处理和重试策略

### 4.  **问题**：如何优化大量邮件的拉取和存储性能？
- **考虑**：
  - 批量插入 vs 单条插入
  - 邮件去重策略（message_id 唯一索引）
  - 增量同步的时间窗口设置
  - 数据库连接池管理

### 5. 用户体验
- **问题**：如何设计友好的多邮箱管理界面？
- **考虑**：
  - 邮箱提供商选择（下拉菜单 + 自动填充）
  - 授权码/应用密码的获取指引
  - 轮询状态和错误提示
  - 统一邮件列表的筛选和排序

### 6. 安全性
- **问题**：如何安全存储多个邮箱的授权信息？
- **考虑**：
  - 密码加密算法（Fernet vs AES）
  - 密钥管理（环境变量 vs 配置文件）
  - 数据库加密
  - API 认证和授权

### 7. 迁移策略
- **问题**：如何从当前架构平滑迁移到新架构？
- **考虑**：
  - 数据库 Schema 升级
  - 现有账号数据的迁移
  - 向后兼容性
  - 分阶段实施计划

### 8. 扩展性
- **问题**：如何设计可扩展的架构以支持未来功能？
- **考虑**：
  - 规则引擎的设计
  - 推送通知的扩展（Telegram、邮件、Webhook）
  - 插件化架构
  - 多租户支持

## 🎯 期望的分析输出

请从以下维度进行深度分析：

### 1. 技术方案设计
- 详细的架构设计方案
- 数据库 Schema 设计
- 核心模块的实现思路
- 技术选型建议（同步 vs 异步、Flask vs FastAPI）

### 2. 实施路线图
- 分阶段实施计划（MVP → 完整功能）
- 每个阶段的关键任务和交付物
- 风险评估和应对策略
- 时间和资源估算

### 3. 代码实现建议
- 关键模块的伪代码或示例代码
- 最佳实践和设计模式
- 性能优化建议
- 测试策略

### 4. 潜在问题和解决方案
- 可能遇到的技术难点
- 兼容性问题
- 性能瓶颈
- 安全风险

### 5. 与参考项目的差异分析
- 哪些设计可以直接借鉴？
- 哪些需要根据当前项目调整？
- 哪些功能可以简化或省略？
- 哪些功能需要增强？

## 📚 参考资料

### 常见邮箱的 IMAP 配置
| 邮箱服务商 | IMAP 服务器 | 端口 | 授权方式 |
|-----------|------------|------|---------|
| Gmail | imap.gmail.com | 993 | 应用专用密码 |
| QQ邮箱 | imap.qq.com | 993 | 授权码 |
| 163邮箱 | imap.163.com | 993 | 授权码 |
| 126邮箱 | imap.126.com | 993 | 授权码 |
| Outlook | outlook.office365.com | 993 | 应用密码 |
| Yahoo | imap.mail.yahoo.com | 993 | 应用密码 |
| 阿里邮箱 | imap.aliyun.com | 993 | 密码 |

### 相关技术栈
- **IMAP 库**：`imap_tools`（Python）
- **异步框架**：FastAPI + SQLAlchemy（异步）
- **加密库**：`cryptography`（Fernet）
- **任务调度**：APScheduler / asyncio
- **前端框架**：React + TypeScript

## 💡 分析重点

请特别关注以下方面：

1. **架构演进路径**：如何从当前的 Outlook 单一邮箱架构演进到多邮箱统一管理架构？
2. **最小可行产品（MVP）**：第一阶段应该实现哪些核心功能？
3. **性能和可扩展性**：如何设计以支持 100+ 邮箱账号的场景？
4. **用户体验**：如何让用户轻松添加和管理多个邮箱？
5. **代码复用**：如何最大化利用当前项目的现有代码？

---

**注意**：这是一个真实的开源项目，请提供实用、可落地的分析建议，而不是理论性的讨论。
