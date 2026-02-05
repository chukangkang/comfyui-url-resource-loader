#!/bin/bash
# 宿主机系统缓存清理脚本（需要在宿主机运行，需要 root 权限）
# 用于清理 Linux 系统的 buff/cache，可以影响到容器内存使用

echo "=========================================="
echo "宿主机系统缓存清理工具"
echo "（适用于清理容器占用的 buff/cache）"
echo "=========================================="

# 检查是否有 root 权限
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 错误: 此脚本需要 root 权限运行"
    echo "请在宿主机上使用: sudo bash clear_system_cache.sh"
    exit 1
fi

echo "📊 清理前的内存状态:"
free -h

echo ""
echo "🔄 同步文件系统..."
sync
echo "✅ 文件系统已同步"

echo ""
echo "🧹 清理 pagecache..."
echo 1 > /proc/sys/vm/drop_caches
sleep 1
echo "✅ pagecache 已清理"

echo "🧹 清理 dentries 和 inodes..."
echo 2 > /proc/sys/vm/drop_caches
sleep 1
echo "✅ dentries 和 inodes 已清理"

echo "🧹 清理所有缓存（pagecache + dentries + inodes）..."
echo 3 > /proc/sys/vm/drop_caches
sleep 1
echo "✅ 所有系统缓存已清理"

echo ""
echo "💾 触发内存压缩..."
if [ -f /proc/sys/vm/compact_memory ]; then
    echo 1 > /proc/sys/vm/compact_memory
    echo "✅ 内存压缩已触发"
else
    echo "⚠️ 内存压缩不可用（内核版本较旧）"
fi

echo ""
echo "✅ 系统缓存清理完成！"
echo ""
echo "📊 清理后的内存状态:"
free -h

echo ""
echo "=========================================="
echo "使用说明:"
echo "1. 在 ComfyUI 中执行深度内存清理节点"
echo "2. 在宿主机运行此脚本: sudo bash clear_system_cache.sh"
echo "3. 这样可以最大化降低容器的内存使用率"
echo ""
echo "注意: 此脚本必须在宿主机上运行，容器内无权限"
echo "=========================================="
