#!/usr/bin/env python3
"""
OpenCode客户端模块 - 集成OpenCode CLI
"""

import subprocess
import tempfile
import os
from typing import Dict, Optional

class OpenCodeClient:
    """OpenCode CLI客户端"""
    
    # 小文件阈值：500KB以下直接传文件路径
    SMALL_FILE_THRESHOLD = 500 * 1024  # 500KB
    
    def __init__(self, model: str = "ollama/qwen3:4b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.timeout = 300  # 5分钟超时
    
    def analyze_logs(self, log_content: str = None, file_path: str = None, user_prompt: str = "") -> str:
        """调用OpenCode分析日志（支持内容或文件路径）
        
        Args:
            log_content: 日志内容字符串（大文件场景）
            file_path: 日志文件路径（小文件场景，<500KB时优先使用）
            user_prompt: 用户提示词
        """
        temp_file = None
        input_file = None
        
        try:
            # 构建分析提示词
            prompt = f"""
请分析以下日志文件：

{user_prompt}

日志内容：
"""
            
            # 判断使用文件路径还是内容
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                if file_size <= self.SMALL_FILE_THRESHOLD:
                    # 小文件：直接使用原文件路径
                    input_file = file_path
                    print(f"📄 小文件模式：直接传递原文件路径 ({file_size} bytes)")
                else:
                    # 大文件：使用传入的内容（已分块处理）
                    temp_file = self._create_temp_file(log_content)
                    input_file = temp_file
                    print(f"📦 大文件模式：使用临时文件 ({len(log_content) if log_content else 0} chars)")
            elif log_content:
                # 只有内容，写入临时文件
                temp_file = self._create_temp_file(log_content)
                input_file = temp_file
                print(f"📝 内容模式：使用临时文件 ({len(log_content)} chars)")
            else:
                return "❌ 未提供日志内容或文件路径"
            
            # 构建OpenCode命令
            command = [
                'opencode',
                '--model', self.model,
                '--prompt', prompt,
                '--file', input_file
            ]
            
            # 执行命令
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, 'OLLAMA_HOST': self.base_url}
            )
            
            if result.returncode != 0:
                # 命令执行失败，返回错误信息
                error_msg = f"OpenCode执行失败: {result.stderr}"
                print(error_msg)
                return error_msg
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            return "❌ OpenCode执行超时"
        except FileNotFoundError:
            return "❌ OpenCode未安装，请先安装OpenCode"
        except Exception as e:
            return f"❌ OpenCode调用失败: {str(e)}"
        finally:
            # 清理临时文件（不清理原文件）
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def _create_temp_file(self, content: str) -> str:
        """创建临时文件并写入内容"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            return f.name
    
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
