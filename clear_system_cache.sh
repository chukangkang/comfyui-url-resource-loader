#!/bin/bash
# 系统缓存清理脚本（需要 root 权限）
# 用于清理 Linux 系统的 buff/cache

echo "=========================================="
echo "系统缓存清理工具"
echo "=========================================="

# 检查是否有 root 权限
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 错误: 此脚本需要 root 权限运行"
    echo "请使用: sudo bash clear_system_cache.sh"
    exit 1
fi

echo "📊 清理前的内存状态:"
free -h

echo ""
echo "🔄 同步文件系统..."
sync

echo "🧹 清理 pagecache (level 1)..."
echo 1 > /proc/sys/vm/drop_caches
sleep 1

echo "🧹 清理 dentries 和 inodes (level 2)..."
echo 2 > /proc/sys/vm/drop_caches
sleep 1

echo "🧹 清理所有缓存 (level 3)..."
echo 3 > /proc/sys/vm/drop_caches
sleep 1

echo "💾 触发内存压缩..."
echo 1 > /proc/sys/vm/compact_memory 2>/dev/null || echo "⚠️ 内存压缩不可用"

echo ""
echo "✅ 系统缓存清理完成！"
echo ""
echo "📊 清理后的内存状态:"
free -h

echo ""
echo "=========================================="
echo "提示: 此脚本可以配合 ComfyUI 的内存清理节点使用"
echo "在 ComfyUI 执行内存清理后，运行此脚本可进一步降低内存使用"
echo "=========================================="
