# 冰封纪要 · 钻探日志的 AI 摘要生成

极地冰芯钻探队每完成一个回次，台账里就要多一份摘要：这次钻到多深、温室气体读数说明了什么、
冰芯该怎么切段送哪几个实验室、下一步往哪儿钻。这份摘要由 `backend/ai_summarizer.py` 生成，
输入是三样东西：本回次的冰芯量测字典、带说话人角色的转写片段、现场标记出来的气候事件列表。

## 目录

- `backend/ai_summarizer.py`：摘要生成。提示词拼装、真实模型调用、离线兜底摘要、样品分配方案。
- `tests/`：现有测试，覆盖离线兜底与提示词拼装的正常路径。
- `conftest.py`：把仓库根加进 sys.path，测试统一用 `from backend import ai_summarizer` 导入。

## 对外契约

- `create_summarizer(api_key=None)` 返回一个 `OpenAISummarizer`。
- `OpenAISummarizer.__init__(api_key=None, model="gpt-4")`；`initialize_client()` 在没有 key 时返回 None。
- `OpenAISummarizer.generate_summary(...)` 返回 `DrillingSummary`；`_build_summary_prompt(...)` 返回提示词字符串。
- `generate_drilling_summary(ice_core_data, transcript_with_speakers, climate_events, api_key=None)` 返回字典，
  键固定为 `log_id`、`summary`、`key_findings`、`climate_events`、`sample_allocation`、`recommendations`，顺序也固定。
- `DrillingSummary` 是 dataclass，六个字段依次为 `log_id`、`summary_text`、`key_findings`、
  `climate_events_detected`、`sample_allocation`、`recommendations`。
- `sample_allocation` 里 `lab_allocations` 的四个实验室、样品项、用量与优先级保持原样。

上面这些名字、既有位置参数的顺序、返回结构的键名与键序都不要改。新增参数只能加在参数列表末尾并且带默认值。

## 模型后端

openai 这个包在运行环境里是装好的，但没有 API key，也不允许联网。所以：

- 不传 key 时 `initialize_client()` 返回 None，`generate_summary` 直接走 `_generate_mock_summary`
  这条离线兜底路径，不抛异常。这是默认被测路径。
- 要覆盖真实调用那条分支，把替身直接挂到实例上：`summarizer.client = 替身对象`。
  `initialize_client()` 见到 `self.client` 不是 None 就原样返回它，不会去建真连接。
  替身只要提供 `chat.completions.create(**kwargs)`，返回一个能取到
  `response.choices[0].message.content` 的对象即可；要模拟传输层故障就让 create 抛 openai 自己的异常类型。
- 调用入参是固定的：temperature 0.4、max_tokens 1500、response_format 要求返回 JSON 对象，
  模型回的内容按 JSON 解析后填进 `DrillingSummary`。

## 运行

    ~/venvs/gsb-farm/bin/python -m pytest tests/ -q

解释器与依赖版本见 `requirements-task.txt`。不要 pip install，不要联网。

### 本次做题人填写

（把你自己拿主意的那一处写在这里：选了哪种做法、为什么不选另一种、代价是什么。）
