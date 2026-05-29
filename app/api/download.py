"""
下载API模块
"""

from flask import Blueprint, send_file, jsonify
from app.core.task_manager import task_manager
from app.storage.file_manager import file_manager

download_bp = Blueprint('download', __name__)

@download_bp.route('/api/download/<task_id>/<format>', methods=['GET'])
def download_report(task_id, format):
    """下载分析报告"""
    try:
        # 获取任务信息
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        
        # 检查任务状态
        if task.get('status') != 'completed':
            return jsonify({'success': False, 'error': '任务未完成'}), 400
        
        # 获取报告路径
        if format == 'markdown' or format == 'md':
            report_path = task.get('output_md')
            mimetype = 'text/markdown'
        elif format == 'pdf':
            report_path = task.get('output_pdf')
            mimetype = 'application/pdf'
        else:
            return jsonify({'success': False, 'error': '不支持的格式'}), 400
        
        if not report_path:
            return jsonify({'success': False, 'error': '报告不存在'}), 404
        
        # 发送文件
        return send_file(
            report_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{task_id}_分析报告.{format}"
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
