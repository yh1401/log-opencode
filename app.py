#!/usr/bin/env python3
"""
日志分析报告系统 - 主应用入口
"""

from flask import Flask, render_template
from config.settings import settings
from app.api.upload import upload_bp
from app.api.analyze import analyze_bp
from app.api.progress import progress_bp
from app.api.download import download_bp
from app.api.history import history_bp

def create_app():
    """创建Flask应用"""
    import os
    template_dir = os.path.join(os.path.dirname(__file__), 'web', 'templates')
    static_dir = os.path.join(os.path.dirname(__file__), 'web', 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # 注册蓝图
    app.register_blueprint(upload_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(history_bp)
    
    # 配置上传大小限制
    app.config['MAX_CONTENT_LENGTH'] = settings.get('max_file_size_mb', 200) * 1024 * 1024
    
    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    server_config = settings.get_server_config()
    
    app.run(
        host='0.0.0.0',
        port=server_config['port'],
        debug=server_config.get('debug', False)
    )
