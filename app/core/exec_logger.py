#!/usr/bin/env python3
"""
执行日志系统 - 记录所有组件交互和操作序列

功能特性：
1. 每个任务独立日志文件 - 便于追踪和管理
2. 清晰的人类可读格式 - 参考用户提供的日志格式
3. 结构化日志格式 - 便于机器读取和分析
4. 日志轮转和保留策略
5. 敏感信息脱敏处理
"""

import os
import json
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

# 日志级别枚举
class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# 组件类型枚举
class ComponentType(Enum):
    UPLOAD = "upload"
    VALIDATION = "validation"
    PARSING = "parsing"
    CLEANING = "cleaning"
    ANALYSIS = "analysis"
    OPENCODE = "opencode"
    REPORT = "report"
    STORAGE = "storage"
    API = "api"

class ExecLogger:
    """执行日志记录器 - 提供结构化的组件交互日志"""
    
    def __init__(self, log_dir: str = None):
        """初始化日志记录器
        
        Args:
            log_dir: 日志存储目录，默认为 logs/exec
        """
        self.log_dir = Path(log_dir) if log_dir else Path(__file__).parent.parent.parent / "logs" / "exec"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._current_conversation = {}  # 存储当前对话状态
        
        # 日志轮转配置
        self.max_file_size_mb = 50
        self.max_files = 10
        
        # 任务日志文件映射 {task_id: log_file_path}
        self._task_log_files = {}
        
    def _generate_log_filename(self, filename: str) -> str:
        """生成日志文件名：{filename}_{datetime}_{random4}.log
        
        Args:
            filename: 原始文件名
            
        Returns:
            日志文件名，格式为：文件名_日期时间_随机4位.log
        """
        # 移除文件扩展名
        base_name = Path(filename).stem
        # 处理特殊字符
        safe_name = base_name.replace('/', '_').replace('\\', '_').replace(':', '_')
        # 日期时间（格式：YYYYMMDD_HHMMSS）
        datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 随机4位字母数字
        random_suffix = uuid.uuid4().hex[:4]
        
        return f"{safe_name}_{datetime_str}_{random_suffix}.log"
    
    def _get_task_log_file(self, task_id: str, filename: str = None) -> Path:
        """获取任务日志文件路径
        
        Args:
            task_id: 任务ID
            filename: 原始文件名（用于首次创建）
            
        Returns:
            日志文件路径
        """
        if task_id in self._task_log_files:
            return self._task_log_files[task_id]
        
        # 创建日期目录
        today = datetime.now().strftime("%Y-%m-%d")
        date_dir = self.log_dir / today
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件名
        if filename:
            log_filename = self._generate_log_filename(filename)
        else:
            log_filename = f"{task_id}.log"
        
        log_file = date_dir / log_filename
        self._task_log_files[task_id] = log_file
        
        return log_file
    
    def _format_time(self, timestamp: Optional[float] = None) -> str:
        """格式化时间为可读格式"""
        if timestamp:
            return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        return datetime.now().strftime("%H:%M:%S")
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
    
    def _redact_sensitive(self, data: Any) -> Any:
        """脱敏敏感信息"""
        sensitive_keys = {"api_key", "password", "secret", "token", "Authorization"}
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key.lower() in sensitive_keys:
                    result[key] = "***REDACTED***"
                else:
                    result[key] = self._redact_sensitive(value)
            return result
        elif isinstance(data, list):
            return [self._redact_sensitive(item) for item in data]
        else:
            return data
    
    def _write_task_log(self, task_id: str, message: str):
        """写入任务日志（人类可读格式）"""
        with self._lock:
            log_file = self._task_log_files.get(task_id)
            if not log_file:
                return
            
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception as e:
                print(f"写入任务日志失败: {e}")
    
    def _write_json_log(self, log_entry: Dict):
        """写入JSON格式日志（用于统一的exec.log）"""
        # 创建日期目录
        today = datetime.now().strftime("%Y-%m-%d")
        date_dir = self.log_dir / today
        date_dir.mkdir(parents=True, exist_ok=True)
        
        json_log_file = date_dir / "exec.log"
        
        with self._lock:
            try:
                with open(json_log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"写入JSON日志失败: {e}")
    
    def _create_task_log_header(self, task_id: str, filename: str):
        """创建任务日志文件头部"""
        log_file = self._get_task_log_file(task_id, filename)
        
        # 如果文件不存在，创建头部
        if not log_file.exists():
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("="*60 + "\n")
                f.write("任务执行日志\n")
                f.write(f"任务ID: {task_id}\n")
                f.write(f"文件名: {filename}\n")
                f.write(f"开始时间: {datetime.now().isoformat()}\n")
                f.write("="*60 + "\n")
                f.write("\n")
    
    def log_task_start(self, task_id: str, filename: str):
        """记录任务开始"""
        self._create_task_log_header(task_id, filename)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.ANALYSIS.value,
            "action": "start",
            "task_id": task_id,
            "filename": filename,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_step(self, task_id: str, step_num: int, step_name: str, detail: str = ""):
        """记录处理步骤"""
        timestamp = self._format_time()
        message = f"[{timestamp}] 步骤 {step_num}: {step_name}"
        if detail:
            message += f" - {detail}"
        
        self._write_task_log(task_id, message)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.ANALYSIS.value,
            "action": "step",
            "task_id": task_id,
            "step_num": step_num,
            "step_name": step_name,
            "detail": detail,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_api_call(self, task_id: str, provider: str, model: str, chunk_num: int, 
                     total_chunks: int, entry_count: int, request_tokens: int = 0,
                     response_tokens: int = 0, duration_ms: int = 0, status: str = "success"):
        """记录API调用详情"""
        timestamp = self._format_time()
        message = f"\n[{timestamp}] API调用:"
        message += f"\n  提供商: {provider}"
        message += f"\n  模型: {model}"
        message += f"\n  分块: 第 {chunk_num}/{total_chunks} 块 ({entry_count} 条)"
        message += f"\n  请求tokens: {request_tokens}"
        message += f"\n  响应tokens: {response_tokens}"
        message += f"\n  耗时: {duration_ms}ms"
        message += f"\n  状态: {status}"
        message += "\n"
        
        self._write_task_log(task_id, message)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.OPENCODE.value,
            "action": "api_call",
            "task_id": task_id,
            "provider": provider,
            "model": model,
            "chunk_num": chunk_num,
            "total_chunks": total_chunks,
            "entry_count": entry_count,
            "request_tokens": request_tokens,
            "response_tokens": response_tokens,
            "duration_ms": duration_ms,
            "status": status,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_file_upload(self, task_id: str, filename: str, file_size: int, file_format: str):
        """记录文件上传"""
        timestamp = self._format_time()
        message = f"[{timestamp}] 文件上传 - {filename} ({self._format_size(file_size)})"
        
        self._write_task_log(task_id, message)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.UPLOAD.value,
            "action": "upload",
            "task_id": task_id,
            "filename": filename,
            "file_size": file_size,
            "file_size_human": self._format_size(file_size),
            "file_format": file_format,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_task_complete(self, task_id: str, duration_ms: int, md_path: str = None, pdf_path: str = None):
        """记录任务完成"""
        timestamp = self._format_time()
        duration_sec = duration_ms / 1000
        
        message = "\n" + "="*60
        message += f"\n[{timestamp}] ✅ 任务完成"
        message += f"\n总耗时: {duration_ms}ms ({duration_sec:.1f}s)"
        
        if md_path:
            message += f"\n报告路径: {md_path}"
        if pdf_path:
            message += f"\nPDF路径: {pdf_path}"
        
        message += "\n" + "="*60 + "\n"
        
        self._write_task_log(task_id, message)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.ANALYSIS.value,
            "action": "complete",
            "task_id": task_id,
            "duration_ms": duration_ms,
            "md_path": md_path,
            "pdf_path": pdf_path,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_task_failed(self, task_id: str, error_message: str, duration_ms: int = 0):
        """记录任务失败"""
        timestamp = self._format_time()
        duration_sec = duration_ms / 1000
        
        message = "\n" + "="*60
        message += f"\n[{timestamp}] ❌ 任务失败"
        message += f"\n总耗时: {duration_ms}ms ({duration_sec:.1f}s)"
        message += f"\n错误信息: {error_message}"
        message += "\n" + "="*60 + "\n"
        
        self._write_task_log(task_id, message)
        
        # 写入JSON日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.ERROR.value,
            "component": ComponentType.ANALYSIS.value,
            "action": "failed",
            "task_id": task_id,
            "duration_ms": duration_ms,
            "error": error_message,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_component_start(self, component: ComponentType, task_id: str = None, 
                          metadata: Dict = None):
        """记录组件调用开始（兼容原有接口）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": component.value,
            "action": "start",
            "task_id": task_id,
            "metadata": metadata or {},
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_component_end(self, component: ComponentType, task_id: str = None,
                        duration_ms: float = 0, success: bool = True,
                        error: str = None, metadata: Dict = None):
        """记录组件调用结束（兼容原有接口）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.ERROR.value if not success else LogLevel.INFO.value,
            "component": component.value,
            "action": "end",
            "task_id": task_id,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
            "metadata": metadata or {},
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_opencode_request(self, task_id: str, session_id: str, prompt: str,
                           model: str, turn_number: int = 1):
        """记录OpenCode请求（兼容原有接口）"""
        truncated_prompt = prompt[:2000] + "..." if len(prompt) > 2000 else prompt
        
        # 写入人类可读的任务日志
        timestamp = self._format_time()
        message = f"\n[{timestamp}] OpenCode请求:"
        message += f"\n  模型: {model}"
        message += f"\n  会话ID: {session_id if session_id else 'N/A'}"
        message += f"\n  对话轮次: {turn_number}"
        message += f"\n  Prompt长度: {len(prompt)} 字符"
        message += f"\n  Prompt内容:"
        message += f"\n{'-'*50}"
        message += f"\n{prompt}"
        message += f"\n{'-'*50}"
        message += "\n"
        self._write_task_log(task_id, message)
        
        # 写入JSON格式日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.INFO.value,
            "component": ComponentType.OPENCODE.value,
            "action": "request",
            "task_id": task_id,
            "session_id": session_id,
            "turn_number": turn_number,
            "model": model,
            "prompt_length": len(prompt),
            "prompt": truncated_prompt,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_opencode_response(self, task_id: str, session_id: str, response: str,
                            duration_ms: float, success: bool = True,
                            error: str = None, turn_number: int = 1):
        """记录OpenCode响应（兼容原有接口）"""
        truncated_response = response[:3000] + "..." if len(response) > 3000 else response
        
        # 写入人类可读的任务日志
        timestamp = self._format_time()
        message = f"\n[{timestamp}] OpenCode响应:"
        message += f"\n  会话ID: {session_id if session_id else 'N/A'}"
        message += f"\n  对话轮次: {turn_number}"
        message += f"\n  耗时: {duration_ms}ms"
        message += f"\n  状态: {'成功' if success else '失败'}"
        if error:
            message += f"\n  错误信息: {error}"
        else:
            message += f"\n  响应长度: {len(response)} 字符"
            message += f"\n  响应内容:"
            message += f"\n{'-'*50}"
            message += f"\n{response}"
            message += f"\n{'-'*50}"
        message += "\n"
        self._write_task_log(task_id, message)
        
        # 写入JSON格式日志
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.ERROR.value if not success else LogLevel.INFO.value,
            "component": ComponentType.OPENCODE.value,
            "action": "response",
            "task_id": task_id,
            "session_id": session_id,
            "turn_number": turn_number,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
            "response_length": len(response),
            "response": truncated_response,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def log_error(self, component: ComponentType, task_id: str, error: str,
                 traceback: str = None):
        """记录错误（兼容原有接口）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": LogLevel.ERROR.value,
            "component": component.value,
            "action": "error",
            "task_id": task_id,
            "error": error,
            "traceback": traceback[:2000] if traceback else None,
            "thread_id": threading.current_thread().ident
        }
        self._write_json_log(log_entry)
    
    def get_logs_by_task(self, task_id: str) -> List[Dict]:
        """获取指定任务的所有日志"""
        logs = []
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            date_dir = self.log_dir / today
            json_log_file = date_dir / "exec.log"
            
            if json_log_file.exists():
                with open(json_log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entry = json.loads(line)
                                if entry.get("task_id") == task_id:
                                    logs.append(entry)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            print(f"读取日志失败: {e}")
        
        return logs
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        """获取最近的日志"""
        logs = []
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            date_dir = self.log_dir / today
            json_log_file = date_dir / "exec.log"
            
            if json_log_file.exists():
                with open(json_log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        line = line.strip()
                        if line:
                            try:
                                logs.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            print(f"读取日志失败: {e}")
        
        return logs

# 创建全局日志实例
exec_logger = ExecLogger()
