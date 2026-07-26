# leekchat

> 迁移自 [mioku](https://github.com/mioku-lab/mioku) chat 模块，也欢迎使用 mioku 机器人框架 awa

小真寻的实用聊天插件OvO

## 功能特性

- **多角色模型**：主模型、工作模型、视觉工作模型三者独立配置
- **人设系统**：完整的 persona + emotion + reply style 配置
- **表情包系统**：从本地 `resources/meme/` 目录加载，由工作模型选择
- **网页工具**：SearXNG 搜索 + 网页读取
- **流式输出**：伪流式逐段发送
- **markdown 截图**：通过 zhenxun 渲染服务生成 PNG
- **CD / 速率限制**：用户级 + 群级限流
- **空闲触发**：群聊空闲时自动评估是否回复

## 关于三个类型的模型

- 主模型是生成回复所用的模型，要求是聪明，否则你的机器人会看上去没有脑子
- 工作模型是用于处理轻量任务的模型，调用频率远大于主模型，要求**便宜**+速度快
- 视觉工作模型是用于处理聊天中的媒体内容（表情包、图片、视频、音频等）的模型，若开启聊天媒体识别调用频率会非常高，**请务必选择特价模型或关闭聊天媒体识别功能**

### 模型使用推荐

- 主模型：gpt-5.4+、gemini-3.0 flash+、claude 4.6 sonnet+、qwen3.7-plus、kimi-k2.7+、GLM5+

> MiniMax-M3（模型无真寻人设，拟人效果强）、Deepseek-v4-pro（拟人效果差）

- 工作模型：deepseek-v4-flash等
- 视觉工作模型：doubao-seed-2.0-mini+、gpt-5.4-mini、mimo-2.5V等

## 关于token消耗

模型输入消耗远大于输出 故在选择模型时需侧重输入价格

也可以购买一个 coding plan 接入 基本够用

### 单次请求预测消耗

由于输出token通常小于100 故不计算

单次请求输入预计消耗 ~5000 token，每次和机器人对话会增加 ~200 token 机器人连续调用工具可命中 ~4000 token 左右缓存

> 在开启外部技能时，单次请求预计消耗 ~6000 token

并不是每次对话都能命中缓存，通常情况下，超过5分钟无请求的提供商会清理上次请求的缓存，故只有连续对话/工具调用有机会命中缓存

| 层级     | 部分                 | Tokens | 说明               |
|--------|--------------------|--------|------------------|
| System | Persona            | ~120   | 人格提示词            |
|        | Response Format    | ~640   | 回复格式             |
|        | 系统提示词合计            | ~760   | 可命中缓存            |
| User   | Time & Environment | ~40    | 当前环境             |
|        | Group Context      | ~3120  | 群聊的聊天记录，可自行调整多少条 |
|        | Taeget Message     | ~30    | 目标用户发言           |
|        | Response Leader    | ~140   | 回复思路引导           |
|        | Emotion State      | ~180   | 情绪状态             |
|        | Reply Style        | ~320   | 回复风格             |
|        | 动态上下文合计            | ~3830  | 无法命中缓存 实打实消耗     |

## 超级用户命令

- 超级用户发送 `/skills` 查看可用技能，默认全部关闭

```text
        "/skills - 显示帮助\n"
        "/skills list - 列出所有技能\n"
        "/skills on <名称|序号> [...] - 启用技能；支持完整名称或"
        "技能列表中的序号，可用空格分隔多个技能\n"
        "/skills off <名称|序号> [...] - 关闭某个技能\n"
        "/skills allon - 启用当前扫描到的全部技能\n"
        "/skills alloff - 不允许任何技能\n"
        "/skills reload - 重新扫描插件并重建技能目录\n"
        "/skills hidden - 查看默认隐藏且禁用的不常用技能\n"
        "/skills hidden add/remove <模块名> [...] - 管理隐藏列表\n"
        "/skills hidden reset - 恢复默认隐藏列表\n\n"
```

## TODO 

- **Memory**：记忆检索功能未实现（`humanize/memory.py`）
- **Topic**：话题跟踪功能未实现（`humanize/topic.py`）
- **Expression**：表达习惯学习功能未实现（`humanize/expression.py`）
- **Audio**：语音消息合成未实现（`core/media/audio.py`）

## 配置

编辑 zhenxun 配置`data/config.yaml`中的 `zhenxun_plugin_leekchat` 模块

## 表情包

将表情包放在 `resources/meme/<character_name>/` 下，每个角色一个子目录。