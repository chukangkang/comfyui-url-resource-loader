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
        
        print("\n" + "="*80)
        print("[ClearMemoryDeep] 🧹 开始深度内存清理...")
        print("="*80)
        
        # 记录清理前的内存状态
        start_gpu = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_reserved = torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0
        
        proc = psutil.Process(os.getpid())
        start_cpu = proc.memory_info().rss / 1024**3
        
        print(f"[ClearMemoryDeep] 📊 清理前状态:")
        if torch.cuda.is_available():
            print(f"[ClearMemoryDeep]    GPU 已分配: {start_gpu:.2f}G")
            print(f"[ClearMemoryDeep]    GPU 已保留: {start_gpu_reserved:.2f}G")
        print(f"[ClearMemoryDeep]    CPU 内存: {start_cpu:.2f}G")
        print()

        # 步骤1：清空ComfyUI全局模型缓存，彻底销毁引用
        print("[ClearMemoryDeep] 🔹 步骤1: 清空ComfyUI全局模型缓存")
        if hasattr(mm, 'model_management') and hasattr(mm.model_management, 'loaded_models'):
            model_count = len(mm.model_management.loaded_models)
            if model_count > 0:
                print(f"[ClearMemoryDeep]    发现 {model_count} 个已加载模型")
                for idx, model_name in enumerate(list(mm.model_management.loaded_models.keys()), 1):
                    model = mm.model_management.loaded_models.pop(model_name)
                    print(f"[ClearMemoryDeep]    正在清理模型 {idx}/{model_count}: {model_name}")
                    self._destroy_model(model)
                print(f"[ClearMemoryDeep]    ✅ 已清空 {model_count} 个全局模型缓存")
            else:
                print("[ClearMemoryDeep]    ℹ️  未发现已加载模型")
        else:
            print("[ClearMemoryDeep]    ℹ️  未找到 model_management.loaded_models")

        # 步骤2：清理model_management附属缓存
        print("\n[ClearMemoryDeep] 🔹 步骤2: 清理model_management附属缓存")
        cleared_attrs = []
        for attr in ['gpu_memory', 'cpu_memory', 'model_dtypes']:
            if hasattr(mm.model_management, attr):
                cache = getattr(mm.model_management, attr)
                cache_size = len(cache) if hasattr(cache, '__len__') else 'N/A'
                cache.clear()
                cleared_attrs.append(f"{attr} ({cache_size} 项)")
        if cleared_attrs:
            print(f"[ClearMemoryDeep]    ✅ 已清空: {', '.join(cleared_attrs)}")
        else:
            print("[ClearMemoryDeep]    ℹ️  未找到附属缓存")

        # 步骤3：全局遍历销毁残留CUDA/CPU张量（第三方节点缓存也清理）
        print("\n[ClearMemoryDeep] 🔹 步骤3: 销毁全局残留张量")
        tensor_count = self._destroy_globals_tensors()
        if tensor_count > 0:
            print(f"[ClearMemoryDeep]    ✅ 已销毁 {tensor_count} 个全局残留张量")
        else:
            print("[ClearMemoryDeep]    ℹ️  未发现残留张量")

        # 步骤4：Python深度GC回收（处理循环引用，容器内关键）
        print("\n[ClearMemoryDeep] 🔹 步骤4: Python GC深度回收")
        collected_1 = gc.collect()
        collected_2 = gc.collect()
        print(f"[ClearMemoryDeep]    第1轮回收: {collected_1} 个对象")
        print(f"[ClearMemoryDeep]    第2轮回收: {collected_2} 个对象")
        gc.set_threshold(0)
        gc.set_threshold(700, 10, 10)
        print(f"[ClearMemoryDeep]    ✅ GC阈值已重置: (700, 10, 10)")

        # 步骤5：CUDA全维度缓存清理（无权限也生效，核心步骤）
        print("\n[ClearMemoryDeep] 🔹 步骤5: CUDA缓存清理")
        if torch.cuda.is_available():
            print("[ClearMemoryDeep]    正在执行 empty_cache()...")
            torch.cuda.empty_cache()
            print("[ClearMemoryDeep]    正在执行 ipc_collect()...")
            torch.cuda.ipc_collect()
            print("[ClearMemoryDeep]    正在执行 synchronize()...")
            torch.cuda.synchronize()
            print("[ClearMemoryDeep]    正在执行 memory.empty_cache()...")
            torch.cuda.memory.empty_cache()
            
            # 计算GPU释放量
            end_gpu = torch.cuda.memory_allocated() / 1024**3
            end_gpu_reserved = torch.cuda.memory_reserved() / 1024**3
            freed_gpu = start_gpu - end_gpu
            freed_reserved = start_gpu_reserved - end_gpu_reserved
            
            print(f"[ClearMemoryDeep]    ✅ GPU已分配内存: {start_gpu:.2f}G → {end_gpu:.2f}G (释放 {freed_gpu:.2f}G)")
            print(f"[ClearMemoryDeep]    ✅ GPU已保留内存: {start_gpu_reserved:.2f}G → {end_gpu_reserved:.2f}G (释放 {freed_reserved:.2f}G)")
        else:
            print("[ClearMemoryDeep]    ℹ️  CUDA不可用，跳过GPU清理")

        # 步骤6：打印容器内内存状态（仅展示，无操作）
        print("\n[ClearMemoryDeep] 🔹 步骤6: 系统内存状态")
        self._print_container_memory_status()
        
        # 计算总体释放量
        end_cpu = proc.memory_info().rss / 1024**3
        freed_cpu = start_cpu - end_cpu
        
        print("\n" + "="*80)
        print("[ClearMemoryDeep] ✅ 深度内存清理完成！")
        print("="*80)
        print(f"[ClearMemoryDeep] 📊 清理效果:")
        print(f"[ClearMemoryDeep]    CPU内存: {start_cpu:.2f}G → {end_cpu:.2f}G (释放 {freed_cpu:.2f}G)")
        if torch.cuda.is_available():
            print(f"[ClearMemoryDeep]    GPU内存: {start_gpu:.2f}G → {end_gpu:.2f}G (释放 {freed_gpu:.2f}G)")
        print("="*80 + "\n")
        
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
        mem_info = proc.memory_info()
        mem_rss = mem_info.rss / 1024**3
        mem_vms = mem_info.vms / 1024**3
        
        sys_mem = psutil.virtual_memory()
        sys_mem_total = sys_mem.total / 1024**3
        sys_mem_used = sys_mem.used / 1024**3
        sys_mem_percent = sys_mem.percent
        
        sys_swap = psutil.swap_memory()
        sys_swap_total = sys_swap.total / 1024**3
        sys_swap_used = sys_swap.used / 1024**3
        sys_swap_percent = sys_swap.percent
        
        print(f"[ClearMemoryDeep]    进程内存 (RSS): {mem_rss:.2f}G")
        print(f"[ClearMemoryDeep]    虚拟内存 (VMS): {mem_vms:.2f}G")
        print(f"[ClearMemoryDeep]    系统内存: {sys_mem_used:.2f}G / {sys_mem_total:.2f}G ({sys_mem_percent:.1f}%)")
        print(f"[ClearMemoryDeep]    Swap内存: {sys_swap_used:.2f}G / {sys_swap_total:.2f}G ({sys_swap_percent:.1f}%)")

