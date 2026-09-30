# 猫咪老师桌宠

Windows x64 桌面宠物，以《夏目友人帐》的猫咪老师（斑，招财猫形态）为角色，基于 [dsh-pet-indesktop](https://github.com/MerZlin/dsh-pet-indesktop) 改编。包含待机、点击、团子、左右散步与小跑、探看、小酌、烤鱿鱼、炸虾、轻跳及桌面 Codex 状态提示。

## 下载与安装

到 [Releases](https://github.com/sfeng13/nyanko-sensei-pet/releases/latest) 下载其中一种：

- **Online-Setup.zip**：体积较小的安装引导包。解压后双击 `Setup.cmd`；首次安装会联网下载完整运行内容，并自动校验 SHA-256。
- **Windows-x64-Offline.zip**：完整离线包。解压后双击其中的 `Setup.cmd` 安装。

两种方式安装相同版本。安装到 `%LOCALAPPDATA%\Programs\NyankoSensei`，只影响当前 Windows 用户，不需要管理员权限，也不要求目标电脑预装 Python。在线方式首次下载的内容仍包含完整运行环境；之后桌宠可以离线启动。发布附件中的 `SIZE_REPORT.md` 列出 Python 运行环境、安装目录和两种下载包的实测大小；`SHA256SUMS.txt` 提供两个下载包的校验值。

安装器默认勾选“启用 Codex 联动”。取消勾选会确保桌宠自己的 Hook 处于关闭状态。安装与修复前会备份已有 `%USERPROFILE%\.codex\hooks.json`；只合并或移除猫咪老师自己的三个事件，不覆盖其他 Hook。安装器不会替你信任 Hook：请在 Codex 中查看 `/hooks` 并审阅、信任这些定义后，它们才会运行。若更改过 `CODEX_HOME`，安装器会使用该目录下的 `hooks.json`。联动不保存对话正文、转录或账号凭据，只记录会话/轮次标识和开始、完成、中断事件。额度读取由已登录的 Codex CLI 完成；未安装或未登录时额度状态会显示不可用。

开始菜单中的“Codex 联动管理”可以修复或关闭联动。“卸载猫咪老师桌宠”会移除桌宠自身的 Hook 与程序文件，保留其他 Hook、个人设置和日志。个人数据位于 `%LOCALAPPDATA%\NyankoSensei`。

## 重新构建

源码仓库不保存嵌入式 Python 环境和生成的安装包。Windows 构建会下载固定版本的 Python embeddable 发行包、按锁文件安装运行依赖、编译启动器和无窗口 Hook 转发器，最后生成在线引导包、离线包、SHA-256 清单与体积报告。

本地构建需要 Windows x64、PowerShell 7、Python 3.13.14 x64 和 Windows 自带的 .NET Framework C# 编译器：

```powershell
./packaging/build_windows.ps1 -Version v0.5.3
```

如果本机已有兼容的 Python 3.13.14 嵌入环境，可仅用于本地复现：

```powershell
./packaging/build_windows.ps1 -Version v0.5.3 -PythonRuntimeSource C:\path\to\python313
```

正式发行由推送 `v*` 标签触发 `.github/workflows/publish-windows.yml`，在 Windows x64 构建机上重新生成并上传发布附件。任何本地运行环境都不会被提交到 Git。

## 目录

- `app/`：桌宠上游程序源码及本仓库保留的修改。
- `characters/nyanko-sensei/`：角色清单和运行动画素材。
- `nyanko_runtime.py`、`nyanko_choreography.py`：猫咪老师动作编排与桌面联动。
- `nyanko_codex_hook.py`、`nyanko_codex_link.py`、`scripts/codex_hooks.py`：Codex 事件桥接、额度读取和 Hook 配置管理。
- `packaging/`：Windows 用户级安装器、启动器、Hook 转发器和构建脚本。

## 来源与说明

桌宠核心基于上游提交 `0da5f1616862187a38fd3e0db85faafbd6a4f456`，上游 MIT 许可和第三方通知见 `app/LICENSE`、`app/THIRD_PARTY_NOTICES.md`。猫咪老师动画为本项目角色素材。该桌宠为非官方粉丝作品，与《夏目友人帐》版权方无关联。
