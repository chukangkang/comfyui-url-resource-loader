# OSS Upload 节点使用示例

## 概述

OSS_Upload节点现在支持三种文件获取模式，**推荐使用 auto_scan 模式配合时间戳过滤**，避免 prompt_id 时序问题。

## 模式一：auto_scan 模式（推荐）

自动扫描 output 目录，配合时间戳过滤只上传最新文件。

### 基础用法（推荐）

```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.*",
  "scan_subdirs": true,
  "min_file_time": 1738570663.076  // Unix时间戳，只上传此时间之后的文件
}
```

### 优势

- ✅ **避免时序问题**：不依赖 prompt_id，不受节点执行顺序影响
- ✅ **精确过滤**：通过时间戳只上传本次任务的文件
- ✅ **简单可靠**：无需 History API，减少依赖
- ✅ **灵活配置**：支持文件模式和子目录扫描
- ✅ **自动重试**：如果第一次没找到文件，会自动重试最多3次
- ✅ **详细日志**：显示目录内容、扫描过程和匹配结果

### 后端集成示例

```python
import time

# 1. 任务开始时记录时间戳
task_start_time = time.time()

# 2. 注入 OSS_Upload 节点
oss_upload_node = {
    "class_type": "OSS_Upload",
    "inputs": {
        "file_source_mode": "auto_scan",
        "access_key_id": sts_credentials['AccessKeyId'],
        "access_key_secret": sts_credentials['AccessKeySecret'],
        "security_token": sts_credentials['SecurityToken'],
        "bucket_name": "my-bucket",
        "endpoint": "oss-cn-beijing.aliyuncs.com",
        "task_id": task_id,
        "file_list": "{}",
        "auto_scan_pattern": "*.*",
        "scan_subdirs": True,
        "min_file_time": task_start_time,  # 关键：只上传任务开始后的文件
        "scan_delay": 2.0,  # 等待2秒让文件完全生成
        "delete_after_upload": True
    }
}
```

### 使用场景

#### 场景1：扫描所有最新文件（推荐）
```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.*",
  "scan_subdirs": true,
  "min_file_time": 1738570663.076
}
```

#### 场景2：只扫描PNG图片
```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.png",
  "scan_subdirs": true,
  "min_file_time": 1738570663.076
}
```

#### 场景3：只扫描顶层目录的MP4视频
```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.mp4",
  "scan_subdirs": false,
  "min_file_time": 1738570663.076
}
```

#### 场景4：不使用时间过滤（上传所有文件）
```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.*",
  "scan_subdirs": true,
  "min_file_time": 0.0  // 0表示不过滤
}
```

### 文件分类

节点会根据文件扩展名自动分类：
- **images**: .jpg, .jpeg, .png, .gif, .bmp, .webp, .svg, .tiff
- **videos**: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v, .mpg, .mpeg
- **audios**: .mp3, .wav, .aac, .flac, .ogg, .m4a, .wma, .aiff
- **files**: 其他类型

## 模式二：file_list 模式

使用传入的JSON格式的文件列表，适合精确控制。

### 使用 _metadata（推荐）

如果file_list中包含`_metadata`，节点会优先使用metadata中的信息：

```json
{
  "images": [
    {
      "filename": "output_001.png",
      "subfolder": "",
      "_metadata": {
        "filename": "ComfyUI_00001_.png",
        "subfolder": "temp",
        "type": "output"
      }
    }
  ]
}
```

在这个例子中，节点会使用`_metadata`中的路径信息来定位文件：
- 实际文件路径：`/root/ComfyUI/output/temp/ComfyUI_00001_.png`
- 上传到OSS后的路径：`outputs/{task_id}/image/ComfyUI_00001_.png`

## 模式三：history_api 模式

从ComfyUI的History API自动获取当前工作流的生成结果。

### 配置参数

- **file_source_mode**: 设置为 `history_api`
- **prompt_id**: ComfyUI执行workflow时生成的prompt_id（可选）
  - 如果提供，使用指定的prompt_id
  - 如果不提供或为空，自动获取最新的prompt_id

### 工作原理

1. 如果没有提供prompt_id，节点会自动获取最新的工作流执行ID
2. 节点向ComfyUI发送HTTP请求：`http://{host}:{port}/history/{prompt_id}`
3. 从返回的history数据中提取文件信息
4. 自动解析outputs中的images、videos、audios等资源
5. 如果API调用失败，自动回退到file_list模式

### 智能自动检测

当`prompt_id`为空时，节点会：
1. 调用ComfyUI的`/history`接口获取所有历史记录
2. 自动选择最新的一条记录
3. 提取该记录中的所有输出文件

这意味着您可以在工作流末尾添加此节点，无需手动指定prompt_id，它会自动上传当前工作流的所有生成结果！

### API响应示例

```json
{
  "prompt_123": {
    "outputs": {
      "9": {
        "images": [
          {
            "filename": "ComfyUI_00001_.png",
            "subfolder": "",
            "type": "output"
          }
        ]
      },
      "12": {
        "videos": [
          {
            "filename": "output.mp4",
            "subfolder": "videos",
            "type": "output"
          }
        ]
      }
    }
  }
}
```

### 环境变量配置

可以通过环境变量自定义ComfyUI服务地址：

```bash
export COMFYUI_HOST=127.0.0.1
export COMFYUI_PORT=8188
```

或在Docker中：
```yaml
environment:
  - COMFYUI_HOST=comfyui-service
  - COMFYUI_PORT=8188
```

## 完整工作流示例

### 示例1：使用 auto_scan + 时间戳过滤（推荐）

```python
import time

# 任务开始时记录时间戳
task_start_time = time.time()

{
  "OSS_Upload_Node": {
    "inputs": {
      "access_key_id": "STS.xxxxx",
      "access_key_secret": "xxxxxxxx",
      "security_token": "CAISxxxxxxxx",
      "bucket_name": "my-bucket",
      "endpoint": "oss-cn-beijing.aliyuncs.com",
      "task_id": "task_001",
      "file_source_mode": "auto_scan",
      "file_list": "{}",
      "auto_scan_pattern": "*.*",
      "scan_subdirs": true,
      "min_file_time": task_start_time,  # 只上传任务开始后的文件
      "delete_after_upload": true
    }
  }
}
```

### 示例2：使用History API（自动获取当前工作流结果）

```python
{
  "OSS_Upload_Node": {
    "inputs": {
      "access_key_id": "STS.xxxxx",
      "access_key_secret": "xxxxxxxx",
      "security_token": "CAISxxxxxxxx",
      "bucket_name": "my-bucket",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "task_003",
      "file_source_mode": "history_api",
      "prompt_id": "",  # 留空，自动获取最新的工作流执行结果
      "file_list": "{}",  # 作为fallback
      "delete_after_upload": true
    }
  }
}
```

**指定特定的prompt_id**

```python
{
  "OSS_Upload_Node": {
    "inputs": {
      "access_key_id": "STS.xxxxx",
      "access_key_secret": "xxxxxxxx",
      "security_token": "CAISxxxxxxxx",
      "bucket_name": "my-bucket",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "task_003",
      "file_source_mode": "history_api",
      "prompt_id": "12345-67890-abcdef",  # 明确指定要上传哪个工作流的结果
      "file_list": "{}",  # 作为fallback
      "delete_after_upload": true
    }
  }
}
```

## 上传结果格式

所有模式的上传结果都返回相同的JSON格式：

```json
{
  "status": "success",
  "task_id": "task_001",
  "uploaded_count": 3,
  "failed_count": 0,
  "total_size": 1048576,
  "uploaded_files": [
    {
      "filename": "output_001.png",
      "oss_path": "outputs/task_001/image/output_001.png",
      "size": 524288,
      "content_type": "image/png",
      "file_type": "images"
    },
    {
      "filename": "animation.mp4",
      "oss_path": "outputs/task_001/video/animation.mp4",
      "size": 524288,
      "content_type": "video/mp4",
      "file_type": "videos"
    },
    {
      "filename": "audio.mp3",
      "oss_path": "outputs/task_001/audio/audio.mp3",
      "size": 62863,
      "content_type": "audio/mpeg",
      "file_type": "audios"
    }
  ],
  "failed_files": [],
  "timestamp": "2026-02-03T10:30:00.000000"
}
```

### OSS 路径结构

文件会按照类型自动组织到不同的子目录：

- **图片**: `outputs/{task_id}/image/{filename}`
- **视频**: `outputs/{task_id}/video/{filename}`
- **音频**: `outputs/{task_id}/audio/{filename}`
- **其他**: `outputs/{task_id}/file/{filename}`

这样的结构便于：
- 文件管理和分类
- 批量下载特定类型的文件
- 设置不同类型文件的访问权限

## 错误处理

### 文件不存在

```json
{
  "status": "partial",
  "failed_files": [
    {
      "filename": "missing.png",
      "reason": "File not found"
    }
  ]
}
```

### History API 失败

当history_api模式失败时，节点会自动回退到file_list模式并记录日志：

```
Failed to fetch from history API: Connection timeout, falling back to file_list
```

### 扫描目录为空

```json
{
  "status": "error",
  "message": "No files found with mode: auto_scan"
}
```

## 最佳实践

1. **使用_metadata定位文件**：如果workflow中节点输出包含metadata，传递完整的file_list可以确保准确定位文件

2. **合理选择删除策略**：
   - 生产环境：设置`delete_after_upload=true`节省磁盘空间
   - 开发/调试：设置`delete_after_upload=false`保留文件以便检查

3. **优化扫描性能**：
   - 使用具体的文件模式（如`*.png`）而不是`*.*`
   - 如果文件都在顶层，设置`scan_subdirs=false`

4. **History API 最佳实践**：
   - 确保prompt_id正确传递
   - 始终提供fallback file_list以防API失败
   - 检查网络连接和ComfyUI服务状态

## 故障排查

### 问题：文件找不到

**检查清单：**
- 确认output目录路径正确（默认：`/root/ComfyUI/output`）
- 检查file_list中的subfolder是否正确
- 如果使用_metadata，确认metadata中的路径信息准确

### 问题：History API 不工作

**检查清单：**
- 确认COMFYUI_HOST和COMFYUI_PORT环境变量
- 测试API连接：`curl http://127.0.0.1:8188/history/{prompt_id}`
- 检查prompt_id是否有效
- 查看节点日志中的错误信息

### 问题：自动扫描找不到文件

**检查清单：**
- 验证auto_scan_pattern语法（使用glob模式）
- 确认scan_subdirs设置是否符合预期
- 手动检查output目录是否有匹配的文件

---

**更新日期：2026年2月3日**
