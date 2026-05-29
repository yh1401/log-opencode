#!/usr/bin/env python3
"""
任务管理器模块 - 管理分析任务的生命周期
"""

import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable

class TaskStatus:
    """任务状态枚举"""
    PENDING = 'pending'
    UPLOADING = 'uploading'
    VALIDATING = 'validating'
    CLEANING = 'cleaning'
    PARSING = 'parsing'
    ANALYZING = 'analyzing'
    GENERATING = 'generating'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ABORTED = 'aborted'

class TaskManager:
    """任务管理器 - 管理任务状态和生命周期"""
    
    def __init__(self):
        self.tasks = {}
        self.tasks_lock = threading.RLock()
        self._next_task_id = 0
    
    def generate_task_id(self) -> str:
        """生成唯一任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = uuid.uuid4().hex[:6]
        return f"{timestamp}_{random_suffix}"
    
    def create_task(self, filename: str, upload_path: str) -> str:
        """创建新任务"""
        task_id = self.generate_task_id()
        
        with self.tasks_lock:
            self.tasks[task_id] = {
                'task_id': task_id,
                'filename': filename,
                'upload_path': upload_path,
                'file_size': 0,  # 新增文件大小字段
                'status': TaskStatus.PENDING,
                'progress': 0,
                'current_step': '等待处理',
                'total_chunks': 0,
                'processed_chunks': 0,
                'start_time': None,
                'elapsed_time': 0,
                'estimated_remaining': '计算中...',
                'user_prompt': '',
                'output_md': None,
                'output_pdf': None,
                'error_message': None,
                'aborted': False
            }
        
        return task_id
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务状态"""
        with self.tasks_lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            
            # 更新状态
            if 'status' in kwargs:
                task['status'] = kwargs['status']
                if kwargs['status'] == TaskStatus.ANALYZING and task['start_time'] is None:
                    task['start_time'] = time.time()
            
            # 更新进度
            if 'progress' in kwargs:
                task['progress'] = kwargs['progress']
            
            # 更新步骤
            if 'current_step' in kwargs:
                task['current_step'] = kwargs['current_step']
            
            # 更新分块信息
            if 'total_chunks' in kwargs:
                task['total_chunks'] = kwargs['total_chunks']
            if 'processed_chunks' in kwargs:
                task['processed_chunks'] = kwargs['processed_chunks']
                # 更新预估剩余时间
                self._update_estimated_time(task)
            
            # 更新输出路径
            if 'output_md' in kwargs:
                task['output_md'] = kwargs['output_md']
            if 'output_pdf' in kwargs:
                task['output_pdf'] = kwargs['output_pdf']
            
            # 更新错误信息
            if 'error_message' in kwargs:
                task['error_message'] = kwargs['error_message']
            
            # 更新提示词
            if 'user_prompt' in kwargs:
                task['user_prompt'] = kwargs['user_prompt']
            
            # 更新上传路径
            if 'upload_path' in kwargs:
                task['upload_path'] = kwargs['upload_path']
            
            # 更新文件大小
            if 'file_size' in kwargs:
                task['file_size'] = kwargs['file_size']
            
            # 更新耗时
            if task['start_time']:
                task['elapsed_time'] = int(time.time() - task['start_time'])
            
            return True
    
    def _update_estimated_time(self, task: Dict):
        """更新预估剩余时间"""
        if task['processed_chunks'] > 0 and task['total_chunks'] > 0 and task['start_time']:
            elapsed = time.time() - task['start_time']
            avg_time_per_chunk = elapsed / task['processed_chunks']
            remaining_chunks = task['total_chunks'] - task['processed_chunks']
            remaining_seconds = avg_time_per_chunk * remaining_chunks
            
            if remaining_seconds < 60:
                task['estimated_remaining'] = f"{int(remaining_seconds)}秒"
            elif remaining_seconds < 3600:
                minutes = int(remaining_seconds // 60)
                seconds = int(remaining_seconds % 60)
                task['estimated_remaining'] = f"{minutes}分{seconds}秒"
            else:
                hours = int(remaining_seconds // 3600)
                minutes = int((remaining_seconds % 3600) // 60)
                task['estimated_remaining'] = f"{hours}小时{minutes}分"
        else:
            task['estimated_remaining'] = '计算中...'
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        with self.tasks_lock:
            return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            return task['status'] if task else None
    
    def mark_aborted(self, task_id: str) -> bool:
        """标记任务为已中止"""
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            if task:
                task['status'] = TaskStatus.ABORTED
                task['aborted'] = True
                task['current_step'] = '用户已中止'
                return True
        return False
    
    def is_aborted(self, task_id: str) -> bool:
        """检查任务是否已中止"""
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            return task.get('aborted', False) if task else False
    
    def mark_failed(self, task_id: str, error_message: str) -> bool:
        """标记任务失败"""
        return self.update_task(task_id, 
                                status=TaskStatus.FAILED, 
                                current_step='处理失败',
                                error_message=error_message)
    
    def mark_completed(self, task_id: str, output_md: str = None, output_pdf: str = None) -> bool:
        """标记任务完成"""
        return self.update_task(task_id,
                                status=TaskStatus.COMPLETED,
                                progress=100,
                                current_step='分析完成',
                                output_md=output_md,
                                output_pdf=output_pdf)
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self.tasks_lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
        return False
    
    def get_all_tasks(self) -> list:
        """获取所有任务列表"""
        with self.tasks_lock:
            return list(self.tasks.values())

# 全局任务管理器实例
task_manager = TaskManager()
