# 极趣待办 (Zectrix Todo) - AstrBot 插件

(非官方)与极趣实验室 AI 待办清单硬件交互的 AstrBot 插件。

## 功能

- 📋 设备管理（查看设备列表）
- 📝 待办 CRUD（增删改查、完成/取消、过滤）
- 📤 显示推送（文本 / 标题+正文 / 图片 / 清除页面）
- 🤖 自然语言执行命令（通过 LLM 解析意图并自动执行）
- ⚙️ WebUI 可视化配置

## 安装

1. 将 `astrbot_plugin_zectrix/` 文件夹放到 AstrBot 的 `data/plugins/` 下
2. 重启 AstrBot 或在 WebUI 插件管理中加载
3. 进入 **WebUI → 插件管理 → 极趣待办 → 设置**，填写：
   - **API Key** — 从 Zectrix Cloud 获取
   - **默认设备 ID** — 设备 MAC 地址（如 `AA:BB:CC:DD:EE:FF`）
   - API 地址一般不用改

## 命令

所有命令以 `zt` 为前缀，输入 `zt help` 查看完整帮助。

```
zt config                              # 查看当前配置
zt devices                             # 查看设备列表

zt todo list                           # 查看待办
zt todo list AA:BB:CC:DD:EE:FF 0      # 按设备/状态过滤
zt todo add 买牛奶 dueDate=2026-04-15 priority=重要
zt todo done 1                         # 切换完成状态
zt todo del 1                          # 删除待办
zt todo update 1 title=买牛奶和面包    # 更新待办

zt push text AA:BB:CC:DD:EE:FF 今日天气晴 fontSize=24 pageId=1
zt push structured AA:BB:CC:DD:EE:FF title=会议提醒 body=15:00 三楼会议室
zt push image AA:BB:CC:DD:EE:FF 1     # 附带图片一起发送
zt push clear AA:BB:CC:DD:EE:FF 1     # 清除指定页面
zt push clear AA:BB:CC:DD:EE:FF       # 清除所有页面
```

### 🤖 自然语言命令

支持直接用自然语言描述意图，由 LLM 解析后自动执行对应操作，无需记忆具体命令格式。

```
zt ask 帮我添加一个待办：明天下午开会
zt ask 把第一个待办标记为完成
zt ask 显示今天所有未完成的待办
zt ask 在设备上推送今日提醒：下午三点有会议
zt ask 删除已完成的待办
```

自然语言覆盖所有子命令，包括待办的增删改查、完成/取消、过滤，以及设备推送操作。

## 依赖

- `aiohttp >= 3.9.0`

## License

MIT
