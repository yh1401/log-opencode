#!/usr/bin/env python3
"""
日志解析器 - 解析各种格式的日志文件
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class LogEntry:
    """表示单个日志条目"""
    
    def __init__(self, timestamp: str, level: str, message: str, raw: str, metadata: Optional[Dict] = None):
        """初始化日志条目
        
        Args:
            timestamp: 时间戳
            level: 日志级别
            message: 消息内容
            raw: 原始日志行
            metadata: 额外元数据
        """
        self.timestamp = timestamp
        self.level = level.upper()
        self.message = message
        self.raw = raw
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            **self.metadata
        }
    
    def __repr__(self):
        """字符串表示"""
        return f"[{self.timestamp}] [{self.level}] {self.message[:50]}..."


class LogParser:
    """解析各种格式的日志文件"""
    
    def __init__(self, config: Dict):
        """初始化解析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.formats = config.get("log", {}).get("formats", [])
        
    def parse_file(self, filepath: str) -> List[LogEntry]:
        """解析日志文件并返回 LogEntry 对象列表
        
        Args:
            filepath: 日志文件路径
            
        Returns:
            LogEntry 对象列表
            
        Raises:
            FileNotFoundError: 文件未找到
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"日志文件未找到: {filepath}")
        
        entries = []
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                entry = self._parse_line(line.strip())
                if entry:
                    entries.append(entry)
        
        return entries
    
    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """尝试解析单行日志
        
        Args:
            line: 日志行
            
        Returns:
            LogEntry 对象或 None
        """
        
        # 首先尝试 JSON 格式
        if line.startswith('{'):
            try:
                data = json.loads(line)
                return self._parse_json_log(data, line)
            except json.JSONDecodeError:
                pass
        
        # 尝试正则表达式模式
        for fmt in self.formats:
            if fmt["name"] == "json":
                continue
            
            pattern = fmt.get("pattern")
            if not pattern:
                continue
            
            match = re.match(pattern, line)
            if match:
                groups = match.groupdict()
                return self._create_entry_from_groups(groups, line, fmt["name"])
        
        # 降级处理：作为纯文本处理
        return LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            message=line[:200],
            raw=line
        )
    
    def _parse_json_log(self, data: Dict, raw: str) -> LogEntry:
        """解析 JSON 格式日志
        
        Args:
            data: JSON 解析后的字典
            raw: 原始日志行
            
        Returns:
            LogEntry 对象
        """
        # 常见 JSON 日志字段
        timestamp = data.get("timestamp") or data.get("time") or data.get("@timestamp", "")
        level = data.get("level") or data.get("severity") or data.get("log_level", "INFO")
        message = data.get("message") or data.get("msg") or data.get("content", "")
        
        # 提取元数据（排除常见字段）
        metadata = {k: v for k, v in data.items() 
                    if k not in ["timestamp", "time", "@timestamp", "level", "severity", "message", "msg", "content"]}
        
        return LogEntry(
            timestamp=str(timestamp),
            level=str(level),
            message=str(message),
            raw=raw,
            metadata=metadata
        )
    
    def _create_entry_from_groups(self, groups: Dict, raw: str, format_name: str) -> LogEntry:
        """从正则分组创建 LogEntry
        
        Args:
            groups: 正则匹配的分组字典
            raw: 原始日志行
            format_name: 日志格式名称
            
        Returns:
            LogEntry 对象
        """
        timestamp = groups.get("timestamp", "")
        level = groups.get("level", "INFO")
        message = groups.get("message", raw)
        
        # 根据格式提取额外的元数据
        metadata = {}
        if format_name == "apache_common":
            metadata = {
                "ip": groups.get("ip"),
                "method": groups.get("method"),
                "path": groups.get("path"),
                "status": groups.get("status"),
                "size": groups.get("size")
            }
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            raw=raw,
            metadata=metadata
        )
    
    def filter_by_level(self, entries: List[LogEntry], levels: List[str]) -> List[LogEntry]:
        """按日志级别过滤条目
        
        Args:
            entries: 日志条目列表
            levels: 要保留的日志级别列表
            
        Returns:
            过滤后的日志条目列表
        """
        levels = [l.upper() for l in levels]
        return [e for e in entries if e.level.upper() in levels]
    
    def get_stats(self, entries: List[LogEntry]) -> Dict:
        """获取日志条目的统计信息
        
        Args:
            entries: 日志条目列表
            
        Returns:
            统计信息字典
        """
        stats = {
            "total": len(entries),
            "by_level": {},
            "time_range": {"start": None, "end": None}
        }
        
        for entry in entries:
            # 按级别计数
            level = entry.level.upper()
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            
            # 时间范围
            if not stats["time_range"]["start"] or entry.timestamp < stats["time_range"]["start"]:
                stats["time_range"]["start"] = entry.timestamp
            if not stats["time_range"]["end"] or entry.timestamp > stats["time_range"]["end"]:
                stats["time_range"]["end"] = entry.timestamp
        
        return stats


if __name__ == "__main__":
    # 测试解析器
    import yaml
    
    with open("../../config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    parser = LogParser(config)
    
    # 创建测试日志文件
    test_log = """2024-01-01 12:00:00 [INFO] Application started
2024-01-01 12:00:01 [WARNING] Memory usage high: 85%
2024-01-01 12:00:02 [ERROR] Database connection failed: timeout
2024-01-01 12:00:03 [INFO] Retrying connection..."""
    
    with open("/tmp/test_log.txt", "w") as f:
        f.write(test_log)
    
    entries = parser.parse_file("/tmp/test_log.txt")
    print(f"解析到 {len(entries)} 个条目:")
    for entry in entries:
        print(f"  - {entry}")
    
    stats = parser.get_stats(entries)
    print(f"\n统计信息: {stats}")
