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

## 日常管理（都在 Railway 的 Variables 页面）

| 想做的事 | 怎么改 `LIVE_TRANSLATE_INVITES` |
|---|---|
| 加一个人 | `Mama:TUMUOI-1954, 阿明:TUMUOI-2024` |
| 给某人每日上限 | `阿明:TUMUOI-2024:200`（第三段是每天最多几次，0 或不写 = 不限） |
| 停用某人 | 把那一段删掉（用量记录会保留） |

改完变量 Railway 会自动重新部署，大约一分钟后生效。

- **看用量和费用**：打开 `https://你的网址/admin?token=你的管理密码`
- **换模型**：改 `LIVE_TRANSLATE_MODEL`（`claude-haiku-5-5` 最便宜、`claude-opus-5-5` 质量最好）
- **换密钥**：改 `ANTHROPIC_API_KEY`

## 手机 App

在 App 的 ⚙️ 设置 → 翻译服务器，填 Railway 的 `https://` 网址，再填邀请码即可。

## 安全提醒

- API 密钥只放在 Railway 的 Variables 里，不要写进代码、不要传给别人。
- 管理密码不要用简单的字；`/admin` 网址不要分享。
- 建议在 Anthropic Console 设每月花费上限。
