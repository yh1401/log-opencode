#!/usr/bin/env python3
"""
OpenCode会话管理器 - 支持多轮对话和会话超时管理
"""

import subprocess
import tempfile
import os
import time
import threading
from typing import Dict, Optional, List
from datetime import datetime, timedelta

class OpenCodeSession:
    """OpenCode会话类 - 维护单个对话会话"""
    
    def __init__(self, session_id: str, model: str = "ollama/qwen3:4b", 
                 base_url: str = "http://localhost:11434", 
                 timeout_minutes: int = 30):
        self.session_id = session_id
        self.model = model
        self.base_url = base_url
        self.timeout_minutes = timeout_minutes
        self.last_active_time = time.time()
        self.message_history: List[Dict] = []
        self.lock = threading.RLock()
    
    def _update_activity(self):
        """更新最后活跃时间"""
        with self.lock:
            self.last_active_time = time.time()
    
    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        with self.lock:
            elapsed = time.time() - self.last_active_time
            return elapsed > self.timeout_minutes * 60
    
    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        with self.lock:
            self.message_history.append({
                "role": role,
                "content": content
            })
            self._update_activity()
    
    def get_history(self) -> List[Dict]:
        """获取消息历史"""
        with self.lock:
            return list(self.message_history)
    
    def clear_history(self):
        """清除消息历史"""
        with self.lock:
            self.message_history = []
    
    def analyze(self, prompt: str, log_content: str = "") -> str:
        """执行分析请求"""
        self._update_activity()
        
        # 构建完整的提示词（包含历史对话）
        history_text = ""
        if self.message_history:
            history_text = "## 对话历史\n"
            for msg in self.message_history[-5:]:  # 只保留最近5条历史
                history_text += f"{msg['role']}: {msg['content']}\n\n"
        
        full_prompt = f"""
{history_text}

## 当前分析任务
{prompt}

{log_content}
"""
        
        # 将日志内容写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            temp_file = f.name
        
        try:
            # 构建OpenCode命令
            command = [
                'opencode',
                '--model', self.model,
                '--prompt', full_prompt,
                '--file', temp_file
            ]
            
            # 设置环境变量
            env = os.environ.copy()
            if self.base_url:
                env['OLLAMA_HOST'] = self.base_url
            
            # 执行命令
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                env=env
            )
            
            if result.returncode != 0:
                error_msg = f"OpenCode执行失败: {result.stderr}"
                print(error_msg)
                return error_msg
            
            # 添加到历史记录
            self.add_message("user", prompt)
            self.add_message("assistant", result.stdout)
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            return "❌ OpenCode执行超时"
        except FileNotFoundError:
            return "❌ OpenCode未安装，请先安装OpenCode"
        except Exception as e:
            return f"❌ OpenCode调用失败: {str(e)}"
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)

class OpenCodeSessionManager:
    """OpenCode会话管理器 - 管理多个会话，支持超时清理"""
    
    def __init__(self, timeout_minutes: int = 30, cleanup_interval_minutes: int = 5):
        self.sessions: Dict[str, OpenCodeSession] = {}
        self.timeout_minutes = timeout_minutes
        self.cleanup_interval = cleanup_interval_minutes * 60
        self.lock = threading.RLock()
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """启动定时清理线程"""
        def cleanup():
            while True:
                time.sleep(self.cleanup_interval)
                self._cleanup_expired_sessions()
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
    
    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        with self.lock:
            expired_ids = [sid for sid, session in self.sessions.items() if session.is_expired()]
            for sid in expired_ids:
                del self.sessions[sid]
                print(f"🔄 会话 {sid} 已过期，已清理")
    
    def create_session(self, model: str = "ollama/qwen3:4b", 
                       base_url: str = "http://localhost:11434") -> str:
        """创建新会话"""
        session_id = f"session_{int(time.time())}_{os.urandom(4).hex()}"
        
        with self.lock:
            self.sessions[session_id] = OpenCodeSession(
                session_id=session_id,
                model=model,
                base_url=base_url,
                timeout_minutes=self.timeout_minutes
            )
        
        print(f"✨ 创建新会话: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[OpenCodeSession]:
        """获取会话"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session and not session.is_expired():
                session._update_activity()
                return session
            elif session and session.is_expired():
                del self.sessions[session_id]
                return None
            return None
    
    def remove_session(self, session_id: str):
        """移除会话"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                print(f"🗑️ 会话 {session_id} 已删除")
    
    def analyze(self, session_id: str, prompt: str, log_content: str = "") -> str:
        """执行分析（支持多轮对话）"""
        session = self.get_session(session_id)
        if not session:
            return "❌ 会话不存在或已过期"
        
        return session.analyze(prompt, log_content)
    
    def list_sessions(self) -> List[str]:
        """列出所有活跃会话"""
        with self.lock:
            return [sid for sid, session in self.sessions.items() if not session.is_expired()]
    
    def get_session_count(self) -> int:
        """获取活跃会话数量"""
        with self.lock:
            return len([s for s in self.sessions.values() if not s.is_expired()])
    
    def is_available(self) -> bool:
        """检查OpenCode是否可用"""
        try:
            result = subprocess.run(
                ['opencode', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def list_models(self) -> list:
        """列出可用模型"""
        try:
            result = subprocess.run(
                ['opencode', '--list-models'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return []
        except Exception:
            return []

# 全局会话管理器实例
# 会话超时时间：30分钟无操作自动关闭
# 定时清理间隔：5分钟检查一次
session_manager = OpenCodeSessionManager(
    timeout_minutes=30,
    cleanup_interval_minutes=5
)