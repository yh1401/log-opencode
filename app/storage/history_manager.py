#!/usr/bin/env python3
"""
历史记录管理模块 - 基于本地文件存储
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import glob

class HistoryManager:
    """历史记录管理器 - 使用JSON文件存储"""
    
    def __init__(self, data_dir: str = None):
        """初始化历史记录管理器
        
        Args:
            data_dir: 数据存储目录，默认为 data/history
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).parent.parent.parent / "data" / "history"
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_task_file(self, task_id: str) -> Path:
        """获取任务文件路径"""
        return self.data_dir / f"{task_id}.json"
    
    def _get_all_task_files(self) -> List[Path]:
        """获取所有任务文件"""
        return sorted(glob.glob(str(self.data_dir / "*.json")), reverse=True)
    
    def save_task(self, task_data: Dict) -> bool:
        """保存任务记录"""
        try:
            task_id = task_data.get('task_id')
            if not task_id:
                return False
            
            task_data['updated_at'] = datetime.now().isoformat()
            
            if 'created_at' not in task_data:
                task_data['created_at'] = datetime.now().isoformat()
            
            file_path = self._get_task_file(task_id)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存任务失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取单个任务"""
        try:
            file_path = self._get_task_file(task_id)
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取任务失败: {e}")
            return None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务列表"""
        tasks = []
        try:
            task_files = self._get_all_task_files()
            for task_file in task_files[:50]:  # 最多返回50条
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"读取任务文件失败 {task_file}: {e}")
            return tasks
        except Exception as e:
            print(f"获取任务列表失败: {e}")
            return []
    
    def update_task(self, task_id: str, updates: Dict) -> bool:
        """更新任务记录"""
        try:
            task_data = self.get_task(task_id)
            if not task_data:
                return False
            
            task_data.update(updates)
            task_data['updated_at'] = datetime.now().isoformat()
            
            return self.save_task(task_data)
        except Exception as e:
            print(f"更新任务失败: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务记录"""
        try:
            file_path = self._get_task_file(task_id)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"删除任务失败: {e}")
            return False
    
    def get_task_count(self) -> int:
        """获取任务总数"""
        try:
            return len(self._get_all_task_files())
        except Exception as e:
            print(f"获取任务数量失败: {e}")
            return 0

# 创建全局实例
history_manager = HistoryManager()
