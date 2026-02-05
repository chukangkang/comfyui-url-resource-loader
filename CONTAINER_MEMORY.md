# 容器环境下的内存清理最佳实践

## 问题说明

容器内的进程通常没有 root 权限，无法直接操作 `/proc/sys/vm/drop_caches` 来清理宿主机的系统缓存（buff/cache）。这导致即使容器内清理了应用内存，系统的 buff/cache 仍然很高。

## 解决方案

### 方案一：容器内清理（推荐）

**ComfyUI 深度内存清洗节点已优化，可在容器内最大化清理：**

1. **在 ComfyUI 工作流中使用"深度内存清洗"节点**
   - 8阶段清洗流程
   - 自动调用 `malloc_trim(0)` 归还内存给操作系统
   - 清理所有模型、张量、缓存
   - 容器内可用，无需特殊权限

2. **效果**：
   - ✅ 释放应用层内存（模型、张量等）
   - ✅ 通过 `malloc_trim` 归还空闲内存给系统
   - ✅ 降低容器 RSS 内存使用
   - ⚠️ 无法直接清理宿主机的 buff/cache

### 方案二：宿主机清理（最彻底）

**在宿主机上运行清理脚本：**

```bash
# 1. 在 ComfyUI 中执行深度内存清理节点

# 2. 在宿主机上运行（需要root权限）：
sudo bash /path/to/comfyui-url-resource-loader/clear_system_cache.sh
```

**脚本功能**：
- 同步文件系统
- 清理 pagecache
- 清理 dentries 和 inodes
- 触发内存压缩
- 显示清理前后内存对比

**效果**：
- ✅ 释放应用层内存
- ✅ 清理系统 buff/cache
- ✅ 最大化降低容器内存使用率
- ✅ 可将内存使用率从 85% 降至 60% 以下

### 方案三：Docker 特权模式（不推荐）

如果必须在容器内清理系统缓存，可以使用特权模式：

```bash
docker run --privileged ...
```

**注意**：
- ⚠️ 安全风险高，不推荐生产环境使用
- ⚠️ 容器可以访问宿主机所有设备
- ⚠️ 可能影响宿主机其他容器

## 内存清理效果对比

### 仅容器内清理
```
清理前: Mem: 60G used / 60G total (100%)
清理后: Mem: 46G used / 60G total (77%)
buff/cache: 42G (高)
```

### 容器内清理 + 宿主机缓存清理
```
清理前: Mem: 60G used / 60G total (100%)
清理后: Mem: 35G used / 60G total (58%)
buff/cache: 5G (正常)
```

## 推荐工作流

1. **日常使用**：
   - 在 ComfyUI 工作流末尾添加"深度内存清洗"节点
   - 让其自动清理每次任务后的内存

2. **深度清理**（内存使用率 >80% 时）：
   - 在 ComfyUI 中执行深度内存清洗
   - SSH 到宿主机运行清理脚本
   - 可将内存使用率降至最低

3. **自动化**（可选）：
   ```bash
   # 在宿主机上创建定时任务
   # 每小时清理一次系统缓存
   0 * * * * echo 3 > /proc/sys/vm/drop_caches
   ```

## FAQ

**Q: 为什么容器内看到 buff/cache 很高？**  
A: buff/cache 是宿主机级别的，容器只能看到但无法清理。这是正常的 Linux 内存管理机制。

**Q: buff/cache 占用内存有问题吗？**  
A: 通常不是问题。Linux 会在需要时自动释放 buff/cache。但如果容器内存限制较严格，建议定期清理。

**Q: malloc_trim 有什么用？**  
A: `malloc_trim(0)` 强制 glibc 归还空闲内存给操作系统，这在容器内是可用的，且不需要特殊权限。

**Q: 清理后为什么 available 内存没变？**  
A: available 内存包括 buff/cache，清理 buff/cache 后它们会被标记为 free，总的 available 可能不变。关注 used 内存的降低。

## 技术原理

### malloc_trim
- C 库函数，容器内可用
- 强制归还堆内存给操作系统
- 降低进程 RSS

### drop_caches（需要root）
- 清理文件系统缓存
- 清理目录项和 inode 缓存
- 降低系统 buff/cache

### 内存回收优先级
1. 应用释放内存（ComfyUI 节点）
2. malloc_trim 归还给系统
3. 系统自动管理 buff/cache
4. 手动 drop_caches（可选）

## 总结

- ✅ **推荐**：使用 ComfyUI 深度内存清洗节点（容器内可用）
- ✅ **可选**：需要时在宿主机运行清理脚本
- ❌ **不推荐**：使用 Docker 特权模式

插件已优化为容器友好版本，大部分情况下容器内清理已足够！
