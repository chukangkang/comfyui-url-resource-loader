# OSS Upload 节点使用示例

## 概述

OSS_Upload节点现在支持三种文件获取模式，可以灵活地从不同来源获取要上传的文件列表。

## 模式一：file_list 模式（默认）

使用传入的JSON格式的文件列表。

### 基础用法

```json
{
  "images": [
    {
      "filename": "output_001.png",
      "subfolder": ""
    }
  ],
  "videos": [
    {
      "filename": "animation.mp4",
      "subfolder": "videos"
    }
  ]
}
```

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
- 上传到OSS后的路径：`outputs/{task_id}/ComfyUI_00001_.png`

## 模式二：auto_scan 模式

自动扫描output目录，无需手动提供文件列表。

### 配置参数

- **file_source_mode**: 设置为 `auto_scan`
- **auto_scan_pattern**: 文件匹配模式（默认：`*.*`）
- **scan_subdirs**: 是否扫描子目录（默认：True）

### 使用场景

#### 场景1：扫描所有文件
```
file_source_mode = "auto_scan"
auto_scan_pattern = "*.*"
scan_subdirs = True
```

#### 场景2：只扫描PNG图片
```
file_source_mode = "auto_scan"
auto_scan_pattern = "*.png"
scan_subdirs = True
```

#### 场景3：只扫描顶层目录的MP4视频
```
file_source_mode = "auto_scan"
auto_scan_pattern = "*.mp4"
scan_subdirs = False
```

### 文件分类

节点会根据文件扩展名自动分类：
- **images**: .jpg, .jpeg, .png, .gif, .bmp, .webp, .svg, .tiff
- **videos**: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v, .mpg, .mpeg
- **audios**: .mp3, .wav, .aac, .flac, .ogg, .m4a, .wma, .aiff
- **files**: 其他类型

## 模式三：history_api 模式

从ComfyUI的History API获取文件列表，适合与工作流集成。

### 配置参数

- **file_source_mode**: 设置为 `history_api`
- **prompt_id**: ComfyUI执行workflow时生成的prompt_id（必填）

### 工作原理

1. 节点向ComfyUI发送HTTP请求：`http://{host}:{port}/history/{prompt_id}`
2. 从返回的history数据中提取文件信息
3. 自动解析outputs中的images、videos、audios等资源
4. 如果API调用失败，自动回退到file_list模式

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

### 示例1：使用file_list + metadata

```python
{
  "OSS_Upload_Node": {
    "inputs": {
      "access_key_id": "STS.xxxxx",
      "access_key_secret": "xxxxxxxx",
      "security_token": "CAISxxxxxxxx",
      "bucket_name": "my-bucket",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "task_001",
      "file_source_mode": "file_list",
      "file_list": "{\"images\":[{\"filename\":\"output.png\",\"_metadata\":{\"filename\":\"ComfyUI_00001_.png\",\"subfolder\":\"temp\",\"type\":\"output\"}}]}",
      "delete_after_upload": true
    }
  }
}
```

### 示例2：自动扫描output目录

```python
{
  "OSS_Upload_Node": {
    "inputs": {
      "access_key_id": "STS.xxxxx",
      "access_key_secret": "xxxxxxxx",
      "security_token": "CAISxxxxxxxx",
      "bucket_name": "my-bucket",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "task_002",
      "file_source_mode": "auto_scan",
      "auto_scan_pattern": "*.png",
      "scan_subdirs": true,
      "delete_after_upload": false
    }
  }
}
```

### 示例3：使用History API

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
      "prompt_id": "12345-67890-abcdef",
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
  "uploaded_count": 2,
  "failed_count": 0,
  "total_size": 1048576,
  "uploaded_files": [
    {
      "filename": "output_001.png",
      "oss_path": "outputs/task_001/output_001.png",
      "size": 524288,
      "content_type": "image/png"
    },
    {
      "filename": "animation.mp4",
      "oss_path": "outputs/task_001/animation.mp4",
      "size": 524288,
      "content_type": "video/mp4"
    }
  ],
  "failed_files": [],
  "timestamp": "2026-02-03T10:30:00.000000"
}
```

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
