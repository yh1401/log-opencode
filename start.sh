#!/bin/bash
# log-opencode 一键启动脚本
# 启动顺序：Flask Web 后端（使用远程模型）
# 用法: ./start.sh [启动选项]
#   --stop         停止所有服务

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PID_DIR="$PROJECT_DIR/.pids"
LOG_DIR="$PROJECT_DIR/logs/startup"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

mkdir -p "$PID_DIR" "$LOG_DIR"

# ===== 停止服务 =====
stop_all() {
    echo -e "${YELLOW}🛑 正在停止所有服务...${NC}"

    if [ -f "$PID_DIR/web.pid" ]; then
        PID=$(cat "$PID_DIR/web.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            echo -e "  ${RED}Web 后端已停止 (PID: $PID)${NC}"
        fi
        rm -f "$PID_DIR/web.pid"
    fi

    echo -e "${GREEN}✅ 所有服务已停止${NC}"
    exit 0
}

# ===== 检查依赖 =====
check_deps() {
    echo -e "${BLUE}🔍 检查依赖...${NC}"

    # 检查 Python venv
    if [ -d "$VENV_DIR" ]; then
        echo -e "  ${GREEN}✅${NC} Python venv: $VENV_DIR"
    else
        echo -e "  ${RED}❌${NC} Python venv 不存在: $VENV_DIR"
        echo -e "  ${YELLOW}  正在创建虚拟环境...${NC}"
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
        "$VENV_DIR/bin/pip" install flask flask-cors reportlab
    fi

    echo ""
}

# ===== 启动 Web 后端 =====
start_web() {
    echo -e "${BLUE}🌐 启动 Flask Web 后端...${NC}"

    # 检查端口占用并查杀
    if lsof -i :5001 &>/dev/null; then
        echo -e "  ${YELLOW}⚠️${NC} 端口 5001 被占用，查杀旧进程..."
        OLD_PID=$(lsof -t -i :5001)
        if [ -n "$OLD_PID" ]; then
            kill -9 "$OLD_PID" 2>/dev/null
            echo -e "  ${YELLOW}⏳${NC} 等待端口释放..."
            # 等待端口释放（最多 10 秒）
            for j in $(seq 1 10); do
                if ! lsof -i :5001 &>/dev/null; then
                    echo -e "  ${GREEN}✅${NC} 端口已释放"
                    break
                fi
                sleep 1
            done
        fi
    fi

    # 如果端口仍被占用，报错退出
    if lsof -i :5001 &>/dev/null; then
        echo -e "  ${RED}❌${NC} 端口 5001 仍被占用，无法启动 Web 后端"
        echo -e "  ${YELLOW}  请手动查杀: lsof -ti :5001 | xargs kill -9${NC}"
        return 1
    fi

    # 启动 Flask
    cd "$PROJECT_DIR"
    PYTHONPATH="$PROJECT_DIR:$PYTHONPATH" \
    "$VENV_DIR/bin/python3" "$PROJECT_DIR/app.py" \
        > "$LOG_DIR/web.log" 2>&1 &
    WEB_PID=$!
    echo $WEB_PID > "$PID_DIR/web.pid"

    # 等待 Web 就绪
    echo -e "  ${YELLOW}⏳${NC} 等待 Web 后端就绪..."
    for i in $(seq 1 15); do
        if curl -s http://localhost:5001 &>/dev/null; then
            echo -e "  ${GREEN}✅${NC} Web 后端就绪 (PID: $WEB_PID)"
            return 0
        fi
        sleep 1
    done
    echo -e "  ${YELLOW}⚠️${NC} Web 后端启动可能未完成，请检查日志: $LOG_DIR/web.log"
}

# ===== 主流程 =====
main() {
    echo ""
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}  📊 日志分析工具 - 一键启动  ${NC}"
    echo -e "${PURPLE}================================${NC}"
    echo ""

    case "${1:-start}" in
        --stop|stop)
            stop_all
            ;;
        start|--start|"")
            check_deps
            start_web
            ;;
        *)
            echo "用法: $0 [start|--stop]"
            echo ""
            echo "选项:"
            echo "  (无参数)  启动 Web 后端（使用远程模型）"
            echo "  --stop      停止所有服务"
            exit 1
            ;;
    esac

    # 启动后监控日志
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}  ✅ 启动完成！                ${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "  🌐 访问地址: ${BLUE}http://localhost:5001${NC}"
    echo ""
    echo -e "  日志文件:"
    echo -e "    Web:    $LOG_DIR/web.log"
    echo ""
    echo -e "  停止服务: ${YELLOW}$0 --stop${NC}"
    echo ""
    echo -e "${PURPLE}📋 实时日志 (Ctrl+C 退出监控，服务继续运行):${NC}"
    echo -e "${PURPLE}────────────────────────────────${NC}"
    tail -f "$LOG_DIR/web.log" 2>/dev/null || cat "$LOG_DIR/web.log"
}

# 执行主流程
main "$@"