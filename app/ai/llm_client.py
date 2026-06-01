#!/usr/bin/env python3
"""
LLM客户端模块 - 调用AI模型API（集成OpenCode会话管理）
"""

import requests
import json
import time
import os
from typing import Dict, Any, Optional, List
from config.settings import settings
from app.ai.opencode_session import session_manager
from app.ai.opencode_client import OpenCodeClient

class LLMClient:
    """LLM模型客户端"""
    
    # 配置常量
    SMALL_FILE_THRESHOLD = 500 * 1024  # 小文件阈值：500KB
    BATCH_SIZE = 3000  # 每批处理的日志条目数
    MAX_TOTAL_ENTRIES = 50000  # 最大处理条目数
    
    def __init__(self):
        self.model_config = settings.get_model_config()
        self.timeout = 120
        self.max_retries = 3
        self.use_opencode = self.model_config.get("use_opencode", False)
        
        # 初始化OpenCode客户端
        model_name = self.model_config.get("name", "ollama/qwen3:4b")
        base_url = self.model_config.get("base_url", "http://localhost:11434")
        self.opencode_client = OpenCodeClient(model=model_name, base_url=base_url)
    
    def call_model(self, messages: list, model_name: str = None, 
                  temperature: float = 0.7, max_tokens: int = 4000) -> Dict:
        """调用LLM模型API"""
        # 如果配置了使用OpenCode，优先使用OpenCode
        if self.use_opencode:
            return self._call_opencode(messages, model_name)
        
        # 否则使用标准API调用
        config = self._get_config(model_name)
        
        url = f"{config['base_url']}/chat/completions"
        
        payload = {
            "model": config['name'],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        if config.get('api_key'):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        
        # 重试机制
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                return {
                    "success": True,
                    "content": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {})
                }
            
            except requests.exceptions.RequestException as e:
                print(f"LLM调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    # 指数退避
                    wait_time = 2 ** attempt
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败
        return {
            "success": False,
            "error": "LLM服务调用失败，请稍后重试"
        }
    
    def _call_opencode(self, messages: list, model_name: str = None) -> Dict:
        """使用OpenCode调用模型"""
        # 构建完整的提示词
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"{role}: {content}\n\n"
        
        # 使用第一个可用的会话，或创建新会话
        sessions = session_manager.list_sessions()
        if sessions:
            session_id = sessions[0]
        else:
            model = model_name or self.model_config.get("name", "ollama/qwen3:4b")
            base_url = self.model_config.get("base_url", "http://localhost:11434")
            session_id = session_manager.create_session(model=model, base_url=base_url)
        
        # 调用OpenCode
        result = session_manager.analyze(session_id, prompt)
        
        if result.startswith("❌"):
            return {
                "success": False,
                "error": result
            }
        
        return {
            "success": True,
            "content": result,
            "session_id": session_id,
            "usage": {}
        }
    
    def _get_config(self, model_name: Optional[str] = None) -> Dict:
        """获取模型配置"""
        if model_name:
            return {
                "name": model_name,
                "base_url": self.model_config.get("base_url", "https://api.modelarts-maas.com/openai/v1"),
                "api_key": self.model_config.get("api_key", "")
            }
        
        return {
            "name": self.model_config.get("name", "qwen3-235b-a22b"),
            "base_url": self.model_config.get("base_url", "https://api.modelarts-maas.com/openai/v1"),
            "api_key": self.model_config.get("api_key", "")
        }
    
    def parse_response(self, response: str) -> Dict:
        """解析模型响应"""
        try:
            # 尝试解析为JSON
            data = json.loads(response)
            return {"type": "json", "data": data}
        except json.JSONDecodeError:
            # 如果不是JSON，作为Markdown文本返回
            return {"type": "markdown", "data": response}
    
    def analyze_logs(self, log_content: str = None, file_path: str = None, user_prompt: str = "", 
                   total_entries: int = 0) -> Dict:
        """分析日志内容（智能处理策略）
        
        Args:
            log_content: 日志内容字符串
            file_path: 日志文件路径（优先使用）
            user_prompt: 用户提示词
            total_entries: 日志条目总数（用于分块决策）
        """
        # 判断处理策略
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            
            if file_size <= self.SMALL_FILE_THRESHOLD:
                # 小文件：直接传递文件路径给OpenCode
                return self._analyze_small_file(file_path, user_prompt)
            else:
                # 大文件：分块分析
                return self._analyze_large_file(log_content, user_prompt, total_entries)
        elif log_content:
            # 只有内容：判断是否需要分块
            if total_entries > self.BATCH_SIZE:
                return self._analyze_large_file(log_content, user_prompt, total_entries)
            else:
                return self._analyze_direct(log_content, user_prompt)
        else:
            return {"success": False, "error": "未提供日志内容或文件路径"}
    
    def _analyze_small_file(self, file_path: str, user_prompt: str) -> Dict:
        """分析小文件（<500KB）：直接传递文件路径"""
        print(f"🔹 小文件分析模式：{file_path}")
        
        try:
            result = self.opencode_client.analyze_logs(
                file_path=file_path,
                user_prompt=user_prompt
            )
            
            if result.startswith("❌"):
                return {"success": False, "error": result}
            
            return {
                "success": True,
                "analysis": result,
                "raw_response": result,
                "strategy": "small_file_direct",
                "usage": {}
            }
        except Exception as e:
            return {"success": False, "error": f"小文件分析失败: {str(e)}"}
    
    def _analyze_direct(self, log_content: str, user_prompt: str) -> Dict:
        """直接分析（不分块）"""
        print(f"🔹 直接分析模式：{len(log_content)} 字符")
        
        # 构建系统提示词
        system_prompt = """
你是一位资深的日志分析专家。请直接输出结构化的Markdown格式分析报告，不要返回JSON格式。

报告结构要求：
1. 使用## 二级标题分隔各个部分
2. 使用列表（- 或数字）展示条目
3. 使用表格展示统计数据
4. 使用**加粗**强调重要内容

报告内容应包含：
- 概览摘要：日志总览和主要问题概述
- 关键事件：重要事件的时间线或摘要
- 错误详情：具体错误分析和影响评估（如有）
- 根因分析：问题根本原因分析（如有）
- 改进建议：具体、可操作的优化建议

请直接输出Markdown文本，不要包含任何JSON格式。
"""
        
        # 构建用户提示词
        user_message = f"""
请分析以下日志内容，并输出结构化的Markdown分析报告：

**分析关注点：** {user_prompt if user_prompt else '全面分析'}

---

**日志内容：**
{log_content}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # 调用模型
        result = self.call_model(messages)
        
        if result.get("success"):
            parsed = self.parse_response(result["content"])
            return {
                "success": True,
                "analysis": parsed["data"],
                "raw_response": result["content"],
                "strategy": "direct",
                "usage": result.get("usage", {}),
                "session_id": result.get("session_id")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "未知错误"),
                "strategy": "direct"
            }
    
    def _analyze_large_file(self, log_content: str, user_prompt: str, total_entries: int) -> Dict:
        """分析大文件：分块处理 + 结果合并"""
        print(f"🔹 大文件分块分析模式：{total_entries} 条，每批 {self.BATCH_SIZE} 条")
        
        # 限制最大处理条目
        actual_entries = min(total_entries, self.MAX_TOTAL_ENTRIES)
        
        # 计算分块数
        num_chunks = max(1, (actual_entries // self.BATCH_SIZE) + 1)
        print(f"📊 将分为 {num_chunks} 批处理")
        
        # 分割日志内容
        lines = log_content.strip().split('\n')
        chunk_size = max(1, len(lines) // num_chunks)
        
        chunk_results = []
        errors = []
        
        for i in range(num_chunks):
            start_idx = i * chunk_size
            end_idx = min((i + 1) * chunk_size, len(lines))
            
            if start_idx >= len(lines):
                break
            
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = '\n'.join(chunk_lines)
            
            print(f"⏳ 处理第 {i+1}/{num_chunks} 批 ({len(chunk_lines)} 条)")
            
            # 分析当前块
            chunk_result = self.opencode_client.analyze_logs(
                log_content=chunk_content,
                user_prompt=f"【批次 {i+1}/{num_chunks}】{user_prompt}"
            )
            
            if chunk_result.startswith("❌"):
                errors.append(f"批次 {i+1} 分析失败: {chunk_result}")
                print(f"❌ 批次 {i+1} 分析失败")
            else:
                chunk_results.append({
                    "chunk": i + 1,
                    "total_chunks": num_chunks,
                    "content": chunk_result
                })
                print(f"✅ 批次 {i+1} 分析完成")
        
        if not chunk_results:
            return {
                "success": False,
                "error": f"所有批次分析失败: {'; '.join(errors)}",
                "strategy": "chunked"
            }
        
        # 合并分析结果
        merged_result = self._merge_chunk_results(chunk_results, user_prompt)
        
        return {
            "success": True,
            "analysis": merged_result,
            "raw_response": merged_result,
            "strategy": "chunked",
            "num_chunks": num_chunks,
            "processed_chunks": len(chunk_results),
            "errors": errors if errors else None,
            "usage": {}
        }
    
    def _merge_chunk_results(self, chunk_results: List[Dict], user_prompt: str) -> str:
        """合并多个分块的分析结果"""
        print("🔄 合并分块分析结果...")
        
        # 收集各批次的分析内容
        chunk_contents = [result["content"] for result in chunk_results]
        
        # 构建合并提示词
        merge_prompt = f"""
你是一位资深的日志分析专家。请将以下多个批次的日志分析结果合并为一份完整的、结构化的Markdown格式分析报告。

**原始分析关注点：** {user_prompt if user_prompt else '全面分析'}

---

**各批次分析结果：**

{chr(10).join([f"=== 批次 {i+1}/{len(chunk_contents)} ===\n{content}" for i, content in enumerate(chunk_contents)])}

---

**要求：**
1. 整合重复信息，避免内容冗余
2. 识别跨批次的模式和趋势
3. 输出完整的结构化报告，包含：
   - 概览摘要
   - 关键事件汇总
   - 错误详情整合
   - 根因分析（如有）
   - 改进建议
4. 使用## 二级标题分隔各个部分
5. 使用列表和表格展示数据
6. 使用**加粗**强调重要内容

请直接输出Markdown文本，不要包含任何JSON格式。
"""
        
        messages = [
            {"role": "system", "content": "你是一位资深的日志分析专家，擅长整合和汇总多份分析报告。"},
            {"role": "user", "content": merge_prompt}
        ]
        
        result = self.call_model(messages)
        
        if result.get("success"):
            return result["content"]
        else:
            # 如果合并失败，返回各批次结果的简单拼接
            return f"""
## 📊 日志分析报告（分块汇总）

> 警告：自动合并失败，以下是各批次分析结果

{chr(10).join([f"### 批次 {i+1}/{len(chunk_contents)}\n{content}\n---" for i, content in enumerate(chunk_contents)])}
"""
    
    def continue_conversation(self, session_id: str, follow_up_question: str) -> Dict:
        """继续对话（多轮对话支持）"""
        if not session_manager.get_session(session_id):
            return {
                "success": False,
                "error": "会话不存在或已过期"
            }
        
        # 直接调用会话继续对话
        result = session_manager.analyze(session_id, follow_up_question)
        
        if result.startswith("❌"):
            return {
                "success": False,
                "error": result
            }
        
        return {
            "success": True,
            "content": result,
            "session_id": session_id
        }
    
    def close_session(self, session_id: str):
        """关闭会话"""
        session_manager.remove_session(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        session = session_manager.get_session(session_id)
        if session:
            return {
                "session_id": session.session_id,
                "model": session.model,
                "message_count": len(session.get_history()),
                "last_active": session.last_active_time
            }
        return None