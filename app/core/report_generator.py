#!/usr/bin/env python3
"""
报告生成器模块 - 生成多种格式的报告
"""

import json
import os
from io import BytesIO
from typing import Dict, Optional, Any
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class ReportGenerator:
    """报告生成器 - 支持多种格式"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_fonts()
    
    def _register_fonts(self):
        """注册中文字体"""
        # 尝试查找系统中文字体
        font_paths = [
            '/System/Library/Fonts/STHeiti Medium.ttc',  # macOS
            '/System/Library/Fonts/PingFang.ttc',         # macOS
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',  # Linux
            '/usr/share/fonts/truetype/arphic/ukai.ttc',       # Linux
            'C:/Windows/Fonts/simsun.ttc',                     # Windows
        ]
        
        self.chinese_font = 'SimHei'
        font_found = False
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('SimHei', font_path))
                    font_found = True
                    break
                except Exception:
                    continue
        
        # 如果找不到系统字体，使用默认字体并添加中文支持
        if not font_found:
            # 使用reportlab内置的Helvetica字体作为后备
            self.chinese_font = 'Helvetica'
    
    def generate_markdown(self, data: Dict, file_info: Optional[Dict] = None) -> str:
        """生成Markdown格式报告
        
        Args:
            data: 分析数据（可以是字典或字符串）
            file_info: 文件信息字典，包含 filename, file_size, total_entries 等
        """
        md = []
        
        # 标题
        md.append("# 📊 日志分析报告")
        md.append("")
        
        # 文件信息
        if file_info:
            md.append("## 📁 文件信息")
            md.append("")
            md.append("| 属性 | 值 |")
            md.append("|------|------|")
            if 'filename' in file_info:
                md.append(f"| 文件名 | `{file_info['filename']}` |")
            if 'file_size' in file_info:
                md.append(f"| 文件大小 | {self._format_size(file_info['file_size'])} |")
            if 'total_entries' in file_info:
                md.append(f"| 日志条目数 | {file_info['total_entries']} |")
            md.append("")
        
        # 如果data是字符串，直接作为Markdown内容添加
        if isinstance(data, str):
            # 检查是否是JSON格式字符串
            try:
                json_data = json.loads(data)
                # 如果是JSON，转换为友好的Markdown
                md.append(self._json_to_markdown(json_data))
            except json.JSONDecodeError:
                # 如果不是JSON，直接作为Markdown内容
                md.append(data)
        elif isinstance(data, dict):
            # 如果是字典，转换为友好的Markdown
            md.append(self._json_to_markdown(data))
        
        # 元数据
        md.append("")
        md.append("---")
        md.append(f"*分析时间: {data.get('analysis_time', '') if isinstance(data, dict) else ''}*")
        md.append(f"*任务ID: {data.get('task_id', '') if isinstance(data, dict) else ''}*")
        
        return '\n'.join(md)
    
    def _json_to_markdown(self, data: Any, depth: int = 0) -> str:
        """将JSON结构转换为友好的Markdown格式"""
        lines = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ("metadata", "analysis_time", "task_id", "raw_analysis", "markdown_analysis"):
                    continue  # 跳过元数据和已处理字段
                
                # 格式化键名
                header_name = self._format_key(key)
                header_prefix = "#" * min(depth + 2, 6)  # 最多 h6
                
                if isinstance(value, dict) and value:
                    lines.append(f"{header_prefix} {header_name}")
                    lines.append("")
                    lines.append(self._json_to_markdown(value, depth + 1))
                elif isinstance(value, list) and value:
                    lines.append(f"{header_prefix} {header_name}")
                    lines.append("")
                    for i, item in enumerate(value, 1):
                        if isinstance(item, dict):
                            lines.append(f"**条目 {i}:**")
                            lines.append(self._json_to_markdown(item, depth + 1))
                            lines.append("---")
                        elif isinstance(item, str):
                            lines.append(f"{i}. {item}")
                        else:
                            lines.append(f"{i}. {str(item)}")
                    lines.append("")
                elif isinstance(value, list) and not value:
                    lines.append(f"{header_prefix} {header_name}")
                    lines.append("")
                    lines.append("_无数据_")
                    lines.append("")
                else:
                    # 简单值
                    if depth == 0:
                        lines.append(f"{header_prefix} {header_name}")
                        lines.append("")
                        lines.append(str(value))
                        lines.append("")
                    else:
                        lines.append(f"- **{header_name}:** {value}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    lines.append(f"### 条目 {i}")
                    lines.append("")
                    lines.append(self._json_to_markdown(item, depth + 1))
                    lines.append("---")
                    lines.append("")
                elif isinstance(item, str):
                    lines.append(f"{i}. {item}")
                else:
                    lines.append(f"{i}. {str(item)}")
        
        else:
            lines.append(str(data))
        
        return '\n'.join(lines)
    
    def _format_key(self, key: str) -> str:
        """将下划线/驼峰格式的key转为可读标题"""
        # 下划线转空格，首字母大写
        return key.replace("_", " ").replace("-", " ").title()
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小为可读格式"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
    
    def _escape_markdown(self, text: str) -> str:
        """转义Markdown格式为PDF可识别的格式"""
        # 处理粗体 **text**
        text = text.replace('**', '<b/>')
        
        # 处理斜体 *text*
        text = text.replace('*', '<i/>')
        
        # 处理反引号 `text`
        text = text.replace('`', '')
        
        # 处理换行
        text = text.replace('\n', '<br/>')
        
        return text
    
    def generate_pdf(self, markdown_content: str, filename: str = None) -> bytes:
        """生成PDF格式报告"""
        buffer = BytesIO()
        
        # 使用A4纸张
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               leftMargin=50, rightMargin=50,
                               topMargin=50, bottomMargin=50)
        
        # 创建支持中文的样式
        heading1_style = ParagraphStyle(
            'CustomHeading1',
            fontName=self.chinese_font,
            fontSize=18,
            spaceAfter=15,
            bold=True,
            alignment=0  # 左对齐
        )
        
        heading2_style = ParagraphStyle(
            'CustomHeading2',
            fontName=self.chinese_font,
            fontSize=14,
            spaceAfter=10,
            bold=True,
            alignment=0  # 左对齐
        )
        
        heading3_style = ParagraphStyle(
            'CustomHeading3',
            fontName=self.chinese_font,
            fontSize=12,
            spaceAfter=8,
            bold=True,
            alignment=0  # 左对齐
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            fontName=self.chinese_font,
            fontSize=10,
            leading=14,
            alignment=0,  # 左对齐
            allowWidows=0,
            allowOrphans=0
        )
        
        list_style = ParagraphStyle(
            'CustomList',
            fontName=self.chinese_font,
            fontSize=10,
            leading=14,
            leftIndent=20,
            alignment=0  # 左对齐
        )
        
        story = []
        lines = markdown_content.split('\n')
        
        # 用于收集表格数据
        table_data = []
        
        for line in lines:
            if line.startswith('# '):
                # 一级标题
                # 如果之前有表格数据，先添加表格
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                story.append(Paragraph(line[2:], heading1_style))
            elif line.startswith('## '):
                # 二级标题
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                story.append(Paragraph(line[3:], heading2_style))
            elif line.startswith('### '):
                # 三级标题
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                story.append(Paragraph(line[4:], heading3_style))
            elif line.startswith('|'):
                # 表格
                if '---' in line:
                    continue  # 跳过分隔线
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if len(cells) > 0:
                    # 转义每个单元格中的Markdown格式
                    cells = [self._escape_markdown(cell) for cell in cells]
                    table_data.append(cells)
            elif line.startswith('- '):
                # 列表项
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                content = self._escape_markdown(line[2:])
                story.append(Paragraph(content, list_style))
            elif line.strip():
                # 普通文本
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                content = self._escape_markdown(line)
                story.append(Paragraph(content, normal_style))
            else:
                # 空行
                if table_data:
                    self._add_table_to_story(story, table_data)
                    table_data = []
                story.append(Spacer(1, 10))
        
        # 处理最后可能剩余的表格数据
        if table_data:
            self._add_table_to_story(story, table_data)
        
        doc.build(story)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def _add_table_to_story(self, story: list, table_data: list):
        """将表格添加到story中"""
        if len(table_data) == 0:
            return
        
        # 计算列宽（根据内容自适应）
        col_widths = []
        for col_idx in range(len(table_data[0])):
            max_width = 50  # 最小宽度
            for row in table_data:
                if col_idx < len(row):
                    cell_width = len(row[col_idx]) * 6  # 估算宽度
                    max_width = max(max_width, cell_width)
            col_widths.append(min(max_width, 200))  # 最大宽度限制
        
        table = Table(table_data, colWidths=col_widths)
        
        # 创建表格样式
        style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # 左对齐
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        # 如果有表头，添加背景色
        if len(table_data) > 1:
            style.add('BACKGROUND', (0, 0), (-1, 0), colors.lightblue)
            style.add('FONTNAME', (0, 0), (-1, 0), self.chinese_font)
            style.add('BOLD', (0, 0), (-1, 0), 1)
        
        table.setStyle(style)
        story.append(table)
        story.append(Spacer(1, 12))
    
    def generate_html(self, markdown_content: str, title: str = "日志分析报告") -> str:
        """生成HTML格式报告"""
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            line-height: 1.6;
            color: #333;
            background: #f8f9fa;
        }}
        h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        h3 {{ color: #555; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f0f4f8; font-weight: 600; }}
        tr:nth-child(even) {{ background: #f8fafc; }}
        ul {{ padding-left: 20px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-size: 14px; }}
    </style>
</head>
<body>
"""
        
        # 简单的Markdown转HTML
        lines = markdown_content.split('\n')
        in_list = False
        
        for line in lines:
            if line.startswith('# '):
                html += f"<h1>{line[2:]}</h1>\n"
            elif line.startswith('## '):
                html += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith('### '):
                html += f"<h3>{line[4:]}</h3>\n"
            elif line.startswith('|'):
                if '---' in line:
                    continue
                cells = [f"<td>{cell.strip()}</td>" for cell in line.split('|') if cell.strip()]
                html += f"<tr>{''.join(cells)}</tr>\n"
            elif line.startswith('|--'):
                html += "<table>\n"
            elif line.startswith('- '):
                if not in_list:
                    html += "<ul>\n"
                    in_list = True
                html += f"<li>{line[2:]}</li>\n"
            else:
                if in_list:
                    html += "</ul>\n"
                    in_list = False
                if line.strip():
                    html += f"<p>{line}</p>\n"
        
        html += """
<div class="footer">Generated by Log Analysis Tool</div>
</body>
</html>
"""
        
        return html
    
    def save_report(self, content: str, output_path: str, format_type: str = 'markdown') -> str:
        """保存报告到文件"""
        filepath = Path(output_path)
        
        if format_type == 'markdown':
            filepath = filepath.with_suffix('.md')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        elif format_type == 'pdf':
            filepath = filepath.with_suffix('.pdf')
            pdf_bytes = self.generate_pdf(content)
            with open(filepath, 'wb') as f:
                f.write(pdf_bytes)
        elif format_type == 'html':
            filepath = filepath.with_suffix('.html')
            html_content = self.generate_html(content)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return str(filepath)
