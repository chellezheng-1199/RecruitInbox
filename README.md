# 求职邮件看板

一个帮你「不错过秋招邮件」的小工具：定时抓取邮箱里最新邮件，用 DeepSeek 自动识别哪些是 **面试 / 测评 / 笔试 / 宣讲会 / Offer / 拒信**，把关键时间和待办汇总到一个网页看板上。

> 支持多个邮箱同时抓取；验证码、广告等噪音邮件会被自动过滤掉。

## 功能一览

- **多邮箱聚合**：最多 5 个邮箱账号同时抓取，自动合并。
- **AI 自动分类**：识别邮件类型，并提取公司、摘要、截止时间、事件日期、优先级。
- **待办视图**：需要你行动的事项集中展示，过期自动归档，支持手动添加。
- **日历视图**：事项按日期落到月历，按时间排序，过期置灰不消失。
- **可配置刷新策略**：自定义刷新间隔，夜间 / 周末 / 节假日不刷新。
- **多邮箱同时抓取**：一个邮箱挂了不影响其它。
- **图示（因为涉及很多个人信息，所以做了部分打码处理～）**：
- <img width="1019" height="762" alt="image" src="https://github.com/user-attachments/assets/ae9377d9-e7ff-4159-8912-472ac3384531" />
- <img width="1135" height="749" alt="image" src="https://github.com/user-attachments/assets/676cca5d-5e0a-40d2-95bb-ab9aa7fec831" />



## 快速开始

### 第 1 步：准备环境

- Python 3.9 及以上（开发测试用的是 3.14）
- 能联网（抓邮件走 IMAP，分类走 DeepSeek API）

```bash
git clone <你的仓库地址>
cd <仓库目录>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> 依赖只有两个：`flask`（网页服务）、`requests`（调 DeepSeek）。

### 第 2 步：配置

```bash
cp .env.example .env
```

用编辑器打开 `.env`，至少填好：

1. **邮箱**：`EMAIL1_ADDRESS` + `EMAIL1_AUTH_CODE`（地址和授权码都填了才会被抓取，想抓多个邮箱就继续填 `EMAIL2_*` …）
2. **DeepSeek**：`DEEPSEEK_API_KEY`

```ini
# 邮箱 1（必填）
EMAIL1_ADDRESS=你的邮箱@example.com
EMAIL1_AUTH_CODE=你的授权码
EMAIL1_SERVER=imap.163.com
EMAIL1_PORT=993

# 邮箱 2（可选，多邮箱就接着填）
EMAIL2_ADDRESS=另一个邮箱@example.com
EMAIL2_AUTH_CODE=你的授权码
EMAIL2_SERVER=imap.163.com
EMAIL2_PORT=993

# DeepSeek
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
```

其余参数：

| 项 | 说明 | 默认 |
|---|---|---|
| `EMAIL{n}_SERVER` | IMAP 收件服务器（不填默认 `imap.163.com`） | — |
| `EMAIL{n}_PORT` | 端口 | 993 |
| `DEEPSEEK_MODEL` | 模型 | deepseek-chat |
| `LOOKBACK_DAYS` | 拉取最近多少天邮件（2 = 今天+昨天） | 2 |
| `MAX_BODY_CHARS` | 发给 DeepSeek 的正文最长字符数 | 3000 |

> 刷新间隔（多久检查一次新邮件）在网页看板右上角「⚙️ 刷新设置」里改，默认 60 分钟，无需写进 `.env`。

### 第 3 步：运行

```bash
python app.py
```

浏览器打开 <http://127.0.0.1:8000>，配置正确的话会自动开始后台定时抓取。

---

## 怎么获取邮箱授权码？

> ⚠️ 授权码**不是**邮箱登录密码，是专门给第三方程序用的临时口令。

**163 / 126 / QQ 邮箱**：网页登录邮箱 → 设置 → POP3/SMTP/IMAP 服务 → 开启 IMAP 服务 → 按提示短信验证后生成一串「授权码」，复制填进 `EMAIL{n}_AUTH_CODE`。

**Gmail**：需要开启两步验证后，在「安全 → 应用专用密码」里生成。

**学校 / 企业邮箱**：以邮箱设置页写明的「IMAP 授权码 / 客户端专用密码」为准；如果支持直接开启 IMAP，也可能用登录密码即可。

## IMAP 服务器地址怎么填？

- 163 / 126 邮箱：`imap.163.com`
- QQ 邮箱：`imap.qq.com`
- Gmail：`imap.gmail.com`
- 学校 / 企业邮箱：去邮箱设置里的「POP3/SMTP/IMAP」页，页面上会明确写出「收件服务器地址」，照抄即可。

## DeepSeek API Key 怎么获取？

1. 打开 <https://platform.deepseek.com> 注册登录
2. 左侧「API Keys」→「创建 API Key」
3. 复制 `sk-` 开头的那串，填进 `.env` 的 `DEEPSEEK_API_KEY`

> 费用：DeepSeek 很便宜，一封邮件分类大约几厘钱到几分钱。

## 看板怎么用

页面顶部两个标签页（顺序：**待办 & 日历** 在前，**邮件看板** 在后）。

- **待办列表**：需要你行动的事项（面试 / 笔试 / 测评 / Offer / 拒信），勾选标记完成，过期自动归档。
- **手动添加**：点「＋ 手动添加待办」录入邮箱里没有的事（名称 + 类型 + 日期 + 时间）。
- **日历**：事项按日期落在月历，按当天时间排序，过期置灰仍可见。
- **邮件看板**：有效邮件卡片流（类型 / 公司 / 摘要 / 截止时间 / 优先级）。
- **⚙️ 刷新设置**：改刷新间隔、夜间 / 周末 / 节假日不刷新。

## 目录结构

```
.
├── app.py            # Flask 主程序 + 后台轮询
├── config.py         # 读取 .env，解析多邮箱配置
├── mail_fetcher.py   # IMAP 抓取 + 正文解析
├── classifier.py     # 调 DeepSeek 分类 + 提取字段
├── schedule.py       # 刷新策略 + 节假日清单 + 配置读写
├── storage.py        # data.json 读写
├── templates/
│   └── index.html    # 前端看板
├── .env.example      # 配置模板（复制成 .env 使用）
└── requirements.txt
```

## 常见问题

- **连接 / 登录失败**：确认 `AUTH_CODE` 是授权码而非登录密码；确认 `EMAIL{n}_SERVER` 与邮箱设置页一致。
- **收不到某邮箱的邮件**：多个邮箱互相独立，一个失败不影响其它；看页面「最近更新」或 `data.json` 的 `errors` 字段定位原因。
- **分类不出来 / 全被过滤**：确认 `DEEPSEEK_API_KEY` 正确、账户有余额。
- **想调刷新频率**：看板右上角「⚙️ 刷新设置」里改间隔，即时生效、无需重启。

## 隐私与安全

- `.env`（含授权码、API Key）和 `data.json`（含邮件内容）都已加入 `.gitignore`，**不要**手动提交它们。
- 本工具默认只在 `127.0.0.1` 本机运行，不上传你的邮件到任何第三方（分类只把「发件人 + 主题 + 时间 + 正文片段」发给 DeepSeek，用于判断类别）。

## 许可

MIT License。欢迎提 Issue / PR。
