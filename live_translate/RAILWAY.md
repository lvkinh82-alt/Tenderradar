# 把 Muối Từ 部署到 Railway（24 小时在线、固定 https 网址）

部署后不用开着 Mac，妈妈和朋友随时都能用；网址自动是 `https://`，手机可以用麦克风。

## 需要准备

- Railway 账号：https://railway.com （用 GitHub 登录最方便）。新账号有免费试用额度，之后 Hobby 方案约每月 5 美元。
- 你的 Anthropic API 密钥（`sk-ant-...`）。

## 步骤

1. **建立项目**：Railway 首页 → **New Project** → **Deploy from GitHub repo** → 选 `lvkinh82-alt/Tenderradar`。
   第一次会要求授权 Railway 读取你的 GitHub，按允许。
   （它会马上试着部署一次，可能失败，没关系，做完下面的设置就好。）

2. **指定分支和文件夹**：点进刚建立的服务 → **Settings**
   - **Source → Branch**：选 `claude/live-translate-ai-software-qm2muq`（如果之后合并进 main，就选 main）
   - **Source → Root Directory**：填 `/live_translate`

3. **设置变量**：服务 → **Variables** → **Raw Editor**，贴上下面内容并改成你的值，按 **Update Variables**：
   ```
   ANTHROPIC_API_KEY=sk-ant-你的密钥
   LIVE_TRANSLATE_MODEL=claude-haiku-5-5
   LIVE_TRANSLATE_INVITES=Mama:TUMUOI-1954
   LIVE_TRANSLATE_ADMIN_TOKEN=自己想一个长一点的管理密码
   ```

4. **保存用量记录**（建议）：在项目画布空白处按右键（或 ⌘K）→ **Volume** → 选这个服务，**Mount path** 填 `/data`。
   不加也能用，只是每次重新部署后，用量统计会归零（邀请码不受影响）。

5. **产生网址**：服务 → **Settings → Networking → Generate Domain**。
   如果要你填端口（port），填部署日志里 `Uvicorn running on http://0.0.0.0:xxxx` 的那个数字（通常是 `8080`）。
   会得到类似 `https://muoitu-production.up.railway.app` 的网址。

6. **测试**：用手机打开网址，输入邀请码 `TUMUOI-1954`，按“確認”，看到“✓ Mama，歡迎使用”就成功了。

## 登录规则：一个邀请码同一时间只能一部装置用

- 打开网址后先「登录」：输入邀请码，可勾选「**记住我**」（下次打开不用再登录）；不勾的话，关掉分页就会登出。
- 某个邀请码正在一部装置上使用时（最近 10 分钟内有用过），**别的装置不能用同一个码登录**。
- 原本那部装置按「**登出**」（首页上方或 ⚙️ 设置里），或闲置超过 10 分钟后，才能换另一部装置登录。
- 你可以在 `/admin?token=管理密码` 看到每个码「使用中 / 闲置」，并按「**强制登出**」（例如手机遗失、或码被别人拿去用）。
- 相关变量（可选）：
  - `LIVE_TRANSLATE_ONE_DEVICE=0`：关闭「一码一机」限制（不建议）
  - `LIVE_TRANSLATE_ACTIVE_MINUTES=10`：闲置多少分钟后可以换装置登录

## 日常管理（都在 Railway 的 Variables 页面）

| 想做的事 | 怎么改 `LIVE_TRANSLATE_INVITES` |
|---|---|
| 加一个人 | `Mama:TUMUOI-1954, 阿明:TUMUOI-2024` |
| 给某人每日上限 | `阿明:TUMUOI-2024:200`（第三段是每天最多几次，0 或不写 = 不限） |
| 停用某人 | 把那一段删掉（用量记录会保留） |

改完变量 Railway 会自动重新部署，大约一分钟后生效。

> 每一段都要写成 **名字:邀请码**（中间是英文冒号 `:`，段与段之间用英文逗号 `,`）。
> 邀请码只能用英文字母、数字和 `-`（不能有 `#`、空格等符号），长度 4–32 个字。
> 写错的那一段会被略过（其他人照常能用），并在 `/admin` 页面上方用红框提示。

- **看用量和费用**：打开 `https://你的网址/admin?token=你的管理密码`
- **换模型**：改 `LIVE_TRANSLATE_MODEL`（`claude-haiku-5-5` 最便宜、`claude-opus-5-5` 质量最好）
- **换密钥**：改 `ANTHROPIC_API_KEY`

## 手机 App

在 App 的 ⚙️ 设置 → 翻译服务器，填 Railway 的 `https://` 网址，再填邀请码即可。

## 安全提醒

- API 密钥只放在 Railway 的 Variables 里，不要写进代码、不要传给别人。
- 管理密码不要用简单的字；`/admin` 网址不要分享。
- 建议在 Anthropic Console 设每月花费上限。

## 📧 Gmail（「我的郵件」功能：看信、AI 帮忙回信）

让持有邀请码的人连接**自己的** Gmail，AI 用他的语言说明每封信，也可以帮忙**回信**。不会删信。
每个人都要在 Google 自己的页面登录并按「允许」，App 永远拿不到 Gmail 密码；看邮件还要输入他自己设的 **PIN**。

### 1. 在 Google Cloud 建立「OAuth 应用」（免费，只做一次）

1. 打开 https://console.cloud.google.com ，用你的 Google 账号登录 → 左上角「选择项目」→ **新建项目**，名称例如 `Muoi Tu`。
2. 上方搜索 **Gmail API** → 点进去 → **启用**。
3. 左侧选单 **Google Auth Platform**（旧版叫「OAuth 同意屏幕」）→ **开始**：
   - 应用名称：`Muối Từ`；用户支持邮箱：你的邮箱
   - 目标对象（Audience）：**外部 External**
   - 联系邮箱：你的邮箱 → 同意条款 → 创建
4. **数据访问（Data access）** → 添加或移除范围 → 勾选这两个 → 更新 → 保存：
   - `.../auth/gmail.readonly`（"View your email messages and settings"，看信）
   - `.../auth/gmail.send`（"Send email on your behalf"，回信）
5. **目标对象（Audience）** → 发布状态保持 **「测试中 Testing」** → **测试用户 → 添加用户**：把每个要用的 Gmail 加进来（例如 `tumuoi1954@gmail.com`）。最多 100 个。
6. **客户端（Clients）** → **创建客户端**：
   - 应用类型：**Web 应用**
   - 已获授权的重定向 URI：`https://你的Railway网址/api/mail/callback`（例如 `https://muoitu-production.up.railway.app/api/mail/callback`）
   - 创建后复制 **客户端 ID** 和 **客户端密钥**。

### 2. 在 Railway 加上变量

```
GOOGLE_CLIENT_ID=刚复制的客户端ID
GOOGLE_CLIENT_SECRET=刚复制的客户端密钥
PUBLIC_BASE_URL=https://你的Railway网址
```

可选：规定某个邀请码只能连接指定的 Gmail（用别的账号登录会被拒绝）：
```
LIVE_TRANSLATE_MAILBOXES=TUMUOI-1954=tumuoi1954@gmail.com, LETAM-1972=letam1972@gmail.com
```

**一定要加 Volume（挂载 `/data`）**：Gmail 连接和 PIN 都存在那里，没有 Volume 的话每次重新部署都要重新连接、重设 PIN。

### 3. 使用

- 首页 →「📧 我的邮件」→ 设定 4–8 位数字 PIN →「设定并连接 Gmail」→ 在 Google 页面登录 → 按「允许」。
- Google 会显示「**Google 尚未验证这个应用**」：这是测试模式的正常提示，按「**高级 → 前往 Muối Từ（不安全）**」继续即可（是你自己的应用）。
- **测试模式每 7 天要重新连接一次**：到期时 App 会提示「重新连接」，重新按一次即可，PIN 不变。
- 忘记 PIN：在 `/admin?token=管理密码` 那一行按「重设 PIN」，对方重新设定并连接。
- 不想要郵件功能：不设 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` 即可。

### ✍️ AI 帮忙回信

- 每封信下面有「✍️ 回覆」→ 按大按钮用自己的语言**说**想回什么（或打字）→ AI 用原信的语言（或你选的语言）写好回信，并用你的语言念给你听「会寄给谁、内容是什么」。
- 想改就再按「🎤 我要修改」说怎么改（例如「客气一点」「改成星期六」），也可以直接改文字。
- **一定要按「✅ 寄出」并再输入一次 PIN 才会寄出**；AI 自己不会寄。
- 只能**回覆给原寄件人**（信里的 Reply-To，没有就是 From），地址由服务器决定，AI 和信件内容都改不了；每个邀请码每天最多寄 20 封（`MAIL_SENDS_PER_DAY` 可改）。
- 加这个功能之前就已连接的人：按「回覆」时会提示「重新连接 Gmail」，在 Google 页面勾选「传送电子邮件」即可。
- 不想要回信功能：设 `LIVE_TRANSLATE_MAIL_SEND=0`（只会要求「读信」权限）。

### 隐私说明

- 邮件内容会传给 Claude AI 做说明（Anthropic API 不会用这些内容训练模型）。
- Google 的连接凭证在服务器上加密保存；PIN 只保存加密后的指纹，连续错 5 次锁 15 分钟。
- 邮件内容一律当作「不可信」：信里写的任何指示 AI 都不会照做，只会说明；看起来像诈骗的信会特别提醒。
