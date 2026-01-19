import requests
import numpy as np
import torch
import io
from PIL import Image
import soundfile as sf
import os
import tempfile
import folder_paths  # ComfyUI核心模块，用于路径管理

# 确保中文路径和特殊字符正常处理
import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = None

# 注册节点
class URLResourceLoader:
    """从URL加载图片或音频资源的ComfyUI节点"""
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """定义节点输入参数（遵循mixlab节点风格）"""
        return {
            "required": {
                "url": ("STRING", {
                    "multiline": False,
                    "default": "https://picsum.photos/800/600",
                    "dynamicPrompts": False,
                    "placeholder": "输入图片或音频的URL地址，例如：\n图片：https://picsum.photos/800/600\n音频：https://example.com/test.wav"
                }),
                "timeout": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 60,
                    "step": 1,
                    "display": "number",
                    "description": "网络请求超时时间（秒）"
                }),
            },
            "optional": {
                "audio_output_format": (["dict", "tuple"], {
                    "default": "dict",
                    "description": "音频输出格式：dict(ComfyUI标准) 或 tuple(wave, sr)"
                })
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("图片", "音频", "加载信息")
    FUNCTION = "load_from_url"
    CATEGORY = "mixlab/URL Loader"
    DESCRIPTION = "从指定URL加载图片或音频文件，自动识别类型并转换为ComfyUI可用格式"

    def load_from_url(self, url, timeout, audio_output_format="dict"):
        """核心函数：从URL加载资源"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            
            image_tensor = None
            audio_output = None
            info = ""

            # 处理图片
            if 'image' in content_type:
                image = Image.open(io.BytesIO(response.content)).convert("RGB")
                image_np = np.array(image).astype(np.float32) / 255.0
                image_tensor = torch.from_numpy(image_np).unsqueeze(0).permute(0, 3, 1, 2)
                info = f"✅ 图片加载成功\n地址：{url}\n尺寸：{image.size} (宽x高)"
                
            # 处理音频
            elif 'audio' in content_type or any(ext in url.lower() for ext in ['.mp3', '.wav', '.flac', '.ogg', '.m4a']):
                temp_dir = folder_paths.get_temp_directory()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=temp_dir) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
                
                audio_data, sample_rate = sf.read(temp_file_path)
                
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)
                
                audio_waveform = torch.from_numpy(audio_data).float()
                if len(audio_waveform.shape) == 1:
                    audio_waveform = audio_waveform.unsqueeze(0)
                
                if audio_output_format == "dict":
                    audio_output = {
                        "waveform": audio_waveform,
                        "sample_rate": sample_rate,
                        "duration": len(audio_data)/sample_rate
                    }
                else:
                    audio_output = (audio_waveform, sample_rate)
                
                info = f"✅ 音频加载成功\n地址：{url}\n采样率：{sample_rate}Hz\n时长：{len(audio_data)/sample_rate:.2f}秒\n输出格式：{audio_output_format}"
                
                os.unlink(temp_file_path)
                
            else:
                info = f"❌ 不支持的文件类型\nContent-Type：{content_type}\n请确认URL指向图片或音频文件"

            return (image_tensor, audio_output, info)

        except requests.exceptions.Timeout:
            return (None, None, f"❌ 请求超时\n超时时间：{timeout}秒\n地址：{url}")
        except requests.exceptions.RequestException as e:
            return (None, None, f"❌ 网络请求错误\n错误信息：{str(e)}\n地址：{url}")
        except Exception as e:
            return (None, None, f"❌ 资源处理失败\n错误信息：{str(e)}\n地址：{url}")

# 节点映射表（供__init__.py导入）
NODE_CLASS_MAPPINGS = {
    "URLResourceLoader": URLResourceLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "URLResourceLoader": "URL资源加载器"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']