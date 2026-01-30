# ComfyUI URL 资源加载器

> 一套强大的 ComfyUI 自定义节点，支持从 URL 加载图片、视频、音频资源，以及上传生成结果到阿里云 OSS。

## 📋 功能特性

### 🖼️ 节点列表

| 节点名称 | 功能描述 | 支持格式 |
|---------|---------|---------|
| **Load Image From URL** | 从 URL 加载图片并支持缩放 | jpg, png, gif, bmp, webp, svg, tiff |
| **Load Video From URL** | 从 URL 加载视频（支持临时文件或永久保存） | mp4, webm, mov, avi, mkv, flv, mpeg, mpg, wmv |
| **Load Audio From URL** | 从 URL 加载音频并标准化采样率 | mp3, wav, flac, ogg, m4a, aiff, wma |
| **URL 资源加载器** | 通用加载器（自动识别图片/音频） | jpg, png, mp3, wav, flac, ogg, m4a |
| **OSS Upload** | 上传输出文件到阿里云 OSS | 所有文件格式 |

### ✨ 核心特性

- ✅ **自动格式识别** - 智能识别 URL 资源类型
- ✅ **异步加载** - 高效的异步网络请求处理
- ✅ **灵活输出** - 支持多种输出格式和参数配置
- ✅ **容错处理** - 完善的错误捕获和日志输出
- ✅ **阿里云 OSS 集成** - 一键上传到 OSS 存储
- ✅ **老版本兼容** - 支持传统 ComfyUI 节点格式

---

## 📦 安装方法

### 方法1：克隆仓库到 custom_nodes

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/chukangkang/comfyui-url-resource-loader.git
cd comfyui-url-resource-loader
pip install -r requirements.txt
```

### 方法2：手动下载

1. 下载本仓库 ZIP 文件
2. 解压到 `ComfyUI/custom_nodes/` 目录
3. 运行命令安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

### 依赖要求

- Python 3.8+
- ComfyUI（最新版本推荐）
- requests >= 2.31.0
- typing-extensions >= 4.5.0

**可选优化依赖：**
```bash
pip install soundfile ffmpeg-python
```

---

## 🚀 快速开始

### 1. Load Image From URL（图片加载）

**功能：** 从 URL 加载图片并支持宽高调整

**输入参数：**
- `image_url` (STRING) - 图片 URL 地址
- `width` (INT, 0-8192) - 目标宽度（0 = 保持原宽）
- `height` (INT, 0-8192) - 目标高度（0 = 保持原高）

**输出：**
- `image` - 图片张量 (B,H,W,C) 格式
- `mask` - 掩码张量

**示例 URL：**
```
https://picsum.photos/800/600
https://example.com/image.jpg
```

---

### 2. Load Video From URL（视频加载）

**功能：** 从 URL 加载视频，支持临时或永久保存

**输入参数：**
- `video_url` (STRING) - 视频 URL 地址
- `save_to_input_folder` (BOOLEAN) - 是否保存到 ComfyUI 输入文件夹
- `filename` (STRING) - 保存文件名（无需扩展名）

**输出：**
- `video` - 视频对象

**支持格式：** mp4, webm, mov, avi, mkv, flv, mpeg, mpg, wmv

**特性：**
- 自动识别视频格式和扩展名
- 8KB 分块下载（适合大文件）
- 自动避免文件名冲突
- 5分钟下载超时保护

---

### 3. Load Audio From URL（音频加载）

**功能：** 从 URL 加载音频，自动转换采样率

**输入参数：**
- `audio_url` (STRING) - 音频 URL 地址

**输出：**
- `audio` - 音频张量 + 采样率

**特性：**
- 自动转换为 16000Hz 采样率（标准化）
- 支持多种音频格式解码
- SSL 校验禁用（适配 CDN）
- 自动重试机制（最多 2 次）

**支持格式：** mp3, wav, flac, ogg, m4a, aiff, wma

---

### 4. URL 资源加载器（通用加载器）

**功能：** 智能识别并加载图片或音频资源

**输入参数：**
- `url` (STRING) - 资源 URL 地址
- `timeout` (INT) - 请求超时时间（1-60秒）
- `audio_output_format` (CHOICE) - dict 或 tuple
- `audio_channels` (CHOICE) - 1 (单声道) 或 2 (立体声)

**输出：**
- `image` - 图片张量（图片时）
- `audio` - 音频对象（音频时）
- `info` - 加载状态信息

---

### 5. OSS Upload（上传到阿里云 OSS）

**功能：** 将生成的文件上传到阿里云 OSS 存储

**输入参数：**
- `access_key_id` - 阿里云临时 AccessKeyId
- `access_key_secret` - 阿里云临时 AccessKeySecret
- `security_token` - STS 临时安全令牌
- `bucket_name` - OSS bucket 名称
- `endpoint` - OSS endpoint (如: oss-cn-hangzhou.aliyuncs.com)
- `task_id` - 任务 ID（用于组织上传文件）
- `file_list` - 文件列表 JSON
- `delete_after_upload` - 上传后删除本地文件

**输出：**
- 上传结果 JSON（包含成功/失败统计）

**文件列表格式：**
```json
{
  "images": [
    {"filename": "output.png", "subfolder": ""}
  ],
  "videos": [
    {"filename": "video.mp4", "subfolder": "outputs"}
  ]
}
```

---

## 🛠️ 工作流示例

### 示例 1：加载并处理网络图片

```
Load Image From URL (URL: https://picsum.photos/800/600)
    ↓
[IMAGE 张量输出]
    ↓
[其他 ComfyUI 节点处理]
```

### 示例 2：加载视频并保存

```
Load Video From URL (URL: https://example.com/video.mp4, save_to_input_folder: true)
    ↓
[VIDEO 对象输出]
    ↓
[VHS VideoCombine 或其他视频处理]
```

### 示例 3：加载音频并生成

```
Load Audio From URL (URL: https://example.com/audio.wav)
    ↓
[AUDIO 对象输出]
    ↓
[音频相关节点处理]
```

### 示例 4：完整工作流（加载+生成+上传）

```
Load Image From URL
    ↓
[KSampler - 图生图]
    ↓
[Save Image]
    ↓
OSS Upload (task_id: "batch_123")
```

---

## ⚙️ 配置说明

### 环境变量（可选）

```bash
# ComfyUI 输入/输出目录
COMFYUI_INPUT_DIR=/path/to/ComfyUI/input
COMFYUI_OUTPUT_DIR=/path/to/ComfyUI/output
```

### 性能优化

- **大文件下载** - 使用 8KB 分块，支持断点续传
- **并发请求** - aiohttp 异步会话，充分利用事件循环
- **缓存机制** - 支持 ComfyUI 原生缓存指纹

---

## 🐛 常见问题

### Q: 为什么加载失败显示 "Module not found"?

**A:** 确保已安装依赖：
```bash
pip install -r requirements.txt
```

### Q: 支持 HTTPS 自签名证书吗?

**A:** 支持。音频加载器已禁用 SSL 验证，适配 CDN。

### Q: 视频加载后文件在哪里?

**A:** 
- `save_to_input_folder=True` → 保存到 ComfyUI 输入文件夹
- `save_to_input_folder=False` → 临时文件（会话结束自动删除）

### Q: OSS 上传需要什么凭证?

**A:** 需要阿里云 STS 临时凭证（推荐）：
- AccessKeyId
- AccessKeySecret  
- SecurityToken

### Q: 支持代理吗?

**A:** 支持。在系统环境变量中设置：
```bash
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=http://proxy:8080
```

---

## 📝 节点对比表

| 功能 | Load Image | Load Video | Load Audio | URL Loader | OSS Upload |
|-----|-----------|-----------|-----------|-----------|-----------|
| 图片加载 | ✅ | ❌ | ❌ | ✅ | ❌ |
| 视频加载 | ❌ | ✅ | ❌ | ❌ | ❌ |
| 音频加载 | ❌ | ❌ | ✅ | ✅ | ❌ |
| 宽高调整 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 自动保存 | ❌ | ✅ | ❌ | ❌ | ❌ |
| 采样率转换 | ❌ | ❌ | ✅ | ❌ | ❌ |
| 格式自动识别 | ❌ | ❌ | ❌ | ✅ | ❌ |
| OSS 上传 | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 📄 版本历史

### v1.1.0 (当前版本)
- ✅ 新增 Load Video From URL 节点
- ✅ 优化异步加载机制
- ✅ 整合 OSS Upload 节点
- ✅ 完整的错误处理和日志
- ✅ 支持老版本 ComfyUI 节点格式

### v1.0.0
- ✅ 初始版本
- ✅ Load Image From URL 节点
- ✅ Load Audio From URL 节点
- ✅ URL Resource Loader 节点

---

## 📧 支持与反馈

- **GitHub Issues** - [提交 Bug 或建议](https://github.com/chukangkang/comfyui-url-resource-loader/issues)
- **Email** - chukangkang@example.com

---

## 📜 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🎉 致谢

感谢 ComfyUI 社区的支持！

**相关资源：**
- [ComfyUI 官网](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI 自定义节点指南](https://github.com/comfyanonymous/ComfyUI/wiki/Custom-Nodes)
- [阿里云 OSS SDK](https://github.com/aliyun/aliyun-oss-python-sdk)
