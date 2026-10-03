# Ubuntu 临时分支验证

`ubuntu-support` 基于 Windows v0.5.4 后的主分支；共用最新素材、编排与源码。
Windows Release 不变。本分支尚未完成 Ubuntu 实机验收，不是新的正式发布。

## 下载和启动

先退出旧猫咪老师。保留旧目录作回退，在新目录下载：

```bash
mkdir -p ~/PET
cd ~/PET
git clone --branch ubuntu-support https://github.com/sfeng13/nyanko-sensei-pet.git nyanko-sensei-pet
cd nyanko-sensei-pet
NYANKO_PYTHON="$HOME/PET/dsh-pet-indesktop/.venv/bin/python" bash start.sh
```

这条命令复用已经可用的大肥鱼环境，不修改该环境。路径不同时改 `NYANKO_PYTHON`。
不要把 Windows 的 runtime 文件夹复制到 Ubuntu，也不要安装 Windows 的锁定依赖清单。

若已有环境缺少依赖，可以在本项目创建独立环境：

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libxcb-cursor0 fonts-noto-cjk
bash install-ubuntu.sh
bash start.sh
```

首版依赖范围面向 Ubuntu 22.04 的 Python 3.10；最终版本需按实机成功结果锁定。
设置沿用 `~/.config/dsh-pet-standalone-nyanko-sensei/`，不覆盖旧配置。
启动日志在 `${XDG_STATE_HOME:-$HOME/.local/state}/nyanko-sensei/logs/launcher.log`。
不要把设置、登录凭据或个人日志提交到仓库。

## 可选 Codex 联动

先安装并登录 Ubuntu 本机的 Codex CLI。使用启动桌宠的同一个 Python：

```bash
# 使用本项目环境时：
PYTHON_BIN="$PWD/.venv/bin/python"
# 复用大肥鱼环境时，改成：
# PYTHON_BIN="$HOME/PET/dsh-pet-indesktop/.venv/bin/python"
"$PYTHON_BIN" scripts/codex_hooks.py install
"$PYTHON_BIN" scripts/codex_hooks.py status
```

安装会备份并合并 `~/.codex/hooks.json`（或 `CODEX_HOME`），保留其他 Hook。
在 Codex 中审阅并信任这些 Hook；随后用真实对话验证开始、完成和中断。
额度需要本机 CLI 登录，Windows 的账号配置不会随项目迁移。

```bash
"$PYTHON_BIN" scripts/codex_hooks.py repair
# 关闭本桌宠的 Hook，保留其他 Hook：
"$PYTHON_BIN" scripts/codex_hooks.py remove
```

移动项目或虚拟环境后需重新 repair，并重新审阅变化后的命令。

## 验收与继续开发

逐项确认透明背景、中文文字、右键菜单、慢走/小跑、倍速、眯眯眼、拖拽和位置锁定；
检查额度描边及真实对话提示。若 Wayland 下窗口置顶、定位或拖拽有问题，记录会话类型，
也可在登录界面选择 Ubuntu on Xorg 对照验证，不要仅凭进程启动判定成功。

后续更新先确认没有未提交改动，再执行 `git pull --ff-only`。
有 Ubuntu 本地修复就提交到 `ubuntu-support`，验证通过后再合并 main。
旧版个人修改应逐项比较合入，勿把旧版整个源码覆盖到新分支。

本地 Windows 检查不能替代 Ubuntu 桌面、音频、窗口管理器和 Hook 实机验收。
