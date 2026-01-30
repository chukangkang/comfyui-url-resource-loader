# 文件名：LoadVideoFromURL.py
# 放置路径：ComfyUI/custom_nodes/LoadVideoFromURL.py

from __future__ import annotations
import os
import sys
import tempfile
import hashlib
import asyncio

# 将ComfyUI主目录添加到Python路径
comfy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if comfy_path not in sys.path:
    sys.path.insert(0, comfy_path)

# 导入ComfyUI核心模块（兼容新老版本）
_import_error = None
try:
    import folder_paths
except ImportError as e:
    folder_paths = None
    _import_error = e

try:
    import aiohttp
except ImportError as e:
    aiohttp = None
    _import_error = e

try:
    from comfy_api.latest import io, InputImpl
    _USE_NEW_API = True
except Exception:
    io = None
    InputImpl = None
    _USE_NEW_API = False


if _USE_NEW_API:
    class LoadVideoFromURL(io.ComfyNode):
        @classmethod
        def define_schema(cls):
            return io.Schema(
                node_id="LoadVideoFromURL",
                display_name="Load Video From URL",
                category="image/video",
                description="Load a video from a remote URL (supports http/https)",
                inputs=[
                    io.String.Input("video_url", default="", tooltip="视频 URL，例如 https://example.com/video.mp4"),
                    io.Boolean.Input("save_to_input_folder", default=False, tooltip="是否保存到 ComfyUI 输入文件夹"),
                    io.String.Input("filename", default="downloaded_video", tooltip="保存的文件名（不含扩展名）"),
                ],
                outputs=[
                    io.Video.Output(),
                ],
            )

        @classmethod
        def execute(cls, video_url: str, save_to_input_folder: bool, filename: str) -> io.NodeOutput:
            async def _run():
                return await cls._download_video_async(video_url, save_to_input_folder, filename)

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            video_path = loop.run_until_complete(_run())
            video_object = InputImpl.VideoFromFile(video_path)
            return io.NodeOutput(video_object)

        @classmethod
        async def _download_video_async(cls, video_url: str, save_to_input_folder: bool, filename: str) -> str:
            if not video_url:
                raise ValueError("Video URL cannot be empty")
            if not video_url.startswith(('http://', 'https://')):
                raise ValueError("URL must start with http:// or https://")

            temp_file = None
            video_path = ""
            try:
                if aiohttp is None:
                    raise RuntimeError("aiohttp not installed")

                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(video_url) as response:
                        response.raise_for_status()

                        file_ext = '.mp4'
                        if '.' in video_url:
                            url_ext = video_url.split('.')[-1].split('?')[0].lower()
                            supported_exts = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'mpeg', 'mpg', 'wmv']
                            if url_ext in supported_exts:
                                file_ext = f'.{url_ext}'

                        if save_to_input_folder:
                            input_dir = folder_paths.get_input_directory()
                            os.makedirs(input_dir, exist_ok=True)
                            video_path = os.path.join(input_dir, f"{filename}{file_ext}")
                            counter = 1
                            while os.path.exists(video_path):
                                video_path = os.path.join(input_dir, f"{filename}_{counter}{file_ext}")
                                counter += 1
                            with open(video_path, 'wb') as f:
                                downloaded_size = 0
                                while True:
                                    chunk = await response.content.read(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                        else:
                            temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False, mode='wb')
                            with temp_file:
                                downloaded_size = 0
                                while True:
                                    chunk = await response.content.read(8192)
                                    if not chunk:
                                        break
                                    temp_file.write(chunk)
                                    downloaded_size += len(chunk)
                            video_path = temp_file.name

                return video_path
            except Exception as e:
                if temp_file and os.path.exists(getattr(temp_file, 'name', '')):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                raise RuntimeError(f"Failed to load video: {e}")

        @classmethod
        def fingerprint_inputs(cls, video_url: str, save_to_input_folder: bool, filename: str):
            fingerprint_data = f"{video_url}|{save_to_input_folder}|{filename}".encode('utf-8')
            return hashlib.md5(fingerprint_data).hexdigest()

        @classmethod
        def validate_inputs(cls, video_url: str, save_to_input_folder: bool, filename: str):
            if not video_url:
                return "Error: Video URL cannot be empty!"
            if not video_url.startswith(('http://', 'https://')):
                return "Error: URL must start with http:// or https://!"
            invalid_chars = r'\\/:*?"<>|'
            if save_to_input_folder and filename and any(c in filename for c in invalid_chars):
                return f"Error: Filename cannot contain these characters: {invalid_chars}!"
            return True
else:
    class LoadVideoFromURL:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "video_url": ("STRING", {"default": "", "multiline": False}),
                    "save_to_input_folder": ("BOOLEAN", {"default": False}),
                    "filename": ("STRING", {"default": "downloaded_video", "multiline": False}),
                }
            }

        RETURN_TYPES = ("VIDEO",)
        RETURN_NAMES = ("video",)
        FUNCTION = "load_video"
        CATEGORY = "image/video"

        def load_video(self, video_url: str, save_to_input_folder: bool, filename: str):
            if _import_error:
                raise RuntimeError(f"Missing dependency: {_import_error}")
            # 延迟导入，避免旧版无法加载模块时阻断节点注册
            try:
                from comfy_api.latest import InputImpl as _InputImpl
            except Exception as e:
                raise RuntimeError(f"Missing comfy_api.latest: {e}")

            async def _run():
                return await self._download_video_async(video_url, save_to_input_folder, filename)

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            video_path = loop.run_until_complete(_run())
            return (_InputImpl.VideoFromFile(video_path),)

        async def _download_video_async(self, video_url: str, save_to_input_folder: bool, filename: str) -> str:
            if aiohttp is None:
                raise RuntimeError("aiohttp not installed")
            # 复用同样的下载逻辑
            if not video_url:
                raise ValueError("Video URL cannot be empty")
            if not video_url.startswith(('http://', 'https://')):
                raise ValueError("URL must start with http:// or https://")

            temp_file = None
            video_path = ""
            try:
                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(video_url) as response:
                        response.raise_for_status()

                        file_ext = '.mp4'
                        if '.' in video_url:
                            url_ext = video_url.split('.')[-1].split('?')[0].lower()
                            supported_exts = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'mpeg', 'mpg', 'wmv']
                            if url_ext in supported_exts:
                                file_ext = f'.{url_ext}'

                        if save_to_input_folder:
                            input_dir = folder_paths.get_input_directory()
                            os.makedirs(input_dir, exist_ok=True)
                            video_path = os.path.join(input_dir, f"{filename}{file_ext}")
                            counter = 1
                            while os.path.exists(video_path):
                                video_path = os.path.join(input_dir, f"{filename}_{counter}{file_ext}")
                                counter += 1
                            with open(video_path, 'wb') as f:
                                downloaded_size = 0
                                while True:
                                    chunk = await response.content.read(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                        else:
                            temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False, mode='wb')
                            with temp_file:
                                downloaded_size = 0
                                while True:
                                    chunk = await response.content.read(8192)
                                    if not chunk:
                                        break
                                    temp_file.write(chunk)
                                    downloaded_size += len(chunk)
                            video_path = temp_file.name

                return video_path
            except Exception as e:
                if temp_file and os.path.exists(getattr(temp_file, 'name', '')):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                raise RuntimeError(f"Failed to load video: {e}")
