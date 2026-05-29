"""
分析API模块
"""

import threading
import time
import json
from flask import Blueprint, request, jsonify
from app.core.task_manager import task_manager
from app.core.data_processor import DataProcessor
from app.core.prompt_engine import PromptEngine
from app.core.report_generator import ReportGenerator
from app.core.exec_logger import exec_logger, ComponentType
from app.ai.llm_client import LLMClient
from app.storage.file_manager import file_manager
from app.storage.history_manager import history_manager

analyze_bp = Blueprint('analyze', __name__)

def analyze_task(task_id: str, user_prompt: str = ""):
    """后台分析任务"""
    start_time = time.time()
    try:
        # 获取任务信息
        task = task_manager.get_task(task_id)
        if not task:
            return
        
        filename = task.get('filename', 'unknown')
        
        # 记录任务开始（使用新的日志格式）
        exec_logger.log_task_start(task_id, filename)
        
        # 步骤1: 文件去重校验
        exec_logger.log_step(task_id, 1, '文件去重校验', f'校验文件MD5')
        
        # 更新状态：开始验证
        task_manager.update_task(task_id, 
                                status='validating',
                                progress=5,
                                current_step='数据验证中...')
        history_manager.update_task(task_id, {'status': 'validating', 'progress': 5, 'current_step': '数据验证中...'})
        
        # 步骤2: 数据验证
        exec_logger.log_step(task_id, 2, '数据验证', f'文件: {task["upload_path"]}')
        exec_logger.log_component_start(ComponentType.VALIDATION, task_id)
        data_processor = DataProcessor()
        is_valid, error_msg = data_processor.validate_file(task['upload_path'])
        exec_logger.log_component_end(ComponentType.VALIDATION, task_id, success=is_valid, error=error_msg if not is_valid else None)
        
        if not is_valid:
            task_manager.mark_failed(task_id, error_msg)
            history_manager.update_task(task_id, {'status': 'failed', 'error_message': error_msg})
            exec_logger.log_task_failed(task_id, error_msg, duration_ms=int((time.time() - start_time) * 1000))
            return
        
        # 更新状态：数据清洗
        task_manager.update_task(task_id,
                                status='cleaning',
                                progress=10,
                                current_step='数据清洗中...')
        history_manager.update_task(task_id, {'status': 'cleaning', 'progress': 10, 'current_step': '数据清洗中...'})
        
        # 步骤3: 解析日志
        exec_logger.log_step(task_id, 3, '解析日志', f'文件: {task["upload_path"]}')
        exec_logger.log_component_start(ComponentType.PARSING, task_id)
        
        task_manager.update_task(task_id,
                                status='parsing',
                                progress=15,
                                current_step='日志解析中...')
        history_manager.update_task(task_id, {'status': 'parsing', 'progress': 15, 'current_step': '日志解析中...'})
        
        entries = data_processor.parse_logs(task['upload_path'])
        exec_logger.log_step(task_id, 3, '解析日志', f'解析到 {len(entries)} 条日志')
        exec_logger.log_component_end(ComponentType.PARSING, task_id, success=True, 
                                     metadata={'entries_count': len(entries)})
        
        # 步骤4: 数据清洗
        exec_logger.log_step(task_id, 4, '数据清洗', f'清洗 {len(entries)} 条日志')
        exec_logger.log_component_start(ComponentType.CLEANING, task_id)
        cleaned_entries = data_processor.clean_data(entries)
        exec_logger.log_step(task_id, 4, '数据清洗', f'清洗完成，剩余 {len(cleaned_entries)} 条')
        exec_logger.log_component_end(ComponentType.CLEANING, task_id, success=True,
                                     metadata={'cleaned_entries': len(cleaned_entries)})
        
        # 更新状态：统计分析
        task_manager.update_task(task_id,
                                status='counting',
                                progress=20,
                                current_step='条目统计中...')
        history_manager.update_task(task_id, {'status': 'counting', 'progress': 20, 'current_step': '条目统计中...'})
        
        # 步骤5: 条目统计
        exec_logger.log_step(task_id, 5, '条目统计', f'共 {len(cleaned_entries)} 条')
        stats = data_processor.get_statistics(cleaned_entries)
        
        # 更新状态：分块处理
        task_manager.update_task(task_id,
                                status='chunking',
                                progress=25,
                                current_step='分块处理中...')
        history_manager.update_task(task_id, {'status': 'chunking', 'progress': 25, 'current_step': '分块处理中...'})
        
        # 步骤6: 分块策略
        batch_size = 5000
        total_chunks = max(1, len(cleaned_entries) // batch_size + 1)
        task_manager.update_task(task_id, total_chunks=total_chunks)
        exec_logger.log_step(task_id, 6, '分块策略', f'共 {len(cleaned_entries)} 条日志，分为 {total_chunks} 块处理（每块 {batch_size} 条）')
        
        # 更新状态：AI分析
        task_manager.update_task(task_id,
                                status='analyzing',
                                progress=60,
                                current_step='AI智能分析中...')
        history_manager.update_task(task_id, {'status': 'analyzing', 'progress': 60, 'current_step': 'AI智能分析中...'})
        
        # 步骤7: AI模型分析
        exec_logger.log_step(task_id, 7, 'AI模型分析', f'开始分析，共 {len(cleaned_entries)} 条日志')
        
        # 构建日志内容
        log_content = data_processor.format_entries(cleaned_entries, limit=len(cleaned_entries))
        
        # AI分析（智能处理策略）
        exec_logger.log_component_start(ComponentType.OPENCODE, task_id)
        llm_client = LLMClient()
        
        # 记录OpenCode请求
        model_name = llm_client.model_config.get("name", "unknown")
        provider = llm_client.model_config.get("provider", "modelarts")
        exec_logger.log_opencode_request(task_id, "", user_prompt, model_name, turn_number=1)
        
        api_start_time = time.time()
        
        # 使用智能分析策略：传递文件路径（小文件直接传，大文件传内容）
        result = llm_client.analyze_logs(
            log_content=log_content,
            file_path=task['upload_path'],
            user_prompt=user_prompt,
            total_entries=len(cleaned_entries)
        )
        
        api_duration_ms = int((time.time() - api_start_time) * 1000)
        
        # 记录API调用详情
        exec_logger.log_api_call(task_id, provider, model_name, 1, total_chunks, 
                                 len(cleaned_entries), duration_ms=api_duration_ms, 
                                 status="success" if result.get("success") else "failed")
        
        # 记录OpenCode响应
        if result.get("success"):
            response_content = result.get("analysis", "")
            exec_logger.log_opencode_response(task_id, "", response_content, 
                                            duration_ms=api_duration_ms, success=True)
            exec_logger.log_component_end(ComponentType.OPENCODE, task_id, success=True)
            exec_logger.log_step(task_id, 7, 'AI模型分析', '分析完成，合并结果')
        else:
            exec_logger.log_opencode_response(task_id, "", "", 
                                            duration_ms=api_duration_ms, success=False, 
                                            error=result.get("error"))
            exec_logger.log_component_end(ComponentType.OPENCODE, task_id, success=False, 
                                        error=result.get("error"))
        
        if not result.get('success'):
            task_manager.mark_failed(task_id, result.get('error', 'AI分析失败'))
            history_manager.update_task(task_id, {'status': 'failed', 'error_message': result.get('error', 'AI分析失败')})
            exec_logger.log_task_failed(task_id, result.get('error', 'AI分析失败'), duration_ms=int((time.time() - start_time) * 1000))
            return
        
        # 更新进度（AI分析完成后到65%）
        task_manager.update_task(task_id,
                                processed_chunks=1,
                                progress=65)
        
        # 更新状态：生成报告
        task_manager.update_task(task_id,
                                status='generating',
                                progress=80,
                                current_step='报告生成中...')
        history_manager.update_task(task_id, {'status': 'generating', 'progress': 80, 'current_step': '报告生成中...'})
        
        # 步骤8: 生成Markdown报告
        exec_logger.log_step(task_id, 8, '生成Markdown')
        exec_logger.log_component_start(ComponentType.REPORT, task_id)
        report_generator = ReportGenerator()
        
        # 收集文件信息
        file_info = {
            'filename': task.get('filename', 'unknown'),
            'file_size': task.get('file_size', 0),
            'total_entries': len(cleaned_entries)
        }
        
        # 如果是JSON格式结果，转换为友好的Markdown
        if isinstance(result['analysis'], dict):
            md_content = report_generator.generate_markdown(result['analysis'], file_info)
        elif isinstance(result['analysis'], str):
            # 检查是否是JSON字符串
            try:
                json_data = json.loads(result['analysis'])
                md_content = report_generator.generate_markdown(json_data, file_info)
            except json.JSONDecodeError:
                # 已经是Markdown格式
                md_content = report_generator.generate_markdown(result['analysis'], file_info)
        else:
            md_content = report_generator.generate_markdown(str(result['analysis']), file_info)
        
        # 保存Markdown报告
        md_path = file_manager.save_report(
            md_content,
            task_id,
            task['filename'],
            report_type='markdown'
        )
        exec_logger.log_step(task_id, 8, '生成Markdown', f'报告: {md_path}')
        
        # 步骤9: 生成PDF报告
        exec_logger.log_step(task_id, 9, '生成PDF')
        pdf_bytes = report_generator.generate_pdf(md_content)
        pdf_path = file_manager.save_report(
            pdf_bytes,
            task_id,
            task['filename'],
            report_type='pdf'
        )
        
        exec_logger.log_component_end(ComponentType.REPORT, task_id, success=True,
                                     metadata={'md_path': md_path, 'pdf_path': pdf_path})
        
        # 更新任务完成状态
        task_manager.mark_completed(task_id, md_path, pdf_path)
        history_manager.update_task(task_id, {
            'status': 'completed', 
            'progress': 100, 
            'output_path': md_path,
            'pdf_path': pdf_path,
            'current_step': '分析完成'
        })
        
        # 记录任务完成
        duration_ms = int((time.time() - start_time) * 1000)
        exec_logger.log_task_complete(task_id, duration_ms, md_path, pdf_path)
        
        print(f"✅ 任务完成: {task_id}")
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"❌ 任务失败: {task_id}, 错误: {str(e)}")
        # 记录错误日志
        exec_logger.log_error(ComponentType.ANALYSIS, task_id, str(e))
        exec_logger.log_task_failed(task_id, str(e), duration_ms)
        task_manager.mark_failed(task_id, str(e))
        history_manager.update_task(task_id, {'status': 'failed', 'error_message': str(e)})

@analyze_bp.route('/api/analyze', methods=['POST'])
def start_analysis():
    """启动分析任务"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        user_prompt = data.get('user_prompt', '')
        
        # 验证任务ID
        if not task_id:
            return jsonify({'success': False, 'error': '缺少任务ID'}), 400
        
        # 获取任务
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        
        # 检查任务状态
        if task['status'] not in ['pending', 'uploaded']:
            return jsonify({'success': False, 'error': f'任务状态不允许分析: {task["status"]}'}), 400
        
        # 更新任务状态
        task_manager.update_task(task_id, 
                                status='analyzing',
                                progress=0,
                                current_step='初始化分析')
        history_manager.update_task(task_id, {'status': 'analyzing', 'progress': 0, 'current_step': '初始化分析'})
        
        # 启动后台分析线程
        thread = threading.Thread(target=analyze_task, args=(task_id, user_prompt))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
