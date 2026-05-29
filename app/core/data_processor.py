#!/usr/bin/env python3
"""
数据处理模块 - 数据清洗、验证和格式化
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path

class LogEntry:
    """日志条目数据结构"""
    
    def __init__(self, timestamp: str, level: str, message: str, raw: str):
        self.timestamp = timestamp
        self.level = level.upper() if level else 'UNKNOWN'
        self.message = message
        self.raw = raw
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'level': self.level,
            'message': self.message,
            'raw': self.raw
        }
    
    def __str__(self) -> str:
        return f"[{self.timestamp}] [{self.level}] {self.message}"

class DataProcessor:
    """数据处理器 - 清洗、验证和格式化"""
    
    # 支持的日志格式模式
    LOG_PATTERNS = [
        # 标准格式: [2024-01-01 12:00:00] [INFO] message
        re.compile(r'^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*(.+)$'),
        # 简化格式: 2024-01-01 12:00:00 INFO message
        re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)$'),
        # Apache格式: [01/Jan/2024:12:00:00 +0000]
        re.compile(r'^\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}\s+[+-]\d{4})\]\s*(\w+)?\s*(.+)$'),
        # JSON格式: {"timestamp": "...", "level": "...", "message": "..."}
        re.compile(r'^\s*\{.*"timestamp".*"level".*"message".*\}\s*$'),
    ]
    
    # 日志级别列表
    LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'WARN', 'FATAL'}
    
    def __init__(self):
        self.parsed_entries = []
        self.validation_errors = []
    
    def validate_file(self, filepath: str) -> tuple:
        """验证文件是否有效"""
        path = Path(filepath)
        
        if not path.exists():
            error_msg = "文件不存在"
            self.validation_errors.append(error_msg)
            return False, error_msg
        
        if not path.is_file():
            error_msg = "路径不是文件"
            self.validation_errors.append(error_msg)
            return False, error_msg
        
        # 检查文件大小（最大100MB）
        max_size = 100 * 1024 * 1024  # 100MB
        if path.stat().st_size > max_size:
            error_msg = f"文件大小超过限制（最大100MB）"
            self.validation_errors.append(error_msg)
            return False, error_msg
        
        # 检查文件扩展名
        allowed_extensions = {'.log', '.txt', '.json', '.csv', '.pcap', '.pcapng'}
        ext = path.suffix.lower()
        if ext not in allowed_extensions:
            error_msg = f"不支持的文件格式: {ext}"
            self.validation_errors.append(error_msg)
            return False, error_msg
        
        return True, "文件验证通过"
    
    def parse_logs(self, filepath: str) -> List[LogEntry]:
        """解析日志文件"""
        self.parsed_entries = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    entry = self._parse_line(line)
                    if entry:
                        self.parsed_entries.append(entry)
                    else:
                        # 无法解析的行作为UNKNOWN级别
                        self.parsed_entries.append(LogEntry(
                            timestamp="",
                            level="UNKNOWN",
                            message=line,
                            raw=line
                        ))
            
            return self.parsed_entries
        except Exception as e:
            self.validation_errors.append(f"文件读取错误: {str(e)}")
            return []
    
    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """解析单行日志"""
        # 尝试匹配各种格式
        for pattern in self.LOG_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    timestamp = groups[0]
                    level = groups[1] if groups[1] else 'UNKNOWN'
                    message = groups[2]
                    
                    # 验证日志级别
                    if level.upper() not in self.LOG_LEVELS:
                        # 如果第二个组不是级别，当作消息处理
                        message = f"{level} {message}"
                        level = 'UNKNOWN'
                    
                    return LogEntry(timestamp, level, message, line)
        
        return None
    
    def clean_data(self, entries: List[LogEntry]) -> List[LogEntry]:
        """清洗数据 - 去重、标准化"""
        cleaned = []
        seen = set()
        
        for entry in entries:
            # 去重
            entry_hash = hash(entry.raw)
            if entry_hash not in seen:
                seen.add(entry_hash)
                
                # 标准化级别
                if entry.level not in self.LOG_LEVELS:
                    entry.level = self._infer_level(entry.message)
                
                # 清理消息内容
                entry.message = self._clean_message(entry.message)
                
                cleaned.append(entry)
        
        return cleaned
    
    def _infer_level(self, message: str) -> str:
        """从消息内容推断日志级别"""
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ['error', 'exception', 'fail', 'fatal']):
            return 'ERROR'
        elif any(keyword in message_lower for keyword in ['warning', 'warn']):
            return 'WARNING'
        elif any(keyword in message_lower for keyword in ['debug', 'trace']):
            return 'DEBUG'
        else:
            return 'INFO'
    
    def _clean_message(self, message: str) -> str:
        """清理消息内容 - 移除多余空格和特殊字符"""
        # 移除多余空格
        message = re.sub(r'\s+', ' ', message).strip()
        
        # 移除控制字符
        message = ''.join(c for c in message if ord(c) >= 32 or c == '\n')
        
        return message
    
    def get_statistics(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """获取日志统计信息"""
        stats = {
            'total': len(entries),
            'levels': {},
            'top_messages': []
        }
        
        # 按级别统计
        for entry in entries:
            level = entry.level
            stats['levels'][level] = stats['levels'].get(level, 0) + 1
        
        # 计算占比
        if stats['total'] > 0:
            for level, count in stats['levels'].items():
                stats['levels'][level] = {
                    'count': count,
                    'percentage': round(count / stats['total'] * 100, 2)
                }
        
        # 消息频率统计（取前10）
        message_counts = {}
        for entry in entries:
            msg = entry.message[:100]  # 截断用于统计
            message_counts[msg] = message_counts.get(msg, 0) + 1
        
        sorted_messages = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)
        stats['top_messages'] = [
            {'message': msg, 'count': count}
            for msg, count in sorted_messages[:10]
        ]
        
        return stats
    
    def format_entries(self, entries: List[LogEntry], limit: int = 5000) -> str:
        """将日志条目格式化为文本"""
        # 如果条目太多，进行分块处理
        if len(entries) > limit:
            entries = entries[:limit]
        
        return '\n'.join(str(entry) for entry in entries)
