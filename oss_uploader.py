"""
ComfyUI Custom Node - 通用 OSS 上传节点
将任务输出直接上传到阿里云 OSS
支持：图片、视频、音频、任意文件
"""

from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# 导入ComfyUI核心模块
try:
    from typing_extensions import override
    from comfy_api.latest import ComfyExtension, io as ComfyIO
    import oss2
    HAVE_OSS2 = True
except ImportError as e:
    HAVE_OSS2 = False
    # 允许模块加载，但在使用时才报错


class OSS_Upload:
    """
    ComfyUI 自定义节点 - 上传输出到 OSS
    
    这个节点通常由 API 自动添加到 workflow 的末尾
    在所有其他节点执行完后，将输出上传到 OSS
    """
    
    def __init__(self):
        self.output_dir = "/root/ComfyUI/output"
        if not os.path.exists(self.output_dir):
            self.output_dir = "./output"
    
    @classmethod
    def INPUT_TYPES(cls):
        """定义节点的输入参数"""
        return {
            "required": {
                # 从 API 获得的临时凭证
                "access_key_id": ("STRING",),
                "access_key_secret": ("STRING",),
                "security_token": ("STRING",),  # STS Token（有效期短）
                
                # OSS 配置
                "bucket_name": ("STRING",),
                "endpoint": ("STRING",),
                "task_id": ("STRING",),
                
                # 文件信息（JSON 格式）
                "file_list": ("STRING",),  # JSON: {"images": [...], "videos": [...]}
            },
            "optional": {
                # 可选的文件输入（支持直接传入张量）
                "images": ("IMAGE",),
                "videos": ("VIDEO",),
                "audios": ("AUDIO",),
                
                # 选项
                "delete_after_upload": ("BOOLEAN", {"default": True}),
                "timeout_seconds": ("INT", {"default": 300}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("upload_result",)
    FUNCTION = "upload"
    CATEGORY = "storage/oss"
    OUTPUT_NODE = True  # 这是一个输出节点
    
    def upload(
        self,
        access_key_id: str,
        access_key_secret: str,
        security_token: str,
        bucket_name: str,
        endpoint: str,
        task_id: str,
        file_list: str,
        images=None,
        videos=None,
        audios=None,
        delete_after_upload: bool = True,
        timeout_seconds: int = 300,
    ) -> Tuple[str]:
        """
        主上传函数
        
        Args:
            access_key_id: 临时 AccessKeyId
            access_key_secret: 临时 AccessKeySecret
            security_token: STS 临时安全令牌
            bucket_name: OSS bucket 名称
            endpoint: OSS endpoint
            task_id: 任务 ID
            file_list: 文件列表 JSON
            delete_after_upload: 上传后是否删除本地文件
            timeout_seconds: 上传超时时间
        """
        
        try:
            if not HAVE_OSS2:
                return (json.dumps({
                    "status": "error",
                    "message": "oss2 module not found, please install: pip install oss2"
                }),)
            
            # 初始化 OSS 客户端（使用 STS 临时凭证）
            oss_client = self._init_oss_client(
                access_key_id,
                access_key_secret,
                security_token,
                endpoint
            )
            
            # 解析文件列表
            try:
                files_info = json.loads(file_list)
            except json.JSONDecodeError:
                return (json.dumps({
                    "status": "error",
                    "message": f"Invalid file_list JSON: {file_list}"
                }),)
            
            # 执行上传
            upload_result = self._upload_files(
                oss_client,
                bucket_name,
                task_id,
                files_info,
                delete_after_upload,
                timeout_seconds
            )
            
            return (json.dumps(upload_result),)
        
        except Exception as e:
            import traceback
            return (json.dumps({
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }),)
    
    @staticmethod
    def _init_oss_client(access_key_id: str, access_key_secret: str, 
                        security_token: str, endpoint: str):
        """初始化 OSS 客户端（STS 临时凭证）"""
        auth = oss2.Auth(
            access_key_id,
            access_key_secret,
            security_token  # STS Token
        )
        return oss2.Bucket(auth, f"http://{endpoint}", "")
    
    def _upload_files(
        self,
        oss_client,
        bucket_name: str,
        task_id: str,
        files_info: Dict[str, List[Dict]],
        delete_after_upload: bool,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """上传文件到 OSS"""
        
        uploaded_files = []
        failed_files = []
        total_size = 0
        
        # 遍历所有文件类型
        for file_type, file_list in files_info.items():
            if not isinstance(file_list, list):
                continue
            
            for file_info in file_list:
                filename = file_info.get("filename")
                subfolder = file_info.get("subfolder", "")
                
                if not filename:
                    continue
                
                try:
                    # 构建本地路径
                    if subfolder:
                        local_path = os.path.join(self.output_dir, subfolder, filename)
                    else:
                        local_path = os.path.join(self.output_dir, filename)
                    
                    # 检查文件是否存在
                    if not os.path.exists(local_path):
                        failed_files.append({
                            "filename": filename,
                            "reason": "File not found"
                        })
                        continue
                    
                    # 构建 OSS 路径
                    oss_path = f"outputs/{task_id}/{filename}"
                    
                    # 获取文件大小和 Content-Type
                    file_size = os.path.getsize(local_path)
                    content_type = self._get_content_type(filename)
                    
                    # 上传文件
                    with open(local_path, "rb") as f:
                        oss_client.put_object(
                            bucket_name,
                            oss_path,
                            f,
                            headers={"Content-Type": content_type}
                        )
                    
                    total_size += file_size
                    
                    # 删除本地文件（可选）
                    if delete_after_upload:
                        try:
                            os.remove(local_path)
                        except:
                            pass
                    
                    uploaded_files.append({
                        "filename": filename,
                        "oss_path": oss_path,
                        "size": file_size,
                        "content_type": content_type
                    })
                    
                except Exception as e:
                    failed_files.append({
                        "filename": filename,
                        "reason": str(e)
                    })
        
        return {
            "status": "success" if not failed_files else "partial",
            "task_id": task_id,
            "uploaded_count": len(uploaded_files),
            "failed_count": len(failed_files),
            "total_size": total_size,
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _get_content_type(filename: str) -> str:
        """根据文件扩展名获取 Content-Type"""
        ext = Path(filename).suffix.lower()
        
        content_types = {
            # 图片
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".tiff": "image/tiff",
            
            # 视频
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".flv": "video/x-flv",
            ".wmv": "video/x-ms-wmv",
            ".webm": "video/webm",
            ".m4v": "video/x-m4v",
            ".mpg": "video/mpeg",
            ".mpeg": "video/mpeg",
            
            # 音频
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".aac": "audio/aac",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".wma": "audio/x-ms-wma",
            ".aiff": "audio/aiff",
            
            # 其他
            ".txt": "text/plain",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
            ".gz": "application/gzip",
        }
        
        return content_types.get(ext, "application/octet-stream")


# 节点导出
NODE_CLASS_MAPPINGS = {
    "OSS_Upload": OSS_Upload
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OSS_Upload": "🔌 OSS Upload"
}

# ---------------------------
# 扩展注册（ComfyUI必需）
# ---------------------------
class OSS_UploadExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[ComfyIO.ComfyNode]]:
        return [OSS_Upload]

# ---------------------------
# 入口函数（ComfyUI扩展标准）
# ---------------------------
async def comfy_entrypoint() -> OSS_UploadExtension:
    print("[OSS_Upload] Extension loaded successfully!")
    return OSS_UploadExtension()
