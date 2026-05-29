"""
历史记录API模块
"""

from flask import Blueprint, jsonify
from app.storage.history_manager import history_manager

history_bp = Blueprint('history', __name__)

@history_bp.route('/api/history', methods=['GET'])
def get_history():
    """获取历史任务列表"""
    try:
        tasks = history_manager.get_all_tasks()
        return jsonify({
            'success': True,
            'tasks': tasks
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@history_bp.route('/api/history/<task_id>', methods=['GET'])
def get_task_detail(task_id):
    """获取任务详情"""
    try:
        task = history_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        
        return jsonify({
            'success': True,
            'task': task
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@history_bp.route('/api/history/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务记录"""
    try:
        success = history_manager.delete_task(task_id)
        if not success:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
