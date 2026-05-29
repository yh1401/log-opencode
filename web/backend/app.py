#!/usr/bin/env python3
"""
Flask 后端 - 日志分析 Web 应用
提供文件上传、分析启动、进度查询、报告下载等 API
"""

import os
import re
import sys
import json
import hashlib
import threading
import time
import logging
import random
import string
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS

# 将项目根目录添加到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from log_parser import LogParser, LogEntry
from log_analyzer import LogAnalyzer

# PCAP 解析器（延迟导入）
try:
    from pcap_parser import PCAPParser
    PCAP_SUPPORTED = True
except ImportError:
    PCAP_SUPPORTED = False

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 最大 200MB
UPLOAD_FOLDER = PROJECT_ROOT / "logs" / "uploads"
OUTPUT_FOLDER_BASE = PROJECT_ROOT / "output"
EXEC_LOG_BASE = PROJECT_ROOT / "logs" / "exec"
ALLOWED_EXTENSIONS = {'.log', '.txt', '.json', '.csv', '.pcap', '.pcapng'}  # 新增 pcap 格式


# 为保持向后兼容，OUTPUT_FOLDER 指向 base（实际路径在运行时由 get_output_folder 决定）
OUTPUT_FOLDER = OUTPUT_FOLDER_BASE

# 分块处理配置
CHUNK_SIZE_MB = 1  # 大文件分块大小：1MB
LARGE_FILE_THRESHOLD_MB = 10  # 大文件阈值：10MB

# 创建必要目录
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER_BASE.mkdir(parents=True, exist_ok=True)
EXEC_LOG_BASE.mkdir(parents=True, exist_ok=True)


# 线程安全存取辅助函数
def get_output_folder(task_id: str = None) -> Path:
    """获取输出目录（按日期分组）
    
    按 YYYY-MM-DD 分目录，如：output/2026-05-29/
    如果指定 task_id，还会包含任务子目录用于存放该任务的文件。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    date_folder = OUTPUT_FOLDER_BASE / today
    date_folder.mkdir(parents=True, exist_ok=True)
    
    if task_id:
        task_folder = date_folder / task_id
        task_folder.mkdir(parents=True, exist_ok=True)
        return task_folder
    
    return date_folder


def build_output_filename(original_filename: str, suffix: str = "分析报告") -> str:
    """构建输出文件名
    
    格式：原始文件名-处理时间-报告类型.md/pdf
    例如：sample-20260529_093521-分析报告.md
    """
    # 去掉扩展名作为基础名
    base_name = Path(original_filename).stem
    # 处理时间
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 组合：基础名-时间-报告类型
    return f"{base_name}-{time_str}-{suffix}"

# 存储任务状态(线程安全实现，使用 threading.RLock)
tasks = {}
tasks_lock = threading.RLock()

# 线程安全存取辅助函数
def task_get(task_id: str):
    with tasks_lock:
        return tasks.get(task_id)

def task_set(task_id: str, **kwargs):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(kwargs)

def task_setitem(task_id: str, value: dict):
    with tasks_lock:
        tasks[task_id] = value


# ========================
# 工具函数
# ========================

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_file_size_mb(filepath: str) -> float:
    """获取文件大小（MB）"""
    return os.path.getsize(filepath) / (1024 * 1024)


def is_large_file(filepath: str) -> bool:
    """判断是否为大文件"""
    return get_file_size_mb(filepath) > LARGE_FILE_THRESHOLD_MB


def estimate_processing_time(total_chunks: int, avg_chunk_time_ms: int = 5000) -> dict:
    """估算剩余处理时间
    
    Args:
        total_chunks: 总分块数
        avg_chunk_time_ms: 平均每块处理时间（毫秒），默认5秒
    
    Returns:
        dict: 包含预估时间的字典
    """
    remaining_seconds = (total_chunks * avg_chunk_time_ms) / 1000
    
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    seconds = int(remaining_seconds % 60)
    
    if hours > 0:
        time_str = f"{hours}小时{minutes}分钟"
    elif minutes > 0:
        time_str = f"{minutes}分钟{seconds}秒"
    else:
        time_str = f"{seconds}秒"
    
    return {
        "total_seconds": int(remaining_seconds),
        "formatted": f"{time_str}（仅供参考）",
        "ref": True,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds
    }


def get_poll_interval(total_chunks: int) -> int:
    """根据分块数动态返回轮询间隔（秒）
    
    规则：
    - 分块数 > 100: 10秒
    - 分块数 > 5: 5秒
    - 其他: 1秒
    """
    if total_chunks > 100:
        return 10
    elif total_chunks > 5:
        return 5
    return 1


def generate_task_id():
    """生成任务ID：日期时间+6位随机字母"""
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_letters = ''.join(random.choices(string.ascii_letters, k=6))
    return f"{now}_{random_letters}"


class TaskLogger:
    """任务执行日志记录器 - 按日期分目录，含时间文件名，记录详细API调用"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.date_str = datetime.now().strftime("%Y-%m-%d")
        self.time_str = datetime.now().strftime("%H%M%S")
        # 按日期分目录
        self.log_dir = EXEC_LOG_BASE / self.date_str
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # 日志文件名含任务ID和时间
        self.log_file = self.log_dir / f"{self.time_str}_{task_id}.log"
        self._write_header()

    def _write_header(self):
        """写入日志头部"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"任务执行日志\n")
            f.write(f"任务ID: {self.task_id}\n")
            f.write(f"开始时间: {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n\n")

    def log_step(self, step: int, step_name: str, message: str = ""):
        """记录步骤日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] 步骤 {step}: {step_name}")
            if message:
                f.write(f" - {message}")
            f.write("\n")

    def log_api_call(self, provider: str, model: str, chunk_info: str = "",
                     request_tokens: int = 0, response_tokens: int = 0,
                     duration_ms: int = 0, status: str = "success", error: str = ""):
        """记录API调用详情"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{timestamp}] API调用:\n")
            f.write(f"  提供商: {provider}\n")
            f.write(f"  模型: {model}\n")
            if chunk_info:
                f.write(f"  分块: {chunk_info}\n")
            f.write(f"  请求tokens: {request_tokens}\n")
            f.write(f"  响应tokens: {response_tokens}\n")
            f.write(f"  耗时: {duration_ms}ms\n")
            f.write(f"  状态: {status}\n")
            if error:
                f.write(f"  错误: {error}\n")
            f.write("\n")

    def log_error(self, step: str, error: str):
        """记录错误"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] ❌ 错误 @ {step}: {error}\n")

    def log_complete(self, total_duration_ms: int):
        """记录任务完成"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] ✅ 任务完成\n")
            f.write(f"总耗时: {total_duration_ms}ms ({total_duration_ms/1000:.1f}s)\n")
            f.write(f"{'='*60}\n")


def make_sub_steps(current_step: int) -> list:
    """生成子步骤状态列表"""
    names = [
        "文件上传",
        "文件去重校验",
        "加载配置",
        "解析日志",
        "条目统计",
        "分块策略",
        "AI 模型分析",
        "生成 Markdown",
        "生成 PDF",
        "完成",
    ]
    result = []
    for i, name in enumerate(names, 1):
        if i < current_step:
            status = "done"
        elif i == current_step:
            status = "active"
        else:
            status = "pending"
        result.append({"name": name, "status": status})
    return result


def update_step(task_id: str, step: int, total_steps: int, step_name: str,
                progress: int, message: str, sub_steps: list = None, **extra):
    """更新任务步骤进度"""
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            return
        task["progress"] = progress
        task["message"] = message
        task["step"] = step
        task["total_steps"] = total_steps
        task["step_name"] = step_name
        if sub_steps is not None:
            task["sub_steps"] = sub_steps
        # 支持额外字段如 chunk_info
        for k, v in extra.items():
            task[k] = v


# ========================
# 路由
# ========================

@app.route('/')
def index():
    """首页 - 返回前端页面"""
    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日志分析工具 - Web 界面</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            padding: 30px 20px;
        }
        .main-container {
            display: flex;
            gap: 24px;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }
        .history-sidebar {
            width: 280px;
            flex-shrink: 0;
            background: rgba(255,255,255,0.97);
            border-radius: 20px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.4);
            padding: 24px;
            height: fit-content;
            max-height: calc(100vh - 80px);
            overflow-y: auto;
        }
        .container {
            background: rgba(255,255,255,0.97);
            border-radius: 20px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.4);
            flex: 1;
            padding: 45px;
            backdrop-filter: blur(10px);
        }
        h1 {
            color: #1a1a2e; margin-bottom: 6px; font-size: 30px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .upload-area {
            border: 2px dashed #c5b3e6; border-radius: 14px; padding: 45px;
            text-align: center; margin-bottom: 24px; transition: all 0.3s;
            cursor: pointer; background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
        }
        .upload-area:hover {
            border-color: #667eea; background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
            transform: translateY(-2px); box-shadow: 0 8px 25px rgba(102,126,234,0.15);
        }
        .upload-area .icon { font-size: 42px; margin-bottom: 12px; }
        .upload-area p { color: #555; }
        .upload-area .hint { color: #999; font-size: 12px; margin-top: 10px; }
        
        /* 中断按钮 */
        .btn-stop {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white; border: none; padding: 10px 24px; border-radius: 8px;
            font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s;
            margin-top: 12px; display: none;
        }
        .btn-stop.active { display: inline-block; }
        .btn-stop:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(239,68,68,0.4); }
        
        /* 预估时间 */
        .time-estimate {
            margin-top: 10px; padding: 8px 12px; background: #fef3c7;
            border-radius: 6px; font-size: 13px; color: #92400e; display: none;
        }
        .time-estimate.active { display: block; }
        .time-estimate.collapsed .eta-header { cursor: pointer; }
        .time-estimate.collapsed .eta-hint { display: none; }
        .time-estimate.collapsed .eta-arrow { transition: transform 0.2s; font-size: 11px; margin-left: 4px; }
        .time-estimate.collapsed .eta-arrow.expanded { transform: rotate(180deg); }
        .time-estimate .eta-header { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .time-estimate .eta-hint { color: #b45309; font-size: 12px; }
        .time-estimate .eta-arrow { font-size: 11px; }
        
                .file-info {
            font-size: 13px; color: #059669; margin-bottom: 10px; text-align: center;
        }
        
        /* 输出路径 */
        .output-path {
            margin-top: 8px; padding: 8px 12px; background: #f0f9ff;
            border-radius: 6px; font-size: 12px; color: #0369a1;
        }
        
        /* 历史对话列表 */
        .history-section {
            margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
        }
        .history-section h4 {
            color: #374151; margin-bottom: 12px; font-size: 15px;
        }
        .history-list {
            max-height: 200px; overflow-y: auto;
        }
        .history-item {
            padding: 10px 12px; background: #f9fafb; border-radius: 8px;
            margin-bottom: 8px; cursor: pointer; transition: all 0.2s;
            border: 1px solid transparent;
        }
        .history-item:hover {
            background: #f3f4f6; border-color: #667eea;
        }
        .history-item .filename { font-weight: 500; color: #1f2937; font-size: 13px; }
        .history-item .time { font-size: 11px; color: #9ca3af; margin-top: 2px; }
        .history-item .status-done { color: #22c55e; font-size: 11px; }
        .history-item .status-error { color: #ef4444; font-size: 11px; }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; padding: 15px 32px; border-radius: 10px;
            font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s; width: 100%;
            letter-spacing: 1px;
        }
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px); box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .prompt-section {
            display: none; margin-bottom: 16px;
        }
        .prompt-section label {
            display: block; font-size: 13px; color: #6b7280; margin-bottom: 6px;
        }
        .prompt-section textarea {
            width: 100%; padding: 10px; border: 1px solid #d1d5db;
            border-radius: 8px; font-size: 13px; resize: vertical; font-family: inherit;
            box-sizing: border-box;
        }
        .prompt-section textarea:focus { outline: none; border-color: #764ba2; }
        
            transform: translateY(-2px);
            box-shadow: 0 12px 30px rgba(102,126,234,0.45);
        }
        .btn-primary:disabled {
            background: #ccc; cursor: not-allowed; transform: none; box-shadow: none;
        }

        /* 进度区域 */
        .progress-section { display: none; margin-top: 28px; }
        .progress-section.active { display: block; }
        .progress-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
        }
        .progress-header .step-name { font-weight: 600; color: #333; font-size: 15px; }
        .progress-header .percent { color: #764ba2; font-weight: 700; font-size: 16px; }
        .progress-bar-track {
            height: 12px; background: #e5e7eb; border-radius: 6px;
            overflow: hidden; margin-bottom: 20px;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
        }
        .progress-bar-fill {
            height: 100%; border-radius: 6px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.6s ease; width: 0%;
        }

        /* 子步骤时间线 */
        .sub-steps { margin-top: 16px; }
        .sub-step {
            display: flex; align-items: center; padding: 7px 0;
            font-size: 13px; color: #888; transition: all 0.3s;
        }
        .sub-step .dot {
            width: 10px; height: 10px; border-radius: 50%;
            margin-right: 10px; background: #ddd; flex-shrink: 0;
            transition: all 0.3s;
        }
        .sub-step.done { color: #22c55e; }
        .sub-step.done .dot { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.4); }
        .sub-step.active { color: #764ba2; font-weight: 600; }
        .sub-step.active .dot {
            background: #764ba2; box-shadow: 0 0 8px rgba(118,75,162,0.5);
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.3); }
        }
        .sub-step.pending { color: #ccc; }
        .sub-step.pending .dot { background: #ddd; }

        /* 分块信息 */
        .chunk-info {
            margin-top: 12px; padding: 10px 14px; background: #f5f3ff;
            border-radius: 8px; font-size: 13px; color: #667eea;
            display: none;
        }
        .chunk-info.active { display: block; }

        /* AI 思考指示器 */
        .ai-thinking {
            display: none; margin-top: 14px; padding: 12px 16px;
            background: linear-gradient(135deg, #fef3c7, #fde68a);
            border-radius: 10px; font-size: 14px; color: #92400e;
            align-items: center;
        }
        .ai-thinking.active { display: flex; }
        .ai-thinking .dots::after {
            content: ''; animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0% { content: ''; }
            25% { content: '.'; }
            50% { content: '..'; }
            75% { content: '...'; }
        }

        /* 结果区域 */
        .result-section {
            display: none; margin-top: 24px; padding: 24px;
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border-radius: 12px; border: 1px solid #86efac;
        }
        .result-section.active { display: block; }
        .result-section h3 { color: #166534; margin-bottom: 12px; font-size: 18px; }
        .btn-download {
            display: inline-block; padding: 10px 20px; border-radius: 8px;
            text-decoration: none; font-weight: 600; font-size: 14px;
            transition: all 0.3s; margin-right: 10px;
        }
        .btn-download.md {
            background: #166534; color: white;
        }
        .btn-download.pdf {
            background: #764ba2; color: white;
        }
        .btn-download:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.15);
        }

        /* 错误区域 */
        .error-section {
            display: none; margin-top: 24px; padding: 20px;
            background: #fef2f2; border-radius: 12px; border: 1px solid #fca5a5;
            color: #dc2626;
        }
        .error-section.active { display: block; }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- 左侧历史记录 -->
        <div class="history-sidebar">
            <h4>📜 历史分析记录</h4>
            <div class="history-list" id="historyList">
                <p style="color: #9ca3af; font-size: 13px;">暂无历史记录</p>
            </div>
        </div>
        
        <!-- 右侧主内容 -->
        <div class="container">
            <h1>📊 日志分析工具</h1>
            <p class="subtitle">上传日志文件，AI 智能分析，生成 Markdown 和 PDF 报告</p>

            <div class="upload-area" id="uploadArea">
                <div class="icon">📂</div>
                <p>拖拽日志文件到此处，或 <strong>点击选择文件</strong></p>
                <p class="hint">支持格式: .log, .txt, .json, .csv, .pcap, .pcapng (最大 200MB)</p>
                <input type="file" id="fileInput" style="display: none;" accept=".log,.txt,.json,.csv,.pcap,.pcapng">
            </div>
            <div class="file-info" id="fileInfo" style="display:none;"></div>

            <button class="btn-primary" id="analyzeBtn" disabled>🚀 开始分析</button>

            <div class="prompt-section" id="promptSection" style="display:none;">
                <label for="userPrompt">💬 你可以补充说明本次分析的关注点或问题（选填）：</label>
                <textarea id="userPrompt" rows="3" placeholder="例如：重点关注 ERROR 和 WARNING 级别的异常、帮我分析响应时间慢的原因..."></textarea>
            </div>

            <div class="progress-section" id="progressArea">
                <div class="progress-header">
                    <span class="step-name" id="stepName">准备中...</span>
                    <span class="percent" id="percentText">0%</span>
                </div>
                <div class="progress-bar-track">
                    <div class="progress-bar-fill" id="progressBar"></div>
                </div>
                <div class="sub-steps" id="subSteps"></div>
                <div class="chunk-info" id="chunkInfo"></div>
                <div class="ai-thinking" id="aiThinking">
                    🤖 AI 正在思考中<span class="dots"></span>
                </div>
                <div class="time-estimate collapsed" id="timeEstimate">
                    <div class="eta-header" onclick="toggleTimeEstimate()">
                        ⏱️ 预计剩余时间: <span id="timeRemaining">计算中...</span>
                        <span class="eta-hint">（仅供参考，仅供参考）</span>
                        <span class="eta-arrow">▼</span>
                    </div>
                </div>
                <button class="btn-stop" id="stopBtn" onclick="stopAnalysis()">⏹️ 停止分析</button>
            </div>

            <div class="result-section" id="resultArea">
                <h3>✅ 分析完成！</h3>
                <div class="output-path" id="outputPath"></div>
                <a href="#" class="btn-download md" id="downloadMd">📄 下载 Markdown</a>
                <a href="#" class="btn-download pdf" id="downloadPdf">📑 下载 PDF</a>
            </div>

            <div class="error-section" id="errorArea">
                <p>❌ <strong>错误：</strong><span id="errorText"></span></p>
            </div>
        </div>
    </div>

    <script>
        let currentTaskId = null;
        let pollTimer = null;
        let totalChunks = 0;
        let processedChunks = 0;
        let chunkTimes = [];  // 记录每块处理时间
        let pollInterval = 1;  // 默认轮询间隔(秒)
        let analysisAborted = false;

        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const progressArea = document.getElementById('progressArea');
        const resultArea = document.getElementById('resultArea');
        const errorArea = document.getElementById('errorArea');
        const subStepsEl = document.getElementById('subSteps');
        const chunkInfoEl = document.getElementById('chunkInfo');
        const aiThinkingEl = document.getElementById('aiThinking');
        const stopBtn = document.getElementById('stopBtn');
        const timeEstimate = document.getElementById('timeEstimate');
        const timeRemaining = document.getElementById('timeRemaining');
        const fileInfo = document.getElementById('fileInfo');
        const promptSection = document.getElementById('promptSection');
        const historyList = document.getElementById('historyList');
        
        // 加载历史记录
        loadHistory();

        // 工具函数：格式化文件大小
        function formatSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // 处理文件选择
        function handleFileSelection(files) {
            if (files && files.length > 0) {
                analyzeBtn.disabled = false;
                uploadArea.innerHTML = '<div class="icon">✅</div><p>已选择文件: <strong>' + files[0].name + '</strong></p>';
                // 保存文件引用用于上传
                window.selectedFile = files[0];
            }
        }

        // 上传区域点击事件
        uploadArea.addEventListener('click', function(e) {
            e.preventDefault();
            fileInput.click();
        });
        
        // 文件选择变化事件
        fileInput.addEventListener('change', function(e) {
            handleFileSelection(fileInput.files);
        });

        // 拖拽支持
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.style.borderColor = '#667eea';
            uploadArea.style.background = 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)';
        });
        
        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.style.borderColor = '#c5b3e6';
            uploadArea.style.background = 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)';
        });
        
        uploadArea.addEventListener('dragenter', function(e) {
            e.preventDefault();
            e.stopPropagation();
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.style.borderColor = '#c5b3e6';
            uploadArea.style.background = 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)';
            
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleFileSelection(files);
            }
        });

        analyzeBtn.addEventListener('click', () => {
            const file = window.selectedFile || fileInput.files[0];
            if (!file) {
                alert('请先选择或拖拽一个文件');
                return;
            }
            analyzeBtn.disabled = true;
            
            // 如果已经上传过文件（有 currentTaskId），直接开始分析
            if (currentTaskId) {
                startAnalysis(currentTaskId);
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/upload', { method: 'POST', body: formData })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        currentTaskId = data.task_id;
                        fileInfo.textContent = '已上传: ' + file.name + ' (' + formatSize(file.size) + ')';
                        fileInfo.classList.add('active');
                        promptSection.style.display = 'block';
                        // 上传成功后立即开始分析
                        startAnalysis(currentTaskId);
                    } else {
                        analyzeBtn.disabled = false;
                        showError(data.error || '上传失败');
                    }
                })
                .catch(err => {
                    analyzeBtn.disabled = false;
                    showError(err.message);
                });
        });

        function startAnalysis(taskId) {
            analysisAborted = false;
            progressArea.classList.add('active');
            resultArea.classList.remove('active');
            errorArea.classList.remove('active');
            stopBtn.classList.add('active');
            timeEstimate.classList.remove('active');
            chunkTimes = [];
            processedChunks = 0;
            const userPrompt = document.getElementById('userPrompt') ? document.getElementById('userPrompt').value.trim() : '';

            fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId, user_prompt: userPrompt })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    pollProgress(taskId);
                } else {
                    showError(data.error || '分析启动失败');
                }
            })
            .catch(err => showError(err.message));
        }
        
        function stopAnalysis() {
            if (confirm('确定要停止当前分析任务吗？')) {
                analysisAborted = true;
                fetch('/api/abort/' + currentTaskId, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        if (pollTimer) clearTimeout(pollTimer);
                        showError('用户已中止分析');
                        stopBtn.classList.remove('active');
                    })
                    .catch(err => {
                        showError('中止请求失败，但已停止轮询');
                        stopBtn.classList.remove('active');
                    });
            }
        }
        
        function loadHistory() {
            fetch('/api/history')
                .then(res => res.json())
                .then(data => {
                    if (data.history && data.history.length > 0) {
                        historyList.innerHTML = data.history.map(item => {
                            let statusClass = item.status === 'completed' ? 'status-done' : 'status-error';
                            let statusIcon = item.status === 'completed' ? '✅' : '❌';
                            return '<div class="history-item" onclick="loadTask(&quot;' + item.task_id + '&quot;)">' +
                                '<div class="filename">' + item.filename + '</div>' +
                                '<div class="time">' + item.time + '</div>' +
                                '<div class="' + statusClass + '">' + statusIcon + ' ' + item.status + '</div>' +
                                '</div>';
                        }).join('');
                    }
                })
                .catch(err => console.log('加载历史失败', err));
        }
        
        function loadTask(taskId) {
            // 加载历史任务结果
            fetch('/api/progress/' + taskId)
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'completed') {
                        currentTaskId = taskId;
                        showResult(data.result);
                    }
                });
        }

        function pollProgress(taskId) {
            fetch('/api/progress/' + taskId)
                .then(res => res.json())
                .then(data => {
                    // 更新进度条
                    document.getElementById('progressBar').style.width = data.progress + '%';
                    document.getElementById('percentText').textContent = data.progress + '%';
                    document.getElementById('stepName').textContent = data.message;

                    // 更新子步骤
                    if (data.sub_steps) {
                        subStepsEl.innerHTML = data.sub_steps.map(s => {
                            let cls = s.status;
                            let icon = s.status === 'done' ? '' : (s.status === 'active' ? '' : '');
                            return '<div class="sub-step ' + cls + '"><span class="dot"></span>' + icon + ' ' + s.name + '</div>';
                        }).join('');
                    }

                    // 分块信息
                    if (data.chunk_info) {
                        chunkInfoEl.textContent = data.chunk_info;
                        chunkInfoEl.classList.add('active');
                    } else {
                        chunkInfoEl.classList.remove('active');
                    }

                    // AI思考指示器：步骤7时显示
                    if (data.step === 7) {
                        aiThinkingEl.classList.add('active');
                    } else {
                        aiThinkingEl.classList.remove('active');
                    }

                    if (data.status === 'completed') {
                        aiThinkingEl.classList.remove('active');
                        timeEstimate.classList.remove('active');
                        stopBtn.classList.remove('active');
                        showResult(data.result);
                    } else if (data.status === 'error') {
                        aiThinkingEl.classList.remove('active');
                        timeEstimate.classList.remove('active');
                        stopBtn.classList.remove('active');
                        showError(data.error);
                    } else if (data.status === 'aborted') {
                        showError('用户已中止分析');
                        stopBtn.classList.remove('active');
                    } else {
                        // 动态轮询间隔
                        let interval = (data.poll_interval || 1) * 1000;
                        pollTimer = setTimeout(() => pollProgress(taskId), interval);
                        
                        // 预估剩余时间
                        if (data.estimated_time) {
                            timeRemaining.textContent = data.estimated_time;
                            timeEstimate.classList.add('active');
                        }
                    }
                })
                .catch(err => showError(err.message));
        }

        function toggleTimeEstimate() {
            const el = document.getElementById('timeEstimate');
            const arrow = el ? el.querySelector('.eta-arrow') : null;
            if (el.classList.contains('collapsed')) {
                el.classList.remove('collapsed');
                if (arrow) { arrow.classList.add('expanded'); }
            } else {
                el.classList.add('collapsed');
                if (arrow) { arrow.classList.remove('expanded'); }
            }
        }

        function showResult(result) {
            progressArea.classList.remove('active');
            stopBtn.classList.remove('active');
            resultArea.classList.add('active');
            document.getElementById('downloadMd').href = '/api/download/' + currentTaskId + '/markdown';
            document.getElementById('downloadPdf').href = '/api/download/' + currentTaskId + '/pdf';
            // 显示输出路径
            if (result && result.output_path) {
                document.getElementById('outputPath').innerHTML = '📁 报告保存位置: <code>' + result.output_path + '</code>';
            }
        }

        function showError(msg) {
            if (pollTimer) clearTimeout(pollTimer);
            progressArea.classList.remove('active');
            aiThinkingEl.classList.remove('active');
            errorArea.classList.add('active');
            document.getElementById('errorText').textContent = msg;
        }
    </script>
</body>
</html>
"""
    return render_template_string(html)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': '不支持的文件类型'}), 400

        # 保存文件
        filename = hashlib.md5(file.filename.encode()).hexdigest() + Path(file.filename).suffix
        filepath = UPLOAD_FOLDER / filename
        file.save(filepath)

        # 去重校验
        file_hash = hashlib.md5(open(filepath, 'rb').read()).hexdigest()

        # 创建任务（线程安全）
        task_id = generate_task_id()
        task_data = {
            'status': 'uploaded',
            'progress': 10,
            'message': '文件上传成功',
            'step': 1,
            'total_steps': 10,
            'step_name': '文件上传',
            'filepath': str(filepath),
            'filename': file.filename,
            'file_hash': file_hash,
            'result': None,
            'error': None,
            'sub_steps': make_sub_steps(1),
            'user_prompt': request.form.get('user_prompt', ''),
        }
        with tasks_lock:
            tasks[task_id] = task_data

        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analyze', methods=['POST'])
def start_analysis():
    """启动分析任务"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        user_prompt = data.get('user_prompt', '')

        if task_id not in tasks:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        task = tasks[task_id]
        task['user_prompt'] = user_prompt
        filepath = task['filepath']
        task_logger = TaskLogger(task_id)

        # 启动后台分析线程
        def analyze():
            start_time = time.time()
            try:
                task['status'] = 'running'

                # 步骤2: 去重校验
                update_step(task_id, 2, 10, "文件去重校验", 15, "校验文件完整性",
                           make_sub_steps(2))
                task_logger.log_step(2, "文件去重校验", "校验文件MD5")
                time.sleep(0.3)

                # 步骤3: 加载配置
                update_step(task_id, 3, 10, "加载配置", 20, "加载分析配置",
                           make_sub_steps(3))
                task_logger.log_step(3, "加载配置", "读取config.yaml")
                config_path = PROJECT_ROOT / "config" / "config.yaml"
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                time.sleep(0.2)

                # 步骤4: 解析日志/网络数据包
                file_ext = Path(filepath).suffix.lower()
                is_pcap = file_ext in ('.pcap', '.pcapng')
                
                update_step(task_id, 4, 10, "解析数据包" if is_pcap else "解析日志", 30, 
                           "正在解析网络数据包..." if is_pcap else "正在解析日志文件...",
                           make_sub_steps(4))
                task_logger.log_step(4, "解析数据包" if is_pcap else "解析日志", f"文件: {filepath}")
                
                if is_pcap:
                    # 使用 PCAP 解析器
                    if not PCAP_SUPPORTED:
                        raise ImportError("scapy 未安装，请安装: pip install scapy")
                    
                    pcap_parser = PCAPParser(config)
                    packets = pcap_parser.parse_file(filepath)
                    
                    # 分析数据包
                    analysis_results = pcap_parser.analyze()
                    
                    # 生成报告
                    report = pcap_parser.generate_report()
                    
                    update_step(task_id, 4, 10, "解析数据包", 40,
                               f"解析完成，共 {len(packets)} 个数据包",
                               make_sub_steps(4))
                    task_logger.log_step(4, "解析数据包", f"解析到 {len(packets)} 个数据包")
                    
                    # 跳过后续步骤，直接生成报告
                    # 步骤5-7: 直接完成
                    update_step(task_id, 5, 10, "分析完成", 45, "网络分析完成", make_sub_steps(5))
                    update_step(task_id, 6, 10, "报告生成", 55, "正在生成报告", make_sub_steps(6))
                    update_step(task_id, 7, 10, "报告生成", 70, "报告生成完成", make_sub_steps(7))
                    
                    # 步骤8: 生成 Markdown
                    update_step(task_id, 8, 10, "生成 Markdown", 75, "正在生成 Markdown 报告...",
                               make_sub_steps(8))
                    task_logger.log_step(8, "生成 Markdown")
                    # 按日期分目录 + 按原文件名生成文件名
                    out_dir = get_output_folder(task_id)
                    output_md = out_dir / (build_output_filename(task['filename'], '分析报告') + ".md")
                    with open(output_md, 'w', encoding='utf-8') as f:
                        f.write(report)
                    update_step(task_id, 8, 10, "生成 Markdown", 85, f"Markdown 报告已生成: {output_md.name}",
                               make_sub_steps(8))
                    task_logger.log_step(8, "生成 Markdown", f"报告: {output_md}")
                    time.sleep(0.2)
                    
                    # 步骤9: 生成 PDF
                    update_step(task_id, 9, 10, "生成 PDF", 90, "正在生成 PDF 报告...",
                               make_sub_steps(9))
                    task_logger.log_step(9, "生成 PDF")
                    output_pdf = out_dir / (build_output_filename(task["filename"], "分析报告") + ".pdf")
                    # PDF 生成（简化）
                    try:
                        from reportlab.platypus import SimpleDocTemplate, Paragraph
                        from reportlab.lib.styles import getSampleStyleSheet
                        from reportlab.pdfbase import pdfmetrics
                        from reportlab.pdfbase.ttfonts import TTFont
                        # 注册中文字体
                        font_paths = [
                            '/System/Library/Fonts/PingFang.ttc',
                            '/System/Library/Fonts/STHeiti Light.ttc',
                            '/Library/Fonts/Arial Unicode.ttf',
                        ]
                        font_registered = False
                        for fp in font_paths:
                            if os.path.exists(fp):
                                try:
                                    pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                                    font_registered = True
                                    break
                                except:
                                    continue
                        if not font_registered:
                            pdfmetrics.registerFont(TTFont('ChineseFont', '/System/Library/Fonts/Helvetica.ttc'))

                        doc = SimpleDocTemplate(str(output_pdf))
                        styles = getSampleStyleSheet()
                        style = styles['Normal']
                        style.fontName = 'ChineseFont'
                        style.fontSize = 10
                        story = []
                        for line in report.split('\n'):
                            if line.startswith('# '):
                                h1_style = styles['Heading1']
                                h1_style.fontName = 'ChineseFont'
                                story.append(Paragraph(line[2:], h1_style))
                            elif line.startswith('## '):
                                h2_style = styles['Heading2']
                                h2_style.fontName = 'ChineseFont'
                                story.append(Paragraph(line[3:], h2_style))
                            elif line.startswith('### '):
                                h3_style = styles['Heading3']
                                h3_style.fontName = 'ChineseFont'
                                story.append(Paragraph(line[4:], h3_style))
                            elif line.startswith('|'):
                                # 表格行
                                style.wordWrap = 'CJK'
                                story.append(Paragraph(line, style))
                            elif line.startswith('- '):
                                # 列表项
                                style.wordWrap = 'CJK'
                                story.append(Paragraph('• ' + line[2:], style))
                            elif line.startswith('**'):
                                # 粗体
                                style.wordWrap = 'CJK'
                                story.append(Paragraph(line.replace('**', '<b>').replace('**', '</b>'), style))
                            elif line.startswith('`'):
                                # 代码
                                code_style = styles['Code']
                                code_style.fontName = 'ChineseFont'
                                story.append(Paragraph(line.replace('`', ''), code_style))
                            else:
                                style.wordWrap = 'CJK'
                                story.append(Paragraph(line, style))
                        doc.build(story)
                        update_step(task_id, 9, 10, "生成 PDF", 95, f"PDF 报告已生成: {output_pdf.name}",
                                   make_sub_steps(9))
                        task_logger.log_step(9, "生成 PDF", f"报告: {output_pdf}")
                    except Exception as pdf_e:
                        task_logger.log_error("PDF生成", str(pdf_e))
                        output_pdf = None
                    
                    # 步骤10: 完成
                    update_step(task_id, 10, 10, "完成", 100, "分析完成",
                               make_sub_steps(10),
                               md_path=str(output_md) if output_md.exists() else None,
                               pdf_path=str(output_pdf) if output_pdf and output_pdf.exists() else None)
                    task_logger.log_step(10, "完成", "分析报告已生成")
                    
                    elapsed = int(time.time() - start_time)
                    task['status'] = 'completed'
                    task['output_md'] = str(output_md) if output_md.exists() else None
                    task['output_pdf'] = str(output_pdf) if output_pdf and output_pdf.exists() else None
                    task['elapsed_time'] = f"{elapsed}秒"
                    return
                
                # 普通日志文件处理
                parser = LogParser(config)
                entries = parser.parse_file(filepath)
                update_step(task_id, 4, 10, "解析日志", 40,
                           f"解析完成，共 {len(entries)} 条日志",
                           make_sub_steps(4))
                task_logger.log_step(4, "解析日志", f"解析到 {len(entries)} 条日志")
                time.sleep(0.2)

                # 步骤5: 条目统计
                update_step(task_id, 5, 10, "条目统计", 45, "统计日志级别分布...",
                           make_sub_steps(5))
                task_logger.log_step(5, "条目统计", f"共 {len(entries)} 条")
                time.sleep(0.2)

                # 步骤6: 分块策略 - 基于文件大小
                update_step(task_id, 6, 10, "分块策略", 50, "制定分块策略...",
                           make_sub_steps(6))
                
                file_size_mb = get_file_size_mb(filepath)
                
                # 大文件(>10MB)按1MB分块，小文件按条数分块
                if file_size_mb > LARGE_FILE_THRESHOLD_MB:
                    # 基于文件大小分块
                    total_chunks = max(1, int(file_size_mb / CHUNK_SIZE_MB))
                    chunk_info = f"大文件 {file_size_mb:.1f}MB，按 {CHUNK_SIZE_MB}MB 分块，共 {total_chunks} 块"
                    batch_size = max(1, len(entries) // total_chunks)
                else:
                    batch_size = config.get("analysis", {}).get("batch_size", 5000)
                    total_chunks = max(1, (len(entries) + batch_size - 1) // batch_size)
                    chunk_info = f"共 {len(entries)} 条日志，分为 {total_chunks} 块处理（每块 {batch_size} 条）"
                
                # 更新轮询间隔
                poll_interval = get_poll_interval(total_chunks)
                
                # 计算预估时间
                estimated = estimate_processing_time(total_chunks)
                
                update_step(task_id, 6, 10, "分块策略", 55, chunk_info,
                           make_sub_steps(6), chunk_info=chunk_info,
                           total_chunks=total_chunks, poll_interval=poll_interval,
                           estimated_time=estimated["formatted"])
                task_logger.log_step(6, "分块策略", chunk_info)
                time.sleep(0.2)

                # 步骤7: AI 模型分析 (进度在步骤7时到70%)
                update_step(task_id, 7, 10, "AI 模型分析", 60,
                           f"AI 正在分析第 1/{total_chunks} 块...",
                           make_sub_steps(7), chunk_info=chunk_info,
                           poll_interval=poll_interval)
                task_logger.log_step(7, "AI 模型分析", f"开始分析，共 {total_chunks} 块")

                analyzer = LogAnalyzer(config)
                chunk_results = []
                chunk_times_ms = []  # 记录每块处理时间

                for i in range(total_chunks):
                    # 检查是否被中断
                    if task.get('aborted', False):
                        task['status'] = 'aborted'
                        task['error'] = '用户中止'
                        task_logger.log_step(7, "AI 模型分析", "用户中止")
                        return
                    
                    start_idx = i * batch_size
                    end_idx = min((i + 1) * batch_size, len(entries))
                    chunk = entries[start_idx:end_idx]

                    # 计算预估剩余时间
                    remaining_chunks = total_chunks - i
                    if chunk_times_ms:
                        avg_time = sum(chunk_times_ms) / len(chunk_times_ms)
                    else:
                        avg_time = 5000  # 默认5秒
                    remaining_seconds = int((remaining_chunks * avg_time) / 1000)
                    if remaining_seconds > 3600:
                        time_estimate = f"{remaining_seconds // 3600}小时{(remaining_seconds % 3600) // 60}分钟"
                    elif remaining_seconds > 60:
                        time_estimate = f"{remaining_seconds // 60}分钟{remaining_seconds % 60}秒"
                    else:
                        time_estimate = f"{remaining_seconds}秒"
                    
                    # 更新分块进度
                    chunk_progress = 60 + int((i + 1) / total_chunks * 10)  # 60-70%
                    update_step(task_id, 7, 10, "AI 模型分析", chunk_progress,
                               f"AI 正在分析第 {i+1}/{total_chunks} 块 ({len(chunk)} 条)...",
                               make_sub_steps(7), chunk_info=f"第 {i+1}/{total_chunks} 块",
                               poll_interval=poll_interval, estimated_time=time_estimate)

                    api_start = time.time()
                    try:
                        result = analyzer.analyze(chunk)
                        api_duration = int((time.time() - api_start) * 1000)
                        chunk_times_ms.append(api_duration)  # 记录处理时间
                        task_logger.log_api_call(
                            provider=config.get("model", {}).get("provider", "unknown"),
                            model=config.get("model", {}).get("name", "unknown"),
                            chunk_info=f"第 {i+1}/{total_chunks} 块 ({len(chunk)} 条)",
                            request_tokens=0, response_tokens=0,
                            duration_ms=api_duration, status="success"
                        )
                        chunk_results.append(result)
                    except Exception as e:
                        api_duration = int((time.time() - api_start) * 1000)
                        task_logger.log_api_call(
                            provider=config.get("model", {}).get("provider", "unknown"),
                            model=config.get("model", {}).get("name", "unknown"),
                            chunk_info=f"第 {i+1}/{total_chunks} 块",
                            duration_ms=api_duration, status="error", error=str(e)
                        )
                        task_logger.log_error(f"AI分析-块{i+1}", str(e))

                # 合并分析结果
                update_step(task_id, 7, 10, "AI 模型分析", 70,
                           "AI 分析完成，正在合并结果...",
                           make_sub_steps(7), chunk_info=chunk_info)
                task_logger.log_step(7, "AI 模型分析", "分析完成，合并结果")
                time.sleep(0.3)

                # 步骤8: 生成 Markdown
                update_step(task_id, 8, 10, "生成 Markdown", 75, "正在生成 Markdown 报告...",
                           make_sub_steps(8))
                task_logger.log_step(8, "生成 Markdown")
                out_dir = get_output_folder(task_id)
                output_md = out_dir / (build_output_filename(task["filename"], "分析报告") + ".md")
                report = analyzer.generate_report(
                    chunk_results[0] if len(chunk_results) == 1 else {"chunks": chunk_results},
                    entries, str(output_md)
                )
                update_step(task_id, 8, 10, "生成 Markdown", 85, "Markdown 报告已生成",
                           make_sub_steps(8))
                task_logger.log_step(8, "生成 Markdown", f"报告: {output_md}")
                time.sleep(0.2)

                # 步骤9: 生成 PDF
                update_step(task_id, 9, 10, "生成 PDF", 90, "正在生成 PDF 报告...",
                           make_sub_steps(9))
                task_logger.log_step(9, "生成 PDF")
                output_pdf = out_dir / (build_output_filename(task["filename"], "分析报告") + ".pdf")
                # PDF 生成（简化）
                try:
                    from reportlab.platypus import SimpleDocTemplate, Paragraph
                    from reportlab.lib.styles import getSampleStyleSheet
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont
                    # 注册中文字体
                    font_paths = [
                        '/System/Library/Fonts/PingFang.ttc',
                        '/System/Library/Fonts/STHeiti Light.ttc',
                        '/Library/Fonts/Arial Unicode.ttf',
                    ]
                    font_registered = False
                    for fp in font_paths:
                        if os.path.exists(fp):
                            try:
                                pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                                font_registered = True
                                break
                            except:
                                continue
                    if not font_registered:
                        pdfmetrics.registerFont(TTFont('ChineseFont', '/System/Library/Fonts/Helvetica.ttc'))

                    doc = SimpleDocTemplate(str(output_pdf))
                    styles = getSampleStyleSheet()
                    style = styles['Normal']
                    style.fontName = 'ChineseFont'
                    style.fontSize = 10
                    story = []
                    for line in report.split('\n'):
                        story.append(Paragraph(line or '&nbsp;', style))
                    doc.build(story)
                except ImportError:
                    # 没有reportlab，跳过PDF生成
                    task_logger.log_step(9, "生成 PDF", "reportlab未安装，跳过PDF生成")
                    pass
                except Exception as e:
                    task_logger.log_error("生成PDF", str(e))

                update_step(task_id, 9, 10, "生成 PDF", 95, "PDF 报告已生成",
                           make_sub_steps(9))
                time.sleep(0.2)

                # 步骤10: 完成
                total_duration = int((time.time() - start_time) * 1000)
                update_step(task_id, 10, 10, "完成", 100, "分析完成！",
                           make_sub_steps(10))
                task_logger.log_complete(total_duration)

                task['status'] = 'completed'
                task['progress'] = 100
                task['message'] = '分析完成'
                task['result'] = {
                    'markdown_path': str(output_md),
                    'pdf_path': str(output_pdf) if output_pdf.exists() else None,
                    'output_path': str(out_dir),
                    'output_filename': output_md.name,
                }

            except Exception as e:
                total_duration = int((time.time() - start_time) * 1000)
                task['status'] = 'error'
                task['error'] = str(e)
                task_logger.log_error("分析流程", str(e))
                task_logger.log_complete(total_duration)

        thread = threading.Thread(target=analyze)
        thread.start()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """查询任务进度"""
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            return jsonify({'error': '任务不存在'}), 404
        # 深拷贝防止外部修改
        task_copy = dict(task)

    return jsonify({
        'status': task_copy['status'],
        'progress': task_copy['progress'],
        'message': task_copy['message'],
        'step': task_copy.get('step', 0),
        'total_steps': task_copy.get('total_steps', 10),
        'step_name': task_copy.get('step_name', ''),
        'sub_steps': task_copy.get('sub_steps', []),
        'chunk_info': task_copy.get('chunk_info', ''),
        'result': task_copy.get('result'),
        'error': task_copy.get('error'),
        'total_chunks': task_copy.get('total_chunks', 0),
        'poll_interval': task_copy.get('poll_interval', 1),
        'estimated_time': task_copy.get('estimated_time', ''),
    })


@app.route('/api/abort/<task_id>', methods=['POST'])
def abort_task(task_id):
    """中止任务"""
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
    
    task['aborted'] = True
    return jsonify({'success': True, 'message': '已发送中止信号'})


@app.route('/api/history')
def get_history():
    """获取历史分析记录"""
    with tasks_lock:
        history = []
        for task_id, task in list(tasks.items()):
            if task['status'] in ['completed', 'error']:
                history.append({
                    'task_id': task_id,
                    'filename': task.get('filename', '未知文件'),
                    'status': task['status'],
                    'time': task_id.split('_')[0] + ' ' + task_id.split('_')[1].replace('-', ':'),
                })
    history.sort(key=lambda x: x['task_id'], reverse=True)
    return jsonify({'history': history[:20]})  # 最多返回20条


@app.route('/api/download/<task_id>/<format>')
def download_report(task_id, format):
    """下载分析报告"""
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            return jsonify({'error': '任务不存在'}), 404
        if task['status'] != 'completed':
            return jsonify({'error': '分析未完成'}), 400
        result = dict(task['result'])


    if format == 'markdown':
        path = result['markdown_path']
    elif format == 'pdf':
        path = result.get('pdf_path')
        if not path:
            return jsonify({'error': 'PDF 未生成'}), 404
    else:
        return jsonify({'error': '不支持的格式'}), 400

    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
