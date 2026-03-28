"""
歌曲下载器模块
支持音质降级、进度显示、文件管理
"""

import os
import re
import requests
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import get_settings, QUALITY_MAPPING
from database.db import get_database


class SongDownloader:
    """歌曲下载器"""
    
    # 文件扩展名映射
    EXTENSION_MAP = {
        'mp3': '.mp3',
        'flac': '.flac',
        'wav': '.wav',
        'm4a': '.m4a',
        'ogg': '.ogg'
    }
    
    def __init__(self, download_dir=None, progress_callback=None):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录，默认从配置读取
            progress_callback: 进度回调函数 (downloaded, total, percentage)
        """
        settings = get_settings()
        self.download_dir = Path(download_dir or settings.get_download_dir())
        self.progress_callback = progress_callback
        self.db = get_database()
        
        # 确保下载目录存在
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://music.163.com/',
            'Origin': 'https://music.163.com',
        })
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名中的非法字符
        
        Args:
            filename: 原始文件名
        
        Returns:
            清理后的文件名
        """
        # Windows 非法字符: < > : " / \ | ? *
        # 替换为全角字符或下划线
        illegal_chars = {
            '<': '＜',
            '>': '＞',
            ':': '：',
            '"': '＂',
            '/': '／',
            '\\': '＼',
            '|': '｜',
            '?': '？',
            '*': '＊'
        }
        
        for char, replacement in illegal_chars.items():
            filename = filename.replace(char, replacement)
        
        # 移除控制字符
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        
        # 去除首尾空格和点
        filename = filename.strip(' .')
        
        # 如果为空，使用默认名称
        if not filename:
            filename = 'unknown'
        
        return filename
    
    def get_file_extension(self, url_data: dict) -> str:
        """
        根据 URL 数据确定文件扩展名
        
        Args:
            url_data: URL 数据字典
        
        Returns:
            文件扩展名
        """
        # 优先使用 API 返回的类型
        file_type = url_data.get('type', '').lower()
        if file_type in self.EXTENSION_MAP:
            return self.EXTENSION_MAP[file_type]
        
        # 从 URL 解析
        url = url_data.get('url', '')
        if url:
            parsed = urlparse(url)
            path = parsed.path.lower()
            for ext in ['.flac', '.mp3', '.wav', '.m4a', '.ogg']:
                if path.endswith(ext):
                    return ext
        
        # 根据音质推断
        level = url_data.get('level', '').lower()
        if level in ['hires', 'lossless']:
            return '.flac'
        
        return '.mp3'
    
    def build_file_path(self, song_name: str, artist: str, album: str, 
                       extension: str, quality: str) -> Path:
        """
        构建文件保存路径
        
        Args:
            song_name: 歌曲名称
            artist: 艺术家
            album: 专辑
            extension: 文件扩展名
            quality: 音质
        
        Returns:
            文件路径
        """
        # 清理名称
        safe_song = self.sanitize_filename(song_name)
        safe_artist = self.sanitize_filename(artist)
        
        # 文件名格式：艺术家 - 歌曲名 [音质].扩展名
        quality_tag = QUALITY_MAPPING.get(quality, quality)
        filename = f"{safe_artist} - {safe_song} [{quality_tag}]{extension}"
        
        # 直接保存至下载根目录，不建子文件夹
        return self.download_dir / filename
    
    def download(self, url_data: dict, song_name: str, artist: str, 
                album: str = '', song_id: int = None) -> tuple[bool, str]:
        """
        下载歌曲
        
        Args:
            url_data: 包含 URL 的数据字典
            song_name: 歌曲名称
            artist: 艺术家
            album: 专辑
            song_id: 歌曲ID（用于数据库记录）
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        url = url_data.get('url')
        if not url:
            return False, "下载链接为空"
        
        quality = url_data.get('level', 'standard')
        extension = self.get_file_extension(url_data)
        
        # 构建文件路径
        file_path = self.build_file_path(song_name, artist, album, extension, quality)
        
        # 检查文件是否已存在
        if file_path.exists():
            print(f"  文件已存在，跳过: {file_path.name}")
            # 仍然记录到数据库
            if song_id:
                self.db.add_download_record(
                    song_id, song_name, artist, album, quality, str(file_path)
                )
            return True, str(file_path)
        
        try:
            # 发送下载请求
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # 下载文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 调用进度回调
                        if self.progress_callback and total_size > 0:
                            percentage = (downloaded / total_size) * 100
                            self.progress_callback(downloaded, total_size, percentage)
            
            # 记录到数据库
            if song_id:
                self.db.add_download_record(
                    song_id, song_name, artist, album, quality, str(file_path)
                )
            
            # 格式化文件大小显示
            size_str = self._format_size(total_size if total_size > 0 else downloaded)
            print(f"  ✓ 下载完成 [{size_str}]")
            
            return True, str(file_path)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"下载失败: {e}"
            print(f"  ✗ {error_msg}")
            # 清理未完成的文件
            if file_path.exists():
                file_path.unlink()
            return False, error_msg
        except IOError as e:
            error_msg = f"文件写入失败: {e}"
            print(f"  ✗ {error_msg}")
            return False, error_msg
    
    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小显示
        
        Args:
            size_bytes: 字节数
        
        Returns:
            格式化后的字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"
    
    def download_with_retry(self, url_data: dict, song_name: str, artist: str,
                           album: str = '', song_id: int = None, 
                           max_retries: int = 3) -> tuple[bool, str]:
        """
        带重试机制的下载
        
        Args:
            url_data: 包含 URL 的数据字典
            song_name: 歌曲名称
            artist: 艺术家
            album: 专辑
            song_id: 歌曲ID
            max_retries: 最大重试次数
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"  第 {attempt + 1} 次重试...")
            
            success, result = self.download(url_data, song_name, artist, album, song_id)
            if success:
                return success, result
            
            # 如果是网络错误，等待后重试
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # 指数退避
        
        return False, f"下载失败，已重试 {max_retries} 次"


# 全局下载器实例
_downloader = None


def get_downloader(progress_callback=None):
    """获取全局下载器实例（单例模式）"""
    global _downloader
    if _downloader is None:
        _downloader = SongDownloader(progress_callback=progress_callback)
    return _downloader
