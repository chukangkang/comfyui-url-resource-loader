import torch
import gc
import multiprocessing
import psutil
import os
import sys
import subprocess


class ClearMemory:
    """清理系统内存和GPU显存的ComfyUI节点"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trigger": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "clear_cpu_memory": ("BOOLEAN", {"default": True}),
                "clear_gpu_memory": ("BOOLEAN", {"default": True}),
                "clear_subprocess_memory": ("BOOLEAN", {"default": True}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "clear_memory"
    CATEGORY = "utils"
    
    def clear_memory(self, trigger, clear_cpu_memory=True, clear_gpu_memory=True, clear_subprocess_memory=True):
        """
        释放内存和显存
        
        Args:
            trigger: 触发器（通常为True）
            clear_cpu_memory: 是否清理CPU内存
            clear_gpu_memory: 是否清理GPU显存
            clear_subprocess_memory: 是否清理子进程共享内存
            
        Returns:
            tuple: (状态信息字符串,)
        """
        messages = []
        
        try:
            if clear_cpu_memory:
                # 清理CPU内存
                gc.collect()
                messages.append("✓ CPU内存已清理")
            
            if clear_gpu_memory:
                # 清理GPU显存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    messages.append("✓ GPU显存已清理")
                else:
                    messages.append("⚠ 未检测到CUDA设备，跳过GPU清理")
            
            if clear_subprocess_memory:
                # 清理子进程共享内存
                self._clear_subprocess_shared_memory()
                messages.append("✓ 子进程共享内存已清理")
            
            status = " | ".join(messages)
            return (status,)
            
        except Exception as e:
            error_msg = f"✗ 内存清理失败: {str(e)}"
            return (error_msg,)
    
    def _clear_subprocess_shared_memory(self):
        """清理所有ComfyUI共享内存（包括多进程共享内存、POSIX共享内存、信号量等）"""
        try:
            current_process = os.getpid()
            
            # 获取当前进程
            try:
                parent = psutil.Process(current_process)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return
            
            # 1. 清理子进程内存
            try:
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        if hasattr(child, 'memory_info'):
                            gc.collect()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ProcessLookupError):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            # 2. 清理multiprocessing的共享内存管理器
            try:
                multiprocessing.Manager().shutdown()
            except Exception:
                pass
            
            # 3. 清理所有POSIX共享内存和信号量（Linux系统）
            if sys.platform in ['linux', 'linux2']:
                try:
                    # 清理所有孤立的共享内存段
                    subprocess.run(['ipcrm', '-a'], capture_output=True, timeout=5)
                except Exception:
                    pass
                
                try:
                    # 查找并清理ComfyUI相关的IPC资源
                    result = subprocess.run(['ipcs', '-m'], capture_output=True, text=True, timeout=5)
                    for line in result.stdout.split('\n'):
                        if 'python' in line.lower() or 'comfyui' in line.lower():
                            try:
                                parts = line.split()
                                if len(parts) > 1:
                                    shmid = parts[1]
                                    subprocess.run(['ipcrm', '-m', shmid], capture_output=True, timeout=2)
                            except Exception:
                                pass
                except Exception:
                    pass
            
            # 4. 强制垃圾回收
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
        except Exception:
            # 忽略任何清理失败，不影响主流程
            pass


# 节点映射和显示名称
NODE_CLASS_MAPPINGS = {
    "ClearMemory": ClearMemory,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ClearMemory": "🔄 Clear Memory & VRAM",
}
