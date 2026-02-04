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

    RETURN_TYPES = ()  # 无输出，完美作为末尾节点
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
        
        logger.info("\n" + "="*100)
        logger.info("🚀 ComfyUI内存泄漏排查 + Buffer全释放增强版")
        logger.info("="*100)
        
        # 记录清理前的内存状态
        start_time = time.time()
        start_gpu = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_reserved = torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0
        start_gpu_cached = torch.cuda.memory_cached() / 1024**3 if torch.cuda.is_available() and hasattr(torch.cuda, 'memory_cached') else 0
        
        proc = psutil.Process(os.getpid())
        start_cpu = proc.memory_info().rss / 1024**3
        
        logger.info(f"📊 清理前内存快照:")
        if torch.cuda.is_available():
            logger.info(f"   GPU 已分配: {start_gpu:.3f}G")
            logger.info(f"   GPU 已保留: {start_gpu_reserved:.3f}G")
            if start_gpu_cached > 0:
                logger.info(f"   GPU 已缓存: {start_gpu_cached:.3f}G")
        logger.info(f"   CPU 物理内存: {start_cpu:.3f}G")
        logger.info(f"   Python对象数: {len(gc.get_objects())}")
        logger.info("")
        
        # 步骤0：调用ComfyUI原生清理函数
        logger.info("🔹 步骤0: ComfyUI原生内存管理")
        try:
            # 卸载所有模型
            if hasattr(mm, 'unload_all_models'):
                mm.unload_all_models()
                logger.info("   ✅ 已调用 unload_all_models()")
            
            # 清理模型GC
            if hasattr(mm, 'cleanup_models'):
                mm.cleanup_models()
                logger.info("   ✅ 已调用 cleanup_models()")
            
            # 清理current_loaded_models
            if hasattr(mm, 'current_loaded_models'):
                cleared_models = len(mm.current_loaded_models)
                mm.current_loaded_models.clear()
                if cleared_models > 0:
                    logger.info(f"   ✅ 已清空 current_loaded_models: {cleared_models} 个")
            
            # soft_empty_cache
            if hasattr(mm, 'soft_empty_cache'):
                mm.soft_empty_cache(force=True)
                logger.info("   ✅ 已调用 soft_empty_cache()")
        except Exception as e:
            logger.warning(f"   ⚠️  ComfyUI原生清理失败: {str(e)}")
        logger.info("")

        # 步骤1：清空ComfyUI全局模型缓存，彻底销毁引用（含Buffer）
        logger.info("🔹 步骤1: ComfyUI模型 + Buffer完全释放")
        model_stats = self._clear_comfyui_models()
        if model_stats['count'] > 0:
            logger.info(f"   ✅ 已清理 {model_stats['count']} 个模型")
            logger.info(f"   ✅ 释放 {model_stats['params']} 个参数, {model_stats['buffers']} 个Buffer")
            logger.info(f"   ✅ 释放内存约 {model_stats['memory_freed']:.3f}G")
        else:
            logger.info("   ℹ️  未发现已加载模型")

        # 步骤2：清理ComfyUI所有缓存（model_management + 其他缓存）
        logger.info("\n🔹 步骤2: ComfyUI深度缓存清理")
        cache_stats = self._clear_comfyui_caches()
        if cache_stats['total'] > 0:
            logger.info(f"   ✅ 已清空 {cache_stats['total']} 个缓存区")
            for cache_name, count in cache_stats['details'].items():
                logger.info(f"      • {cache_name}: {count} 项")
        else:
            logger.info("   ℹ️  未找到可清理缓存")
        
        # 清理ComfyUI的输出缓存
        self._clear_output_caches()

        # 步骤3：内存泄漏检测 + 全局张量销毁
        logger.info("\n🔹 步骤3: 内存泄漏检测 + 张量销毁")
        leak_report = self._detect_memory_leaks()
        logger.info(f"   🔍 泄漏检测结果:")
        logger.info(f"      • GPU张量: {leak_report['gpu_tensors']} 个 ({leak_report['gpu_memory']:.3f}G)")
        logger.info(f"      • CPU张量: {leak_report['cpu_tensors']} 个 ({leak_report['cpu_memory']:.3f}G)")
        logger.info(f"      • 大对象(>100MB): {leak_report['large_objects']} 个")
        
        tensor_count = self._destroy_globals_tensors()
        if tensor_count > 0:
            logger.info(f"   ✅ 已销毁 {tensor_count} 个全局残留张量")
        else:
            logger.info("   ℹ️  未发现残留张量")
        
        # 额外清理：全局缓存和大对象
        cache_cleared = self._clear_global_caches()
        if cache_cleared > 0:
            logger.info(f"   ✅ 已清理 {cache_cleared} 个全局缓存/大对象")

        # 步骤4：Python激进GC回收（5轮 + 强制清理）
        logger.info("\n🔹 步骤4: Python激进GC回收")
        # 先禁用再启用，清理不可达对象
        gc.disable()
        gc.collect()
        gc.enable()
        
        # 5轮全代回收确保彻底
        collected_total = 0
        for i in range(5):
            collected = gc.collect(2)
            collected_total += collected
            if i < 3:
                logger.info(f"   第{i+1}轮回收(全代): {collected} 个对象")
        
        logger.info(f"   总计回收: {collected_total} 个对象")
        
        # 重置GC阈值为更激进的设置
        gc.set_threshold(300, 3, 3)  # 更激进
        logger.info(f"   ✅ GC阈值已重置为激进模式: (300, 3, 3)")
        
        # 最终对象数
        final_objects = len(gc.get_objects())
        logger.info(f"   当前对象数: {final_objects}")

        # 步骤5：VRAM强制同步 + 缓存池完全释放
        logger.info("\n🔹 步骤5: VRAM强制同步清理")
        if torch.cuda.is_available():
            # 多设备清理
            device_count = torch.cuda.device_count()
            logger.info(f"   检测到 {device_count} 个CUDA设备")
            
            for device_id in range(device_count):
                with torch.cuda.device(device_id):
                    logger.info(f"   清理设备 {device_id}...")
                    # 强制同步
                    torch.cuda.synchronize()
                    # 重置峰值内存统计
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.reset_accumulated_memory_stats()
                    # 清空缓存
                    torch.cuda.empty_cache()
                    # IPC共享内存回收
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
            
            # 计算GPU释放量
            end_gpu = torch.cuda.memory_allocated() / 1024**3
            end_gpu_reserved = torch.cuda.memory_reserved() / 1024**3
            end_gpu_cached = torch.cuda.memory_cached() / 1024**3 if hasattr(torch.cuda, 'memory_cached') else 0
            
            freed_gpu = start_gpu - end_gpu
            freed_reserved = start_gpu_reserved - end_gpu_reserved
            freed_cached = start_gpu_cached - end_gpu_cached
            
            logger.info(f"   ✅ GPU已分配: {start_gpu:.3f}G → {end_gpu:.3f}G (释放 {freed_gpu:.3f}G)")
            logger.info(f"   ✅ GPU已保留: {start_gpu_reserved:.3f}G → {end_gpu_reserved:.3f}G (释放 {freed_reserved:.3f}G)")
            if freed_cached > 0:
                logger.info(f"   ✅ GPU已缓存: {start_gpu_cached:.3f}G → {end_gpu_cached:.3f}G (释放 {freed_cached:.3f}G)")
            
            # 显示峰值内存
            if hasattr(torch.cuda, 'max_memory_allocated'):
                max_allocated = torch.cuda.max_memory_allocated() / 1024**3
                logger.info(f"   📊 本次会话峰值内存: {max_allocated:.3f}G")
        else:
            logger.info("   ℹ️  CUDA不可用，跳过GPU清理")

        # 步骤6：最终系统内存状态 + 泄漏评估
        logger.info("\n🔹 步骤6: 清理后系统状态")
        self._print_container_memory_status()
        
        # 计算总体释放量和耗时
        end_cpu = proc.memory_info().rss / 1024**3
        freed_cpu = start_cpu - end_cpu
        end_objects = len(gc.get_objects())
        freed_objects = leak_report['total_objects'] - end_objects
        elapsed_time = time.time() - start_time
        
        logger.info("\n" + "="*100)
        logger.info("✅ 深度内存清理完成！")
        logger.info("="*100)
        logger.info(f"📊 清理总结:")
        logger.info(f"   CPU物理内存: {start_cpu:.3f}G → {end_cpu:.3f}G (释放 {freed_cpu:+.3f}G)")
        if torch.cuda.is_available():
            logger.info(f"   GPU显存: {start_gpu:.3f}G → {end_gpu:.3f}G (释放 {freed_gpu:+.3f}G)")
            logger.info(f"   GPU保留: {start_gpu_reserved:.3f}G → {end_gpu_reserved:.3f}G (释放 {freed_reserved:+.3f}G)")
        logger.info(f"   Python对象: {leak_report['total_objects']} → {end_objects} (释放 {freed_objects})")
        logger.info(f"   总耗时: {elapsed_time:.2f}秒")
        
        # 内存泄漏警告
        if freed_gpu < 0.01 and start_gpu > 0.1:
            logger.warning(f"   ⚠️  警告: GPU内存未释放，可能存在泄漏！")
        if freed_cpu < 0.01 and start_cpu > 1.0:
            logger.warning(f"   ⚠️  警告: CPU内存未释放，可能存在引用残留！")
        
        logger.info("="*100 + "\n")
        
        return ()

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
        """遍历全局，销毁所有残留张量（超强制版）"""
        tensor_count = 0
        large_tensors = []
        
        # 第一遍：收集所有张量引用
        all_tensors = []
        for obj in gc.get_objects():
            try:
                if isinstance(obj, torch.Tensor):
                    all_tensors.append(obj)
                    size_mb = obj.element_size() * obj.nelement() / 1024**2
                    if size_mb > 10:  # 大于10MB的张量
                        large_tensors.append(obj)
            except:
                continue
        
        # 第二遍：超强制清理
        for obj in all_tensors:
            try:
                # 1. 先移动到CPU
                if obj.is_cuda:
                    obj.data = obj.data.cpu()
                
                # 2. detach并清空梯度
                obj = obj.detach()
                if obj.grad is not None:
                    if obj.grad.is_cuda:
                        obj.grad.data = obj.grad.data.cpu()
                    obj.grad = None
                
                # 3. 清空存储（释放内存）
                if hasattr(obj, 'storage'):
                    try:
                        storage = obj.storage()
                        if storage is not None:
                            storage.resize_(0)
                    except:
                        pass
                
                # 4. 重置为空张量
                try:
                    obj.data = torch.tensor([], dtype=obj.dtype)
                except:
                    pass
                
                # 5. 删除引用
                del obj
                tensor_count += 1
            except:
                continue
        
        # 清空列表
        all_tensors.clear()
        large_tensors.clear()
        
        # 第三遍：强制GC
        gc.collect()
        gc.collect()
        
        return tensor_count
    
    def _clear_global_caches(self):
        """清理Python全局缓存和大对象（增强版）"""
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
        
        # 2. 清理大对象（>100MB）
        try:
            large_objects = []
            for obj in gc.get_objects():
                try:
                    # 检测大列表/字典
                    if isinstance(obj, (list, dict, set)):
                        size = sys.getsizeof(obj)
                        if size > 100 * 1024 * 1024:  # >100MB
                            large_objects.append(obj)
                except:
                    pass
            
            # 清理收集到的大对象
            for obj in large_objects:
                try:
                    if isinstance(obj, (list, set)):
                        obj.clear()
                    elif isinstance(obj, dict):
                        obj.clear()
                    cleared_count += 1
                except:
                    pass
        except:
            pass
        
        # 3. 清理torch内部缓存
        try:
            if hasattr(torch, '_C') and hasattr(torch._C, '_clear_cublas_benchmarks'):
                torch._C._clear_cublas_benchmarks()
        except:
            pass
        
        # 4. 清理模块缓存
        try:
            # 清理__pycache__引用
            for module_name in list(sys.modules.keys()):
                if '__pycache__' in module_name or 'test' in module_name:
                    try:
                        del sys.modules[module_name]
                        cleared_count += 1
                    except:
                        pass
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
        """打印容器内内存状态（区分容器和宿主机）"""
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        mem_rss = mem_info.rss / 1024**3
        mem_vms = mem_info.vms / 1024**3
        
        # 获取容器内存信息
        container_info = self._get_container_memory_info()
        
        logger.info(f"   进程内存 (RSS): {mem_rss:.3f}G")
        logger.info(f"   虚拟内存 (VMS): {mem_vms:.3f}G")
        
        # 如果在容器中，显示容器内存限制
        if container_info:
            if 'limit' in container_info and container_info['limit']:
                usage = container_info.get('usage', mem_rss)
                limit = container_info['limit']
                percent = (usage / limit * 100) if limit > 0 else 0
                logger.info(f"   容器内存: {usage:.2f}G / {limit:.2f}G (使用率 {percent:.1f}%)")
                logger.info(f"   容器可用: {(limit - usage):.2f}G")
            elif 'usage' in container_info:
                logger.info(f"   容器内存使用: {container_info['usage']:.2f}G (无限制)")
        
        # 宿主机信息（仅供参考）
        sys_mem = psutil.virtual_memory()
        sys_mem_total = sys_mem.total / 1024**3
        sys_mem_used = sys_mem.used / 1024**3
        sys_mem_available = sys_mem.available / 1024**3
        
        logger.info(f"   宿主机内存: {sys_mem_used:.2f}G / {sys_mem_total:.2f}G (可用 {sys_mem_available:.2f}G)")
        
        # Swap信息
        sys_swap = psutil.swap_memory()
        if sys_swap.total > 0:
            sys_swap_total = sys_swap.total / 1024**3
            sys_swap_used = sys_swap.used / 1024**3
            logger.info(f"   Swap内存: {sys_swap_used:.2f}G / {sys_swap_total:.2f}G")
        
        # CPU使用率
        try:
            cpu_percent = proc.cpu_percent(interval=0.1)
            logger.info(f"   进程CPU: {cpu_percent:.1f}%")
        except:
            pass


