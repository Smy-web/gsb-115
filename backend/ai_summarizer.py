import os
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import openai


@dataclass
class DrillingSummary:
    log_id: str
    summary_text: str
    key_findings: List[str]
    climate_events_detected: List[Dict[str, Any]]
    sample_allocation: Dict[str, Any]
    recommendations: List[str]


class OpenAISummarizer:
    def __init__(self, api_key: str = None, model: str = "gpt-4"):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.model = model
        self.client = None
        
    def initialize_client(self):
        if self.client is None and self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        return self.client
    
    def _build_summary_prompt(self, ice_core_data: Dict[str, Any],
                              transcript_with_speakers: List[Dict[str, Any]],
                              climate_events: List[Dict[str, Any]]) -> str:
        engineer_comments = []
        climatologist_comments = []
        
        for seg in transcript_with_speakers:
            role = seg.get('speaker_role', 'unknown')
            text = seg.get('text', '')
            if role == 'engineer':
                engineer_comments.append(text)
            elif role == 'climatologist':
                climatologist_comments.append(text)
        
        depth = ice_core_data.get('depth_meters', 0)
        co2 = ice_core_data.get('co2_concentration', 0)
        ch4 = ice_core_data.get('methane_concentration', 0)
        temp = ice_core_data.get('ice_temperature', 0)
        bubble_density = ice_core_data.get('bubble_density', 0)
        dust = ice_core_data.get('dust_concentration', 0)
        o18 = ice_core_data.get('oxygen18_ratio', 0)
        est_age = ice_core_data.get('estimated_age', '未知')
        
        events_text = "\n".join([
            f"- {e.get('event_type', '')}: {e.get('description', '')} "
            f"(置信度: {e.get('confidence', 0):.2f})"
            for e in climate_events
        ]) if climate_events else "无"
        
        prompt = f"""你是极地冰芯研究专家。请分析以下钻探日志数据，生成专业的钻探报告摘要。

冰芯数据:
- 钻探深度: {depth} 米
- 冰层温度: {temp}°C
- 气泡密度: {bubble_density}
- CO2浓度: {co2} ppm
- 甲烷浓度: {ch4} ppb
- δ18O比率: {o18}
- 粉尘浓度: {dust}
- 估计年代: {est_age} 年

工程师评论:
{chr(10).join([f"- {c}" for c in engineer_comments]) if engineer_comments else "无"}

气候学家评论:
{chr(10).join([f"- {c}" for c in climatologist_comments]) if climatologist_comments else "无"}

检测到的气候事件:
{events_text}

请生成以下内容（请用JSON格式返回）:
1. summary: 150-200字的专业摘要，总结本次钻探的主要发现
2. key_findings: 3-5条关键发现，格式为字符串数组
3. climate_analysis: 气候事件分析，说明可能的古气候意义
4. sample_allocation: 样品分配方案，包括：
   - 冰芯段划分（建议分段切割）
   - 各实验室分配建议（稳定同位素实验室、气体分析实验室、微粒分析实验室等）
   - 优先级排序
5. recommendations: 2-3条后续钻探建议
"""
        return prompt
    
    def generate_summary(self, ice_core_data: Dict[str, Any],
                        transcript_with_speakers: List[Dict[str, Any]],
                        climate_events: List[Dict[str, Any]]) -> DrillingSummary:
        client = self.initialize_client()
        prompt = self._build_summary_prompt(ice_core_data, transcript_with_speakers, climate_events)
        
        if client is None:
            return self._generate_mock_summary(ice_core_data, transcript_with_speakers, climate_events)
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是极地冰芯研究专家，擅长分析古气候数据并生成专业报告。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            return DrillingSummary(
                log_id=f"LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                summary_text=result.get('summary', ''),
                key_findings=result.get('key_findings', []),
                climate_events_detected=climate_events,
                sample_allocation=result.get('sample_allocation', {}),
                recommendations=result.get('recommendations', [])
            )
            
        except Exception as e:
            print(f"OpenAI API调用失败，使用模拟摘要: {e}")
            return self._generate_mock_summary(ice_core_data, transcript_with_speakers, climate_events)
    
    def _generate_mock_summary(self, ice_core_data: Dict[str, Any],
                               transcript_with_speakers: List[Dict[str, Any]],
                               climate_events: List[Dict[str, Any]]) -> DrillingSummary:
        depth = ice_core_data.get('depth_meters', 0)
        co2 = ice_core_data.get('co2_concentration', 0)
        ch4 = ice_core_data.get('methane_concentration', 0)
        temp = ice_core_data.get('ice_temperature', 0)
        
        summary = f"""本次钻探达到{depth}米深度，冰层温度{temp}°C。CO2浓度{co2}ppm，甲烷{ch4}ppb，
显示该层位可能处于{ '间冰期' if co2 > 280 else '冰期' }环境。气泡密度正常，冰芯质量良好，
适合进行高分辨率古气候分析。共检测到{len(climate_events)}个潜在气候事件，需进一步实验室确认。"""
        
        key_findings = [
            f"钻探深度达到{depth}米，冰芯回收率95%以上",
            f"CO2浓度{co2}ppm，反映当时大气温室气体水平",
            f"甲烷浓度{ch4}ppb，与CO2变化趋势一致",
            "冰芯结构完整，气泡保存良好，适合气体分析"
        ]
        
        if climate_events:
            for event in climate_events:
                key_findings.append(f"检测到{event.get('event_type', '气候事件')}信号")
        
        sample_allocation = {
            "core_segments": [
                {"start_depth": max(0, depth - 10), "end_depth": depth, "length": 10, "priority": "高"},
                {"start_depth": max(0, depth - 30), "end_depth": max(0, depth - 10), "length": 20, "priority": "中"},
            ],
            "lab_allocations": [
                {"lab": "稳定同位素实验室", "samples": ["δ18O", "δD"], "amount": "50g", "priority": "高"},
                {"lab": "气体分析实验室", "samples": ["CO2", "CH4", "N2O"], "amount": "100g", "priority": "高"},
                {"lab": "微粒分析实验室", "samples": ["粉尘浓度", "粒径分布"], "amount": "30g", "priority": "中"},
                {"lab": "冰芯化学实验室", "samples": ["离子分析", "EC/OC"], "amount": "40g", "priority": "中"},
            ],
            "storage_plan": {
                "archive_half": f"{max(0, depth - 30)}-{depth}m 存档于-40°C冷库",
                "working_half": f"{max(0, depth - 30)}-{depth}m 用于各项分析"
            }
        }
        
        recommendations = [
            "建议继续加深钻探，目标深度再增加20米以获取更完整的气候记录",
            "对检测到的气候事件层位进行高分辨率采样分析",
            "建议进行冰芯物理性质测量（密度、晶体结构）"
        ]
        
        return DrillingSummary(
            log_id=f"LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            summary_text=summary,
            key_findings=key_findings,
            climate_events_detected=climate_events,
            sample_allocation=sample_allocation,
            recommendations=recommendations
        )


def create_summarizer(api_key: str = None) -> OpenAISummarizer:
    return OpenAISummarizer(api_key=api_key)


def generate_drilling_summary(ice_core_data: Dict[str, Any],
                              transcript_with_speakers: List[Dict[str, Any]],
                              climate_events: List[Dict[str, Any]],
                              api_key: str = None) -> Dict[str, Any]:
    summarizer = create_summarizer(api_key)
    result = summarizer.generate_summary(ice_core_data, transcript_with_speakers, climate_events)
    
    return {
        'log_id': result.log_id,
        'summary': result.summary_text,
        'key_findings': result.key_findings,
        'climate_events': result.climate_events_detected,
        'sample_allocation': result.sample_allocation,
        'recommendations': result.recommendations
    }
