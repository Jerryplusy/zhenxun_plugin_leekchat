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

- 主模型是生成最终文本所用的模型，要求是智商和情商高，否则你的机器人会看上去没有脑子
- 工作模型是用于处理轻量任务的模型，调用频率远大于主模型，要求**便宜**+速度快
- 视觉工作模型是用于处理聊天中的媒体内容（表情包、图片、视频、音频等）的模型，若开启聊天媒体识别调用频率会非常高，**请务必选择特价模型或关闭聊天媒体识别功能**

## 关于token消耗

模型输入消耗远大于输出 故在选择模型时需侧重输入价格

也可以购买一个 coding plan 接入 基本够用

### 单次请求预测消耗

由于输出token通常小于100 故不计算

单次请求输入预计消耗 ~5000 token，每次和机器人对话会增加 ~200 token 机器人调用工具可命中 ~1000 token 左右缓存

| 层级     | 部分                 | Tokens | 说明               |
|--------|--------------------|--------|------------------|
| System | Persona            | ~120   | 人格提示词            |
|        | Reply Style        | ~320   | 回复风格             |
|        | Response Format    | ~640   | 回复格式             |
|        | 系统提示词合计            | ~1070  | 可吃到缓存            |
| User   | Time & Environment | ~40    | 当前环境             |
|        | Group Context      | ~3120  | 群聊的聊天记录，可自行调整多少条 |
|        | Taeget Message     | ~30    | 目标用户发言           |
|        | Response Leader    | ~140   | 回复思路引导           |
|        | Emotion State      | ~180   | 情绪状态             |
|        | 动态上下文合计            | ~3570  | 无法命中缓存 实打实消耗     |


## TODO 

- **Memory**：记忆检索功能未实现（`humanize/memory.py`）
- **Topic**：话题跟踪功能未实现（`humanize/topic.py`）
- **Expression**：表达习惯学习功能未实现（`humanize/expression.py`）
- **Audio**：语音消息合成未实现（`core/media/audio.py`）
- **外部 Skills**：外部 Skill 加载机制未实现（`core/external_skills.py`）
- **各种细节优化**：插件来自 mioku，使用MiniMax-M3迁移，可能存在细节问题，有问题请提出issue。

## 配置

编辑 zhenxun 配置中的 `zhenxun_plugin_leekchat` 模块：

```yaml
zhenxun_plugin_leekchat:
  MAIN_MODEL: "OpenAI/gpt-4o"        # 主模型
  WORKING_MODEL: "OpenAI/gpt-4o-mini" # 工作模型
  VISION_MODEL: "OpenAI/gpt-4o"      # 视觉工作模型
  BASE: "{}"                          # 基础配置 JSON
  SETTINGS: "{}"                      # 设置项 JSON
  PERSONALIZATION: "{}"               # 人设/情感/风格 JSON
  GROUPS: "{}"                        # 群覆盖 JSON
```

详细字段见 `configs/base.py`。

## 表情包

将表情包放在 `resources/meme/<character_name>/` 下，每个角色一个子目录。