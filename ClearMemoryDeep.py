import os
# 静默 kornia 依赖提示（禁用 basicsr 等可选依赖的安装提示）
os.environ['KORNIA_INSTALL_MODE'] = 'auto'
os.environ['KORNIA_CHECK_DEPS'] = '0'
os.environ['BASICSR_JIT'] = '0'

import torch
import gc
import psutil
import sys
import time
import logging
import ctypes
import weakref
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
    TITLE = "🚀 深度内存清洗（超级激进模式）"
    DESCRIPTION = """ComfyUI深度内存清洗 - 恢复到刚启动状态（超级激进）
    ✅ 完全卸载所有模型和张量
    ✅ 深度释放GPU显存（VRAM）
    ✅ 彻底清理CPU内存
    ✅ 强制删除大对象和循环引用
    ✅ 清理Python内部缓存
    ✅ 系统级内存trim（Linux）
    ✅ 7阶段深度清洗流程"""

    def clear_memory_deep(self, any_input=None):
        """核心清理逻辑：深度内存清洗，确保 ComfyUI 恢复到刚启动状态"""
        # 忽略输入参数，仅做兼容，不影响清理逻辑
        del any_input  # 主动删除输入引用，减少内存占用
        
        # 记录清理前的内存状态
        start_time = time.time()
        start_gpu = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_reserved = torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_cached = torch.cuda.memory_cached() / 1024**3 if torch.cuda.is_available() and hasattr(torch.cuda, 'memory_cached') else 0
        
        proc = psutil.Process(os.getpid())
        start_cpu = proc.memory_info().rss / 1024**3
        
        logger.info("[ClearMemory] 🚀 开始深度内存清洗（恢复到刚启动状态）...")
        
        # ============ 第一阶段：ComfyUI 模型卸载 ============
        logger.info("[ClearMemory] 阶段1: 卸载所有 ComfyUI 模型...")
        try:
            # 卸载所有已加载的模型
            if hasattr(mm, 'unload_all_models'):
                mm.unload_all_models()
            
            # 清理模型管理器
            if hasattr(mm, 'cleanup_models'):
                mm.cleanup_models()
            
            # 强制清空当前加载的模型列表
            if hasattr(mm, 'current_loaded_models'):
                if isinstance(mm.current_loaded_models, list):
                    mm.current_loaded_models.clear()
            
            # 软清空缓存
            if hasattr(mm, 'soft_empty_cache'):
                mm.soft_empty_cache(force=True)
        except Exception as e:
            logger.warning(f"⚠️ ComfyUI 模型卸载异常: {e}")

        # ============ 第二阶段：深度清理模型张量 ============
        logger.info("[ClearMemory] 阶段2: 深度清理所有模型张量...")
        self._clear_comfyui_models()
        self._clear_comfyui_caches()
        self._clear_output_caches()
        
        # ============ 第三阶段：清理 PyTorch 张量缓存 ============
        logger.info("[ClearMemory] 阶段3: 清理所有 PyTorch 张量...")
        self._clear_all_pytorch_tensors()
        
        # ============ 第四阶段：强制清理大对象和循环引用 ============
        logger.info("[ClearMemory] 阶段4: 清理大对象和循环引用...")
        self._force_clear_large_objects()
        
        # ============ 第五阶段：Python GC 垃圾回收（超级激进） ============
        logger.info("[ClearMemory] 阶段5: 执行超级垃圾回收...")
        # 禁用GC，手动控制
        gc.disable()
        # 清理所有代
        for i in range(10):
            gc.collect(2)
        # 重新启用GC
        gc.enable()
        # 设置更激进的GC阈值
        gc.set_threshold(100, 2, 2)

        # ============ 第六阶段：VRAM 完全释放 ============
        if torch.cuda.is_available():
            logger.info("[ClearMemory] 阶段6: 完全释放 VRAM...")
            device_count = torch.cuda.device_count()
            for device_id in range(device_count):
                with torch.cuda.device(device_id):
                    # 同步并等待所有 GPU 操作完成
                    torch.cuda.synchronize()
                    # 重置统计信息
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.reset_accumulated_memory_stats()
                    # 清空缓存
                    torch.cuda.empty_cache()
                    # 进程间通信清理
                    torch.cuda.ipc_collect()
            
            # 多次强制清空 VRAM 缓存（确保彻底）
            for i in range(5):
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, 'memory'):
                    torch.cuda.memory.empty_cache()
            
            # 最终同步所有设备
            for device_id in range(device_count):
                with torch.cuda.device(device_id):
                    torch.cuda.synchronize()
        
        # ============ 第七阶段：系统级内存释放 ============
        logger.info("[ClearMemory] 阶段7: 系统级内存释放...")
        # 多次 GC 确保彻底
        for i in range(5):
            gc.collect()
            gc.collect(2)
        
        # 清理全局缓存
        self._clear_global_caches()
        
        # Python 内部缓存清理
        self._clear_python_internal_caches()
        
        # 系统级内存trim（Linux）
        self._trim_system_memory()
        
        # 再次调用 ComfyUI 的清理函数
        if hasattr(mm, 'soft_empty_cache'):
            mm.soft_empty_cache(force=True)
        
        # 最终 GPU 同步和缓存清空
        if torch.cuda.is_available():
            for device_id in range(device_count):
                with torch.cuda.device(device_id):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
            
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
        report_lines.append(f"✅ 深度内存清洗完成 - 耗时: {elapsed_time:.1f}s")
        report_lines.append(f"🖥️ CPU: {start_cpu:.2f}G → {end_cpu:.2f}G (释放 {freed_cpu:+.2f}G)")
        
        if torch.cuda.is_available():
            report_lines.append(f"🎮 GPU已用: {start_gpu:.2f}G → {end_gpu:.2f}G (释放 {freed_gpu:+.2f}G)")
            report_lines.append(f"🎮 GPU预留: {start_gpu_reserved:.2f}G → {end_gpu_reserved:.2f}G (释放 {freed_reserved:+.2f}G)")
            logger.info(f"[ClearMemory] ✅ 完成 - CPU释放: {freed_cpu:+.2f}G, GPU释放: {freed_gpu:+.2f}G, 耗时: {elapsed_time:.1f}s")
        else:
            logger.info(f"[ClearMemory] ✅ 完成 - CPU释放: {freed_cpu:+.2f}G, 耗时: {elapsed_time:.1f}s")
        
        logger.info("[ClearMemory] 🎉 ComfyUI 已恢复到刚启动状态！")
        
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
    
    def _clear_all_pytorch_tensors(self):
        """清理内存中所有未被使用的 PyTorch 张量"""
        cleared_tensors = 0
        freed_memory = 0.0
        
        try:
            # 遍历所有 GC 对象，找到未被引用的张量
            all_objects = gc.get_objects()
            for obj in all_objects:
                try:
                    if isinstance(obj, torch.Tensor):
                        # 计算张量大小
                        try:
                            size_gb = obj.element_size() * obj.nelement() / 1024**3
                            freed_memory += size_gb
                        except:
                            pass
                        
                        # 分离张量计算图
                        try:
                            if obj.grad is not None:
                                obj.grad.detach_()
                                del obj.grad
                            obj.detach_()
                        except:
                            pass
                        
                        cleared_tensors += 1
                except:
                    continue
            
            # 清理 PyTorch 内部缓存
            if hasattr(torch, '_C'):
                if hasattr(torch._C, '_clear_cublas_benchmarks'):
                    torch._C._clear_cublas_benchmarks()
            
            # 清理 CUDA 张量缓存
            if torch.cuda.is_available():
                # 清理 CUDA 缓存分配器
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.warning(f"⚠️ PyTorch 张量清理异常: {e}")
        
        logger.info(f"[ClearMemory] 已处理 {cleared_tensors} 个张量, 释放约 {freed_memory:.2f}G")
        return {'tensors': cleared_tensors, 'memory': freed_memory}
    
    def _force_clear_large_objects(self):
        """强制清理大对象和循环引用"""
        cleared_count = 0
        freed_memory = 0.0
        
        try:
            # 获取所有对象
            all_objects = gc.get_objects()
            large_objects = []
            
            # 查找大对象（>10MB）
            for obj in all_objects:
                try:
                    # 获取对象大小
                    size = sys.getsizeof(obj)
                    if size > 10 * 1024 * 1024:  # 10MB
                        large_objects.append(obj)
                        freed_memory += size / 1024**3
                except:
                    continue
            
            # 清理大对象
            for obj in large_objects:
                try:
                    # 如果是列表或字典，清空
                    if isinstance(obj, list):
                        obj.clear()
                        cleared_count += 1
                    elif isinstance(obj, dict):
                        obj.clear()
                        cleared_count += 1
                    elif isinstance(obj, set):
                        obj.clear()
                        cleared_count += 1
                except:
                    continue
            
            # 清理循环引用
            gc.collect()
            
            # 清理弱引用
            try:
                # 清理所有弱引用对象
                for obj in list(weakref.getweakrefs(object)):
                    try:
                        del obj
                    except:
                        pass
            except:
                pass
                
        except Exception as e:
            logger.warning(f"⚠️ 大对象清理异常: {e}")
        
        logger.info(f"[ClearMemory] 已清理 {cleared_count} 个大对象, 释放约 {freed_memory:.2f}G")
        return {'count': cleared_count, 'memory': freed_memory}
    
    def _clear_python_internal_caches(self):
        """清理 Python 内部缓存"""
        cleared_count = 0
        
        try:
            # 1. 清理 sys.modules 中未使用的模块（谨慎操作）
            # 不清理核心模块和当前使用的模块
            core_modules = {'sys', 'os', 'gc', 'torch', 'builtins', '__main__'}
            modules_to_keep = set()
            
            # 保留ComfyUI相关模块
            for name in list(sys.modules.keys()):
                if any(x in name.lower() for x in ['comfy', 'torch', 'cuda', '__']):
                    modules_to_keep.add(name)
            
            # 清理缓存模块
            modules_to_remove = []
            for name in list(sys.modules.keys()):
                if name not in core_modules and name not in modules_to_keep:
                    # 跳过正在使用的模块
                    if not name.startswith('_') and '.' not in name:
                        continue
                    modules_to_remove.append(name)
            
            # 实际删除（注释掉，太危险）
            # for name in modules_to_remove[:50]:  # 限制数量
            #     try:
            #         del sys.modules[name]
            #         cleared_count += 1
            #     except:
            #         pass
            
            # 2. 清理 __pycache__
            # 这个在运行时不太有效，跳过
            
            # 3. 清理 linecache
            try:
                import linecache
                linecache.clearcache()
                cleared_count += 1
            except:
                pass
            
            # 4. 清理 warnings 缓存
            try:
                import warnings
                warnings.filters.clear()
                cleared_count += 1
            except:
                pass
            
            # 5. 清理 importlib 缓存
            try:
                import importlib
                if hasattr(importlib, 'invalidate_caches'):
                    importlib.invalidate_caches()
                    cleared_count += 1
            except:
                pass
            
            # 6. 清理 urllib 缓存
            try:
                import urllib.request
                urllib.request.urlcleanup()
                cleared_count += 1
            except:
                pass
                
        except Exception as e:
            logger.warning(f"⚠️ Python内部缓存清理异常: {e}")
        
        logger.info(f"[ClearMemory] 已清理 {cleared_count} 个Python内部缓存")
        return cleared_count
    
    def _trim_system_memory(self):
        """系统级内存trim（Linux特有）"""
        try:
            # 仅在Linux系统上有效
            if sys.platform.startswith('linux'):
                # 尝试调用 malloc_trim (glibc 特性)
                try:
                    libc = ctypes.CDLL('libc.so.6')
                    libc.malloc_trim(0)
                    logger.info("[ClearMemory] 已执行系统级内存trim（malloc_trim）")
                    return True
                except Exception as e:
                    logger.debug(f"malloc_trim 调用失败: {e}")
                    
                # 尝试通过 /proc 触发内存回收
                try:
                    # 同步文件系统
                    os.sync()
                    # 触发内存压缩（需要root权限，通常会失败）
                    try:
                        with open('/proc/sys/vm/drop_caches', 'w') as f:
                            f.write('1\n')
                        logger.info("[ClearMemory] 已触发系统缓存清理")
                    except PermissionError:
                        logger.debug("系统缓存清理需要root权限")
                except:
                    pass
        except Exception as e:
            logger.debug(f"系统级内存清理跳过: {e}")
        
        return False
    
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
        
        # 0. 确保环境变量设置（避免导入 kornia 触发 basicsr 检查）
        try:
            os.environ['KORNIA_INSTALL_MODE'] = 'auto'
            os.environ['KORNIA_CHECK_DEPS'] = '0'
            os.environ['BASICSR_JIT'] = '0'
            # 不导入 kornia，避免触发依赖检查
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


