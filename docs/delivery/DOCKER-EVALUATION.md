# ESG-Agent 1.5 交付形式与 Docker 评估

## 1. 结论与排序

1. 方案 B：Release ZIP + 固定依赖 + PowerShell，作为主要接收方交付。
2. 方案 A：Git clone + 固定 commit/tag，作为维护、审计和重建入口。
3. 方案 C：PostgreSQL、后端、前端全栈 Docker Compose，延期。

选择依据是授权接收方能恢复相同行为，同时把环境差异、非公开数据、密钥和运维复杂度控制在可验证范围。当前 Compose 只封装固定 digest 的 PostgreSQL/pgvector；后端、前端和默认关闭的 OCR 工具继续运行在 Windows 本机。

## 2. 方案总体比较

| 维度 | A：Git clone | B：Release ZIP | C：全栈 Compose |
| --- | --- | --- | --- |
| 接收门槛 | 需要 Git 与 commit/tag 操作 | 解压、初始化、双击 EXE | 需要构建/拉取多镜像并处理挂载 |
| 审计性 | 最强，可直接查看历史 | manifest + checksum + 固定 commit | 还需镜像 digest、SBOM 和构建链 |
| 未跟踪文件风险 | 接收方需理解工作区 | 构建器只读 commit，默认排除 | build context 需另建严格规则 |
| Windows 体验 | 适合维护者 | 当前最合适 | 路径、卷和 Docker Desktop 状态更复杂 |
| 首次联网成本 | 下载源码与全部依赖 | 下载约 1.9 MB 中间候选 ZIP及全部依赖 | 下载/构建多个镜像与层缓存 |
| 离线成本 | 需准备 Git 与包缓存 | 需另做 uv/pnpm/镜像缓存 | 需分发全部镜像 tar、校验与导入脚本 |

ZIP 大小是 Task 8 中间候选的实测值，Task 10 文档和元数据加入后会变化。当前固定 PostgreSQL/pgvector 镜像本机展开大小约 156 MB。全栈镜像尚未构建；后端若包含 OCRmyPDF、Ghostscript、Tesseract 语言包和 PDF 工具，工程量级预计为 1–3 GB，前端与构建层还会增加数百 MB，最终必须以实际构建和 `docker image inspect` 为准。

## 3. 逐项技术矩阵

| 项目 | A/B 依赖与风险 | C 依赖与风险 | 验证方法 | 是否阻断默认链路 |
| --- | --- | --- | --- | --- |
| OCRmyPDF | Windows 可选安装；版本 17.8.0；缺失时 OCR 保持关闭 | Python、qpdf、Ghostscript、Tesseract 的系统包与版本需在同一镜像固定，平台差异明显 | `ocrmypdf --version`；受控页试点；关闭态 capability | 否，`OCR_ENABLED=false` |
| Ghostscript | Windows 可选 10.07.1；路径可能因安装方式不同 | Linux 包版本、字体和安全策略会改变 PDF 行为 | `gswin64c -version` 或容器版本；固定 PDF 冒烟 | 否，OCR 关闭 |
| Tesseract 与语言包 | Windows 可选 5.5.0；需 `chi_sim+eng+osd` | 镜像必须固定引擎和 traineddata，语言包显著增加体积 | `tesseract --version`、`--list-langs`、OCR 页对照 | 否，OCR 关闭 |
| PDF 页面渲染 | 当前 pdfplumber/Pillow 链在 Windows 已验收；系统字体差异仍需记录 | headless 系统库、字体和图形依赖需纳入镜像 | `/pages/{n}/image` 返回 PNG；浏览器核对固定页 | 是，产品证据页必须可用；与 OCR 无关 |
| Windows 文件路径 | A/B 使用项目相对路径，旧绝对路径只在受控恢复时按哈希规范化 | bind mount、盘符、反斜杠、文件共享权限会增加转换层 | 不同解压目录启动；runtime path 测试；无绝对路径扫描 | 是，相对路径失败会破坏迁移 |
| 持久化目录 | B 用本地 runtime + 命名 volume，边界直观但需授权备份 | 需分别设计数据库 volume、上传/派生/导出 mount 与 UID/权限 | 重启、换目录、备份恢复、volume identity | 是，数据不得随容器消失 |
| 数据库备份恢复 | 现有 PowerShell + 容器内 `pg_dump/pg_restore` 已验证 | 可复用命令，但还需处理跨 Compose project 与镜像兼容 | custom dump、内外 checksum、新目标库恢复 | 是 |
| 镜像体积 | A/B ZIP 小，联网安装缓存大但不进入交付包 | 估计 1–3 GB OCR 后端 + 前端层 + 约 156 MB 数据库展开层；未实测 | 实际 build 后记录各 digest、压缩/展开大小 | 不阻断功能，阻断便捷/离线交付决策 |
| 首次拉取时间 | 取决于 uv、pnpm 和数据库镜像缓存；可分阶段重试 | 多镜像下载与解压集中发生，弱网络风险更高 | 清缓存环境计时，分别记录下载、构建、migration | 不改变语义，可能使安装体验不合格 |
| 完全离线交付 | 当前未提供；需单独准备包缓存和数据库镜像 | 还需镜像 export/import、SBOM、许可证、平台架构与 checksum | 断网隔离机完整恢复演练 | 当前不阻断本地联网交付；阻断离线承诺 |

## 4. 为什么当前不创建全栈 Dockerfile

全栈容器会扩大本阶段范围：需要固定操作系统包、字体、PDF/OCR 工具、Node 构建层、健康检查、非 root 权限、Windows 挂载、日志、多个持久卷、镜像漏洞与许可证清单。它不会消除数据库备份、密钥注入和资产授权问题，还会增加首次拉取和完全离线交付成本。

在当前单机 Windows、默认 OCR 关闭、允许安装阶段联网的前提下，B 提供最短接收路径，A 提供审计底座，C 的额外成本没有成为恢复同一产品行为的必要条件。

## 5. 重新评估 C 的触发条件

满足任一条件时重新立项评估：

- 明确要求 Linux 或服务器部署；
- 需要支持两个以上独立接收环境；
- OCR 必须容器化并纳入默认交付；
- 要求完全离线镜像交付。

触发后先做小型可丢弃原型，实测镜像体积、首次拉取、PDF 页面渲染、OCR 固定页、Windows mount、备份恢复和无外部调用，再决定是否加入正式 Dockerfile 与全栈 Compose。
