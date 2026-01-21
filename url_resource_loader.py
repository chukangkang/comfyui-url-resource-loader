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
                }),
                "audio_channels": (["1", "2"], {
                    "default": "1",
                    "description": "输出音频声道数：1=单声道（推荐），2=立体声"
                })
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("图片", "音频", "加载信息")
    FUNCTION = "load_from_url"
    CATEGORY = "mixlab/URL Loader"
    DESCRIPTION = "从URL加载图片或音频文件，自动识别类型并转换为ComfyUI可用格式"

    def load_from_url(self, url, timeout, audio_output_format="dict", audio_channels="1"):
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
                
            # 处理音频 - 完整修复维度和声道数问题
            elif 'audio' in content_type or any(ext in url.lower() for ext in ['.mp3', '.wav', '.flac', '.ogg', '.m4a']):
                temp_dir = folder_paths.get_temp_directory()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=temp_dir) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
                
                # 读取音频数据
                audio_data, sample_rate = sf.read(temp_file_path)
                target_channels = int(audio_channels)
                
                # 步骤1：标准化音频数据维度（确保是2维：[samples, channels]）
                if len(audio_data.shape) == 1:
                    # 单声道：[samples] -> [samples, 1]
                    audio_data = audio_data.reshape(-1, 1)
                # 步骤2：调整声道数到目标值（1或2）
                if audio_data.shape[1] != target_channels:
                    if target_channels == 1:
                        # 多声道转单声道：取平均值
                        audio_data = np.mean(audio_data, axis=1, keepdims=True)
                    elif target_channels == 2:
                        # 单声道转立体声：复制声道
                        if audio_data.shape[1] == 1:
                            audio_data = np.repeat(audio_data, 2, axis=1)
                        else:
                            # 多声道转立体声：取前两个声道
                            audio_data = audio_data[:, :2]
                
                # 步骤3：转换为ComfyUI标准张量格式 [channels, frames]
                # 原始audio_data是 [samples, channels]，需要转置为 [channels, samples]
                audio_waveform = torch.from_numpy(audio_data.T).float()
                
                # 验证维度（确保是2维：[channels, frames]）
                assert len(audio_waveform.shape) == 2, f"音频张量维度错误，应为2维，实际：{audio_waveform.shape}"
                assert audio_waveform.shape[0] == target_channels, f"声道数错误，应为{target_channels}，实际：{audio_waveform.shape[0]}"
                
                # 构建符合ComfyUI标准的音频字典
                if audio_output_format == "dict":
                    audio_output = {
                        "waveform": audio_waveform,  # 2维张量：[channels, frames]
                        "sample_rate": sample_rate,
                        "duration": audio_data.shape[0] / sample_rate,
                        "channels": target_channels  # 明确指定声道数
                    }
                else:
                    # tuple格式也保证维度正确：(waveform[channels, frames], sample_rate)
                    audio_output = (audio_waveform, sample_rate)
                
                info = (
                    f"✅ 音频加载成功\n"
                    f"地址：{url}\n"
                    f"采样率：{sample_rate}Hz\n"
                    f"时长：{audio_data.shape[0]/sample_rate:.2f}秒\n"
                    f"声道数：{target_channels}\n"
                    f"张量维度：{audio_waveform.shape} (channels, frames)\n"
                    f"输出格式：{audio_output_format}"
                )
                
                # 清理临时文件
                os.unlink(temp_file_path)
                
            else:
                info = f"❌ 不支持的文件类型\nContent-Type：{content_type}\n请确认URL指向图片或音频文件"

            return (image_tensor, audio_output, info)

        except requests.exceptions.Timeout:
            return (None, None, f"❌ 请求超时\n超时时间：{timeout}秒\n地址：{url}")
        except requests.exceptions.RequestException as e:
            return (None, None, f"❌ 网络请求错误\n错误信息：{str(e)}\n地址：{url}")
        except AssertionError as e:
            return (None, None, f"❌ 音频维度验证失败\n错误信息：{str(e)}\n地址：{url}")
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