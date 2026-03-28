#!/usr/bin/env python3
"""
网易云歌单下载工具 - 主程序
"""

import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings, QUALITY_ORDER, QUALITY_MAPPING
from core.ncm_api import get_api
from core.playlist import get_playlist_manager
from database.db import get_database


def print_banner():
    """打印程序横幅"""
    print("=" * 60)
    print("       网易云歌单下载工具")
    print("=" * 60)
    print()


def check_api():
    """检查 pyncm 库是否可用"""
    import sys
    print("正在检查 API 库...")
    print(f"  当前 Python: {sys.executable}")

    try:
        import pyncm
        print("✓ pyncm 已加载")
        return True
    except ImportError as e:
        print(f"✗ pyncm 未安装: {e}")
    except Exception as e:
        print(f"✗ pyncm 加载失败 ({type(e).__name__}): {e}")

    print()
    print("请在当前 Python 环境中安装依赖:")
    print(f"  {sys.executable} -m pip install pyncm")
    print()
    return False


def check_config():
    """检查配置是否有效"""
    settings = get_settings()
    is_valid, error_msg = settings.validate()
    
    if not is_valid:
        print(f"配置错误: {error_msg}")
        print()
        print("请编辑 config/config.json 配置文件:")
        print('  {')
        print('      "playlist_url": "https://music.163.com/playlist?id=xxx",')
        print('      "download_dir": "./downloads",')
        print('      "default_quality": "hires",')
        print('      "api_server_url": "http://localhost:3000"')
        print('  }')
        print()
        return False
    
    print("配置检查通过")
    print(f"  歌单链接: {settings.get('playlist_url')}")
    print(f"  下载目录: {settings.get_download_dir()}")
    print(f"  默认音质: {QUALITY_MAPPING.get(settings.get('default_quality'), '未知')}")
    login_cfg = settings.get_login_config()
    account = login_cfg.get('phone') or login_cfg.get('email') or ''
    if account:
        print(f"  登录账号: {account}")
    else:
        print("  登录账号: 未配置（游客模式，只能下载试听片段）")
        print("  → 请在 config/config.json 中配置 login.phone / login.email 和 login.password")
    print()
    return True


def show_stats():
    """显示下载统计"""
    db = get_database()
    count = db.get_download_count()
    print(f"已下载歌曲总数: {count} 首")
    print()


def clear_records():
    """清除所有下载记录"""
    db = get_database()
    count = db.get_download_count()
    print(f"当前下载记录: {count} 首")
    
    confirm = input("确定要清除所有下载记录吗? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if db.clear_all_records():
            print("✓ 下载记录已清除")
        else:
            print("✗ 清除失败")
    else:
        print("已取消")
    print()


def process_single_playlist(playlist_url: str, download_dir: str, default_quality: str):
    """处理单个歌单下载"""
    from pathlib import Path
    from core.downloader import get_downloader
    from core.playlist import PlaylistManager
    
    # 创建独立的歌单管理器
    manager = PlaylistManager()
    manager.download_dir = Path(download_dir)
    manager.download_dir.mkdir(parents=True, exist_ok=True)
    
    success, msg = manager.load_playlist_from_url(playlist_url)
    
    if not success:
        print(f"错误: {msg}")
        return False
    
    print()
    manager.show_playlist_info()
    
    if not manager.new_songs:
        print("\n所有歌曲已是最新，无需下载")
        return True
    
    print()
    confirm = input(f"是否开始下载 {len(manager.new_songs)} 首新歌曲? (Y/n): ").strip().lower()
    
    if confirm and confirm not in ('y', 'yes', ''):
        print("已取消下载")
        return True
    
    print()
    stats = manager.download_all()
    return True


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='网易云歌单下载工具')
    parser.add_argument('--clear', action='store_true', help='清除所有下载记录')
    args = parser.parse_args()
    
    print_banner()
    
    # 检查 API 库
    if not check_api():
        input("按回车键退出...")
        return 1
    
    print()
    
    # 处理清除记录命令
    if args.clear:
        clear_records()
        input("按回车键退出...")
        return 0
    
    # 检查配置
    settings = get_settings()
    is_valid, error_msg = settings.validate()
    
    if not is_valid:
        print(f"配置错误: {error_msg}")
        print()
        print("请编辑 config/config.json 配置文件")
        print()
        input("按回车键退出...")
        return 1
    
    # 显示配置信息
    print("配置检查通过")
    playlists = settings.get_playlists()
    print(f"  歌单数量: {len(playlists)} 个")
    login_cfg = settings.get_login_config()
    account = login_cfg.get('phone') or login_cfg.get('email') or ''
    if account:
        print(f"  登录账号: {account}")
    else:
        print("  登录账号: 未配置（游客模式）")
    print()
    
    show_stats()
    
    # 处理所有歌单
    default_quality = settings.get('default_quality', 'hires')
    total_stats = {'success': 0, 'failed': 0, 'skipped': 0}
    
    for i, pl in enumerate(playlists, 1):
        print(f"\n{'='*60}")
        print(f"处理歌单 {i}/{len(playlists)}: {pl.get('name', '未命名')}")
        print(f"下载目录: {pl.get('download_dir', './downloads')}")
        print('='*60)
        
        process_single_playlist(
            pl['url'],
            pl.get('download_dir', './downloads'),
            pl.get('quality', default_quality)
        )
    
    print()
    print("=" * 60)
    print("所有歌单处理完毕")
    print("=" * 60)
    
    input("按回车键退出...")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序异常: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
        sys.exit(1)
