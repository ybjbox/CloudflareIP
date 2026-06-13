# Cloudflare IP 自动测速与 DNS 优选同步

本项目专为个人代理节点加速设计。通过 GitHub Actions 定时运行测速脚本，筛选出最快的 Cloudflare 边缘节点 IP，并将其**自动、全量同步**到你指定的 Cloudflare 域名解析（A 记录）中，同时自动生成订阅文件，并支持 Bark 消息实时推送。

---

## 🌟 核心功能

1. **多地区独立测速**：
   - **SG（新加坡）**、**JP（日本）**、**US（美国）**：通过独立脚本分别测速并筛选出本地区最快的 20 个节点 IP。
   - **US_MAX（综合优选）**：从公开优选源抓取最新测速数据，并按速度从大到小对 IP 进行降序排序。
2. **DNS 声明式全量同步（全部绑定）**：
   - 自动对比本地测速 IP 列表与 Cloudflare 上现有的 A 记录。
   - **保留不变**：对依然有效的优选 IP 保持原样；
   - **自动新建**：对新增优选 IP 自动新建 A 记录并关闭代理状态（仅限 DNS 灰色云朵）；
   - **自动删除**：对已失效/多余的旧 IP 解析进行删除。
   - 彻底解决多个 IP 并发更新冲突及 Cloudflare API `81058` 重复解析错误。
3. **订阅文件自动更新**：
   - 定时生成 `SG.txt`、`JP.txt`、`US.txt` 和 `US_MAX.txt` 订阅文件并推送回仓库，可作为你的节点优选 IP 源使用。
4. **并发推送与历史自动清理**：
   - 引入 Rebase 机制，完美避开多个工作流整点同时推送代码到主分支时的并发冲突。
   - 自动运行历史清理工作流，使每个任务严格只保留**最新的 20 次**历史记录，保持仓库极其精简。
5. **Bark 推送支持**：
   - 支持在每次域名解析自动同步完成后，通过 Bark 实时推送同步结果（Skipped/Created/Deleted）到你的手机上。

---

## 🛠️ 部署与使用指南

### 第一步：Fork / 导入本仓库
直接克隆或导入本仓库到你的 GitHub 账号。

### 第二步：在 GitHub 配置 Actions Secrets
前往你的 GitHub 仓库的 **Settings** ➡️ **Secrets and variables** ➡️ **Actions** ➡️ 点击 **New repository secret**，添加以下 4 个变量：

| Secret 键名 | 作用描述 | 示例值 |
| :--- | :--- | :--- |
| `CF_API_TOKEN` | Cloudflare API 令牌（需要有编辑 DNS 的权限） | `xxxxxx_xxxxxxxxxxxxxxxxx` |
| `CF_ZONE_ID` | Cloudflare 域名区域区域 ID | `a1b2c3d4e5f6g7h8i9j0...` |
| `CF_BASE_DOMAIN` | 你的主域名（用于自动拼接前缀） | `yourdomain.com` |
| `BARK_URL` (选填) | Bark 推送地址（用于手机接收结果通知） | `https://api.day.app/YOUR_KEY` |

> 💡 **如何获取 Cloudflare 凭证**：
> - **ZONE_ID**：在 Cloudflare 域名控制台的右侧“概述”页中可以直接复制。
> - **API_TOKEN**：在右上角“我的个人资料” ➡️ “API 令牌” ➡️ “创建令牌” ➡️ 使用“编辑区域 DNS”模板创建。

### 第三步：在 Cloudflare 创建子域名 A 记录
前往你的 Cloudflare DNS 控制台，手动为你配置的主域名添加以下 4 个子域名（A 记录，IP 随便填一个，如 `1.1.1.1`，必须**关闭代理状态**，即保持“灰色小云朵/仅限 DNS”）：
* **sg**（最终为 `sg.yourdomain.com`）
* **jp**（最终为 `jp.yourdomain.com`）
* **us**（最终为 `us.yourdomain.com`）
* **usmax**（最终为 `usmax.yourdomain.com`）

> ⚠️ **注意**：脚本在后续定时运行时，会自动动态管理并覆盖这四个子域名下的 A 记录。

### 第四步：启用与手动触发工作流
由于 GitHub 安全限制，Fork 或克隆的仓库默认不自动运行工作流。
1. 前往仓库的 **Actions** 标签页。
2. 页面顶部会提示 "Workflows are not running..."，点击 **Enable workflows** 激活。
3. 可以在左侧分别找到 `SG`、`JP`、`US`、`US_MAX`，点击 **Run workflow** ➡️ **Run workflow** 进行首次运行测试。

---

## 🛰️ 对应子域名与订阅文件对照表

| 任务名称 | 定时周期 | 生成的订阅文本 | 自动更新绑定的域名 |
| :--- | :--- | :--- | :--- |
| **SG** | 每小时 | `SG.txt` | `sg.yourdomain.com` |
| **JP** | 每小时 | `JP.txt` | `jp.yourdomain.com` |
| **US** | 每小时 | `US.txt` | `us.yourdomain.com` |
| **US_MAX** | 每小时 | `US_MAX.txt` | `usmax.yourdomain.com` |
| **Clean Runs**| 每天 0 点 | - (自动清理多余 Actions 日志，仅保留最新 20 条) | - |

---

## 📱 客户端配置示例（以 Clash YAML 节点为例）

将节点配置中的 `server`（服务器地址）替换为你的优选域名，**混淆 Host 和 SNI 必须保留为你真实的后端节点服务域名（如 Cloudflare Worker 域名）**。

```yaml
proxies:
  - name: "新加坡优选节点"
    type: vless
    server: sg.yourdomain.com               # 👈 修改为你的新加坡优选域名
    port: 443
    uuid: 04ede3a4-83ee-47d9-8727-93ee97b94ed7
    tls: true
    skip-cert-verify: false
    client-fingerprint: chrome
    network: ws
    ws-opts:
      path: "/"
      headers:
        Host: your-worker-domain.com           # 👈 保持你的真实后端/伪装域名不变
    servername: your-worker-domain.com         # 👈 保持你的真实后端/SNI不变
```

---

## 👨‍💻 免责声明
本项目基于公开测速算法与接口集成，所得 IP 均为 Cloudflare 官方公开的 CDN 节点 IP。请在合规及合理范围内使用。
