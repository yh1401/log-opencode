#!/usr/bin/env python3
"""
文件管理模块 - 处理文件存储和读取
"""

import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

class FileManager:
    """文件管理器"""
    
    def __init__(self, upload_folder: str, output_folder: str):
        self.upload_folder = Path(upload_folder)
        self.output_folder = Path(output_folder)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保目录存在"""
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
    
    def save_uploaded_file(self, file_content, filename: str, task_id: str) -> str:
        """保存上传的文件"""
        # 使用任务ID重命名文件，避免冲突
        ext = Path(filename).suffix
        safe_filename = f"{task_id}{ext}"
        filepath = self.upload_folder / safe_filename
        
        # 如果是文件对象，使用save方法
        if hasattr(file_content, 'save'):
            file_content.save(str(filepath))
        else:
            # 否则直接写入内容
            with open(filepath, 'wb') as f:
                f.write(file_content)
        
        return str(filepath)
    
    def get_output_folder(self, task_id: str, original_filename: str = None) -> Path:
        """获取任务输出目录（按日期分组）
        
        Args:
            task_id: 任务ID
            original_filename: 原始文件名（用于生成文件夹名称）
            
        Returns:
            输出目录路径，格式为：日期时间+文件名
        """
        today = datetime.now().strftime("%Y-%m-%d")
        date_folder = self.output_folder / today
        
        # 如果提供了原始文件名，使用日期时间+文件名作为文件夹名
        if original_filename:
            time_str = datetime.now().strftime("%Y%m%d%H%M%S")
            base_name = Path(original_filename).stem
            # 清理文件名中的特殊字符
            safe_name = base_name.replace('/', '_').replace('\\', '_').replace(':', '_')
            task_folder_name = f"{time_str}+{safe_name}"
        else:
            task_folder_name = task_id
            
        task_folder = date_folder / task_folder_name
        task_folder.mkdir(parents=True, exist_ok=True)
        return task_folder
    
    def build_output_filename(self, original_filename: str, suffix: str = "分析报告") -> str:
        """构建输出文件名"""
        base_name = Path(original_filename).stem
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_name}-{time_str}-{suffix}"
    
    def save_report(self, content: str, task_id: str, original_filename: str, 
                    report_type: str = 'markdown') -> str:
        """保存报告文件"""
        output_folder = self.get_output_folder(task_id, original_filename)
        base_name = self.build_output_filename(original_filename)
        
        if report_type == 'markdown':
            filepath = output_folder / f"{base_name}.md"
        elif report_type == 'pdf':
            filepath = output_folder / f"{base_name}.pdf"
        elif report_type == 'html':
            filepath = output_folder / f"{base_name}.html"
        else:
            filepath = output_folder / f"{base_name}.txt"
        
        # 根据内容类型选择写入方式
        if isinstance(content, bytes):
            with open(filepath, 'wb') as f:
                f.write(content)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return str(filepath)
    
    def get_report_path(self, task_id: str, original_filename: str, report_type: str = 'markdown') -> Optional[str]:
        """获取报告文件路径"""
        try:
            output_folder = self.get_output_folder(task_id)
            base_name = Path(original_filename).stem
            
            # 查找匹配的文件
            pattern = f"{base_name}-*-分析报告.{report_type}"
            files = list(output_folder.glob(pattern))
            
            if files:
                # 返回最新的文件
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return str(files[0])
            return None
        except Exception:
            return None
    
    def calculate_file_hash(self, filepath: str) -> str:
        """计算文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def delete_task_files(self, task_id: str) -> bool:
        """删除任务相关文件"""
        try:
            # 删除上传文件
            for f in self.upload_folder.glob(f"{task_id}.*"):
                f.unlink()
            
            # 删除输出目录
            today = datetime.now().strftime("%Y-%m-%d")
            output_folder = self.output_folder / today / task_id
            if output_folder.exists():
                shutil.rmtree(output_folder)
            
            return True
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False
    
    def list_output_files(self, task_id: str) -> list:
        """列出任务输出文件"""
        try:
            output_folder = self.get_output_folder(task_id)
            return [str(f) for f in output_folder.iterdir() if f.is_file()]
        except Exception:
            return []

# 全局文件管理器实例
from config.settings import settings
storage_config = settings.get_storage_config()
file_manager = FileManager(
    upload_folder=storage_config['upload_folder'],
    output_folder=storage_config['output_folder']
)
