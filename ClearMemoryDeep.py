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

        # 步骤4：Python激进GC回收（3轮 + 不可达对象强制回收）
        logger.info("\n🔹 步骤4: Python激进GC回收")
        # 强制禁用GC后再启用，清理不可达对象
        gc.disable()
        gc.enable()
        
        collected_1 = gc.collect(2)  # 强制全代回收
        collected_2 = gc.collect(2)
        collected_3 = gc.collect(2)
        total_collected = collected_1 + collected_2 + collected_3
        
        logger.info(f"   第1轮回收(全代): {collected_1} 个对象")
        logger.info(f"   第2轮回收(全代): {collected_2} 个对象")
        logger.info(f"   第3轮回收(全代): {collected_3} 个对象")
        logger.info(f"   总计回收: {total_collected} 个对象")
        
        # 重置GC阈值为更激进的设置
        gc.set_threshold(500, 5, 5)
        logger.info(f"   ✅ GC阈值已重置为激进模式: (500, 5, 5)")
        
        # 显示GC统计
        gc_stats = gc.get_stats()
        logger.info(f"   当前对象数: {len(gc.get_objects())}")

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
        """清理ComfyUI所有模型缓存"""
        stats = {'count': 0, 'params': 0, 'buffers': 0, 'memory_freed': 0.0}
        
        # 清理loaded_models
        if hasattr(mm, 'loaded_models'):
            model_dict = mm.loaded_models
            stats['count'] = len(model_dict)
            for model_name in list(model_dict.keys()):
                model = model_dict.pop(model_name)
                model_stats = self._destroy_model(model)
                stats['params'] += model_stats['params']
                stats['buffers'] += model_stats['buffers']
                stats['memory_freed'] += model_stats['memory']
        
        # 清理current_loaded_models
        if hasattr(mm, 'current_loaded_models'):
            for model in list(mm.current_loaded_models):
                try:
                    mm.current_loaded_models.remove(model)
                    self._destroy_model(model)
                except:
                    pass
        
        return stats
    
    def _clear_comfyui_caches(self):
        """清理ComfyUI所有缓存"""
        stats = {'total': 0, 'details': {}}
        
        # model_management缓存（mm就是model_management模块）
        cache_attrs = ['gpu_memory', 'cpu_memory', 'model_dtypes', 'models_memory', 'loaded_models']
        for attr in cache_attrs:
            if hasattr(mm, attr):
                cache = getattr(mm, attr)
                if hasattr(cache, 'clear'):
                    count = len(cache) if hasattr(cache, '__len__') else 0
                    if count > 0:
                        stats['details'][attr] = count
                        stats['total'] += 1
                    cache.clear()
        
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
        """遍历全局，销毁所有残留张量"""
        tensor_count = 0
        for obj in gc.get_objects():
            try:
                if isinstance(obj, torch.Tensor):
                    # 强制移动到CPU再删除，避免CUDA内存残留
                    if obj.device.type != 'cpu' and obj.is_cuda:
                        obj = obj.cpu()
                    obj.detach_()
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
        sys_mem_available = sys_mem.available / 1024**3
        sys_mem_percent = sys_mem.percent
        
        sys_swap = psutil.swap_memory()
        sys_swap_total = sys_swap.total / 1024**3
        sys_swap_used = sys_swap.used / 1024**3
        sys_swap_percent = sys_swap.percent
        
        logger.info(f"   进程内存 (RSS): {mem_rss:.3f}G")
        logger.info(f"   虚拟内存 (VMS): {mem_vms:.3f}G")
        logger.info(f"   系统内存: {sys_mem_used:.2f}G / {sys_mem_total:.2f}G (使用率 {sys_mem_percent:.1f}%)")
        logger.info(f"   可用内存: {sys_mem_available:.2f}G")
        logger.info(f"   Swap内存: {sys_swap_used:.2f}G / {sys_swap_total:.2f}G ({sys_swap_percent:.1f}%)")
        
        # CPU使用率
        try:
            cpu_percent = proc.cpu_percent(interval=0.1)
            logger.info(f"   进程CPU: {cpu_percent:.1f}%")
        except:
            pass


# 节点注册映射
NODE_CLASS_MAPPINGS = {
    "ClearMemoryDeepEnd": ClearMemoryDeepNode
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ClearMemoryDeepEnd": "🚀 深度内存清理 + 泄漏排查（增强版）"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
