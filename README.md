# ComfyUI URL资源加载器

一个功能完整的ComfyUI自定义节点插件，提供从URL加载多媒体资源、资源上传和内存管理等功能。

## 功能特性

### 📥 资源加载节点
- **Load Image From URL** - 从URL加载图片，支持自动缩放
- **Load Video From URL** - 从URL加载视频资源
- **Load Audio From URL** - 从URL加载音频资源
- **🔄 Clear Memory & VRAM** - 清理CPU内存和GPU显存（工作流前置）

### 📤 资源上传节点
- **Upload to OSS** - 上传文件到阿里云OSS

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

**输入参数：**
- `local_path` (STRING) - 本地文件路径
- `oss_path` (STRING) - OSS中的目标路径
- `access_key_id` (STRING) - 阿里云AccessKeyId
- `access_key_secret` (STRING) - 阿里云AccessKeySecret
- `bucket_name` (STRING) - OSS Bucket名称
- `endpoint` (STRING) - OSS服务端点

**输出：**
- `status` (STRING) - 上传状态

## 工作流示例

### 基础图片加载工作流
```
[Clear Memory & VRAM] 
    ↓
[Load Image From URL] (输入图片URL)
    ↓
[其他处理节点...]
```

### 多资源加载工作流
```
[Clear Memory & VRAM]
    ↓
┌─[Load Image From URL]
├─[Load Audio From URL]
└─[Load Video From URL]
    ↓
[合成/处理节点...]
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

### Q: 加载URL资源超时怎么办？
A: 检查网络连接，可在节点中调整超时时间参数（单位：秒）

### Q: 如何使用GPU加速视频处理？
A: 确保安装了CUDA版本的PyTorch，节点会自动检测并使用

### Q: 显存不足怎么办？
A: 在工作流前面使用"Clear Memory & VRAM"节点释放资源

### Q: OSS上传失败怎么办？
A: 检查阿里云凭证是否正确，确保Bucket名称和Endpoint配置无误

## 许可证

MIT License - 详见LICENSE文件

## 贡献者

[chukangkang](https://github.com/chukangkang)

## 相关资源

- [ComfyUI官方文档](https://github.com/comfyanonymous/ComfyUI)
- [阿里云OSS文档](https://help.aliyun.com/product/31815.html)

---

**最后更新：2026年2月**
