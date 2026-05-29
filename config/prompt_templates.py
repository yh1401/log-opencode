#!/usr/bin/env python3
"""
提示词模板管理模块
"""

from typing import Dict, Optional

class PromptTemplates:
    """提示词模板管理器"""
    
    # 专业日志分析提示词模板
    LOG_ANALYSIS_TEMPLATE = """
你是一位资深的日志分析专家，请按照以下结构进行专业分析：

## 📋 分析要求
1. 识别日志中的关键事件和异常
2. 深入分析问题根因
3. 提供具体可操作的改进建议
4. 输出格式为结构化 Markdown

## 📊 日志数据
{log_entries}

## 🔍 分析重点
{analysis_focus}

## 📝 输出结构
请按照以下结构输出分析报告：

### 一、概览摘要
- 日志总条数
- 错误/警告数量统计
- 主要问题概述

### 二、日志级别分布
| 级别 | 数量 | 占比 |
|------|------|------|

### 三、错误详情
按严重程度排序，包含：
- 错误类型
- 出现次数
- 具体示例
- 影响分析

### 四、根因分析
深入分析问题产生的根本原因

### 五、改进建议
具体、可操作的优化建议

## ⚠️ 注意事项
- 保持专业但易懂的语言
- 使用 Markdown 格式输出
- 表格使用标准 Markdown 语法
- 避免使用 HTML 标签
"""
    
    # PCAP网络分析提示词模板
    PCAP_ANALYSIS_TEMPLATE = """
你是一位专业的网络安全分析专家，请分析以下网络抓包数据：

## 网络流量数据
{pcap_data}

## 分析要求
1. 分析协议分布和流量特征
2. 识别潜在安全威胁
3. 发现异常网络行为
4. 输出专业分析报告

## 输出结构
### 一、流量概览
- 总数据包数
- 流量大小
- 时间范围

### 二、协议分布
| 协议 | 数量 | 占比 |

### 三、Top Talkers
| 源IP | 目的IP | 数据包数 |

### 四、安全告警
- SYN洪水检测
- 端口扫描检测
- 异常连接模式

### 五、DNS分析
- 域名查询统计

### 六、HTTP分析
- 请求方法分布
- 状态码统计
"""
    
    # 总结报告模板
    SUMMARY_TEMPLATE = """
## 📊 分析报告总结

### 基本信息
- **任务ID**: {task_id}
- **文件名**: {filename}
- **分析时间**: {analysis_time}
- **耗时**: {duration}

### 分析结果
{analysis_content}
"""
    
    @classmethod
    def get_log_template(cls) -> str:
        """获取日志分析模板"""
        return cls.LOG_ANALYSIS_TEMPLATE
    
    @classmethod
    def get_pcap_template(cls) -> str:
        """获取PCAP分析模板"""
        return cls.PCAP_ANALYSIS_TEMPLATE
    
    @classmethod
    def get_summary_template(cls) -> str:
        """获取总结报告模板"""
        return cls.SUMMARY_TEMPLATE
    
    @classmethod
    def format_log_prompt(cls, log_entries: str, analysis_focus: str = "") -> str:
        """格式化日志分析提示词"""
        return cls.LOG_ANALYSIS_TEMPLATE.format(
            log_entries=log_entries,
            analysis_focus=analysis_focus if analysis_focus else "全面分析所有日志内容"
        )
    
    @classmethod
    def format_pcap_prompt(cls, pcap_data: str) -> str:
        """格式化PCAP分析提示词"""
        return cls.PCAP_ANALYSIS_TEMPLATE.format(pcap_data=pcap_data)
    
    @classmethod
    def format_summary(cls, task_id: str, filename: str, analysis_time: str, 
                       duration: str, analysis_content: str) -> str:
        """格式化总结报告"""
        return cls.SUMMARY_TEMPLATE.format(
            task_id=task_id,
            filename=filename,
            analysis_time=analysis_time,
            duration=duration,
            analysis_content=analysis_content
        )
