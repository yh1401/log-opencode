#!/usr/bin/env python3
"""
验证工具模块
"""

import re
from pathlib import Path

class ValidationUtils:
    """验证工具类"""
    
    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {'.log', '.txt', '.json', '.csv', '.pcap', '.pcapng'}
    
    # 文件大小限制（字节）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        """检查文件扩展名是否允许"""
        ext = Path(filename).suffix.lower()
        return ext in ValidationUtils.ALLOWED_EXTENSIONS
    
    @staticmethod
    def is_valid_filename(filename: str) -> bool:
        """检查文件名是否合法"""
        if not filename:
            return False
        
        # 检查长度
        if len(filename) > 255:
            return False
        
        # 检查特殊字符
        invalid_chars = r'[\\/:*?"<>|]'
        if re.search(invalid_chars, filename):
            return False
        
        return True
    
    @staticmethod
    def validate_file(filepath: str) -> tuple:
        """验证文件是否有效"""
        path = Path(filepath)
        
        if not path.exists():
            return False, "文件不存在"
        
        if not path.is_file():
            return False, "路径不是文件"
        
        if path.stat().st_size > ValidationUtils.MAX_FILE_SIZE:
            return False, f"文件大小超过限制（最大100MB）"
        
        ext = path.suffix.lower()
        if ext not in ValidationUtils.ALLOWED_EXTENSIONS:
            return False, f"不支持的文件格式: {ext}"
        
        return True, "文件验证通过"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除危险字符"""
        if not filename:
            return "unnamed"
        
        # 移除路径分隔符和特殊字符
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
        
        # 截断过长的文件名
        if len(sanitized) > 200:
            ext = Path(sanitized).suffix
            sanitized = sanitized[:200 - len(ext)] + ext
        
        return sanitized
    
    @staticmethod
    def validate_prompt(prompt: str) -> tuple:
        """验证提示词内容"""
        if not prompt:
            return True, ""
        
        # 检查长度
        if len(prompt) > 5000:
            return False, "提示词长度超过限制（最大5000字符）"
        
        # 检查危险内容
        dangerous_patterns = [
            r'<script[^>]*>.*</script>',
            r'javascript:',
            r'on\w+\s*='
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return False, "提示词包含不安全内容"
        
        return True, "提示词验证通过"
