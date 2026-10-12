# dsh-pet → 猫咪老师功能迁移核对

基线：`ubuntu-support` 的 `8838497`。本轮沿用原启动器的纯桌宠模式（`enable_chat=False`），逐项追踪设置控件、保存路径、运行时消费者、菜单回调和角色动作包。没有启用新的联网 AI 服务，没有创建标签或发布 Release。

“已接入”表示存在完整调用路径并通过相应本地测试；不等于 Windows/macOS/Ubuntu 桌面实机验收。当前可用机器是 Linux + Qt offscreen；音频听感、原生托盘、置顶/穿透、真实桌面全屏和 Wayland 合成仍须目标桌面验证。

## 明确的迁移缺口与本轮修复

| 功能 | 原来为什么无效 | 本轮结果 |
| --- | --- | --- |
| 动作等待间隔 | 猫咪老师重写动画结束处理，绕过原版 gap timer | 整段吃团子、睡觉、走路等动作结束后才进入配置的休息间隔；不拆断入场/循环/收尾；点击可即时结束自动等待 |
| 通用 Agent 动作池 | `cats` 仍把内部循环/收尾片段当独立动作；名称与原版写代码/吃 Token 不同 | 分类统一成可播放公开动作；忙碌采用警觉探看/得意说教，间歇采用伸懒腰/眯眯眼，不虚构不存在的素材 |
| Agent 动作队列与连续反馈 | 角色动画结束路径从未消费原版待播队列；内部循环也没被判为完整的一次性动作 | 请求在整段动作安全结束后接续；仍忙则继续下一段；空闲事件取消过期队列；内部阶段不被硬切 |
| 独立进程多开 | 原版仍启动 `python -m pet`，跳过角色启动器；角色启动器又把所有实例固定到 slot 0 | 子进程使用同一角色入口，竞争空闲槽；显式 `--slot` 保留；主宠和子宠均保留角色编排、游戏、状态提示及独立设置 |
| Ubuntu 配置目录 | `Config` 忽略 `XDG_CONFIG_HOME`，与角色发现/其他 XDG 组件不一致 | 采用标准 XDG 配置目录；未设置时继续使用原 `~/.config` 路径；不自动搬迁或覆盖旧配置 |
| 更新检查、项目页 | 查询 dsh-pet Release，并用上游 4.1.0 与本产品 0.5.x 比较 | 查询本仓库；正式安装读取 `version.txt`，源码基准保持当前 0.5.4；版本比较使用运行时配置值；不回退到上游 update.json/网盘 |
| 音乐自动唱歌的无效开关 | 猫咪老师没有悠闲哼歌素材；音乐检测本身也仅支持 Windows | 保留原保存值，但禁用控件并明确提示缺素材；停止本角色无效轮询，没有用别的动作冒充唱歌 |
| 退出子宠说明 | 设置文字称会删除配置/会话/待办，实际实现保留数据 | 修正说明，行为继续保留数据 |

回归先验证旧行为失败，再验证修复。两条旧预热测试还被发现假定“写代码”总是第一个素材；现改为同步实际首个素材，保留所有阻塞、去重及首帧断言。哈希种子 0 下旧测试 2 失败，修复后同种子 2 通过；没有固定一个有利的随机种子掩盖问题。

## 没迁移、没启用或需要决定的功能

| 项目 | 当前实际状态 | 建议 |
| --- | --- | --- |
| AI 对话、API 设置、视觉模型、看看屏幕 | 上游模块仍在，但纯桌宠入口显式关闭，设置页/菜单不创建入口 | 需明确是否要做带 AI 的猫咪老师版本；届时接入 API 配置、错误反馈和实际服务测试，不能只改一个开关 |
| 点击/自动查询 DeepSeek 余额 | 同样受 `enable_chat=False` 限制；不等于 Codex 剩余额度 | 使用 Codex 的用户通常不需要；先保留代码，不擅自要求 API Key |
| 主动识屏 | Windows 专用，且需 AI；Ubuntu 没有实现 | 需要桌面捕获、隐私与模型连接的完整适配；本轮不移植 |
| Harness 自动启动、DSH Bridge | 纯桌宠入口禁用本地 Harness；DSH Agent 的桥接只在用户启用并安装该服务后有意义 | 未使用 DSH 时无需开启；桥接依赖/安装及真实 DSH 事件未验收 |
| 系统音乐唱歌 | 无猫咪老师唱歌素材；Ubuntu/macOS 音乐检测未实现 | 先决定是否保留，再补素材及平台检测；本轮仅清楚标示不可用 |
| 原“厉害了我的鲸”彩蛋、头像、弹窗图片目录 | 角色层移除了默认鲸鱼菜单入口，但上游彩蛋设置/图片池还在；更改入口标题可能使入口再出现 | 可删掉整组或替换成猫咪老师彩蛋；本轮不猜素材和玩法 |
| 内置鲸鱼/女仆台词、自言自语配图默认值 | 原模板和鲸鱼图片池仍继承；自定义文字/图片路径有效 | 属角色内容未迁移，建议改成猫咪老师主题；需要确定口吻与素材，不替用户生成整套台词 |
| “生小肥鱼/子肥鱼”名称、灵动岛鲸鱼默认图标 | 技术路径有效，文案/默认图标保留上游身份 | 可改为“再来一只猫咪老师”等；本轮不改已保存的个人图标、别名和台词 |
| 灵动岛余额数值/峰谷 | 源自 DeepSeek 余额与价格时段；纯桌宠没有查询余额的服务 | 与 Codex 配额无关；建议隐藏这两个模式或另做 Codex 额度模式，需决定 |
| 灵动岛状态、表达风格、Agent 提示音 | 通用 Agent/DSH 系统与猫咪老师自己的 Codex Hook 状态标签是两条路径 | 不能假定通用音效/文案/岛状态会响应 Codex；若需要，应明确合并哪些事件和显示优先级 |
| 通用 Agent 的错误/焦急等专用表演 | 气泡逻辑保留，缺对应角色素材时不播放专用表演 | 忙碌动作已适配；其他情绪映射/新素材先保留为待定 |
| Codex 联动与互动游戏的菜单编排 | 两个入口由角色层额外追加，不在上游菜单布局编辑器的动作注册表中 | 功能有效，但暂不能用布局编辑器隐藏/排序/改名；可作为后续独立菜单模型整合 |
| 角色特效、备用下载与发行 | 猫咪老师 33 个片段包含 19 个公开动作，其他是连续动作内部阶段；上游额外形象/唱歌/余额素材没有对应猫咪老师素材 | 不复制原角色素材冒充；Windows 发行包需在 Windows 构建验证，Ubuntu 分支尚无正式 Release |

## 菜单及不在设置页的动作

| 功能 | 核对结果与限制 |
| --- | --- |
| 猫咪老师 19 个公开动作、慢走、小跑、眯眯眼 | 已接入；33 个片段组成完整编排，内部循环/收尾不作为独立菜单动作；动作请求不无限排队 |
| 普通点击、按下/松开音效包、自言自语、黄金回旋 | 上一版已有接入；本轮相关测试通过，音效测试静音，听感未实机验证 |
| 拖拽、释放坐稳、惯性、重力、弹射、边缘探头 | 继承物理与特效；角色保留拖起/悬空/坐稳阶段；模拟与现有回归通过，原生桌面操作待验收 |
| 回到右下角、隐藏/恢复、退出、切换角色、角色别名 | 已接入；另一角色退回上游引擎，不要求它具备猫咪老师编排 |
| 生小肥鱼、退出子宠、继承大小/灵动岛、单进程多窗 | 独立进程迁移问题已修；真实两进程使用主槽/slot-1 并解码猫咪老师帧；单进程路径通过原有测试，开关需重启 |
| 快捷启动 | 编辑器与实际菜单共享保存列表；启动外部应用依赖本机路径，不能迁移其他电脑的可执行文件 |
| 待办面板与提前提醒 | 已接入且不依赖 AI；保存、调度和气泡路径通过原有测试 |
| 拖文件模拟投喂 | 上游入口已接线；可选择猫咪老师吃食物动作并记录统计，设计上不删除源文件 |
| 运势、吃什么、自写签、猜拳、猜数字、硬币、骰子 | 游戏实现和菜单共用控制器；候选列表保存到用户数据目录；游戏/持久化/结果气泡相关测试通过 |
| Codex 开始、完成、中断、额度常驻/时长、手动额度查询 | 专用实现存在；本轮测试不替代真实登录 CLI 和受信任 Hook 的验收；不读取聊天内容 |
| 更新检查/项目页 | 本轮纠正仓库与版本；测试覆盖查询配置、版本比较及真实菜单 action 的 URL；没有发布新版本 |
| 开机自启/托盘/全屏隐藏/光标隐藏穿透/直播捕获/Dock 图标 | 平台相关代码仍在；Windows 专属项在 Ubuntu 不创建控件，不能视为丢失迁移；本轮未修改用户的真实开机自启或 Hook 配置 |

## 设置控件逐项清单

以下直接从猫咪老师、纯桌宠模式的真实 Qt 设置窗口提取，涵盖本机显示的每个设置行；相同功能的音量、路径、冷却等子项也分别保留。平台专属设置见前表。

### 常规

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 开机自启 | `autostart` | 角色入口已接入；配置生成/单元测试通过，未修改真实系统自启 |
| 随桌宠启动 dsh 服务 | `harness_autostart` | 纯桌宠模式禁用；需 DSH/AI 服务 |
| 窗口置顶 | `on_top` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 单进程多开（省内存） | `single_process_spawn` | 已接入；开关保存后重启生效 |

### 桌宠

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 桌宠大小 | `scale` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 不透明度 | `pet_opacity` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 播放速率 | `playback_speed` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| 动作等待间隔 | `animation_gap` | 本轮修复并专测：完整角色动作后的等待生效 |
| 省电模式 | `idle_low_fps` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 不移动 | `no_move` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| 音乐自动唱歌 | `music_sing` | 缺角色素材；本轮禁用并提示原因 |
| 拖动物理 | `drag_physics` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 甩出力度 | `throw_strength` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 弹弓弹射 | `slingshot_enabled` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 锁定位置 | `lock_position` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| SHIFT+左键拖动 | `shift_drag` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 边缘探头 | `edge_probe` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 生小肥鱼继承大小 | `spawn_inherit_size` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 小肥鱼大小 | `spawn_scale` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 生小肥鱼继承灵动岛 | `spawn_inherit_dynamic_island` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 一键退出子肥鱼 | `clear_spawned_pets` | 已接入；说明已修正，退出后保留数据 |
| 碰撞开关 | `collision_enabled` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 碰撞音效 | `collision_sound_enabled` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 弹性系数 | `collision_restitution` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 摩擦系数 | `collision_friction` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 质量倍率 | `collision_mass_scale` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 冲量上限 | `collision_impulse_cap` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 碰撞音量 | `collision_sound_volume` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |

### 互动

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 鼠标穿透 | `mouse_through` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 点击音效 | `click_sound` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 音效音源 | `click_sound_pack` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 音效音量 | `click_sound_volume` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 试听音效 | `click_sound_preview` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 点击触发自言自语 | `click_self_talk` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| 点击动画台词绑定 | `click_talk_bindings` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 点击触发黄金回旋 | `golden_spin_click` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 点击回旋跳过动画 | `golden_spin_direct` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 气泡方案 | `self_talk_bubble_style` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 气泡自言自语 | `self_talk` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| 显示时间 | `self_talk_duration` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 最短间隔 | `self_talk_min` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 最长间隔 | `self_talk_max` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 候选内容 | `self_talk_texts` | 本轮通过实际设置关闭/保存/重载及角色窗口应用验证 |
| 图片目录 | `self_talk_images` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 配图大小 | `self_talk_image_scale` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |

### 菜单

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 颜色主题 | `menu_theme` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 菜单密度 | `menu_density` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 圆角大小 | `menu_radius` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| UI 字体 | `menu_font` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| UI 字号 | `menu_font_size` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 半透明菜单 | `menu_translucent` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 表面不透明度 | `menu_opacity` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 背景色 | `light_background` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 文字色 | `light_foreground` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 悬停色 | `light_hover` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 背景色 | `dark_background` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 文字色 | `dark_foreground` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 悬停色 | `dark_hover` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 显示彩蛋 | `egg_enabled` | 上游彩蛋内容未迁移；待决定删除或更换 |
| 入口标题 | `egg_title` | 上游彩蛋内容未迁移；待决定删除或更换 |
| 右侧提示 | `egg_hint` | 上游彩蛋内容未迁移；待决定删除或更换 |
| 头像图片 | `egg_avatar` | 上游彩蛋内容未迁移；待决定删除或更换 |
| 弹窗图片目录 | `egg_image_dir` | 上游彩蛋内容未迁移；待决定删除或更换 |
| 应用快捷启动 | `quick_launch_apps` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 菜单模式 | `menu_template` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 菜单编排 | `context_menu_layout` | 通用动作已接入；Codex/互动游戏追加项尚不能编排 |

### 桌面组件

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 启用灵动岛 | `dynamic_island_enabled` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 显示图标 | `dynamic_island_icon` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 显示名称 | `dynamic_island_name` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 显示信息槽 | `dynamic_island_info` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 显示状态灯 | `dynamic_island_status` | 时间/自定义文本有效；DSH/余额/Codex 信息来源需区分，见待定表 |
| 信息槽内容 | `dynamic_island_info_mode` | 时间/自定义文本有效；DSH/余额/Codex 信息来源需区分，见待定表 |
| 背景风格 | `dynamic_island_style` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 图标 | `dynamic_island_icon_value` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 自定义短文本 | `dynamic_island_custom_text` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |

### 自动化与联动

| 设置 | setting ID | 结果 |
| --- | --- | --- |
| 启用 Codex 联动提示 | `codex_enabled` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 显示对话中提示 | `codex_show_activity` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 显示完成提示 | `codex_show_completion` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 显示中断提示 | `codex_show_interrupt` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 显示额度 | `codex_show_quota` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 额度常驻显示 | `codex_quota_persistent` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 临时显示时长 | `codex_quota_duration` | 专用路径已接入；需要本机 Codex CLI 登录及可信 Hook |
| 表达风格 | `dialogue_mode` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 专属文案对象(仅在自定义模式生效) | `dialogue_scope` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 弹窗文案模板（JSON） | `dialogue_template_actions` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 其他工具操作 | `dialogue_activity.default` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 编辑代码 | `dialogue_activity.edit` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 读取文件 | `dialogue_activity.read` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 运行或测试 | `dialogue_activity.run` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 搜索或查找 | `dialogue_activity.search` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 需要用户处理 | `dialogue_agent.attention` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| Agent 出错 | `dialogue_agent.error` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 未找到 Agent | `dialogue_agent.missing` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 审批命令 | `dialogue_approval.command` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 审批提示 | `dialogue_approval.generic` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 审批工具 | `dialogue_approval.tool` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 查询余额中 | `dialogue_balance.loading` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 余额结果 | `dialogue_balance.result` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 桥接安装失败 | `dialogue_bridge.install.failed` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 安装桥接中 | `dialogue_bridge.install.pending` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 桥接安装成功 | `dialogue_bridge.install.success` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 桥接卸载失败 | `dialogue_bridge.uninstall.failed` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 任务暂停待确认 | `dialogue_done.attention` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 任务完成 | `dialogue_done.success` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 回写 DSH 失败 | `dialogue_dsh.writeback.failed` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 执行失败 | `dialogue_failure.generic` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 重试后失败 | `dialogue_failure.retry` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 工具执行失败 | `dialogue_failure.tool` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| AI 服务错误 | `dialogue_llm_error.api` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 行为重复干预 | `dialogue_pattern.control` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 行为重复警告 | `dialogue_pattern.warning` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 等待选择 | `dialogue_question.empty` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 多个用户问题 | `dialogue_question.many` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 单个用户问题 | `dialogue_question.one` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 连续限流 | `dialogue_rate_limit.many` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 单次限流 | `dialogue_rate_limit.one` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 开始工作 | `dialogue_start` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 卡住提醒 | `dialogue_stuck.reminder` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 思考 | `dialogue_thinking` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 循环检测控制告警 | `dialogue_watchdog.control` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 循环检测控制回执 | `dialogue_watchdog.control.result` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 循环检测警告 | `dialogue_watchdog.warning` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| Agent 音效联动 | `agent_sound_enabled` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 开始工作提示音 | `agent_sound_start` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 任务完成提示音 | `agent_sound_done` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 发生错误提示音 | `agent_sound_error` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 音效音量 | `agent_sound_volume` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 冷却时间 | `agent_sound_cooldown` | 通用 Agent 路径已接入；不会自动作用于专用 Codex 标签 |
| 待办提醒 | `todo_reminder_enabled` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 提前提醒 | `todo_reminder_lead_minutes` | 已接入；源码调用链与现有回归核对，原生桌面效果见平台限制 |
| 启用循环检测 | `watchdog_enabled` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |
| Warning 阈值 | `warning_threshold` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |
| Control 阈值 | `control_threshold` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |
| 评估冷却步数 | `cooldown_steps` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |
| 启动宽限期 | `early_grace_minutes` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |
| 长运行降阈值 | `long_run_minutes` | DSH 探索监测路径保留；需启用对应 Agent，未做真实服务验收 |

共核对 136 个本机设置行，未把隐藏子项或高级披露中的控件漏记。

## 验证记录

| 检查 | 结果 |
| --- | --- |
| Ruff：`ruff check app/pet app/tests` 与根级 F 规则检查 | 通过 |
| 主套件（按现有 CI 将 WebM/预热族分开运行） | 1631 passed / 13 skipped |
| WebM reader / clip lifecycle / first-frame lock | 37 passed |
| WebM loop | 34 passed |
| 根级打包、Hook、游戏、平台路径及角色启动器测试 | 31 passed |
| 低优先级预热两条顺序回归，哈希种子 0 | 修复前 2 failed，修复后 2 passed |
| 低优先级预热族，逐例新进程运行 | 27 passed / 0 failed |
| 低优先级预热族，全部共用一个进程 | 仍在 `app/tests/conftest.py:150` 的 Qt 清理中崩溃，未通过；不是断言被跳过或停用 |
| 真实源码启动器及独立进程多开 | 主槽和 slot-1 均为 NyankoWindow，窗口可见，33 个片段，640×360 解码帧；测试后退出自己启动的进程 |
| 实际设置关闭、保存、重载和应用到角色窗口 | 禁止移动、位置锁定、自言自语开关/文字、动作间隔和播放速度通过 |
| `git diff --check` | 通过 |

同进程预热族的清理崩溃在本轮改动前的云环境设置时已出现；本轮没有把它描述为全套通过，也没有放宽断言。所有 27 条用例仍完整执行，但共享 Qt 生命周期问题需另行排查。

真实 Qt 截图已检查 720 px/1100 px、浅色/深色；只修正不可用说明，未改变字号、控件层级和默认开关。当前为 Linux offscreen 实际渲染，不代表 Cocoa/Windows/Wayland 原生桌面验收。新偏好、新配置 key、个人数据迁移与新的菜单布局 schema 均未引入；旧值保留。版本基准仍为 0.5.4，没有提升版本号。

- [浅色设置页](media/migration-settings-light.png)
- [深色设置页](media/migration-settings-dark.png)
- [720 px 紧凑设置页](media/migration-settings-compact.png)

修改保留在当前工作区，未推送、未创建标签、未更新 Release。完整 Windows 安装包需要 Windows 构建机验证；真实 Codex 登录/Hook、DSH、AI 服务及原生桌面效果未在本云机器代测。
