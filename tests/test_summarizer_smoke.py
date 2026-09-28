"""现有测试：覆盖摘要生成的既有正常路径。跑通说明离线兜底与提示词拼装的基本流程没坏。"""
import dataclasses

import pytest

from backend import ai_summarizer
from backend.ai_summarizer import (
    DrillingSummary,
    OpenAISummarizer,
    create_summarizer,
    generate_drilling_summary,
)

ICE_CORE = {
    'depth_meters': 50,
    'ice_temperature': -31.5,
    'bubble_density': 0.82,
    'co2_concentration': 295,
    'methane_concentration': 610,
    'oxygen18_ratio': -42.1,
    'dust_concentration': 1.7,
    'estimated_age': 12000,
}

TRANSCRIPT = [
    {'speaker_role': 'engineer', 'text': '钻杆液压压力正常，本回次进尺三米'},
    {'speaker_role': 'climatologist', 'text': '这段气泡浓度偏高，二氧化碳要复测'},
    {'speaker_role': 'unknown', 'text': '今天风很大'},
]

EVENTS = [{'event_type': '火山喷发', 'description': '凝灰岩层', 'confidence': 0.87}]

DICT_KEYS = ['log_id', 'summary', 'key_findings', 'climate_events', 'sample_allocation', 'recommendations']


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """运行环境没有 key，也不许联网：把环境变量摘掉，保证走离线兜底。"""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)


def test_create_summarizer_without_key_stays_offline():
    summarizer = create_summarizer()
    assert isinstance(summarizer, OpenAISummarizer)
    assert summarizer.model == 'gpt-4'
    assert summarizer.initialize_client() is None
    assert create_summarizer(api_key=None).client is None


def test_offline_summary_returns_the_six_dict_keys_in_order():
    got = generate_drilling_summary(ICE_CORE, TRANSCRIPT, EVENTS)
    assert list(got) == DICT_KEYS
    assert isinstance(got['summary'], str) and got['summary']
    assert got['climate_events'] == EVENTS


def test_drilling_summary_dataclass_fields_unchanged():
    names = [f.name for f in dataclasses.fields(DrillingSummary)]
    assert names == ['log_id', 'summary_text', 'key_findings',
                     'climate_events_detected', 'sample_allocation', 'recommendations']


def test_prompt_buckets_comments_by_speaker_role():
    prompt = ai_summarizer.OpenAISummarizer()._build_summary_prompt(ICE_CORE, TRANSCRIPT, EVENTS)
    assert '- 钻杆液压压力正常，本回次进尺三米' in prompt
    assert '- 这段气泡浓度偏高，二氧化碳要复测' in prompt
    assert '今天风很大' not in prompt
    assert prompt.index('工程师评论') < prompt.index('气候学家评论')


def test_prompt_renders_measures_and_confidence():
    prompt = ai_summarizer.OpenAISummarizer()._build_summary_prompt(ICE_CORE, TRANSCRIPT, EVENTS)
    assert '- 钻探深度: 50 米' in prompt
    assert '- 冰层温度: -31.5°C' in prompt
    assert '- CO2浓度: 295 ppm' in prompt
    assert '- 估计年代: 12000 年' in prompt
    assert '(置信度: 0.87)' in prompt
    assert '3-5条关键发现' in prompt


def test_deep_core_segments_and_storage_span():
    alloc = generate_drilling_summary(ICE_CORE, TRANSCRIPT, EVENTS)['sample_allocation']
    assert alloc['core_segments'] == [
        {'start_depth': 40, 'end_depth': 50, 'length': 10, 'priority': '高'},
        {'start_depth': 20, 'end_depth': 40, 'length': 20, 'priority': '中'},
    ]
    assert alloc['storage_plan']['archive_half'].startswith('20-50m ')
    assert alloc['storage_plan']['working_half'].startswith('20-50m ')


def test_lab_allocations_and_recommendations_unchanged():
    got = generate_drilling_summary(ICE_CORE, TRANSCRIPT, EVENTS)
    labs = [row['lab'] for row in got['sample_allocation']['lab_allocations']]
    assert labs == ['稳定同位素实验室', '气体分析实验室', '微粒分析实验室', '冰芯化学实验室']
    assert [row['amount'] for row in got['sample_allocation']['lab_allocations']] == ['50g', '100g', '30g', '40g']
    assert len(got['recommendations']) == 3


def test_co2_reading_drives_the_period_wording():
    warm = generate_drilling_summary(dict(ICE_CORE, co2_concentration=295), TRANSCRIPT, EVENTS)['summary']
    cold = generate_drilling_summary(dict(ICE_CORE, co2_concentration=210), TRANSCRIPT, EVENTS)['summary']
    assert '间冰期' in warm
    assert '冰期' in cold and '间冰期' not in cold
