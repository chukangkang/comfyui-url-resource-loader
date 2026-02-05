# ComfyUI URL资源加载器

一个功能完整的ComfyUI自定义节点插件，提供从URL加载多媒体资源、资源上传和内存管理等功能。

## 功能特性

### 📥 资源加载节点
- **Load Image From URL** - 从URL加载图片，支持自动缩放
- **Load Video From URL** - 从URL加载视频资源
- **Load Audio From URL** - 从URL加载音频资源

### 🚀 内存管理节点
- **深度内存清洗（容器优化）** - 8阶段终极清洗，完全卸载所有模型和张量，彻底释放 CPU/GPU 内存
  - ✅ 容器内可用，无需特殊权限
  - ✅ 自动调用 malloc_trim 归还内存
  - ✅ **解决工作流后内存不释放问题**
  - 💡 推荐：在每个工作流末尾添加此节点
  - 📖 详细说明：[内存释放完全指南](MEMORY_GUIDE.md)
  - 📖 容器环境：[容器内存清理指南](CONTAINER_MEMORY.md)

## 安装步骤

### 1. 克隆仓库
将本仓库克隆到ComfyUI的`custom_nodes`目录：
```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/chukangkang/comfui-url-resource-loader.git
```

### 2. 安装依赖
进入节点目录，安装Python依赖：
```bash
cd comfui-url-resource-loader
pip install -r requirements.txt
```

### 3. 重启ComfyUI
重启ComfyUI应用，新节点将自动加载

## 节点使用说明

### 📥 Load Image From URL
**功能：** 从URL直接加载图片

**输入参数：**
- `image_url` (STRING) - 图片的完整URL地址
- `width` (INT) - 目标宽度，0表示保持原始尺寸，默认：0
- `height` (INT) - 目标高度，0表示保持原始尺寸，默认：0

**输出：**
- `image` - 转换后的图片张量（RGB格式）
- `mask` - 对应的透明度掩码

**使用例：**
```
https://picsum.photos/800/600
```

### 🎬 Load Video From URL
**功能：** 从URL加载视频资源，支持多种视频格式

**输入参数：**
- `video_url` (STRING) - 视频的完整URL地址
- `fps` (INT) - 视频帧率，默认：30

**输出：**
- `VIDEO` - 视频帧序列

### 🔊 Load Audio From URL
**功能：** 从URL加载音频资源

**输入参数：**
- `audio_url` (STRING) - 音频的完整URL地址
- `channels` (INT) - 输出声道数（1=单声道，2=立体声），默认：1

**输出：**
- `AUDIO` - 音频数据
- `sr` - 采样率

### 🔄 Clear Memory & VRAM
**功能：** 清理系统内存和GPU显存

**输入参数：**
- `trigger` (BOOLEAN) - 触发清理操作，默认：True
- `clear_cpu_memory` (BOOLEAN) - 是否清理CPU内存，默认：True
- `clear_gpu_memory` (BOOLEAN) - 是否清理GPU显存，默认：True

**输出：**
- `status` (STRING) - 执行状态信息

**使用建议：** 在工作流最前面连接此节点，确保每次运行前释放资源

### 📤 Upload to OSS
**功能：** 上传文件到阿里云OSS存储

**输入参数（必填）：**
- `access_key_id` (STRING) - 阿里云AccessKeyId（STS临时凭证）
- `access_key_secret` (STRING) - 阿里云AccessKeySecret（STS临时凭证）
- `security_token` (STRING) - STS临时安全令牌
- `bucket_name` (STRING) - OSS Bucket名称
- `endpoint` (STRING) - OSS服务端点
- `task_id` (STRING) - 任务ID（用于文件路径组织）
- `file_list` (STRING) - 文件列表JSON（支持_metadata）
- `file_source_mode` (ENUM) - 文件获取模式：
  - `auto_scan` - **自动扫描output目录（推荐）**
  - `file_list` - 使用传入的file_list参数
  - `history_api` - 从ComfyUI History API自动获取当前工作流生成结果

**输入参数（可选）：**
- `images` (IMAGE) - 可选的图片张量输入
- `videos` (VIDEO) - 可选的视频输入
- `audios` (AUDIO) - 可选的音频输入
- `delete_after_upload` (BOOLEAN) - 上传后是否删除本地文件，默认：True
- `timeout_seconds` (INT) - 上传超时时间（秒），默认：300
- `auto_scan_pattern` (STRING) - 自动扫描的文件模式，默认：`*.*`
- `scan_subdirs` (BOOLEAN) - 是否扫描子目录，默认：True
- `min_file_time` (FLOAT) - 最小文件时间戳（Unix timestamp），只上传此时间之后的文件，默认：0.0（不过滤）
- `scan_delay` (FLOAT) - 扫描延迟（秒），等待文件完全生成后再扫描，默认：2.0
- `prompt_id` (STRING) - ComfyUI执行的prompt_id
  - **如果留空，自动获取最新工作流的执行结果**
  - **如果指定，获取特定工作流的执行结果**
  - 仅在history_api模式下使用

**输出：**
- `upload_result` (STRING) - JSON格式的上传结果，包含：
  - `status` - 上传状态（success/partial/error）
  - `task_id` - 任务ID
  - `uploaded_count` - 成功上传文件数
  - `failed_count` - 失败文件数
  - `total_size` - 总上传大小（字节）
  - `uploaded_files` - 已上传文件列表（包含 `oss_path`、`file_type` 等信息）
  - `failed_files` - 失败文件列表
  - `timestamp` - 时间戳

**OSS 文件路径结构：**

文件会按类型自动组织到子目录中：
- 图片：`outputs/{task_id}/image/{filename}`
- 视频：`outputs/{task_id}/video/{filename}`
- 音频：`outputs/{task_id}/audio/{filename}`
- 其他：`outputs/{task_id}/file/{filename}`

这种结构便于文件管理、分类和批量操作。

**使用场景：**

1. **使用auto_scan模式（推荐 - 避免时序问题）**
   ```json
   {
     "file_source_mode": "auto_scan",
     "auto_scan_pattern": "*.*",
     "scan_subdirs": true,
     "min_file_time": 1738570663.0,  // 只上传此时间戳之后的文件
     "scan_delay": 2.0  // 等待2秒让文件完全生成
   }
   ```
   
   **特点：**
   - ✅ 避免 prompt_id 时序问题
   - ✅ 通过时间戳过滤，只上传最新生成的文件
   - ✅ 简单可靠，不依赖 History API
   - ✅ 支持自定义文件模式和子目录扫描
   - ✅ 后端可传入工作流开始时间作为 min_file_time
   - ✅ **自动重试机制**：如果第一次没找到文件，会等待后重试最多3次

2. **使用history_api模式（自动获取当前工作流结果）**
   ```json
   {
     "file_source_mode": "history_api",
     "prompt_id": "",  // 留空，自动获取当前工作流的所有生成结果
     "file_list": "{}"  // 作为备用方案
   }
   ```
   
   **特点：**
   - ✅ 完全自动化，无需手动指定文件
   - ✅ 自动获取当前工作流的所有输出（图片、视频、音频等）
   - ✅ 支持自动检测最新的工作流执行
   - ⚠️ 可能存在时序问题（节点执行顺序导致 prompt_id 未生成）

3. **使用file_list模式（精确控制）**
   ```json
   {
     "file_source_mode": "file_list",
     "images": [
       {
         "filename": "output_001.png",
         "subfolder": "",
         "_metadata": {
           "filename": "output_001.png",
           "subfolder": "",
           "type": "output"
         }
       }
     ]
   }
   ```

**推荐使用 auto_scan + min_file_time 组合：**

后端在提交任务时记录当前时间戳，然后注入 OSS_Upload 节点时传入：

```python
import time

# 任务开始时记录时间戳
task_start_time = time.time()

# 注入 OSS_Upload 节点
oss_node = {
    "file_source_mode": "auto_scan",
    "min_file_time": task_start_time,  # 只上传任务开始后的文件
    ...
}
```

这样可以：
- ✅ 避免上传旧文件
- ✅ 避免 prompt_id 时序问题
- ✅ 保证只上传当前任务的输出

**_metadata支持：**
节点现在能够识别并处理file_list中的`_metadata`字段，优先使用metadata中的文件路径信息来定位文件。

### 📋 日志输出

OSS_Upload 节点使用 Python logging 模块输出日志，适用于 UI 和 API 模式：

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.INFO)

# 或者只启用 OSS_Upload 的日志
logging.getLogger("OSS_Upload").setLevel(logging.INFO)
```

日志包含：
- 节点执行开始/结束标记
- 输出目录内容列表
- 文件扫描过程和匹配结果
- 上传进度和结果
- 错误和警告信息

**环境变量：**
- `COMFYUI_HOST` - ComfyUI服务地址，默认：127.0.0.1
- `COMFYUI_PORT` - ComfyUI服务端口，默认：12800
- `COMFYUI_OUTPUT_DIR` - ComfyUI输出目录路径，默认：/root/ComfyUI/output

## 工作流示例

### 图片生成 + 自动上传到OSS
```
[Clear Memory & VRAM] 
    ↓
[Load Image From URL] (输入图片URL)
    ↓
[图片处理节点...]
    ↓
[Save Image]
    ↓
[Upload to OSS] (自动上传当前工作流生成的所有图片)
```

### 视频生成 + 自动上传到OSS
```
[Load Video From URL]
    ↓
[视频处理节点...]
    ↓
[Save Video]
    ↓
[Upload to OSS] (file_source_mode="history_api", prompt_id="")
```

### 多资源处理工作流
```
[Clear Memory & VRAM]
    ↓
┌─[Load Image From URL]
├─[Load Audio From URL]
└─[Load Video From URL]
    ↓
[合成/处理节点...]
    ↓
[保存节点...]
    ↓
[Upload to OSS] (自动上传所有生成的文件)
```

## 依赖列表

主要依赖包：
- `requests` - HTTP请求库，用于下载URL资源
- `torch` - PyTorch框架
- `torchvision` - 视觉处理库
- `numpy` - 数值计算库
- `Pillow` - 图像处理库
- `soundfile` - 音频文件处理
- `ffmpeg-python` - 视频处理支持
- `typing-extensions` - 类型注解扩展

## 项目结构

```
comfui-url-resource-loader/
├── __init__.py                 # 插件入口和节点注册
├── LoadImageFromURL.py         # 图片加载节点
├── LoadVideoFromURL.py         # 视频加载节点
├── LoadAudioFromURL.py         # 音频加载节点
├── ClearMemory.py              # 内存清理节点
├── oss_uploader.py             # OSS上传节点
├── url_resource_loader.py      # 通用资源加载工具
├── requirements.txt            # Python依赖列表
├── LICENSE                     # MIT许可证
└── README.md                   # 本文件
```

## 常见问题

### Q: 如何自动上传当前工作流生成的所有文件？
A: 使用OSS_Upload节点，设置`file_source_mode="history_api"`，并将`prompt_id`留空。节点会自动检测并上传当前工作流的所有输出文件。

### Q: 加载URL资源超时怎么办？
A: 检查网络连接，可在节点中调整超时时间参数（单位：秒）

### Q: 如何使用GPU加速视频处理？
A: 确保安装了CUDA版本的PyTorch，节点会自动检测并使用

### Q: 显存不足怎么办？
A: 在工作流前面使用"Clear Memory & VRAM"节点释放资源

### Q: OSS上传失败怎么办？
A: 检查阿里云凭证是否正确，确保Bucket名称和Endpoint配置无误。如果使用history_api模式，确保ComfyUI的History API可访问。

### Q: history_api模式如何工作？
A: 节点会调用ComfyUI的`/history`接口获取最新工作流执行记录，然后提取所有输出文件。如果提供了`prompt_id`，则获取指定工作流的输出。

## 许可证

MIT License - 详见LICENSE文件

## 贡献者

[chukangkang](https://github.com/chukangkang)

## 相关资源

- [ComfyUI官方文档](https://github.com/comfyanonymous/ComfyUI)
- [阿里云OSS文档](https://help.aliyun.com/product/31815.html)

---

**最后更新：2026年2月**
