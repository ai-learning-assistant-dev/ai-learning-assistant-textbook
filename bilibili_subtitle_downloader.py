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
import sys
import time
import random
import hashlib
import urllib.parse
from typing import Optional, Dict, List
import argparse
from pathlib import Path
import process_video_info
try:
    import video_transcriber
except ImportError:
    video_transcriber = None


class BilibiliSubtitleDownloader:
    """Bilibili字幕下载器"""
    
    def __init__(self, sessdata: Optional[str] = None, bili_jct: Optional[str] = None, 
                 buvid3: Optional[str] = None, debug: bool = False,
                 request_delay: float = 2.0, max_retries: int = 3):
        """
        初始化下载器
        
        Args:
            sessdata: B站登录Cookie中的SESSDATA
            bili_jct: B站登录Cookie中的bili_jct
            buvid3: B站登录Cookie中的buvid3
            debug: 是否开启调试模式
            request_delay: 请求间隔（秒）
            max_retries: 最大重试次数
        """
        self.sessdata = sessdata
        self.bili_jct = bili_jct
        self.buvid3 = buvid3
        self.debug = debug
        self.request_delay = request_delay
        self.max_retries = max_retries
        
        # 使用更真实的浏览器User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        
        self.headers = {
            'User-Agent': random.choice(user_agents),
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        
        self.cookies = {}
        if sessdata:
            self.cookies['SESSDATA'] = sessdata
        if bili_jct:
            self.cookies['bili_jct'] = bili_jct
        if buvid3:
            self.cookies['buvid3'] = buvid3

        self.wbi_img_key = None
        self.wbi_sub_key = None
        self.last_request_time = 0
        
        # 初始化Wbi密钥
        self._get_wbi_keys()

    def _get_wbi_keys(self):
        """获取最新的Wbi密钥"""
        try:
            resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=self.headers, cookies=self.cookies)
            resp.raise_for_status()
            json_content = resp.json()
            wbi_img = json_content['data']['wbi_img']
            self.wbi_img_key = wbi_img['img_url'].split("/")[-1].split(".")[0]
            self.wbi_sub_key = wbi_img['sub_url'].split("/")[-1].split(".")[0]
            if self.debug:
                print(f"[DEBUG] Wbi密钥获取成功: {self.wbi_img_key}, {self.wbi_sub_key}")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 获取Wbi密钥失败: {e}")
            # 使用默认/后备密钥，虽然可能无效但防止程序直接崩溃
            self.wbi_img_key = "7cd084941338484aae1ad9425b84077c" 
            self.wbi_sub_key = "4932caff0a9246c7a592540e2310d958"

    def _get_mixin_key(self, ae):
        """混合密钥生成"""
        oe = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
        le = []
        for n in oe:
            if n < len(ae):
                le.append(ae[n])
        return "".join(le)[:32]

    def _enc_wbi(self, params: dict):
        """为参数添加Wbi签名"""
        mixin_key = self._get_mixin_key(self.wbi_img_key + self.wbi_sub_key)
        curr_time = round(time.time())
        params['wts'] = curr_time
        params = dict(sorted(params.items()))
        # 过滤不用签名的字符
        params = {
            k: ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v in params.items()
        }
        query = urllib.parse.urlencode(params)
        wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
        params['w_rid'] = wbi_sign
        return params

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
    
    def extract_page_number(self, url: str) -> Optional[int]:
        """
        从URL中提取分P参数（p参数）
        
        Args:
            url: Bilibili视频URL
            
        Returns:
            分P编号（从1开始），如果没有p参数返回None
        """
        # 匹配p参数：?p=2 或 &p=2
        pattern = r'[?&]p=(\d+)'
        match = re.search(pattern, url)
        
        if match:
            return int(match.group(1))
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
        # 更严格的判断：必须包含 favlist 且有 fid= 参数
        return 'favlist' in url and 'fid=' in url
    
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

    def save_video_info(self, video_info: Dict, video_index: str, output_path: str, download_all_parts: bool, part_title: Optional[str] = None, page_num: Optional[int] = None):
        """
        保存视频信息到JSON文件

        Args:
            video_info: 视频信息字典
            output_path: 输出文件路径
            download_all_parts: 是否下载所有分P
            part_title: 分P标题（可选）
            page_num: 分P序号（可选）
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(video_info, f, ensure_ascii=False, indent=2)
        tittle = video_info['title']
        # 处理视频信息并生成Excel文件,并命名为video_info中的tittle字段.xlsx
        if download_all_parts:
            process_video_info.process_video_to_excel_final(output_path, '模板.xlsx')
        else:
            process_video_info.process_video_to_excel_flash(output_path, '模板.xlsx' , video_index, part_title=part_title, page_num=page_num)

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
        # 定义要尝试的API列表
        api_attempts = []
        
        # 1. 尝试不带签名的 Wbi API (参照 PRE 版本，兼容性好)
        api_attempts.append({
            'name': 'Wbi API (Unsigned)',
            'url': f'https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}'
        })
        
        # 2. 尝试带签名的 Wbi API (如果 keys 有效)
        try:
            params = {'bvid': bvid, 'cid': cid}
            signed_params = self._enc_wbi(params)
            query_string = urllib.parse.urlencode(signed_params)
            api_attempts.append({
                'name': 'Wbi API (Signed)',
                'url': f'https://api.bilibili.com/x/player/wbi/v2?{query_string}'
            })
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Wbi签名生成失败: {e}")

        # 3. 尝试旧版 API (作为最后后备)
        api_attempts.append({
            'name': 'Legacy API',
            'url': f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}'
        })
        
        for api_info in api_attempts:
            name = api_info['name']
            api_url = api_info['url']
            
            if self.debug:
                print(f"[DEBUG] 尝试请求字幕API ({name}): {api_url}")
            
            # 对每个API进行重试
            for attempt in range(self.max_retries):
                try:
                    self._wait_if_needed()
                    
                    response = requests.get(api_url, headers=self.headers, cookies=self.cookies, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if self.debug:
                        print(f"[DEBUG] {name} 响应码: {data.get('code')}")
                    
                    if data.get('code') == 0:
                        subtitle_data = data.get('data', {}).get('subtitle', {})
                        subtitles = subtitle_data.get('subtitles', [])
                        
                        # 检查是否有AI字幕
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
                        
                        if subtitles:
                            if self.debug:
                                print(f"[DEBUG] {name} 获取成功，找到 {len(subtitles)} 个字幕")
                            return subtitles
                        else:
                            # 响应成功但无字幕，可能是真没字幕
                            # 继续尝试下一个API，以防不同API返回不同
                            if self.debug:
                                print(f"[DEBUG] {name} 返回成功但无字幕，尝试下一个API...")
                            break
                    else:
                        print(f"获取字幕失败 ({name}): {data.get('message')}")
                        # API返回错误，跳出重试，尝试下一个API
                        break
                        
                except Exception as e:
                    print(f"请求出错 ({name}, 尝试 {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                    # 如果重试耗尽，循环自然结束，尝试下一个API
        
        # If we reach here, no subtitles were found after all attempts
        if not self.cookies.get('SESSDATA'):
            print("\n[警告] 未找到在线字幕且未检测到登录凭证(SESSDATA)。")
            print("该视频可能需要登录才能获取AI字幕。")
            print("请在程序目录下创建 'cookies.txt' 文件，并填入 SESSDATA=你的SESSDATA值")
            print("或者使用命令行参数 --sessdata 传入。\n")
            
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
    
    def _save_subtitle_file(self, subtitle_content, page_title, lan, format_type, video_dir):
        """
        保存字幕文件的辅助函数
        
        Args:
            subtitle_content: 字幕内容
            page_title: 页面标题
            lan: 语言代码
            format_type: 格式类型 (srt/json/txt)
            video_dir: 输出目录
            
        Returns:
            输出文件路径，如果保存失败返回None
        """
        filename = f"{page_title}_{lan}.{format_type}"
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
            return None
        
        return output_path

    def _download_single_subtitle(self, sub, page_title, format_type, video_dir):
        """
        下载并保存单个字幕文件的辅助函数
        
        Args:
            sub: 字幕信息字典
            page_title: 页面标题
            format_type: 格式类型
            video_dir: 输出目录
            
        Returns:
            输出文件路径，如果下载失败返回None
        """
        lan = sub.get('lan', 'unknown')
        lan_doc = sub.get('lan_doc', lan)
        subtitle_url = sub.get('subtitle_url')
        is_ai = sub.get('is_ai', False)
        
        if not subtitle_url:
            print(f"警告: {lan_doc} 字幕URL为空")
            return None
        
        print(f"\n下载 {lan_doc} 字幕...")
        subtitle_content = self.download_subtitle(subtitle_url, is_ai=is_ai)
        
        if not subtitle_content:
            print(f"错误: 无法下载 {lan_doc} 字幕")
            return None
        
        # 保存字幕文件
        output_path = self._save_subtitle_file(subtitle_content, page_title, lan, format_type, video_dir)
        return output_path

    def _download_chinese_subtitle(self, subtitles, page_title, format_type, video_dir):
        """
        下载中文字幕，按优先级顺序
        
        Args:
            subtitles: 字幕列表
            page_title: 页面标题
            format_type: 格式类型
            video_dir: 输出目录
            
        Returns:
            成功下载的文件路径列表
        """
        # 定义中文语言代码的优先级顺序
        chinese_priority = ['zh-CN', 'zh-Hans', 'ai-zh']
        
        for priority_lan in chinese_priority:
            for sub in subtitles:
                lan = sub.get('lan', 'unknown')
                if lan == priority_lan:
                    # 找到匹配的字幕，进行下载
                    output_path = self._download_single_subtitle(sub, page_title, format_type, video_dir)
                    if output_path:
                        return [output_path]  # 下载成功后立即返回
        
        return []  # 如果没有找到任何中文字幕，返回空列表

    def download(self, video_url: str, video_index: str = "1", output_dir: str = 'subtitles',
                 format_type: str = 'srt', language: Optional[str] = None,
                 download_cover: bool = True, custom_folder_name: Optional[str] = None,
                 download_all_parts: bool = False) -> Dict[str, any]:
        """
        下载视频字幕和封面的主函数
        
        Args:
            video_url: Bilibili视频URL
            output_dir: 输出目录
            format_type: 输出格式 (srt/json/txt)
            language: 指定语言，None则下载所有语言
            download_cover: 是否下载封面图片（默认True）
            custom_folder_name: 自定义输出文件夹名称，None则使用视频标题
            download_all_parts: 是否下载所有分P（默认False，只下载URL指定的视频）
            
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
        
        # 根据 download_all_parts 开关和URL参数决定下载哪些分P
        if not download_all_parts:
            # 如果开关关闭，只下载URL指定的那一个分P
            target_page_number = self.extract_page_number(video_url)
            if target_page_number is None:
                # 如果URL没有p参数，默认下载第一个
                target_page_number = 1
            
            if self.debug:
                print(f"[DEBUG] download_all_parts=False，只下载第 {target_page_number} 个分P")
            
            # 检查目标分P是否存在
            if target_page_number > len(pages):
                print(f"错误: 请求的分P编号 p={target_page_number} 不存在（该视频共 {len(pages)} 个分P）")
                return result
            
            # 只保留目标视频
            # 注意：这里必须通过 cid 来精确匹配，因为 pages 列表中的顺序可能和 p 参数一致，也可能不一致（对于 ugc_season）
            # 如果是普通多P，pages[i] 对应 p=i+1
            # 如果是合集，需要更复杂的匹配
            
            target_page = None
            
            # 优先尝试匹配BVID（针对合集视频）
            for page in pages:
                if page.get('bvid') == bvid:
                    target_page = page
                    break
            
            # 尝试1：如果是普通多P，直接用索引
            if not target_page and target_page_number <= len(pages):
                potential_page = pages[target_page_number - 1]
                # 简单的校验：对于普通视频，page字段通常就是分P序号
                if potential_page.get('page') == target_page_number:
                    target_page = potential_page
            
            # 尝试2：如果上面没匹配到（比如合集，或者索引不对），遍历查找
            if not target_page:
                for page in pages:
                    if page.get('page') == target_page_number:
                        target_page = page
                        break
            
            if target_page:
                 pages = [target_page]
            else:
                 # 兜底：如果实在找不到对应 page 字段的，就按索引取（虽然前面已经判断过越界）
                 pages = [pages[target_page_number - 1]]
        else:
            # 如果开关开启，下载所有分P（保持现有逻辑）
            if self.debug:
                print(f"[DEBUG] download_all_parts=True，下载所有 {len(pages)} 个分P")
        
        # 先检查是否有可用字幕
        has_subtitle = False
        for page in pages:
            cid = page['cid']
            subtitles = self.get_subtitle_info(bvid, cid)
            if subtitles:
                has_subtitle = True
                break
        
        # 修改策略：只要 video_transcriber 模块可用，就允许使用 ASR 作为兜底
        # 原逻辑是只有当所有分P都没有字幕时才启用 ASR，这会导致部分分P有字幕而部分没有时，没有字幕的分P无法触发 ASR
        use_asr = video_transcriber is not None
        
        if not has_subtitle:
            if use_asr:
                print("提示: 此视频没有官方/AI字幕，将尝试使用本地ASR模型转录...")
            else:
                print("提示: 此视频没有官方/AI字幕，且未检测到 video_transcriber 模块，无法进行本地转录")
        
        # 确认有字幕后，才创建输出目录和下载封面
        # 如果指定了自定义文件夹名称，则使用它；否则使用视频标题
        folder_name = custom_folder_name if custom_folder_name else title
        root_dir = os.path.join(output_dir, folder_name)
        # 将所有视频数据文件放在 data 子目录下
        video_dir = os.path.join(root_dir, 'data')
        
        os.makedirs(root_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)
        
        result['video_dir'] = video_dir
        print(f"输出目录: {video_dir}")
        
        # Determine the part title and page number to use for Excel
        excel_part_title = None
        excel_page_num = None
        if not download_all_parts and pages:
             # Since pages is filtered to contain only the target page (if found)
             # We can use the first page's part title and page number
             excel_part_title = pages[0].get('part')
             excel_page_num = pages[0].get('page')

        # 保存视频信息到JSON文件（带视频标题前缀）
        video_info_filename = f"{title}_video_info.json"
        video_info_path = os.path.join(video_dir, video_info_filename)
        self.save_video_info(video_info, video_index, video_info_path, download_all_parts, part_title=excel_part_title, page_num=excel_page_num)
        
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
            
            # 始终尝试构建分P标题，即使用户只下载其中一个分P
            # 如果不这样做，当 download_all_parts=False 时，文件名就不会包含 Px 前缀
            # 这会导致用户困惑（不知道下载的是哪一集），且可能导致文件覆盖
            
            # 1. 确定当前分P的序号 (page_num)
            # 优先使用 API 返回的 page 字段，如果没有则默认为 1
            page_num = page.get('page', 1)
            
            # 2. 构建新标题
            part_title = page.get('part', '').strip()
            
            # 逻辑修改：用户请求直接使用分P子标题作为文件名，不加主标题前缀
            # 如果有子标题，直接使用子标题
            # 如果没有子标题，且是多P，则使用 主标题_P序号
            # 如果没有子标题，且是单P，则使用 主标题
            
            if part_title:
                page_title = part_title
            else:
                if len(pages) > 1 or page_num > 1:
                    page_title = f"{title}_P{page_num}"
                else:
                    page_title = title
            
            # 再次清理文件名，确保安全
            page_title = process_video_info.sanitize_filename(page_title)

            if len(pages) > 1:
                print(f"\n处理分P: {page_title} (cid: {cid})")
            
            # 获取字幕信息
            subtitles = self.get_subtitle_info(main_bvid, cid)
            
            if not subtitles:
                print(f"此视频{'分P' if len(pages) > 1 else ''}没有在线字幕")
                
                # 检查本地是否存在字幕文件
                # 优先检查标准命名格式
                check_filenames = [
                    f"{page_title}_ai-zh.srt",
                    f"{page_title}.srt",
                    f"{page_title}_zh-CN.srt",
                    f"{page_title}_zh.srt"
                ]
                
                local_subtitle_found = False
                for filename in check_filenames:
                    local_path = os.path.join(video_dir, filename)
                    if os.path.exists(local_path):
                        print(f"✅ 发现本地已存在字幕文件: {filename}")
                        print("将在后续步骤中使用此本地文件。")
                        result['subtitles'].append(local_path)
                        local_subtitle_found = True
                        break
                
                if local_subtitle_found:
                    continue

                if use_asr and video_transcriber:
                    print("尝试使用本地ASR转录...")
                    
                    # 构建视频URL
                    if page.get('bvid') and page.get('bvid') != bvid:
                        # 合集/列表中的独立视频
                        target_url = f"https://www.bilibili.com/video/{page.get('bvid')}"
                    else:
                        # 多P视频
                        # 必须明确指定 p 参数，否则 yt-dlp 默认下载第一P
                        # 注意：page.get('page') 是 B站 API 返回的分P序号，通常从1开始
                        page_num = page.get('page', 1)
                        target_url = f"https://www.bilibili.com/video/{bvid}?p={page_num}"
                    
                    # 构建输出路径
                    # 使用带有分P信息的 page_title 加上随机后缀来命名，彻底避免并发冲突
                    # 临时音频文件不需要保持可读性，只要保证唯一性即可
                    import uuid
                    random_suffix = str(uuid.uuid4())[:8]
                    audio_filename = f"{page_title}_audio_{random_suffix}.mp3"
                    audio_path = os.path.join(video_dir, audio_filename)
                    
                    srt_filename = f"{page_title}_ai-zh.srt"
                    srt_path = os.path.join(video_dir, srt_filename)
                    
                    # 下载音频
                    if video_transcriber.download_audio(target_url, audio_path):

                        print("正在生成...")
                        sys.stdout.flush()
                        # 转录
                        # 使用subprocess调用转录脚本，以隔离可能的底层Crash（特别是Windows+CUDA环境下）
                        import subprocess
                        # 注意：sys已经在文件头部导入，此处不要重复导入，否则会导致UnboundLocalError
                        
                        print(f"启动独立进程进行转录 (Model: small)...")
                        sys.stdout.flush()
                        
                        # 获取当前Python解释器路径
                        python_executable = sys.executable
                        video_transcriber_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_transcriber.py")
                        
                        cmd = [
                            python_executable,
                            video_transcriber_script,
                            audio_path,
                            srt_path,
                            "--model_size", "small"
                        ]
                        
                        try:
                            # 运行子进程
                            # 注意：即使子进程Crash（返回非0），只要SRT文件生成了，我们也视为成功
                            result_proc = subprocess.run(cmd, check=False)
                            
                            if os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
                                print(f"成功生成 {srt_filename}")
                                sys.stdout.flush()
                                
                                result['subtitles'].append(srt_path)
                                if os.path.exists(audio_path):
                                    try:
                                        os.remove(audio_path)
                                    except Exception as e:
                                        print(f"警告: 无法删除临时音频文件: {e}")
                            else:
                                print("转录失败：未生成SRT文件或文件为空")
                                if result_proc.returncode != 0:
                                    print(f"转录进程异常退出，返回码: {result_proc.returncode}")
                        except Exception as e:
                            print(f"调用转录进程失败: {e}")
                    else:
                        print("音频下载失败")
                
                continue
            
            print(f"找到 {len(subtitles)} 个字幕:")
            for sub in subtitles:
                print(f"  - {sub.get('lan_doc', sub.get('lan', 'Unknown'))}")
            
            # 下载字幕
            # 下载字幕
            downloaded_paths = []
            
            if language:
                # 如果指定了语言，按优先级下载最匹配的字幕
                if language in ['zh-CN', 'zh', 'zh-Hans']:
                    # 下载中文字幕
                    downloaded_paths = self._download_chinese_subtitle(subtitles, page_title, format_type, video_dir)
                else:
                    # 非中文语言，按原逻辑处理
                    for sub in subtitles:
                        lan = sub.get('lan', 'unknown')
                        if lan != language:
                            continue
                        
                        output_path = self._download_single_subtitle(sub, page_title, format_type, video_dir)
                        if output_path:
                            downloaded_paths.append(output_path)
            else:
                # 没有指定语言，下载所有字幕
                for sub in subtitles:
                    output_path = self._download_single_subtitle(sub, page_title, format_type, video_dir)
                    if output_path:
                        downloaded_paths.append(output_path)
            
            # 更新结果
            result['subtitles'].extend(downloaded_paths)
        
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




