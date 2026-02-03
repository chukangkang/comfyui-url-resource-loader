# OSS Upload 快速开始

## 最简单的用法：自动上传当前工作流生成的所有文件

### 步骤1：在ComfyUI工作流末尾添加OSS_Upload节点

在你的ComfyUI工作流中，添加"🔌 Upload to OSS"节点作为最后一个节点。

### 步骤2：配置OSS凭证

最少需要配置以下参数：

```json
{
  "file_source_mode": "history_api",
  "access_key_id": "你的临时AccessKeyId",
  "access_key_secret": "你的临时AccessKeySecret",
  "security_token": "你的STS Token",
  "bucket_name": "你的OSS Bucket名称",
  "endpoint": "oss-cn-hangzhou.aliyuncs.com",
  "task_id": "任务ID（用于组织文件路径）",
  "prompt_id": "",  # 留空，自动获取当前工作流
  "file_list": "{}"  # 作为备用方案
}
```

### 步骤3：运行工作流

执行工作流后，OSS_Upload节点会：

1. ✅ 自动检测当前工作流的执行ID
2. ✅ 从ComfyUI的History API获取所有生成的文件（图片、视频、音频等）
3. ✅ 将所有文件上传到OSS的`outputs/{task_id}/`路径下
4. ✅ 返回上传结果（包含OSS路径、文件大小等信息）

## 三种文件获取模式对比

### 1. history_api（推荐）- 最智能

```json
{
  "file_source_mode": "history_api",
  "prompt_id": ""  // 自动获取当前工作流
}
```

**优点：**
- ✅ 完全自动化，无需手动指定文件
- ✅ 获取当前工作流的所有输出
- ✅ 支持图片、视频、音频等多种类型

**适用场景：**
- 工作流集成，自动上传生成结果
- 不确定会生成哪些文件
- 需要上传工作流的所有输出

### 2. auto_scan - 最简单

```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.png",
  "scan_subdirs": true
}
```

**优点：**
- ✅ 简单直接，扫描output目录
- ✅ 支持通配符模式
- ✅ 可控制是否扫描子目录

**适用场景：**
- 上传output目录中的特定类型文件
- 批量上传已有文件
- 定期清理和归档

### 3. file_list - 最精确

```json
{
  "file_source_mode": "file_list",
  "file_list": "{\"images\":[{\"filename\":\"output.png\",\"subfolder\":\"\"}]}"
}
```

**优点：**
- ✅ 精确控制要上传的文件
- ✅ 支持metadata定位
- ✅ 与其他节点输出对接

**适用场景：**
- 只上传特定文件
- 从前置节点接收文件列表
- 需要精确控制上传内容

## 完整工作流示例

### 图片生成 + 自动上传

```python
{
  "1": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "example.png"
    }
  },
  "2": {
    "class_type": "ImageProcess",
    "inputs": {
      "image": ["1", 0]
    }
  },
  "3": {
    "class_type": "SaveImage",
    "inputs": {
      "images": ["2", 0],
      "filename_prefix": "processed_"
    }
  },
  "4": {
    "class_type": "OSS_Upload",
    "inputs": {
      "file_source_mode": "history_api",
      "access_key_id": "${OSS_ACCESS_KEY_ID}",
      "access_key_secret": "${OSS_ACCESS_KEY_SECRET}",
      "security_token": "${OSS_SECURITY_TOKEN}",
      "bucket_name": "my-comfyui-outputs",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "${TASK_ID}",
      "prompt_id": "",
      "file_list": "{}",
      "delete_after_upload": true
    }
  }
}
```

### 视频生成 + 自动上传

```python
{
  "1": {
    "class_type": "LoadVideo",
    "inputs": {
      "video": "input.mp4"
    }
  },
  "2": {
    "class_type": "VideoProcess",
    "inputs": {
      "video": ["1", 0]
    }
  },
  "3": {
    "class_type": "SaveVideo",
    "inputs": {
      "video": ["2", 0],
      "filename_prefix": "output_"
    }
  },
  "4": {
    "class_type": "OSS_Upload",
    "inputs": {
      "file_source_mode": "history_api",
      "access_key_id": "${OSS_ACCESS_KEY_ID}",
      "access_key_secret": "${OSS_ACCESS_KEY_SECRET}",
      "security_token": "${OSS_SECURITY_TOKEN}",
      "bucket_name": "my-comfyui-videos",
      "endpoint": "oss-cn-hangzhou.aliyuncs.com",
      "task_id": "${TASK_ID}",
      "prompt_id": "",
      "file_list": "{}",
      "delete_after_upload": true
    }
  }
}
```

## 环境变量配置

建议使用环境变量管理敏感信息：

```bash
# OSS凭证（临时凭证，建议通过STS获取）
export OSS_ACCESS_KEY_ID="STS.xxxxx"
export OSS_ACCESS_KEY_SECRET="xxxxxxxx"
export OSS_SECURITY_TOKEN="CAISxxxxxxxx"

# OSS配置
export OSS_BUCKET_NAME="my-bucket"
export OSS_ENDPOINT="oss-cn-hangzhou.aliyuncs.com"

# ComfyUI配置（如果不在本机）
export COMFYUI_HOST="127.0.0.1"
export COMFYUI_PORT="8188"
```

## 常见问题

### Q: 如何获取OSS临时凭证？

A: 使用阿里云STS服务获取临时凭证：

```python
from aliyunsdkcore.client import AcsClient
from aliyunsdksts.request.v20150401 import AssumeRoleRequest

client = AcsClient(
    '<your-access-key-id>',
    '<your-access-key-secret>',
    'cn-hangzhou'
)

request = AssumeRoleRequest.AssumeRoleRequest()
request.set_RoleArn('<role-arn>')
request.set_RoleSessionName('comfyui-upload')
request.set_DurationSeconds(3600)

response = client.do_action_with_exception(request)
```

### Q: 如何知道文件是否上传成功？

A: 检查节点的输出（upload_result），它会返回详细的上传结果：

```json
{
  "status": "success",
  "uploaded_count": 3,
  "failed_count": 0,
  "uploaded_files": [
    {
      "filename": "output_001.png",
      "oss_path": "outputs/task_123/output_001.png",
      "size": 524288
    }
  ]
}
```

### Q: 如何避免上传重复文件？

A: 使用唯一的task_id，每次执行使用不同的ID：

```python
import uuid
task_id = str(uuid.uuid4())
```

### Q: prompt_id 留空安全吗？

A: 是的！节点会自动获取最新的工作流执行结果。如果你需要上传特定工作流的结果，可以明确指定prompt_id。

### Q: 能否只上传特定类型的文件？

A: 使用`auto_scan`模式配合文件模式：

```json
{
  "file_source_mode": "auto_scan",
  "auto_scan_pattern": "*.mp4"  // 只上传MP4视频
}
```

## 获取帮助

- 查看详细文档：[OSS_UPLOAD_EXAMPLES.md](OSS_UPLOAD_EXAMPLES.md)
- 问题反馈：在项目仓库提交Issue
- 日志查看：检查ComfyUI控制台输出

---

**最后更新：2026年2月3日**
