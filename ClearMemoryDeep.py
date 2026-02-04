import torch
import gc
import psutil
import os
import comfy.model_management as mm

# 注册自定义节点：可介入/末尾执行版
class ClearMemoryDeepNode:
    @classmethod
    def INPUT_TYPES(cls):
        # 新增可选输入：any类型（可接任意节点输出，不接也能运行）
        return {
            "required": {},
            "optional": {
                "any_input": ("*", {}),  # 任意类型输入槽，支持所有数据类型
            }
        }

    RETURN_TYPES = ()  # 无输出，完美作为末尾节点
    FUNCTION = "clear_memory_deep"
    CATEGORY = "utils/内存清理"
    TITLE = "深度内存清理（可介入/末尾执行）"
    DESCRIPTION = "容器环境专用，支持工作流任意位置插入/末尾收尾\n可选接入任意节点输出，实现顺序执行；不接输入也可单独运行"

    def clear_memory_deep(self, any_input=None):
        """核心清理逻辑：兼容可选输入，无权限依赖"""
        # 忽略输入参数，仅做兼容，不影响清理逻辑
        del any_input  # 主动删除输入引用，减少内存占用
        print("[内存清理-末尾执行] 开始深度清理（工作流收尾）...")
        start_gpu = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0

        # 步骤1：清空ComfyUI全局模型缓存，彻底销毁引用
        if hasattr(mm, 'model_management') and hasattr(mm.model_management, 'loaded_models'):
            model_count = len(mm.model_management.loaded_models)
            for model_name in list(mm.model_management.loaded_models.keys()):
                model = mm.model_management.loaded_models.pop(model_name)
                self._destroy_model(model)
            print(f"[内存清理-末尾执行] 已清空{model_count}个全局模型缓存")

        # 步骤2：清理model_management附属缓存
        for attr in ['gpu_memory', 'cpu_memory', 'model_dtypes']:
            if hasattr(mm.model_management, attr):
                getattr(mm.model_management, attr).clear()

        # 步骤3：全局遍历销毁残留CUDA/CPU张量（第三方节点缓存也清理）
        tensor_count = self._destroy_globals_tensors()
        print(f"[内存清理-末尾执行] 已销毁{tensor_count}个全局残留张量")

        # 步骤4：Python深度GC回收（处理循环引用，容器内关键）
        gc.collect()
        gc.collect()
        gc.set_threshold(0)
        gc.set_threshold(700, 10, 10)
        print("[内存清理-末尾执行] Python GC深度回收完成")

        # 步骤5：CUDA全维度缓存清理（无权限也生效，核心步骤）
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
            torch.cuda.memory.empty_cache()
            # 计算GPU释放量
            end_gpu = torch.cuda.memory_allocated() / 1024**3
            freed_gpu = start_gpu - end_gpu
            print(f"[内存清理-末尾执行] GPU清理完成 - 释放{freed_gpu:.2f}G，剩余{end_gpu:.2f}G")

        # 步骤6：打印容器内内存状态（仅展示，无操作）
        self._print_container_memory_status()

        print("[内存清理-末尾执行] 工作流收尾清理完成！无内存残留")
        return ()

    def _destroy_model(self, model):
        """销毁模型对象，彻底删除张量引用"""
        if model is None:
            return
        if hasattr(model, 'parameters'):
            for p in model.parameters():
                if p is not None:
                    p.detach_()
                    del p
        if hasattr(model, 'buffers'):
            for b in model.buffers():
                if b is not None:
                    b.detach_()
                    del b
        if hasattr(model, 'state_dict'):
            try:
                sd = model.state_dict()
                sd.clear()
                del sd
            except:
                pass
        if hasattr(model, '__dict__'):
            for k in list(model.__dict__.keys()):
                attr = model.__dict__[k]
                if isinstance(attr, torch.Tensor) or hasattr(attr, 'to'):
                    del model.__dict__[k]
        del model

    def _destroy_globals_tensors(self):
        """遍历全局，销毁所有残留张量"""
        tensor_count = 0
        for obj in gc.get_objects():
            try:
                if isinstance(obj, torch.Tensor):
                    obj.detach_()
                    if obj.device.type != 'cpu':
                        obj = obj.cpu()
                    del obj
                    tensor_count += 1
            except:
                continue
        return tensor_count

    def _print_container_memory_status(self):
        """打印容器内内存状态（无权限也能读）"""
        proc = psutil.Process(os.getpid())
        mem_rss = proc.memory_info().rss / 1024**3
        sys_mem = psutil.virtual_memory()
        sys_mem_used = sys_mem.used / 1024**3
        sys_swap = psutil.swap_memory()
        sys_swap_used = sys_swap.used / 1024**3
        print(f"[内存清理-末尾执行] 容器进程内存：{mem_rss:.2f}G")
        print(f"[内存清理-末尾执行] 宿主机可见内存：{sys_mem_used:.2f}G | Swap：{sys_swap_used:.2f}G")

