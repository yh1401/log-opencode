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
请按照以下固定抓包分析报告模板，对pcap网络抓包数据做标准化分析输出：

## 一、基础信息概览
输出分析日期、抓包文件、时长、总包数、总流量；生成通信角色IP端口表格，说明传输层/应用层协议。

## 二、连接生命周期
梳理TCP握手耗时、链路质量、按时间线拆解连接建立、指令交互、数据传输、连接状态全流程。

## 三、流量特征分析
1. 制作上下行帧数/流量/占比统计表，分析流量不对称比例
2. 按包大小分类统计并标注业务含义
3. 分析TCP初始窗口、窗口衰减、应用消费速率匹配问题

## 四、关键问题
按严重、中等分级列出每个问题，写明现象+业务影响。

## 五、优化建议
分高优先级、中优先级、低优先级，给出业务策略、TCP系统参数、连接超时清理等具体可落地方案，可附带配置命令。

## 六、优化预期收益对比
输出优化预期收益对比表格。

## 七、补充信息
补充报告生成时间。

---

## 网络抓包数据
{pcap_data}

## 输出要求
1. 保持表格格式、章节结构完全固定
2. 只填充分析内容
3. 输出专业标准化抓包分析报告
4. 使用Markdown格式输出
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