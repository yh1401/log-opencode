"""
上传API模块
"""

from flask import Blueprint, request, jsonify
from app.core.task_manager import task_manager
from app.storage.file_manager import file_manager
from app.storage.history_manager import history_manager
from app.utils.validators import ValidationUtils
from app.core.exec_logger import exec_logger, ComponentType
from pathlib import Path
import os

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        # 检查文件
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 验证文件
        if not ValidationUtils.is_allowed_file(file.filename):
            return jsonify({'success': False, 'error': '不支持的文件格式'}), 400
        
        # 清理文件名
        safe_filename = ValidationUtils.sanitize_filename(file.filename)
        
        # 生成任务ID
        task_id = task_manager.create_task(safe_filename, '')
        
        # 记录文件上传开始
        exec_logger.log_component_start(ComponentType.UPLOAD, task_id)
        
        # 保存上传文件
        upload_path = file_manager.save_uploaded_file(file, safe_filename, task_id)
        
        # 获取文件大小
        file_size = os.path.getsize(upload_path) if os.path.exists(upload_path) else 0
        file_format = Path(file.filename).suffix.lower()
        
        # 记录文件上传详情
        exec_logger.log_file_upload(task_id, safe_filename, file_size, file_format)
        
        # 更新任务信息
        task_manager.update_task(task_id, 
                                upload_path=upload_path,
                                status='uploaded',
                                progress=5,
                                file_size=file_size)
        
        # 保存任务到历史记录
        task_data = {
            'task_id': task_id,
            'filename': safe_filename,
            'status': 'uploaded',
            'progress': 5,
            'upload_path': upload_path,
            'file_size': file_size,
            'file_format': file_format
        }
        history_manager.save_task(task_data)
        
        # 记录上传完成
        exec_logger.log_component_end(ComponentType.UPLOAD, task_id, success=True)
        
        # 获取用户提示词
        user_prompt = request.form.get('user_prompt', '')
        if user_prompt:
            task_manager.update_task(task_id, user_prompt=user_prompt)
            history_manager.update_task(task_id, {'user_prompt': user_prompt})
        
        return jsonify({
            'success': True,
            'task_id': task_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
