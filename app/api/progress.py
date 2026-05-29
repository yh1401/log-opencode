"""
进度查询API模块
"""

from flask import Blueprint, jsonify
from app.core.task_manager import task_manager

progress_bp = Blueprint('progress', __name__)

@progress_bp.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """获取任务进度"""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': task.get('status', 'unknown'),
            'progress': task.get('progress', 0),
            'current_step': task.get('current_step', ''),
            'total_chunks': task.get('total_chunks', 0),
            'processed_chunks': task.get('processed_chunks', 0),
            'error': task.get('error', None)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
