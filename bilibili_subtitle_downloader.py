#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili视频字幕下载器
支持下载Bilibili视频的CC字幕
"""

import requests
import json
import re
import os
import time
import random
from typing import Optional, Dict, List
import argparse
from pathlib import Path
import process_video_info


class BilibiliSubtitleDownloader:
    """Bilibili字幕下载器"""
    
    def __init__(self, sessdata: Optional[str] = None, bili_jct: Optional[str] = None, 
                 buvid3: Optional[str] = None, debug: bool = False,
                 request_delay: float = 2.0, max_retries: int = 3):
        """
        初始化下载器
        
        Args:
            sessdata: Bilibili登录凭证 SESSDATA
            bili_jct: Bilibili登录凭证 bili_jct
            buvid3: Bilibili登录凭证 buvid3
            debug: 是否启用调试模式
            request_delay: 请求间隔时间（秒），防止触发反爬虫
            max_retries: 最大重试次数
        """
        # 使用更真实的浏览器User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        
        self.headers = {
            'User-Agent': random.choice(user_agents),
            'Referer': 'https://www.bilibili.com',
            'Origin': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        
        # 构建cookies
        self.cookies = {}
        if sessdata:
            self.cookies['SESSDATA'] = sessdata
        if bili_jct:
            self.cookies['bili_jct'] = bili_jct
        if buvid3:
            self.cookies['buvid3'] = buvid3
        
        self.debug = debug
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.last_request_time = 0
        
        if self.debug:
            print(f"[DEBUG] 请求延迟: {request_delay}秒")
            print(f"[DEBUG] 最大重试次数: {max_retries}")
    
    def _wait_if_needed(self):
        """在请求前等待，避免请求过快"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.request_delay:
                wait_time = self.request_delay - elapsed + random.uniform(0, 0.5)  # 添加随机延迟
                if self.debug:
                    print(f"[DEBUG] 等待 {wait_time:.2f} 秒...")
                time.sleep(wait_time)
        self.last_request_time = time.time()
    
    def extract_bvid(self, url: str) -> Optional[str]:
        """
        从URL中提取BV号
        
        Args:
            url: Bilibili视频URL
            
        Returns:
            BV号，如果提取失败返回None
        """
        # 匹配BV号的正则表达式
        pattern = r'BV[a-zA-Z0-9]+'
        match = re.search(pattern, url)
        
        if match:
            return match.group(0)
        return None
    
    def extract_fid(self, url: str) -> Optional[str]:
        """
        从收藏夹URL中提取收藏夹ID
        
        Args:
            url: Bilibili收藏夹URL
            
        Returns:
            收藏夹ID，如果提取失败返回None
        """
        # 匹配收藏夹ID的正则表达式
        # 格式: https://space.bilibili.com/UID/favlist?fid=FAVID
        pattern = r'fid=(\d+)'
        match = re.search(pattern, url)
        
        if match:
            return match.group(1)
        return None
    
    def is_favorite_url(self, url: str) -> bool:
        """
        判断URL是否为收藏夹URL
        
        Args:
            url: URL字符串
            
        Returns:
            是否为收藏夹URL
        """
        return 'favlist' in url or 'fav' in url
    
    def get_favorite_videos(self, fid: str, max_count: Optional[int] = None) -> List[Dict]:
        """
        获取收藏夹内的视频列表
        
        Args:
            fid: 收藏夹ID
            max_count: 最大获取数量，None表示获取全部
            
        Returns:
            视频信息列表
        """
        videos = []
        page_size = 20
        page_num = 1
        
        if self.debug:
            print(f"[DEBUG] 开始获取收藏夹 {fid} 的视频列表")
        
        while True:
            try:
                self._wait_if_needed()
                
                # B站收藏夹API
                api_url = f'https://api.bilibili.com/x/v3/fav/resource/list?media_id={fid}&ps={page_size}&pn={page_num}'
                
                if self.debug:
                    print(f"[DEBUG] 请求收藏夹API (第{page_num}页): {api_url}")
                
                response = requests.get(api_url, headers=self.headers, cookies=self.cookies, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') != 0:
                    print(f"获取收藏夹信息失败: {data.get('message')}")
                    break
                
                result_data = data.get('data', {})
                medias = result_data.get('medias', [])
                
                if not medias:
                    break
                
                for media in medias:
                    video_info = {
                        'bvid': media.get('bvid'),
                        'title': media.get('title'),
                        'intro': media.get('intro'),
                        'cover': media.get('cover'),
                        'upper': media.get('upper', {}).get('name'),
                        'duration': media.get('duration')
                    }
                    videos.append(video_info)
                    
                    if self.debug:
                        print(f"[DEBUG] 找到视频: {video_info['title']} ({video_info['bvid']})")
                    
                    # 如果达到最大数量限制，停止获取
                    if max_count and len(videos) >= max_count:
                        break
                
                # 检查是否还有更多页
                has_more = result_data.get('has_more', False)
                if not has_more or (max_count and len(videos) >= max_count):
                    break
                
                page_num += 1
                
            except Exception as e:
                print(f"获取收藏夹视频列表时出错: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                break
        
        print(f"收藏夹内找到 {len(videos)} 个视频")
        return videos
    
    def get_video_info(self, bvid: str) -> Optional[Dict]:
        """
        获取视频信息，包括cid（带重试机制）
        
        Args:
            bvid: 视频的BV号
            
        Returns:
            包含视频信息的字典，失败返回None
        """
        api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
        
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                
                response = requests.get(api_url, headers=self.headers, cookies=self.cookies, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if self.debug:
                    print(f"[DEBUG] 视频信息API响应码: {data.get('code')}")
                
                if data.get('code') == 0:
                    return data.get('data')
                else:
                    print(f"获取视频信息失败: {data.get('message')}")
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避
                        print(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            except Exception as e:
                print(f"请求视频信息时出错: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None

    def save_video_info(self, video_info: Dict, output_path: str):
        """
        保存视频信息到JSON文件

        Args:
            video_info: 视频信息字典
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(video_info, f, ensure_ascii=False, indent=2)
        tittle = video_info['title']
        # 处理视频信息并生成Excel文件,并命名为video_info中的tittle字段.xlsx
        process_video_info.process_video_to_excel_final(output_path, '模板.xlsx')

        if self.debug:
            print(f"[DEBUG] 视频信息已保存到: {output_path}")

    def get_subtitle_info(self, bvid: str, cid: int) -> Optional[List[Dict]]:
        """
        获取字幕信息（包括官方CC字幕和AI字幕，带重试机制）
        
        Args:
            bvid: 视频的BV号
            cid: 视频的cid
            
        Returns:
            字幕信息列表，失败返回None
        """
        # 尝试新版API (wbi)
        api_url = f'https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}'
        
        if self.debug:
            print(f"[DEBUG] 请求字幕API: {api_url}")
            print(f"[DEBUG] Cookies: {self.cookies}")
        
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                
                response = requests.get(api_url, headers=self.headers, cookies=self.cookies, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if self.debug:
                    print(f"[DEBUG] 字幕API响应码: {data.get('code')}")
                
                if data.get('code') == 0:
                    subtitle_data = data.get('data', {}).get('subtitle', {})
                    subtitles = subtitle_data.get('subtitles', [])
                    
                    # 检查是否有AI字幕
                    ai_subtitle = subtitle_data.get('ai_subtitle')
                    if ai_subtitle and self.debug:
                        print(f"[DEBUG] 发现AI字幕信息: {ai_subtitle}")
                    
                    # 如果有AI字幕URL，添加到字幕列表
                    if ai_subtitle and isinstance(ai_subtitle, dict):
                        ai_subtitle_url = ai_subtitle.get('subtitle_url')
                        if ai_subtitle_url:
                            ai_sub_info = {
                                'lan': 'ai-zh',
                                'lan_doc': 'AI字幕(中文)',
                                'subtitle_url': ai_subtitle_url,
                                'is_ai': True
                            }
                            subtitles.append(ai_sub_info)
                            if self.debug:
                                print(f"[DEBUG] 添加AI字幕到列表: {ai_sub_info}")
                    
                    if self.debug:
                        print(f"[DEBUG] 找到字幕总数: {len(subtitles)}")
                        for sub in subtitles:
                            print(f"[DEBUG] 字幕: {sub.get('lan_doc', sub.get('lan', 'Unknown'))} - {sub.get('subtitle_url', 'No URL')}")
                    
                    return subtitles if subtitles else None
                else:
                    print(f"获取字幕信息失败 (wbi API): {data.get('message')}")
                    
                    # 尝试旧版API
                    if self.debug:
                        print("[DEBUG] 尝试使用旧版API...")
                    
                    self._wait_if_needed()
                    api_url_old = f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}'
                    response = requests.get(api_url_old, headers=self.headers, cookies=self.cookies, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if self.debug:
                        print(f"[DEBUG] 旧版API响应码: {data.get('code')}")
                    
                    if data.get('code') == 0:
                        subtitle_data = data.get('data', {}).get('subtitle', {})
                        subtitles = subtitle_data.get('subtitles', [])
                        
                        # 同样检查AI字幕
                        ai_subtitle = subtitle_data.get('ai_subtitle')
                        if ai_subtitle and isinstance(ai_subtitle, dict):
                            ai_subtitle_url = ai_subtitle.get('subtitle_url')
                            if ai_subtitle_url:
                                ai_sub_info = {
                                    'lan': 'ai-zh',
                                    'lan_doc': 'AI字幕(中文)',
                                    'subtitle_url': ai_subtitle_url,
                                    'is_ai': True
                                }
                                subtitles.append(ai_sub_info)
                        
                        return subtitles if subtitles else None
                    else:
                        if attempt < self.max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"获取字幕信息失败，等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                        continue
                        
            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            except Exception as e:
                print(f"请求字幕信息时出错: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def download_subtitle(self, subtitle_url: str, is_ai: bool = False) -> Optional[List[Dict]]:
        """
        下载字幕内容（带重试机制）
        
        Args:
            subtitle_url: 字幕文件的URL
            is_ai: 是否为AI字幕
            
        Returns:
            字幕内容列表，失败返回None
        """
        # 如果URL是相对路径，添加https:前缀
        if subtitle_url.startswith('//'):
            subtitle_url = 'https:' + subtitle_url
        
        if self.debug:
            print(f"[DEBUG] 下载字幕URL: {subtitle_url}")
            print(f"[DEBUG] 是否AI字幕: {is_ai}")
        
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                
                # AI字幕需要带cookies
                if is_ai or 'aisubtitle' in subtitle_url:
                    response = requests.get(subtitle_url, headers=self.headers, cookies=self.cookies, timeout=15)
                else:
                    response = requests.get(subtitle_url, headers=self.headers, timeout=15)
                
                response.raise_for_status()
                subtitle_data = response.json()
                
                if self.debug:
                    print(f"[DEBUG] 字幕数据类型: {subtitle_data.get('type', 'standard')}")
                    print(f"[DEBUG] 字幕条数: {len(subtitle_data.get('body', []))}")
                
                return subtitle_data.get('body', [])
                
            except requests.exceptions.Timeout:
                print(f"下载字幕超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            except Exception as e:
                print(f"下载字幕时出错: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def save_subtitle_as_srt(self, subtitle_content: List[Dict], output_path: str):
        """
        将字幕保存为SRT格式
        
        Args:
            subtitle_content: 字幕内容列表
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for index, item in enumerate(subtitle_content, 1):
                # SRT格式：序号
                f.write(f"{index}\n")
                
                # 时间轴
                start_time = self._format_timestamp(item['from'])
                end_time = self._format_timestamp(item['to'])
                f.write(f"{start_time} --> {end_time}\n")
                
                # 字幕内容
                f.write(f"{item['content']}\n\n")
        
        print(f"字幕已保存到: {output_path}")
    
    def save_subtitle_as_json(self, subtitle_content: List[Dict], output_path: str):
        """
        将字幕保存为JSON格式
        
        Args:
            subtitle_content: 字幕内容列表
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(subtitle_content, f, ensure_ascii=False, indent=2)
        
        print(f"字幕已保存到: {output_path}")
    
    def save_subtitle_as_txt(self, subtitle_content: List[Dict], output_path: str):
        """
        将字幕保存为纯文本格式
        
        Args:
            subtitle_content: 字幕内容列表
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in subtitle_content:
                f.write(f"{item['content']}\n")
        
        print(f"字幕已保存到: {output_path}")
    
    def download_cover(self, cover_url: str, output_path: str) -> bool:
        """
        下载视频封面图片
        
        Args:
            cover_url: 封面图片URL
            output_path: 输出文件路径
            
        Returns:
            是否下载成功
        """
        try:
            # 确保URL是完整的
            if cover_url.startswith('//'):
                cover_url = 'https:' + cover_url
            elif not cover_url.startswith('http'):
                cover_url = 'https://' + cover_url
            
            if self.debug:
                print(f"[DEBUG] 下载封面URL: {cover_url}")
            
            # 下载图片
            response = requests.get(cover_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # 保存图片
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"封面已保存到: {output_path}")
            return True
            
        except Exception as e:
            print(f"下载封面时出错: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        将秒数转换为SRT时间格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def download(self, video_url: str, output_dir: str = 'subtitles', 
                 format_type: str = 'srt', language: Optional[str] = 'ai-zh',
                 download_cover: bool = True, custom_folder_name: Optional[str] = None) -> Dict[str, any]:
        """
        下载视频字幕和封面的主函数
        
        Args:
            video_url: Bilibili视频URL
            output_dir: 输出目录
            format_type: 输出格式 (srt/json/txt)
            language: 指定语言，None则下载所有语言
            download_cover: 是否下载封面图片（默认True）
            custom_folder_name: 自定义输出文件夹名称，None则使用视频标题
            
        Returns:
            包含下载结果的字典：
            {
                'subtitles': [字幕文件路径列表],
                'cover': 封面文件路径或None,
                'title': 视频标题,
                'bvid': 视频BV号
            }
        """
        print(f"开始处理视频: {video_url}")
        
        result = {
            'subtitles': [],
            'cover': None,
            'title': '',
            'bvid': '',
            'video_dir': ''
        }
        
        # 提取BV号
        bvid = self.extract_bvid(video_url)
        if not bvid:
            print("错误: 无法从URL中提取BV号")
            return result
        
        result['bvid'] = bvid
        print(f"提取到BV号: {bvid}")
        
        # 获取视频信息
        video_info = self.get_video_info(bvid)
        if not video_info:
            print("错误: 无法获取视频信息")
            return result
        
        # 获取视频标题和封面
        title = video_info.get('title', bvid)
        result['title'] = title
        cover_url = video_info.get('pic', '')
        # 清理文件名中的非法字符
        title = process_video_info.sanitize_filename(title)

        if 'ugc_season' in video_info and video_info['ugc_season'].get('sections'):
            pages = []
            # 这是一个合集/系列。遍历所有 sections 中的 episodes
            for section in video_info['ugc_season']['sections']:
                if section.get('episodes'):
                    # 将每个 episode 转换为与原 pages 结构类似的字典，方便后续逻辑复用
                    for episode in section['episodes']:
                        # 提取关键信息，bvid 是下载字幕时可能需要传递的参数
                        cid = episode.get('cid')
                        page_title = episode.get('title') or episode.get('page', {}).get('part', '未知剧集')
                        bvid_ep = episode.get('bvid')

                        if cid:
                            pages.append({
                                'cid': cid,
                                'part': page_title,
                                'bvid': bvid_ep  # 存储bvid，以便在循环中使用
                            })
        else:
            # 否则，使用顶层的 'pages' 字段作为分P列表（如果是普通视频）
            pages = video_info.get('pages', [])
            if not pages:
                print("错误: 未找到视频分P信息")
                return result
        
        # 先检查是否有可用字幕（不创建文件夹）
        has_subtitle = False
        for page in pages:
            cid = page['cid']
            subtitles = self.get_subtitle_info(bvid, cid)
            if subtitles:
                has_subtitle = True
                break
        
        if not has_subtitle:
            print("错误: 此视频没有字幕")
            return result
        
        # 确认有字幕后，才创建输出目录和下载封面
        # 如果指定了自定义文件夹名称，则使用它；否则使用视频标题
        folder_name = custom_folder_name if custom_folder_name else title
        video_dir = os.path.join(output_dir, folder_name)
        os.makedirs(video_dir, exist_ok=True)
        result['video_dir'] = video_dir
        print(f"输出目录: {video_dir}")
        
        # 保存视频信息到JSON文件（带视频标题前缀）
        video_info_filename = f"{title}_video_info.json"
        video_info_path = os.path.join(video_dir, video_info_filename)
        self.save_video_info(video_info, video_info_path)
        
        # 下载封面图片（带视频标题前缀）
        if download_cover and cover_url:
            print(f"\n下载视频封面...")
            # 从URL中提取文件扩展名，如果没有则使用.jpg
            import urllib.parse
            parsed_url = urllib.parse.urlparse(cover_url)
            cover_ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            
            cover_filename = f"{title}_cover{cover_ext}"
            cover_path = os.path.join(video_dir, cover_filename)
            
            if self.download_cover(cover_url, cover_path):
                result['cover'] = cover_path
            print()
        
        # 遍历每个分P下载字幕
        for page in pages:
            # 优先使用剧集自己的 bvid，如果没有，则使用原始视频的 bvid
            main_bvid = page.get('bvid') or bvid
            cid = page['cid']
            page_title = page.get('part', '第1P')
            
            if len(pages) > 1:
                print(f"\n处理分P: {page_title} (cid: {cid})")
            
            # 获取字幕信息
            subtitles = self.get_subtitle_info(main_bvid, cid)
            
            if not subtitles:
                print(f"此视频{'分P' if len(pages) > 1 else ''}没有字幕")
                continue
            
            print(f"找到 {len(subtitles)} 个字幕:")
            for sub in subtitles:
                print(f"  - {sub.get('lan_doc', sub.get('lan', 'Unknown'))}")
            
            # 下载字幕
            for sub in subtitles:
                lan = sub.get('lan', 'unknown')
                lan_doc = sub.get('lan_doc', lan)
                subtitle_url = sub.get('subtitle_url')
                is_ai = sub.get('is_ai', False)
                
                # 如果指定了语言，只下载指定语言的字幕
                if language and lan != language:
                    continue
                
                if not subtitle_url:
                    print(f"警告: {lan_doc} 字幕URL为空")
                    continue
                
                print(f"\n下载 {lan_doc} 字幕...")
                subtitle_content = self.download_subtitle(subtitle_url, is_ai=is_ai)
                
                if not subtitle_content:
                    print(f"错误: 无法下载 {lan_doc} 字幕")
                    continue
                
                # 构建输出文件名
                filename = f"{process_video_info.sanitize_filename(page_title)}_{lan}.{format_type}"
                
                output_path = os.path.join(video_dir, filename)
                
                # 根据格式保存字幕
                if format_type == 'srt':
                    self.save_subtitle_as_srt(subtitle_content, output_path)
                elif format_type == 'json':
                    self.save_subtitle_as_json(subtitle_content, output_path)
                elif format_type == 'txt':
                    self.save_subtitle_as_txt(subtitle_content, output_path)
                else:
                    print(f"不支持的格式: {format_type}")
                    continue
                
                # 记录成功下载的文件
                result['subtitles'].append(output_path)
        
        return result


def load_cookies_from_file(config_file: str = 'cookies.txt') -> Dict[str, Optional[str]]:
    """
    从配置文件加载Cookie
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        包含Cookie的字典
    """
    cookies = {
        'sessdata': None,
        'bili_jct': None,
        'buvid3': None
    }
    
    config_path = Path(config_file)
    if not config_path.exists():
        return cookies
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 解析 key=value 格式
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key in cookies and value:
                        cookies[key] = value
    except Exception as e:
        print(f"警告: 读取配置文件失败: {e}")
    
    return cookies


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Bilibili视频字幕下载器 - 支持从cookies.txt读取登录凭证',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用cookies.txt中的凭证
  python bilibili_subtitle_downloader.py "https://www.bilibili.com/video/BV1xx411c7mu"
  
  # 命令行指定凭证（会覆盖cookies.txt）
  python bilibili_subtitle_downloader.py "https://www.bilibili.com/video/BV1xx411c7mu" --sessdata "你的SESSDATA"
  
  # 指定输出格式和目录
  python bilibili_subtitle_downloader.py "https://www.bilibili.com/video/BV1xx411c7mu" -o ./output -f json
  
  # 启用调试模式
  python bilibili_subtitle_downloader.py "https://www.bilibili.com/video/BV1xx411c7mu" --debug
        """
    )
    
    parser.add_argument('url', help='Bilibili视频URL')
    parser.add_argument('-o', '--output', default='subtitles', 
                       help='输出目录 (默认: subtitles)')
    parser.add_argument('-f', '--format', default='srt', 
                       choices=['srt', 'json', 'txt'],
                       help='输出格式 (默认: srt)')
    parser.add_argument('-l', '--language', default=None,
                       help='指定语言代码，如 zh-CN, ai-zh (默认: 下载所有语言)')
    parser.add_argument('--config', default='cookies.txt',
                       help='配置文件路径 (默认: cookies.txt)')
    parser.add_argument('--sessdata', default=None,
                       help='Bilibili登录凭证 SESSDATA (会覆盖配置文件中的值)')
    parser.add_argument('--bili-jct', default=None,
                       help='Bilibili登录凭证 bili_jct (会覆盖配置文件中的值)')
    parser.add_argument('--buvid3', default=None,
                       help='Bilibili登录凭证 buvid3 (会覆盖配置文件中的值)')
    parser.add_argument('--debug', action='store_true',
                       help='启用调试模式，输出详细信息')
    
    args = parser.parse_args()
    
    # 从配置文件加载Cookie
    config_cookies = load_cookies_from_file(args.config)
    
    # 命令行参数优先级高于配置文件
    sessdata = args.sessdata or config_cookies.get('sessdata')
    bili_jct = args.bili_jct or config_cookies.get('bili_jct')
    buvid3 = args.buvid3 or config_cookies.get('buvid3')
    
    # 提示用户Cookie来源
    if args.debug:
        if args.sessdata:
            print("[DEBUG] 使用命令行提供的SESSDATA")
        elif config_cookies.get('sessdata'):
            print(f"[DEBUG] 从配置文件 {args.config} 加载SESSDATA")
        else:
            print("[DEBUG] 未提供SESSDATA，可能无法下载AI字幕")
    
    downloader = BilibiliSubtitleDownloader(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3,
        debug=args.debug
    )
    downloader.download(args.url, args.output, args.format, args.language)


if __name__ == '__main__':
    main()

