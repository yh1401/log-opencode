#!/usr/bin/env python3
"""
日志分析工具 - 主程序入口
用法：
    python main.py <日志文件> [--config <配置文件路径>] [--output <输出路径>]
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime

# 将 scripts 目录添加到路径
import sys
sys.path.insert(0, str(Path(__file__).parent))

from log_parser import LogParser
from log_analyzer import LogAnalyzer


def load_config(config_path: str = None) -> dict:
    """加载配置文件
    
    Args:
        config_path: 配置文件路径（可选）
        
    Returns:
        配置字典
    """
    if not config_path:
        # 默认配置文件路径
        config_path = str(Path(__file__).parent.parent / "config" / "config.yaml")
    
    print(f"📋 正在加载配置: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def analyze_log_file(log_path: str, config: dict, output_path: str = None):
    """主分析工作流程
    
    Args:
        log_path: 日志文件路径
        config: 配置字典
        output_path: 输出文件路径（可选）
        
    Returns:
        (分析结果字典, 报告内容)
    """
    
    print(f"\n🚀 开始日志分析...")
    print(f"📂 日志文件: {log_path}")
    
    # 步骤 1: 解析日志文件
    print(f"\n📊 步骤 1: 正在解析日志文件...")
    parser = LogParser(config)
    
    try:
        entries = parser.parse_file(log_path)
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        return None, None
    
    print(f"✅ 成功解析 {len(entries)} 个日志条目")
    
    # 显示统计信息
    stats = parser.get_stats(entries)
    print(f"\n📊 统计信息:")
    print(f"   - 总条目数: {stats['total']}")
    print(f"   - 时间范围: {stats['time_range']['start']} 至 {stats['time_range']['end']}")
    print(f"   - 按级别统计:")
    for level, count in stats['by_level'].items():
        print(f"     • {level}: {count}")
    
    # 步骤 2: 使用 AI 分析
    print(f"\n🤖 步骤 2: 正在使用 AI 模型分析...")
    analyzer = LogAnalyzer(config)
    
    analysis = analyzer.analyze(entries)
    
    if "error" in analysis:
        print(f"❌ 分析失败: {analysis['error']}")
        return None, None
    
    print(f"✅ 分析完成!")
    
    # 显示元数据
    metadata = analysis.get("metadata", {})
    print(f"   - 模型: {metadata.get('model', 'unknown')}")
    print(f"   - 分析的条目数: {metadata.get('entries_analyzed', 0)}")
    usage = metadata.get('usage', {})
    if usage:
        print(f"   - Token 使用量: {usage.get('total_tokens', 'N/A')} 总共")
    
    # 步骤 3: 生成报告
    print(f"\n📄 步骤 3: 正在生成报告...")
    
    if not output_path:
        # 自动生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(config.get("output", {}).get("directory", "../output"))
        output_dir = Path(__file__).parent.parent / output_dir
        output_path = str(output_dir / f"analysis_{timestamp}.md")
    
    report = analyzer.generate_report(analysis, entries, output_path)
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 步骤 4: 显示摘要
    print(f"\n✨ 分析摘要:")
    
    if "raw_analysis" in analysis:
        # 显示前 500 个字符
        summary = analysis["raw_analysis"][:500]
        if len(analysis["raw_analysis"]) > 500:
            summary += "..."
        print(summary)
    else:
        # 显示结构化分析的键
        for key in analysis.keys():
            if key != "metadata":
                print(f"   • {key}")
    
    print(f"\n🎉 分析完成! 查看完整报告: {output_path}")
    
    return analysis, report


def main():
    """主 CLI 入口点"""
    
    parser = argparse.ArgumentParser(
        description="日志分析工具 - 使用 AI 模型分析日志文件"
    )
    
    parser.add_argument(
        "log_file",
        help="要分析的日志文件路径"
    )
    
    parser.add_argument(
        "-c", "--config",
        help="配置文件路径 (默认: ../config/config.yaml)",
        default=None
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出报告文件路径 (默认: 自动生成)",
        default=None
    )
    
    parser.add_argument(
        "--json",
        help="以 JSON 格式输出分析（而不是 Markdown）",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 如果设置了 --json 标志，覆盖输出格式
    if args.json:
        config["output"]["format"] = "json"
    
    # 运行分析
    analysis, report = analyze_log_file(
        log_path=args.log_file,
        config=config,
        output_path=args.output
    )
    
    # 如果输出格式是 JSON，也打印到标准输出
    if args.json and analysis:
        print("\n" + json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
