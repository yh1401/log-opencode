#!/usr/bin/env python3
"""
数据库操作模块 - SQLite持久化
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path

class TaskDatabase:
    """任务数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._ensure_directory()
        self._init_database()
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id VARCHAR(64) UNIQUE NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    current_step VARCHAR(64),
                    user_prompt TEXT,
                    upload_path VARCHAR(512),
                    output_path VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            ''')
            conn.commit()
    
    def create_task(self, task_id: str, filename: str, upload_path: str) -> bool:
        """创建任务记录"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tasks (task_id, filename, status, upload_path, created_at)
                    VALUES (?, ?, 'pending', ?, ?)
                ''', (task_id, filename, upload_path, datetime.now()))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
    
    def update_task_status(self, task_id: str, status: str, progress: int = 0, 
                           current_step: str = None, error_message: str = None) -> bool:
        """更新任务状态"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                update_fields = ["status = ?", "progress = ?"]
                params = [status, progress]
                
                if current_step:
                    update_fields.append("current_step = ?")
                    params.append(current_step)
                
                if error_message:
                    update_fields.append("error_message = ?")
                    params.append(error_message)
                
                if status == 'completed':
                    update_fields.append("completed_at = ?")
                    params.append(datetime.now())
                elif status == 'analyzing':
                    update_fields.append("started_at = COALESCE(started_at, ?)")
                    params.append(datetime.now())
                
                params.append(task_id)
                
                query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = ?"
                cursor.execute(query, params)
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
    
    def update_task_output(self, task_id: str, output_path: str) -> bool:
        """更新任务输出路径"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks SET output_path = ?, status = 'completed', progress = 100, completed_at = ?
                    WHERE task_id = ?
                ''', (output_path, datetime.now(), task_id))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
            return None
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT status FROM tasks WHERE task_id = ?', (task_id,))
                row = cursor.fetchone()
                
                if row:
                    return row[0]
            return None
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return None
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取历史任务列表"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT task_id, filename, status, created_at, completed_at, output_path
                    FROM tasks ORDER BY created_at DESC LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return []
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务记录"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
    
    def set_task_failed(self, task_id: str, error_message: str) -> bool:
        """标记任务失败"""
        return self.update_task_status(task_id, 'failed', 0, '失败', error_message)

# 全局数据库实例
from config.settings import settings
storage_config = settings.get_storage_config()
db = TaskDatabase(storage_config.get('database_path', 'data/log_analysis.db'))
