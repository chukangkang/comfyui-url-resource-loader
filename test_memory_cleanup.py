#!/usr/bin/env python3
"""
内存清理效果测试脚本
用于验证深度内存清洗节点的效果
"""

import os
import sys

# 在导入其他模块前设置环境变量
os.environ['KORNIA_INSTALL_MODE'] = 'skip'
os.environ['KORNIA_LAZY_INSTALL'] = '0'
os.environ['KORNIA_CHECK_DEPS'] = '0'

import psutil
import torch
import gc

def get_memory_info():
    """获取当前内存使用信息"""
    proc = psutil.Process(os.getpid())
    cpu_mem = proc.memory_info().rss / 1024**3
    
    gpu_mem = 0
    gpu_reserved = 0
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.memory_allocated() / 1024**3
        gpu_reserved = torch.cuda.memory_reserved() / 1024**3
    
    # 容器内存（如果在容器中）
    container_mem = None
    try:
        with open('/sys/fs/cgroup/memory.current', 'r') as f:
            container_mem = int(f.read().strip()) / 1024**3
    except:
        try:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                container_mem = int(f.read().strip()) / 1024**3
        except:
            pass
    
    return {
        'cpu': cpu_mem,
        'gpu_allocated': gpu_mem,
        'gpu_reserved': gpu_reserved,
        'container': container_mem
    }

def print_memory_info(label=""):
    """打印内存信息"""
    info = get_memory_info()
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    print(f"CPU 内存使用: {info['cpu']:.2f} GB")
    if torch.cuda.is_available():
        print(f"GPU 已分配: {info['gpu_allocated']:.2f} GB")
        print(f"GPU 预留: {info['gpu_reserved']:.2f} GB")
    if info['container']:
        print(f"容器内存使用: {info['container']:.2f} GB")
    print(f"{'='*60}\n")

def test_memory_cleanup():
    """测试内存清理"""
    print("🚀 开始内存清理测试...")
    
    # 1. 清理前
    print_memory_info("清理前")
    
    # 2. 执行清理
    print("执行深度内存清理...")
    try:
        from ClearMemoryDeep import ClearMemoryDeepNode
        node = ClearMemoryDeepNode()
        result = node.clear_memory_deep()
        print(f"\n清理结果: {result[0]}")
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return
    
    # 3. 清理后
    print_memory_info("清理后")
    
    print("✅ 测试完成！")

if __name__ == "__main__":
    test_memory_cleanup()
