#!/usr/bin/env python3
"""
提示词引擎模块 - 管理和生成专业提示词
"""

from typing import Dict, Optional
from config.prompt_templates import PromptTemplates

class PromptEngine:
    """提示词引擎 - 构建专业分析提示词"""
    
    def __init__(self):
        self.templates = PromptTemplates()
    
    def build_log_analysis_prompt(self, log_content: str, user_prompt: str = "") -> str:
        """构建日志分析提示词"""
        # 确保内容不超过最大长度（约8000token，每token约4字符）
        max_chars = 32000
        if len(log_content) > max_chars:
            # 如果内容太长，取开头和结尾
            log_content = log_content[:max_chars//2] + "\n...（中间内容省略）...\n" + log_content[-max_chars//2:]
        
        return self.templates.format_log_prompt(
            log_entries=log_content,
            analysis_focus=user_prompt
        )
    
    def build_pcap_analysis_prompt(self, pcap_summary: str) -> str:
        """构建PCAP分析提示词"""
        return self.templates.format_pcap_prompt(pcap_data=pcap_summary)
    
    def build_summary_report(self, task_id: str, filename: str, 
                            analysis_time: str, duration: str, 
                            analysis_content: str) -> str:
        """构建总结报告"""
        return self.templates.format_summary(
            task_id=task_id,
            filename=filename,
            analysis_time=analysis_time,
            duration=duration,
            analysis_content=analysis_content
        )
    
    def add_system_prompt(self, user_prompt: str, role: str = "日志专家") -> str:
        """添加系统角色提示"""
        system_prompts = {
            "日志专家": """
你是一位资深的日志分析专家，拥有丰富的系统运维和故障排查经验。
请使用专业但易懂的语言进行分析，提供具体的问题定位和解决方案。
""",
            "网络专家": """
你是一位专业的网络安全分析专家，精通网络协议和安全威胁检测。
请分析网络流量数据，识别潜在威胁并提供安全建议。
""",
            "数据分析师": """
你是一位专业的数据分析师，擅长从海量数据中发现规律和异常。
请提供数据驱动的分析报告和可视化建议。
"""
        }
        
        system_prompt = system_prompts.get(role, system_prompts["日志专家"])
        return f"{system_prompt}\n\n{user_prompt}"
    
    def enhance_prompt(self, base_prompt: str, context: Dict = None) -> str:
        """增强提示词 - 添加上下文信息"""
        if context:
            context_str = "\n\n## 📋 上下文信息\n"
            for key, value in context.items():
                context_str += f"- **{key}**: {value}\n"
            base_prompt += context_str
        
        return base_prompt
    
    def format_for_llm(self, prompt: str, model_type: str = "general") -> Dict:
        """格式化为LLM API请求格式"""
        system_content = {
            "general": "你是一位专业的AI助手，擅长分析和总结。",
            "code": "你是一位资深程序员，精通多种编程语言和技术栈。",
            "analyst": "你是一位数据分析专家，擅长从数据中提取洞察。"
        }
        
        return {
            "messages": [
                {"role": "system", "content": system_content.get(model_type, system_content["general"])},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
