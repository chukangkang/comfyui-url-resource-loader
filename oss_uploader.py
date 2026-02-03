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
import glob
import requests
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
        self.comfyui_host = os.getenv("COMFYUI_HOST", "127.0.0.1")
        self.comfyui_port = os.getenv("COMFYUI_PORT", "12800")
    
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
                
                # 新增：文件获取模式
                "file_source_mode": (["file_list", "auto_scan", "history_api"],),
            },
            "optional": {
                # 可选的文件输入（支持直接传入张量）
                "images": ("IMAGE",),
                "videos": ("VIDEO",),
                "audios": ("AUDIO",),
                
                # 选项
                "delete_after_upload": ("BOOLEAN", {"default": True}),
                "timeout_seconds": ("INT", {"default": 300}),
                
                # History API 相关
                "prompt_id": ("STRING", {"default": ""}),  # ComfyUI workflow执行的prompt_id
                "auto_scan_pattern": ("STRING", {"default": "*.*"}),  # 自动扫描的文件模式
                "scan_subdirs": ("BOOLEAN", {"default": True}),  # 是否扫描子目录
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
        file_source_mode: str = "file_list",
        images=None,
        videos=None,
        audios=None,
        delete_after_upload: bool = True,
        timeout_seconds: int = 300,
        prompt_id: str = "",
        auto_scan_pattern: str = "*.*",
        scan_subdirs: bool = True,
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
            file_source_mode: 文件获取模式 (file_list/auto_scan/history_api)
            delete_after_upload: 上传后是否删除本地文件
            timeout_seconds: 上传超时时间
            prompt_id: ComfyUI prompt ID (用于history API)
            auto_scan_pattern: 自动扫描文件模式
            scan_subdirs: 是否扫描子目录
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
            
            # 根据模式获取文件列表
            if file_source_mode == "history_api":
                files_info = self._get_files_from_history_api(prompt_id, file_list)
            elif file_source_mode == "auto_scan":
                files_info = self._scan_output_directory(auto_scan_pattern, scan_subdirs)
            else:  # file_list
                files_info = self._parse_file_list(file_list)
            
            if not files_info:
                return (json.dumps({
                    "status": "error",
                    "message": f"No files found with mode: {file_source_mode}"
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
    
    def _parse_file_list(self, file_list: str) -> Dict[str, List[Dict]]:
        """解析file_list字符串，提取文件信息"""
        try:
            files_info = json.loads(file_list)
            
            # 处理带有_metadata的文件列表
            processed_files = {}
            for file_type, file_list_data in files_info.items():
                if not isinstance(file_list_data, list):
                    continue
                
                processed_list = []
                for file_info in file_list_data:
                    # 如果有_metadata，优先使用metadata中的信息
                    if isinstance(file_info, dict) and "_metadata" in file_info:
                        metadata = file_info["_metadata"]
                        processed_list.append({
                            "filename": metadata.get("filename", file_info.get("filename")),
                            "subfolder": metadata.get("subfolder", file_info.get("subfolder", "")),
                            "type": metadata.get("type", file_type),
                        })
                    elif isinstance(file_info, dict):
                        processed_list.append(file_info)
                    elif isinstance(file_info, str):
                        # 如果只是字符串，直接作为文件名
                        processed_list.append({"filename": file_info, "subfolder": ""})
                
                if processed_list:
                    processed_files[file_type] = processed_list
            
            return processed_files
        except json.JSONDecodeError as e:
            print(f"Failed to parse file_list: {e}")
            return {}
    
    def _scan_output_directory(self, pattern: str = "*.*", scan_subdirs: bool = True) -> Dict[str, List[Dict]]:
        """自动扫描output目录，获取文件列表"""
        files_info = {}
        
        try:
            # 根据是否扫描子目录选择不同的glob模式
            if scan_subdirs:
                search_pattern = os.path.join(self.output_dir, "**", pattern)
                file_paths = glob.glob(search_pattern, recursive=True)
            else:
                search_pattern = os.path.join(self.output_dir, pattern)
                file_paths = glob.glob(search_pattern)
            
            # 按文件类型分类
            for file_path in file_paths:
                if not os.path.isfile(file_path):
                    continue
                
                filename = os.path.basename(file_path)
                # 计算相对于output_dir的子文件夹路径
                rel_path = os.path.relpath(os.path.dirname(file_path), self.output_dir)
                subfolder = "" if rel_path == "." else rel_path
                
                # 根据扩展名分类
                ext = Path(filename).suffix.lower()
                file_type = self._classify_file_type(ext)
                
                if file_type not in files_info:
                    files_info[file_type] = []
                
                files_info[file_type].append({
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": file_type
                })
            
            return files_info
        except Exception as e:
            print(f"Failed to scan output directory: {e}")
            return {}
    
    def _get_files_from_history_api(self, prompt_id: str, fallback_file_list: str) -> Dict[str, List[Dict]]:
        """从ComfyUI的history API获取当前工作流生成的文件列表"""
        
        # 如果没有提供prompt_id，尝试获取最新的
        if not prompt_id:
            print("No prompt_id provided, trying to get latest from history API...")
            prompt_id = self._get_latest_prompt_id()
            
            if not prompt_id:
                print("Could not get latest prompt_id, falling back to file_list")
                return self._parse_file_list(fallback_file_list)
        
        try:
            # 调用ComfyUI history API获取特定prompt的执行结果
            url = f"http://{self.comfyui_host}:{self.comfyui_port}/history/{prompt_id}"
            print(f"Fetching workflow outputs from history API: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"History API returned status {response.status_code}, falling back to file_list")
                return self._parse_file_list(fallback_file_list)
            
            history_data = response.json()
            
            # 解析history数据，提取所有输出文件
            files_info = {}
            if prompt_id in history_data:
                outputs = history_data[prompt_id].get("outputs", {})
                print(f"Found {len(outputs)} output nodes in workflow execution")
                
                for node_id, node_output in outputs.items():
                    # 处理images
                    if "images" in node_output:
                        if "images" not in files_info:
                            files_info["images"] = []
                        for img in node_output["images"]:
                            file_info = {
                                "filename": img.get("filename"),
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")
                            }
                            files_info["images"].append(file_info)
                            print(f"  Found image: {file_info['subfolder']}/{file_info['filename']}")
                    
                    # 处理videos和gifs
                    if "videos" in node_output or "gifs" in node_output:
                        if "videos" not in files_info:
                            files_info["videos"] = []
                        videos = node_output.get("videos", []) + node_output.get("gifs", [])
                        for video in videos:
                            file_info = {
                                "filename": video.get("filename"),
                                "subfolder": video.get("subfolder", ""),
                                "type": video.get("type", "output")
                            }
                            files_info["videos"].append(file_info)
                            print(f"  Found video: {file_info['subfolder']}/{file_info['filename']}")
                    
                    # 处理audios
                    if "audios" in node_output:
                        if "audios" not in files_info:
                            files_info["audios"] = []
                        for audio in node_output["audios"]:
                            file_info = {
                                "filename": audio.get("filename"),
                                "subfolder": audio.get("subfolder", ""),
                                "type": audio.get("type", "output")
                            }
                            files_info["audios"].append(file_info)
                            print(f"  Found audio: {file_info['subfolder']}/{file_info['filename']}")
            
            # 如果没有从history获取到文件，回退到file_list
            if not files_info:
                print("No files found in history API output, falling back to file_list")
                return self._parse_file_list(fallback_file_list)
            
            total_files = sum(len(v) for v in files_info.values())
            print(f"Successfully retrieved {total_files} files from workflow execution (prompt_id: {prompt_id})")
            return files_info
            
        except Exception as e:
            import traceback
            print(f"Failed to fetch from history API: {e}")
            print(traceback.format_exc())
            print("Falling back to file_list")
            return self._parse_file_list(fallback_file_list)
    
    def _get_latest_prompt_id(self) -> Optional[str]:
        """获取最新的prompt_id"""
        try:
            # 获取所有history
            url = f"http://{self.comfyui_host}:{self.comfyui_port}/history"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            history_data = response.json()
            
            # history_data是一个字典，key是prompt_id
            # 我们需要找到最新的一个（通过timestamp或直接取第一个）
            if not history_data:
                return None
            
            # 获取所有prompt_id并按时间排序（假设返回的是有序的）
            prompt_ids = list(history_data.keys())
            if prompt_ids:
                latest_prompt_id = prompt_ids[0]  # 通常第一个是最新的
                print(f"Auto-detected latest prompt_id: {latest_prompt_id}")
                return latest_prompt_id
            
            return None
            
        except Exception as e:
            print(f"Failed to get latest prompt_id: {e}")
            return None
    
    @staticmethod
    def _classify_file_type(ext: str) -> str:
        """根据文件扩展名分类文件类型"""
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff"}
        video_exts = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg"}
        audio_exts = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".aiff"}
        
        if ext in image_exts:
            return "images"
        elif ext in video_exts:
            return "videos"
        elif ext in audio_exts:
            return "audios"
        else:
            return "files"
    
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
                    
                    # 构建 OSS 路径，包含文件类型子目录
                    # 根据文件类型组织目录结构：outputs/{task_id}/{file_type}/{filename}
                    # 例如：outputs/task123/audio/file.mp3, outputs/task123/images/img.png
                    if file_type in ["images", "videos", "audios", "files"]:
                        # 单数形式的文件类型名，去掉末尾的 's'
                        type_folder = file_type.rstrip('s') if file_type != "audios" else "audio"
                        if file_type == "images":
                            type_folder = "image"
                        elif file_type == "videos":
                            type_folder = "video"
                        elif file_type == "files":
                            type_folder = "file"
                        oss_path = f"outputs/{task_id}/{type_folder}/{filename}"
                    else:
                        # 未知类型，直接放在根目录
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
                        "content_type": content_type,
                        "file_type": file_type  # 添加文件类型信息，方便验证
                    })
                    
                    print(f"✅ Uploaded: {filename} -> {oss_path} ({file_size} bytes)")
                    
                except Exception as e:
                    import traceback
                    error_msg = str(e)
                    failed_files.append({
                        "filename": filename,
                        "reason": error_msg
                    })
                    print(f"❌ Failed to upload {filename}: {error_msg}")
                    print(traceback.format_exc())
        
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
