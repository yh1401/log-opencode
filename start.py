#!/usr/bin/env python3
"""
日志分析报告系统启动脚本
"""

import os
import signal
import subprocess
import sys

def check_port(port):
    """检查端口是否被占用"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    except Exception:
        return False

def kill_process_on_port(port):
    """杀死占用指定端口的进程"""
    try:
        # Linux/Mac
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True
        )
        pids = result.stdout.strip().split('\n')
        pids = [pid for pid in pids if pid]
        
        if pids:
            print(f"发现 {len(pids)} 个进程占用端口 {port}")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"已终止进程 {pid}")
                except Exception as e:
                    print(f"终止进程 {pid} 失败: {e}")
            return True
        return False
    except Exception as e:
        print(f"检查端口失败: {e}")
        return False

def main():
    """主函数"""
    port = 5001
    
    # 检查端口是否被占用
    if check_port(port):
        print(f"端口 {port} 已被占用，尝试释放...")
        if kill_process_on_port(port):
            # 等待进程终止
            import time
            time.sleep(2)
        
        # 再次检查
        if check_port(port):
            print(f"端口 {port} 仍然被占用，请手动释放后重试")
            sys.exit(1)
    
    # 设置环境变量
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # 启动应用
    print(f"🚀 启动日志分析报告系统，端口: {port}")
    subprocess.run(['python', '-m', 'flask', 'run', '--host', '0.0.0.0', '--port', str(port)])

if __name__ == '__main__':
    main()