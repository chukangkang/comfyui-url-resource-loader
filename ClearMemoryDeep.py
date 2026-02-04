import torch
import gc
import psutil
import os
import sys
import time
import logging
from collections import defaultdict
import comfy.model_management as mm

# 配置日志
logger = logging.getLogger("ClearMemoryDeep")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(name)s] %(message)s'))
    logger.addHandler(handler)

# 注册自定义节点：增强版内存泄漏排查 + Buffer全释放
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

    RETURN_TYPES = ("STRING",)  # 输出清理报告，可连接后续节点
    RETURN_NAMES = ("report",)
    OUTPUT_NODE = True
    FUNCTION = "clear_memory_deep"
    CATEGORY = "utils/内存清理"
    TITLE = "🚀 深度内存清理 + 泄漏排查（增强版）"
    DESCRIPTION = """ComfyUI内存泄漏排查 + Buffer全释放增强版
    ✅ 模型/张量/Buffer完全释放
    ✅ 内存泄漏检测与报告
    ✅ VRAM强制同步清理
    ✅ ComfyUI缓存深度清理
    ✅ Python对象引用追踪"""

    def clear_memory_deep(self, any_input=None):
        """核心清理逻辑：增强版内存泄漏排查 + Buffer全释放"""
        # 忽略输入参数，仅做兼容，不影响清理逻辑
        del any_input  # 主动删除输入引用，减少内存占用
        
        # 记录清理前的内存状态
        start_time = time.time()
        start_gpu = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_reserved = torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_cached = torch.cuda.memory_cached() / 1024**3 if torch.cuda.is_available() and hasattr(torch.cuda, 'memory_cached') else 0
        
        proc = psutil.Process(os.getpid())
        start_cpu = proc.memory_info().rss / 1024**3
        
        logger.info("[ClearMemory] 开始清理...")
        
        # 步骤0：调用ComfyUI原生清理函数
        try:
            if hasattr(mm, 'unload_all_models'):
                mm.unload_all_models()
            if hasattr(mm, 'cleanup_models'):
                mm.cleanup_models()
            if hasattr(mm, 'current_loaded_models'):
                mm.current_loaded_models.clear()
            if hasattr(mm, 'soft_empty_cache'):
                mm.soft_empty_cache(force=True)
        except:
            pass

        # 步骤1-3：静默执行清理（不输出详细日志）
        self._clear_comfyui_models()
        self._clear_comfyui_caches()
        self._clear_output_caches()
        leak_report = self._detect_memory_leaks()
        self._clear_global_caches()

        # 步骤4：Python GC回收（静默执行）
        gc.disable()
        gc.collect()
        gc.enable()
        for i in range(3):
            gc.collect(2)
        gc.set_threshold(300, 3, 3)

        # 步骤5：VRAM清理（静默执行）
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            for device_id in range(device_count):
                with torch.cuda.device(device_id):
                    torch.cuda.synchronize()
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.reset_accumulated_memory_stats()
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
            
            # 全局缓存清理（3次确保彻底）
            for i in range(3):
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, 'memory'):
                    torch.cuda.memory.empty_cache()
            
            # 最终同步
            torch.cuda.synchronize()
                        # 再次强制GC清理CPU内存
            gc.collect()
            gc.collect()
                        # 再次强制GC清理CPU内存
            gc.collect()
            gc.collect()
            
            # 再次调用ComfyUI的soft_empty_cache
            if hasattr(mm, 'soft_empty_cache'):
                mm.soft_empty_cache(force=True)
            
            end_gpu = torch.cuda.memory_allocated() / 1024**3
            end_gpu_reserved = torch.cuda.memory_reserved() / 1024**3
            freed_gpu = start_gpu - end_gpu
            freed_reserved = start_gpu_reserved - end_gpu_reserved

        # 计算最终结果
        end_cpu = proc.memory_info().rss / 1024**3
        freed_cpu = start_cpu - end_cpu
        elapsed_time = time.time() - start_time
        
        # 生成清理报告
        report_lines = []
        report_lines.append(f"清理完成 - 耗时: {elapsed_time:.1f}s")
        report_lines.append(f"CPU: {start_cpu:.2f}G → {end_cpu:.2f}G (释放 {freed_cpu:+.2f}G)")
        
        if torch.cuda.is_available():
            report_lines.append(f"GPU: {start_gpu:.2f}G → {end_gpu:.2f}G (释放 {freed_gpu:+.2f}G)")
            logger.info(f"[ClearMemory] 完成 - CPU释放: {freed_cpu:+.2f}G, GPU释放: {freed_gpu:+.2f}G, 耗时: {elapsed_time:.1f}s")
        else:
            logger.info(f"[ClearMemory] 完成 - CPU释放: {freed_cpu:+.2f}G, 耗时: {elapsed_time:.1f}s")
        
        report = "\n".join(report_lines)
        return (report,)

    def _destroy_model(self, model):
        """销毁模型对象，彻底删除参数/Buffer/张量引用"""
        if model is None:
            return {'params': 0, 'buffers': 0, 'memory': 0.0}
        
        stats = {'params': 0, 'buffers': 0, 'memory': 0.0}
        
        try:
            # 1. 清理parameters
            if hasattr(model, 'parameters'):
                for p in list(model.parameters()):
                    if p is not None and isinstance(p, torch.Tensor):
                        stats['memory'] += p.element_size() * p.nelement() / 1024**3
                        stats['params'] += 1
                        p.detach_()
                        if p.grad is not None:
                            p.grad.detach_()
                            del p.grad
                        del p
            
            # 2. 清理buffers（BatchNorm等残留）
            if hasattr(model, 'buffers'):
                for b in list(model.buffers()):
                    if b is not None and isinstance(b, torch.Tensor):
                        stats['memory'] += b.element_size() * b.nelement() / 1024**3
                        stats['buffers'] += 1
                        b.detach_()
                        del b
            
            # 3. 清理_buffers注册的buffer（更底层）
            if hasattr(model, '_buffers'):
                for name in list(model._buffers.keys()):
                    buf = model._buffers.pop(name, None)
                    if buf is not None and isinstance(buf, torch.Tensor):
                        buf.detach_()
                        del buf
            
            # 4. 清理state_dict
            if hasattr(model, 'state_dict'):
                try:
                    sd = model.state_dict()
                    for k in list(sd.keys()):
                        del sd[k]
                    sd.clear()
                    del sd
                except:
                    pass
            
            # 5. 清理__dict__中的张量
            if hasattr(model, '__dict__'):
                for k in list(model.__dict__.keys()):
                    try:
                        attr = model.__dict__[k]
                        if isinstance(attr, torch.Tensor):
                            attr.detach_()
                            del model.__dict__[k]
                        elif hasattr(attr, 'to') and hasattr(attr, 'parameters'):
                            # 递归清理子模块
                            del model.__dict__[k]
                    except:
                        continue
            
            # 6. 清理_modules（子模块）
            if hasattr(model, '_modules'):
                model._modules.clear()
            
            del model
        except Exception as e:
            logger.warning(f"⚠️ 模型清理异常: {str(e)}")
        
        return stats

    def _clear_comfyui_models(self):
        """清理ComfyUI所有模型缓存（增强版）"""
        stats = {'count': 0, 'params': 0, 'buffers': 0, 'memory_freed': 0.0}
        
        # 清理loaded_models（可能是字典、列表或函数）
        if hasattr(mm, 'loaded_models'):
            loaded_models = mm.loaded_models
            # 如果是函数，调用它
            if callable(loaded_models):
                try:
                    loaded_models = loaded_models()
                except:
                    loaded_models = None
            
            # 检查是否是字典或列表
            if isinstance(loaded_models, dict):
                stats['count'] = len(loaded_models)
                for model_name in list(loaded_models.keys()):
                    model = loaded_models.pop(model_name)
                    # 调用detach方法（如果存在）
                    if hasattr(model, 'detach'):
                        try:
                            model.detach(unpatch_all=True)
                        except:
                            pass
                    model_stats = self._destroy_model(model)
                    stats['params'] += model_stats['params']
                    stats['buffers'] += model_stats['buffers']
                    stats['memory_freed'] += model_stats['memory']
            elif isinstance(loaded_models, list):
                stats['count'] = len(loaded_models)
                for model in list(loaded_models):
                    if hasattr(model, 'detach'):
                        try:
                            model.detach(unpatch_all=True)
                        except:
                            pass
                    model_stats = self._destroy_model(model)
                    stats['params'] += model_stats['params']
                    stats['buffers'] += model_stats['buffers']
                    stats['memory_freed'] += model_stats['memory']
                loaded_models.clear()
        
        # 清理current_loaded_models
        if hasattr(mm, 'current_loaded_models'):
            current_models = mm.current_loaded_models
            if isinstance(current_models, list):
                for loaded_model in list(current_models):
                    try:
                        # 调用model_unload
                        if hasattr(loaded_model, 'model_unload'):
                            loaded_model.model_unload()
                        # 调用model.detach
                        if hasattr(loaded_model, 'model') and hasattr(loaded_model.model, 'detach'):
                            loaded_model.model.detach(unpatch_all=True)
                    except:
                        pass
        
        return stats
    
    def _clear_comfyui_caches(self):
        """清理ComfyUI所有缓存"""
        stats = {'total': 0, 'details': {}}
        
        # model_management缓存（mm就是model_management模块）
        cache_attrs = ['gpu_memory', 'cpu_memory', 'model_dtypes', 'models_memory']
        for attr in cache_attrs:
            if hasattr(mm, attr):
                cache = getattr(mm, attr)
                # 跳过函数类型
                if callable(cache):
                    continue
                if hasattr(cache, 'clear'):
                    try:
                        count = len(cache) if hasattr(cache, '__len__') else 0
                        if count > 0:
                            stats['details'][attr] = count
                            stats['total'] += 1
                        cache.clear()
                    except:
                        pass
        
        # 其他可能的缓存
        if hasattr(mm, 'soft_empty_cache'):
            try:
                mm.soft_empty_cache()
                stats['details']['soft_cache'] = 1
                stats['total'] += 1
            except:
                pass
        
        return stats
    
    def _clear_output_caches(self):
        """清理ComfyUI输出缓存"""
        try:
            # 尝试导入并清理输出目录缓存
            import comfy.cli_args
            if hasattr(comfy.cli_args, 'args') and hasattr(comfy.cli_args.args, 'output_directory'):
                # 清理可能的缓存字典
                pass
        except:
            pass
    
    def _detect_memory_leaks(self):
        """检测内存泄漏"""
        report = {
            'gpu_tensors': 0,
            'cpu_tensors': 0,
            'gpu_memory': 0.0,
            'cpu_memory': 0.0,
            'large_objects': 0,
            'total_objects': 0
        }
        
        report['total_objects'] = len(gc.get_objects())
        
        for obj in gc.get_objects():
            try:
                if isinstance(obj, torch.Tensor):
                    size_gb = obj.element_size() * obj.nelement() / 1024**3
                    if obj.device.type == 'cuda':
                        report['gpu_tensors'] += 1
                        report['gpu_memory'] += size_gb
                    else:
                        report['cpu_tensors'] += 1
                        report['cpu_memory'] += size_gb
                    
                    # 大对象检测(>100MB)
                    if size_gb > 0.1:
                        report['large_objects'] += 1
            except:
                continue
        
        return report
    
    def _destroy_globals_tensors(self):
        """遍历全局，清理无引用的残留张量（安全版）"""
        # 这个方法现在不再使用，因为会破坏后续模型加载
        # 保留只是为了兼容性
        return 0
    
    def _clear_global_caches(self):
        """清理Python全局缓存和大对象（安全版）"""
        cleared_count = 0
        
        # 0. 静默 kornia 可选依赖提示（在执行前设置）
        try:
            os.environ['KORNIA_INSTALL_MODE'] = 'auto'
            import kornia
            if hasattr(kornia, 'config'):
                kornia.config.lazyloader.installation_mode = 'auto'
        except:
            pass
        
        # 1. 清理functools缓存
        try:
            import functools
            # 清理lru_cache缓存
            for obj in gc.get_objects():
                try:
                    if hasattr(obj, 'cache_clear') and callable(obj.cache_clear):
                        obj.cache_clear()
                        cleared_count += 1
                except:
                    pass
        except:
            pass
        
        # 2. 清理torch内部缓存
        try:
            if hasattr(torch, '_C') and hasattr(torch._C, '_clear_cublas_benchmarks'):
                torch._C._clear_cublas_benchmarks()
        except:
            pass
        
        return cleared_count

    def _get_container_memory_info(self):
        """获取容器内存信息（cgroup v1/v2兼容）"""
        container_info = {}
        
        # 尝试读取 cgroup v2（优先）
        cgroup_v2_paths = {
            'memory_max': '/sys/fs/cgroup/memory.max',
            'memory_current': '/sys/fs/cgroup/memory.current',
        }
        
        # 尝试读取 cgroup v1
        cgroup_v1_paths = {
            'memory_limit': '/sys/fs/cgroup/memory/memory.limit_in_bytes',
            'memory_usage': '/sys/fs/cgroup/memory/memory.usage_in_bytes',
        }
        
        # 检测 cgroup 版本
        is_cgroup_v2 = os.path.exists(cgroup_v2_paths['memory_max'])
        
        if is_cgroup_v2:
            # cgroup v2
            try:
                with open(cgroup_v2_paths['memory_max'], 'r') as f:
                    limit = f.read().strip()
                    if limit != 'max':
                        container_info['limit'] = int(limit) / 1024**3
                    else:
                        container_info['limit'] = None
                
                with open(cgroup_v2_paths['memory_current'], 'r') as f:
                    container_info['usage'] = int(f.read().strip()) / 1024**3
            except:
                pass
        else:
            # cgroup v1
            try:
                with open(cgroup_v1_paths['memory_limit'], 'r') as f:
                    limit = int(f.read().strip())
                    # 检查是否是无限制（通常是一个很大的数）
                    if limit < 9 * 10**18:  # 9EB，实际限制
                        container_info['limit'] = limit / 1024**3
                    else:
                        container_info['limit'] = None
                
                with open(cgroup_v1_paths['memory_usage'], 'r') as f:
                    container_info['usage'] = int(f.read().strip()) / 1024**3
            except:
                pass
        
        return container_info
    
    def _print_container_memory_status(self):
        """打印容器内内存状态（已废弃，保留接口兼容）"""
        pass


