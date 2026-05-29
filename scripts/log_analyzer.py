#!/usr/bin/env python3
"""
日志分析器 - 调用 AI 模型分析日志
"""

import os
import json
import yaml
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
from log_parser import LogEntry, LogParser


class LogAnalyzer:
    """使用 AI 模型分析日志"""
    
    def __init__(self, config: Dict):
        """初始化分析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.model_config = config.get("model", {})
        self.analysis_config = config.get("analysis", {})
        self.output_config = config.get("output", {})
        
        # 加载提示词模板
        self.prompt_template = self.analysis_config.get("prompt_template", "")
        
    def analyze(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """使用 AI 模型分析日志条目
        
        Args:
            entries: 日志条目列表
            
        Returns:
            分析结果的字典
        """
        
        # 尝试主模型
        try:
            return self._call_model(entries, self.model_config)
        except Exception as e:
            print(f"⚠️ 主模型调用失败: {e}")
            
            # 尝试降级模型
            fallback_config = {
                "provider": self.model_config.get("fallback_provider", "ollama"),
                "name": self.model_config.get("fallback_model", "qwen3.5:9b"),
                "base_url": self.model_config.get("fallback_url", "http://localhost:11434/v1"),
                "api_key": ""  # Ollama 不需要 API key
            }
            
            print(f"🔄 正在降级到: {fallback_config['name']}")
            try:
                return self._call_model(entries, fallback_config)
            except Exception as e2:
                print(f"❌ 降级模型也失败: {e2}")
                return {"error": str(e2), "entries": [e.to_dict() for e in entries[:10]]}
    
    def _call_model(self, entries: List[LogEntry], model_config: Dict) -> Dict[str, Any]:
        """调用 AI 模型 API"""
        
        provider = model_config.get("provider", "modelarts")
        model_name = model_config.get("name", "qwen3-235b-a22b")
        base_url = model_config.get("base_url", "https://api.modelarts-maas.com/openai/v1")
        api_key = model_config.get("api_key", "")
        
        # 格式化日志条目为提示词
        log_text = self._format_entries(entries)
        
        # 创建提示词
        prompt = self.prompt_template.format(log_entries=log_text)
        
        # 准备 API 请求
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一个日志分析专家。请以 Markdown 格式输出分析报告，包含标题、列表、表格等格式。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        # 调用 API
        print(f"🤖 正在调用模型: {provider}/{model_name}")
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 从响应中提取分析内容
        analysis_text = result["choices"][0]["message"]["content"]
        
        # 尝试解析为 JSON，如果成功则转换为易读 Markdown
        try:
            analysis = json.loads(analysis_text)
            # 将 JSON 结构转为 Markdown 文本
            analysis["markdown_analysis"] = self._json_to_markdown(analysis)
        except json.JSONDecodeError:
            # 如果不是 JSON，作为纯文本/Markdown 返回
            analysis = {"raw_analysis": analysis_text, "markdown_analysis": analysis_text}
        
        # 添加元数据
        analysis["metadata"] = {
            "model": model_name,
            "provider": provider,
            "entries_analyzed": len(entries),
            "usage": result.get("usage", {})
        }
        
        return analysis
    
    def _json_to_markdown(self, data: Any, depth: int = 0) -> str:
        """递归将 JSON 结构转换为易读的 Markdown 格式
        
        Args:
            data: JSON 数据
            depth: 当前嵌套深度
            
        Returns:
            Markdown 格式的文本
        """
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if key in ("metadata", "markdown_analysis"):
                    continue  # 跳过元数据和已转换的字段
                header_prefix = "#" * min(depth + 2, 4)  # 最多 h4
                if isinstance(value, (dict, list)) and value:
                    lines.append(f"{header_prefix} {self._format_key(key)}\n")
                    lines.append(self._json_to_markdown(value, depth + 1))
                elif isinstance(value, list) and not value:
                    lines.append(f"{header_prefix} {self._format_key(key)}\n")
                    lines.append("*无数据*\n")
                else:
                    lines.append(f"- **{self._format_key(key)}:** {value}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    lines.append(f"\n---\n**条目 {i+1}**\n")
                    lines.append(self._json_to_markdown(item, depth + 1))
                else:
                    lines.append(f"{i+1}. {item}")
            return "\n".join(lines)
        else:
            return str(data)
    
    def _format_key(self, key: str) -> str:
        """将下划线/驼峰格式的key转为可读标题"""
        # 下划线转空格，首字母大写
        return key.replace("_", " ").replace("-", " ").title()
    
    def _format_entries(self, entries: List[LogEntry]) -> str:
        """格式化日志条目为提示词"""
        
        # 限制条目数量避免 token 溢出
        max_entries = self.analysis_config.get("batch_size", 5000)
        if len(entries) > max_entries:
            print(f"⚠️ 限制为 {max_entries} 个条目 (总数: {len(entries)})")
            entries = entries[:max_entries]
        
        # 格式化为文本
        lines = []
        for i, entry in enumerate(entries, 1):
            line = f"{i}. [{entry.timestamp}] [{entry.level}] {entry.message}"
            if entry.metadata:
                line += f" {json.dumps(entry.metadata, ensure_ascii=False)}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def generate_report(self, analysis: Dict, entries: List[LogEntry], output_path: Optional[str] = None) -> str:
        """生成分析报告"""
        
        # 确定输出格式
        fmt = self.output_config.get("format", "markdown")
        
        if fmt == "markdown":
            report = self._generate_markdown_report(analysis, entries)
        elif fmt == "json":
            report = json.dumps({"analysis": analysis, "entries": [e.to_dict() for e in entries]}, indent=2, ensure_ascii=False)
        else:
            report = str(analysis)
        
        # 保存到文件
        if output_path:
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            
            print(f"📄 报告已保存到: {output_path}")
        
        return report
    
    def _generate_markdown_report(self, analysis: Dict, entries: List[LogEntry]) -> str:
        """生成 Markdown 格式报告 - 优先使用 Markdown 格式的分析内容"""
        
        lines = []
        lines.append("# 📊 日志分析报告\n")
        lines.append(f"**生成时间:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 元数据
        metadata = analysis.get("metadata", {})
        lines.append(f"**分析模型:** {metadata.get('model', 'unknown')}")
        lines.append(f"**模型提供商:** {metadata.get('provider', 'unknown')}")
        lines.append(f"**分析条目数:** {metadata.get('entries_analyzed', 0)}\n")
        
        # 统计信息
        try:
            from log_parser import LogParser
            parser = LogParser(self.config)
            stats = parser.get_stats(entries)
            
            lines.append("## 📈 统计概览\n")
            lines.append(f"| 指标 | 值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 总条目数 | {stats['total']} |")
            lines.append(f"| 时间范围 | {stats['time_range']['start']} 至 {stats['time_range']['end']} |")
            lines.append("")
            
            # 级别统计表格
            lines.append("### 按级别统计\n")
            lines.append("| 级别 | 数量 |")
            lines.append("|------|------|")
            for level, count in stats['by_level'].items():
                emoji = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵", "DEBUG": "⚪", "CRITICAL": "💥"}.get(level, "📋")
                lines.append(f"| {emoji} {level} | {count} |")
            lines.append("\n---\n")
        except Exception:
            lines.append("\n---\n")
        
        # 分析内容 - 优先使用 markdown_analysis 字段
        lines.append("## 🔍 分析结果\n")
        
        if "markdown_analysis" in analysis:
            # 使用已转换为 Markdown 的分析内容
            lines.append(analysis["markdown_analysis"])
        elif "raw_analysis" in analysis:
            # 原始文本（可能已是 Markdown）
            lines.append(analysis["raw_analysis"])
        elif "chunks" in analysis:
            # 多块合并结果
            for i, chunk in enumerate(analysis["chunks"]):
                lines.append(f"### 分析块 {i+1}\n")
                if "markdown_analysis" in chunk:
                    lines.append(chunk["markdown_analysis"])
                elif "raw_analysis" in chunk:
                    lines.append(chunk["raw_analysis"])
                else:
                    lines.append(self._json_to_markdown(chunk))
                lines.append("")
        else:
            # 结构化分析 - 转为 Markdown
            for key, value in analysis.items():
                if key in ("metadata", "markdown_analysis"):
                    continue
                
                lines.append(f"### {self._format_key(key)}\n")
                
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            lines.append(self._json_to_markdown(item))
                        else:
                            lines.append(f"- {item}")
                elif isinstance(value, dict):
                    lines.append(self._json_to_markdown(value))
                else:
                    lines.append(str(value))
                
                lines.append("")
        
        return "\n".join(lines)


if __name__ == "__main__":
    # 测试分析器
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    # 加载配置
    with open("../../config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # 解析测试日志
    parser = LogParser(config)
    entries = parser.parse_file("/tmp/test_log.txt")
    
    print(f"📊 解析到 {len(entries)} 个条目")
    
    # 分析
    analyzer = LogAnalyzer(config)
    analysis = analyzer.analyze(entries)
    
    print(f"\n🔍 分析结果:")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
    
    # 生成报告
    output_path = "../../output/test_analysis.md"
    report = analyzer.generate_report(analysis, entries, output_path)
    print(f"\n📄 报告已生成: {output_path}")
