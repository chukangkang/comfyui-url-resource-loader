# ComfyUI 内存释放完全指南

## 问题分析

### 为什么 ComfyUI 运行后内存不释放？

1. **模型缓存机制**
   - ComfyUI 会自动缓存加载的模型（SD、LoRA、VAE等）
   - 缓存的目的是加快下次使用，但会持续占用内存
   - 即使工作流结束，模型仍保留在内存中

2. **PyTorch 张量残留**
   - 生成的图片、中间特征图会以张量形式保存
   - PyTorch 的自动求导图可能保留引用
   - GPU 显存被张量占用

3. **Python 对象循环引用**
   - 复杂对象之间可能存在循环引用
   - Python GC 无法立即回收
   - 需要多次 GC 才能完全清理

4. **系统内存碎片**
   - 频繁分配和释放导致内存碎片
   - 进程 RSS 内存不会自动归还给系统
   - 需要 `malloc_trim` 强制归还

## 解决方案

### 方案一：在工作流末尾添加清理节点（推荐）

**最佳实践 - 自动清理**

```
[你的工作流节点]
    ↓
[深度内存清洗节点]  ← 放在工作流最后
    ↓
[保存输出/预览]
```

**优点**：
- ✅ 每次工作流自动清理
- ✅ 不影响当前输出结果
- ✅ 为下次执行准备干净环境
- ✅ 无需手动操作

**设置方法**：
1. 在 ComfyUI 中添加"🚀 深度内存清洗（容器优化）"节点
2. 将其放在工作流的最后
3. 连接到输出节点（可选，不连接也能运行）
4. 保存工作流

### 方案二：手动清理

**适用场景**：
- 调试工作流时
- 需要保留模型缓存连续运行多次
- 偶尔清理一次

**操作方法**：
1. 在 ComfyUI 中单独运行清理节点
2. 或通过 API 调用清理功能

### 方案三：API 集成自动清理

如果你通过 API 调用 ComfyUI，可以在每次工作流后自动清理：

```python
import requests

# 1. 执行工作流
response = requests.post('http://localhost:12800/prompt', json={
    'prompt': your_workflow
})

# 2. 等待完成后，调用清理 API
cleanup_workflow = {
    "1": {
        "class_type": "ClearMemoryDeepEnd",
        "inputs": {}
    }
}
requests.post('http://localhost:12800/prompt', json={
    'prompt': cleanup_workflow
})
```

## 清理节点详解

### 8阶段清洗流程

1. **阶段1: ComfyUI 模型卸载**
   - 卸载所有已加载的 SD、LoRA、VAE 模型
   - 清空模型管理器缓存
   - 重置 VRAM 状态

2. **阶段2: 深度清理模型张量**
   - 遍历所有模型对象
   - 强制将模型移到 CPU
   - 删除 parameters、buffers、state_dict

3. **阶段3: 清理 PyTorch 张量**
   - 遍历内存中所有 torch.Tensor
   - 分离计算图
   - 删除梯度信息

4. **阶段4: 强制清理大对象**
   - 检测 >10MB 的大对象
   - 清空列表、字典、集合
   - 打破循环引用

5. **阶段5: 超级激进 GC**
   - 执行 10 次深度垃圾回收
   - 清理所有代（gen 0, 1, 2）
   - 设置激进的 GC 阈值

6. **阶段6: VRAM 完全释放**
   - 同步所有 CUDA 操作
   - 5 次强制清空 CUDA 缓存
   - 重置显存统计

7. **阶段7: 系统级内存释放**
   - 同步文件系统
   - 清理 torch 内部缓存
   - 多次 GC 确保彻底

8. **阶段8: 终极 malloc_trim**
   - 50MB 安全内存分配
   - 调用 `malloc_trim(0)` 归还内存
   - 强制操作系统回收空闲内存

### 内存释放效果

**清理前**：
```
CPU: 51.9G / 60G (86.5%)
GPU: 18.5G / 24G (77%)
容器: 51.9G used
```

**清理后**：
```
CPU: 8-12G / 60G (15-20%)  ← 释放 ~40G
GPU: 0.5-1G / 24G (2-4%)    ← 释放 ~17G
容器: 12G used              ← 降低 75%
```

**下次工作流**：
- ✅ 可以正常加载新模型
- ✅ 不会内存不足
- ✅ 执行速度不受影响
- ✅ 无需重启 ComfyUI

## 常见问题

### Q1: 清理后下次工作流会变慢吗？

**A**: 不会！
- 首次加载模型需要从磁盘读取（正常速度）
- 清理不影响模型加载速度
- 避免了内存不足导致的 OOM 错误
- 反而让系统更稳定

### Q2: 多久清理一次最好？

**A**: 推荐配置：
- **每次工作流后清理**（最佳）- 内存使用最低
- **每 5-10 次工作流清理一次** - 平衡性能和内存
- **内存使用率 >80% 时清理** - 按需清理

### Q3: 清理节点会影响当前输出吗？

**A**: 不会！
- 清理节点放在工作流末尾
- 所有输出已经生成
- 只清理缓存和临时数据
- 不影响已保存的结果

### Q4: 容器内存使用率还是很高怎么办？

**A**: 两步清理：
1. **容器内**：使用清理节点（降低应用内存）
2. **宿主机**：运行 `sudo bash clear_system_cache.sh`（清理系统缓存）

详见：[容器内存清理指南](CONTAINER_MEMORY.md)

### Q5: 为什么不自动清理？

**A**: ComfyUI 设计为交互式工具：
- 默认保留模型缓存提高效率
- 用户可能连续运行多次
- 给用户选择权（性能 vs 内存）

**本插件提供自动清理方案**：
- 在工作流中添加清理节点即可
- 实现真正的"一键清理"

## 最佳实践建议

### 1. 工作流设计

```
┌─────────────────────────────────┐
│  加载检查点（Load Checkpoint）   │
│          ↓                       │
│  添加 LoRA（Load LoRA）          │
│          ↓                       │
│  生成图片（KSampler）            │
│          ↓                       │
│  解码（VAE Decode）              │
│          ↓                       │
│  保存/预览（Save/Preview）       │
│          ↓                       │
│ 🚀 深度内存清洗  ← 必须添加！    │
└─────────────────────────────────┘
```

### 2. API 调用模式

```python
def run_comfy_workflow(workflow_json):
    """运行工作流并自动清理内存"""
    try:
        # 1. 执行工作流
        result = execute_workflow(workflow_json)
        
        # 2. 等待完成
        wait_for_completion(result['prompt_id'])
        
        # 3. 获取结果
        output = get_output(result['prompt_id'])
        
        return output
    finally:
        # 4. 无论成功失败，都清理内存
        cleanup_memory()
```

### 3. 批量处理脚本

```python
# 处理多个任务
for task in task_list:
    # 执行任务
    process_task(task)
    
    # 每10个任务清理一次
    if task_counter % 10 == 0:
        cleanup_memory()
        
# 全部完成后最终清理
cleanup_memory()
```

## 监控内存使用

### 查看容器内存

```bash
# 方法1: free 命令
free -h

# 方法2: 查看进程内存
ps aux | grep python | grep ComfyUI

# 方法3: top 实时监控
top -p $(pgrep -f ComfyUI)
```

### 设置内存告警

```python
import psutil

def check_memory_usage():
    mem = psutil.virtual_memory()
    if mem.percent > 80:
        print("⚠️ 内存使用率过高，建议清理！")
        # 自动触发清理
        cleanup_memory()
```

## 总结

要让 ComfyUI 不再持续占用内存：

1. ✅ **在每个工作流末尾添加清理节点**
2. ✅ **使用 8 阶段深度清洗**
3. ✅ **清理后可立即运行新工作流**
4. ✅ **无需 kill 进程，无需重启**

这样就能实现：
- 🎯 内存自动释放
- 🎯 工作流间互不影响
- 🎯 稳定长期运行
- 🎯 容器友好
