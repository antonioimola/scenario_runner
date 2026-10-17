#!/bin/bash

# 自动刷新脚本：监控 .dot 文件变化并自动生成 PNG
# 使用方法: ./auto_refresh.sh [dot_file] [png_file]

DOT_FILE="${1:-xosc_fsm.dot}"
PNG_FILE="${2:-xosc_fsm.png}"

echo "============================================================"
echo "Graphviz 自动刷新工具"
echo "============================================================"
echo "监控文件: $DOT_FILE"
echo "输出文件: $PNG_FILE"
echo "============================================================"
echo ""
echo "提示: 按 Ctrl+C 停止"
echo ""

# 检查 inotifywait 是否可用
if ! command -v inotifywait &> /dev/null; then
    echo "警告: inotifywait 未安装"
    echo "安装方法: sudo apt install inotify-tools"
    echo ""
    echo "使用轮询模式（每1秒检查一次）..."
    
    LAST_MODIFIED=0
    while true; do
        if [ -f "$DOT_FILE" ]; then
            CURRENT_MODIFIED=$(stat -c %Y "$DOT_FILE" 2>/dev/null || echo 0)
            if [ "$CURRENT_MODIFIED" -gt "$LAST_MODIFIED" ]; then
                echo "[$(date +%H:%M:%S)] 检测到文件变化，生成 PNG..."
                dot -Tpng "$DOT_FILE" -o "$PNG_FILE" 2>&1
                if [ $? -eq 0 ]; then
                    echo "✓ 已更新: $PNG_FILE"
                else
                    echo "✗ 生成失败"
                fi
                LAST_MODIFIED=$CURRENT_MODIFIED
            fi
        fi
        sleep 1
    done
else
    # 使用 inotifywait（更高效）
    echo "使用 inotify 模式（实时监控）..."
    echo ""
    
    while inotifywait -e close_write "$DOT_FILE" 2>/dev/null; do
        echo "[$(date +%H:%M:%S)] 检测到文件变化，生成 PNG..."
        dot -Tpng "$DOT_FILE" -o "$PNG_FILE" 2>&1
        if [ $? -eq 0 ]; then
            echo "✓ 已更新: $PNG_FILE"
        else
            echo "✗ 生成失败"
        fi
    done
fi

