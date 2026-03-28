"""
数据模型定义
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DownloadedSong:
    """已下载歌曲数据模型"""
    
    id: Optional[int]           # 数据库自增ID
    song_id: int                # 网易云歌曲ID
    song_name: str              # 歌曲名称
    artist: str                 # 艺术家
    album: str                  # 专辑
    quality: str                # 下载音质
    download_time: datetime     # 下载时间
    file_path: Optional[str]    # 文件保存路径
    
    def __post_init__(self):
        """初始化后处理"""
        if isinstance(self.download_time, str):
            self.download_time = datetime.fromisoformat(self.download_time)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'song_id': self.song_id,
            'song_name': self.song_name,
            'artist': self.artist,
            'album': self.album,
            'quality': self.quality,
            'download_time': self.download_time.isoformat() if self.download_time else None,
            'file_path': self.file_path
        }
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建实例"""
        if row is None:
            return None
        return cls(
            id=row[0],
            song_id=row[1],
            song_name=row[2],
            artist=row[3],
            album=row[4],
            quality=row[5],
            download_time=row[6],
            file_path=row[7]
        )


@dataclass
class SongInfo:
    """歌曲信息数据模型（来自网易云API）"""
    
    id: int                     # 歌曲ID
    name: str                   # 歌曲名称
    artists: list               # 艺术家列表
    album: str                  # 专辑名称
    album_id: int               # 专辑ID
    duration: int               # 时长（毫秒）
    
    @property
    def artist_names(self):
        """获取艺术家名称字符串"""
        if isinstance(self.artists, list):
            return ', '.join([a.get('name', '') for a in self.artists if isinstance(a, dict)])
        return str(self.artists)
    
    @classmethod
    def from_api_response(cls, data):
        """从API响应创建实例"""
        if not data:
            return None
        
        # 处理不同的API返回格式
        if 'id' not in data:
            return None
        
        # 获取艺术家信息
        artists = data.get('ar', []) or data.get('artists', [])
        
        # 获取专辑信息
        album_data = data.get('al', {}) or data.get('album', {})
        album_name = album_data.get('name', '') if isinstance(album_data, dict) else ''
        album_id = album_data.get('id', 0) if isinstance(album_data, dict) else 0
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            artists=artists,
            album=album_name,
            album_id=album_id,
            duration=data.get('dt', 0) or data.get('duration', 0)
        )
