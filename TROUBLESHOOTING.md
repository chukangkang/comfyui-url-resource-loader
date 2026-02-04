# OSS_Upload 调试指南

## 启用日志输出

OSS_Upload 使用 Python 的 logging 模块，在 API 模式下也能正常输出日志。

### ComfyUI 启动时配置

在启动 ComfyUI 前设置日志级别：

```python
# main.py 或启动脚本中
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 运行时配置

```python
import logging
logging.getLogger("OSS_Upload").setLevel(logging.INFO)
```

### 查看日志

日志会输出到：
- **UI 模式**：ComfyUI 控制台和浏览器控制台
- **API 模式**：ComfyUI 服务器日志（标准输出）
- **Docker**：容器日志 `docker logs <container_id>`

## 问题：扫描找不到文件

### 症状
```
❌ [Task xxx] 后端声称上传但OSS上缺失文件
⚠️ [Task xxx] 后端OSS_Upload节点执行失败，API将执行兜底上传
```

### 根本原因

1. **时序问题**：OSS_Upload 节点执行时，SaveImage/SaveVideo 等节点还没完成文件写入
2. **时间戳过滤太严**：`min_file_time` 设置的时间晚于文件实际生成时间
3. **目录路径不对**：output 目录配置错误
4. **扫描延迟不够**：文件还在写入过程中就开始扫描了

## 解决方案

### 1. 调整扫描延迟（推荐）

增加 `scan_delay` 参数，让节点等待更长时间：

```json
{
  "file_source_mode": "auto_scan",
  "scan_delay": 3.0,  // 增加到3秒或更长
  "min_file_time": task_start_time
}
```

**建议值：**
- 图片：2-3秒
- 视频：5-10秒
- 大文件：10-20秒

### 2. 调整时间戳过滤

确保 `min_file_time` 早于工作流开始时间：

```python
# 后端代码
import time

# 在提交工作流前记录时间，留点余量
task_start_time = time.time() - 5.0  # 往前推5秒

oss_node_inputs = {
    "min_file_time": task_start_time,
    ...
}
```

### 3. 使用环境变量指定输出目录

如果 ComfyUI 使用自定义输出目录：

```bash
export COMFYUI_OUTPUT_DIR="/path/to/custom/output"
```

### 4. 依赖自动重试机制

新版本自动包含重试逻辑：
- 第一次扫描：立即执行
- 第二次扫描：等待1秒后重试
- 第三次扫描：再等待1秒后重试

总共会尝试3次，确保捕获到文件。

## 调试日志解读

### 正常输出示例（详细版）

使用 logging 模块后的输出格式：

```
[OSS_Upload] ================================================================================
[OSS_Upload] 🚀 OSS_Upload Node Execution Started
[OSS_Upload]    Task ID: 8e1dfca7-c55c-4ae3-86b2-7a79b83d07c9
[OSS_Upload]    Mode: auto_scan
[OSS_Upload]    Output Dir: /root/ComfyUI/output
[OSS_Upload]    Delete After Upload: True
[OSS_Upload] ================================================================================

[OSS_Upload] ⏱️  Waiting 2.0s for files to be fully generated...

[OSS_Upload] 📂 Output directory contents (3 items):
[OSS_Upload]    📄 ComfyUI_00058_.mp3 (62863 bytes, 20:25:45)
[OSS_Upload]    📁 temp/

[OSS_Upload] 🔍 Scanning output directory: /root/ComfyUI/output
[OSS_Upload]    Search pattern: /root/ComfyUI/output/**/*.*
[OSS_Upload]    Glob pattern: *.*, Recursive: True
[OSS_Upload]    Min file time: 1738590340.0 (2026-02-03 20:25:40)
[OSS_Upload]    Current time: 1738590347.5 (2026-02-03 20:25:47)
[OSS_Upload]    Found 1 potential files/dirs

[OSS_Upload] 📋 All paths found by glob:
[OSS_Upload]    1. [FILE] /root/ComfyUI/output/ComfyUI_00058_.mp3
[OSS_Upload]       Size: 62863 bytes, Modified: 2026-02-03 20:25:45 (1738590345.5)

[OSS_Upload]    ✓ Matched: ComfyUI_00058_.mp3 (mtime: 2026-02-03 20:25:45)

[OSS_Upload] 📊 Scan Results:
[OSS_Upload]    Total matched files: 1
[OSS_Upload]    Filtered (old): 0
[OSS_Upload]    Skipped (not file): 0

[OSS_Upload] 📦 Files by type:
[OSS_Upload]    - audios: 1 files
[OSS_Upload]      • ComfyUI_00058_.mp3

[OSS_Upload] 📤 Starting upload to OSS...
[OSS_Upload]    Bucket: my-bucket
[OSS_Upload]    Task ID: 8e1dfca7-c55c-4ae3-86b2-7a79b83d07c9
[OSS_Upload]    Total file types: 1
[OSS_Upload]    - audios: 1 files

[OSS_Upload] 🔍 Processing: ComfyUI_00058_.mp3
[OSS_Upload]    Local path: /root/ComfyUI/output/ComfyUI_00058_.mp3
[OSS_Upload]    Subfolder: ''
[OSS_Upload]    File type: audios
[OSS_Upload]    OSS path: outputs/8e1dfca7-c55c-4ae3-86b2-7a79b83d07c9/audio/ComfyUI_00058_.mp3
[OSS_Upload]    File size: 62863 bytes
[OSS_Upload]    Content-Type: audio/mpeg
[OSS_Upload]    Starting upload to bucket: my-bucket
[OSS_Upload]    Upload completed in 0.23s
[OSS_Upload]    Deleted local file: /root/ComfyUI/output/ComfyUI_00058_.mp3
[OSS_Upload] ✅ Uploaded: ComfyUI_00058_.mp3 -> outputs/8e1dfca7-c55c-4ae3-86b2-7a79b83d07c9/audio/ComfyUI_00058_.mp3 (62863 bytes)

[OSS_Upload] ================================================================================
[OSS_Upload] ✅ OSS_Upload Node Execution Completed
[OSS_Upload]    Status: success
[OSS_Upload]    Uploaded: 1 files
[OSS_Upload]    Failed: 0 files
[OSS_Upload]    Total size: 62863 bytes

[OSS_Upload]    Uploaded files:
[OSS_Upload]    ✓ ComfyUI_00058_.mp3 -> outputs/8e1dfca7-c55c-4ae3-86b2-7a79b83d07c9/audio/ComfyUI_00058_.mp3
[OSS_Upload] ================================================================================
```

### 问题诊断

#### 场景1：目录为空

```
📂 Output directory contents (0 items):

⚠️  No files found on attempt 1
🔄 Retry 1/2: No files found, waiting 1.0s and scanning again...
```

**原因**：文件还没生成  
**解决**：增加 `scan_delay`

#### 场景2：文件被过滤

```
📂 Output directory contents (1 items):
   📄 ComfyUI_00057_.mp3 (62863 bytes, 20:10:00)

⏭️  Filtered (too old): ComfyUI_00057_.mp3 (mtime: 2026-02-03 20:10:00)

📊 Scan Results:
   Total matched files: 0
   Filtered (old): 1
```

**原因**：`min_file_time` 时间晚于文件生成时间  
**解决**：调整 `min_file_time`，确保早于工作流开始时间

#### 场景3：目录路径错误

```
❌ Output directory does not exist: /wrong/path
```

**原因**：output 目录配置错误  
**解决**：设置 `COMFYUI_OUTPUT_DIR` 环境变量

## 最佳实践

### 后端注入配置（推荐）

```python
import time

class TaskService:
    def inject_oss_upload_node(self, workflow, task_id):
        # 1. 记录当前时间（往前推5秒作为安全余量）
        task_start_time = time.time() - 5.0
        
        # 2. 注入 OSS_Upload 节点
        oss_node = {
            "class_type": "OSS_Upload",
            "inputs": {
                # 必需参数
                "access_key_id": sts_credentials['AccessKeyId'],
                "access_key_secret": sts_credentials['AccessKeySecret'],
                "security_token": sts_credentials['SecurityToken'],
                "bucket_name": "my-bucket",
                "endpoint": "oss-cn-beijing.aliyuncs.com",
                "task_id": task_id,
                "file_list": "{}",
                
                # 文件发现配置（关键）
                "file_source_mode": "auto_scan",
                "auto_scan_pattern": "*.*",
                "scan_subdirs": True,
                "min_file_time": task_start_time,  # 时间戳过滤
                "scan_delay": 3.0,  # 等待3秒让文件完全生成
                
                # 其他配置
                "delete_after_upload": True,
                "timeout_seconds": 300
            }
        }
        
        return oss_node
```

### 环境变量配置

```bash
# .env 文件或系统环境变量
export COMFYUI_OUTPUT_DIR="/root/ComfyUI/output"
export COMFYUI_HOST="127.0.0.1"
export COMFYUI_PORT="8188"
```

## 验证检查清单

部署后验证：

- [ ] OSS_Upload 节点能找到输出目录
- [ ] 扫描延迟足够长（查看日志中的文件生成时间）
- [ ] 时间戳过滤正确（文件时间应晚于 min_file_time）
- [ ] 文件类型正确分类（audio/image/video/file）
- [ ] OSS 路径包含类型子目录（outputs/{task_id}/{type}/{filename}）
- [ ] 后端验证逻辑匹配新的路径结构

## 监控建议

在后端日志中关注这些指标：

1. **扫描成功率**：`Total matched files > 0` 的比例
2. **重试次数**：`Retry X/2` 出现的频率
3. **过滤统计**：`Filtered (old)` 数量
4. **上传成功率**：OSS 验证通过的比例

## 获取支持

如果问题仍然存在：

1. 收集完整的节点执行日志
2. 检查 ComfyUI output 目录的实际内容
3. 验证时间戳是否合理
4. 提供工作流 JSON 配置

---

**最后更新：2026年2月3日**
