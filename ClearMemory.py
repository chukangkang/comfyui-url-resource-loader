import torch
import gc


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
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "clear_memory"
    CATEGORY = "utils"
    
    def clear_memory(self, trigger, clear_cpu_memory=True, clear_gpu_memory=True):
        """
        释放内存和显存
        
        Args:
            trigger: 触发器（通常为True）
            clear_cpu_memory: 是否清理CPU内存
            clear_gpu_memory: 是否清理GPU显存
            
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
            
            status = " | ".join(messages)
            return (status,)
            
        except Exception as e:
            error_msg = f"✗ 内存清理失败: {str(e)}"
            return (error_msg,)


# 节点映射和显示名称
NODE_CLASS_MAPPINGS = {
    "ClearMemory": ClearMemory,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ClearMemory": "🔄 Clear Memory & VRAM",
}
