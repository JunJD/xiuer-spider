#!/usr/bin/env python3
"""
增强版 GitHub Action 入口文件
基于 xiuer 项目的 webhook schema 输出规范的数据结构
支持完整的笔记数据、评论数据，并符合 Pydantic 模式定义
"""

import argparse
import json
import os
import sys
import traceback
import requests
import uuid
import time
import random
from datetime import datetime
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, handle_comment_info


def generate_run_id():
    """生成唯一的运行ID"""
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0, note_index: int = None):
    """
    添加随机延迟，模拟真实用户行为
    
    Args:
        min_seconds: 最小延迟秒数
        max_seconds: 最大延迟秒数  
        note_index: 笔记索引，用于调整延迟策略
    """
    # 基础随机延迟
    base_delay = random.uniform(min_seconds, max_seconds)
    
    # 根据笔记索引调整延迟策略
    if note_index is not None:
        if note_index == 1:
            # 第一个笔记稍微快一点，模拟刚开始浏览的状态
            base_delay *= random.uniform(0.5, 0.8)
        elif note_index % 5 == 0:
            # 每5个笔记加一个稍长的停顿，模拟用户思考或休息
            base_delay *= random.uniform(1.5, 2.5)
        elif note_index % 3 == 0:
            # 每3个笔记稍微停顿一下
            base_delay *= random.uniform(1.2, 1.8)
    
    # 添加一些随机性：有10%的概率会有更长的延迟
    if random.random() < 0.1:
        base_delay *= random.uniform(2.0, 4.0)
        logger.info(f"⏱️  随机长延迟: {base_delay:.2f}秒 (模拟用户停顿思考)")
    else:
        logger.debug(f"⏱️  延迟: {base_delay:.2f}秒")
    
    time.sleep(base_delay)
    return base_delay


def send_webhook(webhook_url: str, data: dict):
    """发送数据到 webhook"""
    if not webhook_url or webhook_url.lower() == 'none':
        logger.info("跳过Webhook发送（未提供URL）")
        return True
        
    try:
        response = requests.post(
            webhook_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        logger.success(f"✅ Webhook 发送成功: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Webhook 发送失败: {e}")
        logger.debug(f"Webhook错误详情: {traceback.format_exc()}")
        return False


def parse_interact_info(interact_info: dict) -> dict:
    """解析互动信息，符合 XhsInteractInfo 模式"""
    return {
        "liked_count": int(interact_info.get("liked_count", 0)) if interact_info.get("liked_count") else 0,
        "collected_count": int(interact_info.get("collected_count", 0)) if interact_info.get("collected_count") else 0,
        "comment_count": int(interact_info.get("comment_count", 0)) if interact_info.get("comment_count") else 0,
        "share_count": int(interact_info.get("shared_count", 0)) if interact_info.get("shared_count") else 0
    }


def parse_author_info(user_info: dict) -> dict:
    """解析作者信息，符合 XhsAuthorInfo 模式"""
    return {
        "user_id": user_info.get("user_id"),
        "nickname": user_info.get("nickname") or user_info.get("nick_name"),
        "avatar": user_info.get("avatar")
    }


def extract_tags_from_note(note_data: dict) -> list:
    """从笔记数据中提取标签"""
    tags = []
    
    # 从 corner_tag_info 提取
    corner_tags = note_data.get("note_card", {}).get("corner_tag_info", [])
    for tag in corner_tags:
        if tag.get("text") and tag.get("text") not in tags:
            tags.append(tag.get("text"))
    
    # 如果有其他标签字段，也可以在这里提取
    # 例如从 display_title 中提取 # 标签
    title = note_data.get("note_card", {}).get("display_title", "")
    if "#" in title:
        import re
        hashtags = re.findall(r'#([^#\s]+)', title)
        tags.extend(hashtags)
    
    return list(set(tags))  # 去重


def convert_note_to_xhs_format(note: dict, run_id: str) -> dict:
    """将搜索结果的笔记数据转换为符合 XhsNoteData 模式的格式"""
    note_card = note.get("note_card", {})
    user_info = note_card.get("user", {})
    interact_info = note_card.get("interact_info", {})
    
    # 提取图片列表
    image_list = []
    images = note_card.get("image_list", [])
    for img in images:
        if 'info_list' in img:
            for info in img['info_list']:
                if info.get('image_scene') == 'WB_DFT':
                    image_list.append(info['url'])
                    break
    
    # 解析上传时间
    upload_time = None
    corner_tags = note_card.get("corner_tag_info", [])
    for tag in corner_tags:
        if tag.get("type") == "publish_time":
            time_text = tag.get("text", "")
            if "小时前" in time_text:
                hours = int(time_text.replace("小时前", ""))
                upload_time = datetime.now().replace(hour=datetime.now().hour - hours)
            elif "分钟前" in time_text:
                minutes = int(time_text.replace("分钟前", ""))
                upload_time = datetime.now().replace(minute=datetime.now().minute - minutes)
            elif "-" in time_text and len(time_text) == 5:  # MM-DD格式
                try:
                    month, day = time_text.split("-")
                    current_year = datetime.now().year
                    upload_time = datetime(current_year, int(month), int(day))
                except:
                    pass
            break
    
    # 构建符合 XhsNoteData 模式的数据
    xhs_note_data = {
        "note_id": note.get("id"),
        "note_url": f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}",
        "note_type": "video" if note_card.get("type") == "video" else "normal",
        
        # 作者信息
        "author": parse_author_info(user_info),
        
        # 内容信息
        "title": note_card.get("display_title"),
        "desc": None,  # 搜索结果中没有详细描述，需要详情页获取
        "tags": extract_tags_from_note(note),
        "upload_time": upload_time.isoformat() if upload_time else None,
        "ip_location": None,  # 搜索结果中通常没有位置信息
        
        # 互动数据
        "interact_info": parse_interact_info(interact_info),
        
        # 媒体内容
        "video_cover": note_card.get("cover", {}).get("url_default") if note_card.get("type") == "video" else None,
        "video_addr": None,  # 需要详情页获取
        "image_list": image_list,
        
        # 额外数据
        "xsec_token": note.get("xsec_token")
    }
    
    return xhs_note_data


def convert_comment_to_xhs_format(comment: dict, note_id: str) -> dict:
    """将评论数据转换为符合 XhsCommentData 模式的格式"""
    comment_time = None
    if 'create_time' in comment:
        try:
            comment_time = datetime.fromtimestamp(comment['create_time'])
        except:
            pass
    
    return {
        "comment_id": comment.get("id"),
        "note_id": note_id,
        "content": comment.get("content"),
        "like_count": int(comment.get("like_count", 0)),
        "upload_time": comment_time.isoformat() if comment_time else None,
        "ip_location": comment.get("ip_location"),
        
        # 评论者信息
        "commenter_user_id": comment.get("user_info", {}).get("user_id"),
        "commenter_nickname": comment.get("user_info", {}).get("nickname"),
        
        # 层级关系
        "parent_comment_id": comment.get("parent_comment_id"),
        "root_comment_id": comment.get("root_comment_id")
    }


def search_and_process_notes(
    query: str,
    num: int,
    cookies_str: str,
    sort_type: int,
    webhook_url: str = None,
    get_comments: bool = False,
    no_delay: bool = False,
    run_id: str = None,
    task_id: str = None
):
    """搜索笔记并处理数据，输出符合webhook schema的格式"""
    start_time = datetime.now()
    
    try:
        logger.info(f"🚀 开始搜索: 关键词='{query}', 数量={num}, 排序类型={sort_type}")
        
        # 发送开始状态
        if webhook_url:
            start_webhook_data = {
                "status": "started",
                "message": f"开始搜索关键词: {query}",
                "timestamp": start_time.isoformat(),
                "run_id": run_id,
                "progress": 0,
                "data": {
                    "query": query,
                    "total_found": 0,
                    "notes": []
                }
            }
            if task_id:
                start_webhook_data["task_id"] = task_id
            send_webhook(webhook_url, start_webhook_data)
        
        xhs_apis = XHS_Apis()
        
        # 1. 搜索笔记
        success, msg, notes = xhs_apis.search_some_note(
            query=query,
            require_num=num,
            cookies_str=cookies_str,
            sort_type_choice=sort_type,
            note_type=0,  # 不限类型
            note_time=0,  # 不限时间
            note_range=0,  # 不限范围
            pos_distance=0,  # 不限位置
            geo=None,
            proxies=None
        )
        
        if not success:
            error_msg = f"搜索失败: {msg}"
            logger.error(f"❌ {error_msg}")
            
            error_data = {
                "status": "error",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
                "run_id": run_id,
                "elapsed_time": (datetime.now() - start_time).total_seconds(),
                "data": {
                    "query": query,
                    "total_found": 0,
                    "notes": []
                }
            }
            if task_id:
                error_data["task_id"] = task_id
            
            if webhook_url:
                send_webhook(webhook_url, error_data)
            
            return False, error_msg, []
        
        # 2. 过滤笔记类型
        notes = list(filter(lambda x: x['model_type'] == "note", notes))
        logger.info(f'✅ 搜索到 {len(notes)} 条笔记')
        
        if not notes:
            warning_msg = "搜索成功但无结果"
            logger.warning(f"⚠️ {warning_msg}")
            
            warning_data = {
                "status": "completed",
                "message": warning_msg,
                "timestamp": datetime.now().isoformat(),
                "run_id": run_id,
                "elapsed_time": (datetime.now() - start_time).total_seconds(),
                "data": {
                    "query": query,
                    "total_found": 0,
                    "notes": []
                }
            }
            if task_id:
                warning_data["task_id"] = task_id
            
            if webhook_url:
                send_webhook(webhook_url, warning_data)
            
            return True, warning_msg, []
        
        # 3. 处理笔记数据
        processed_notes = []
        all_comments = {}
        errors = []
        
        for i, note in enumerate(notes[:num], 1):
            try:
                # 添加随机延迟，模拟真实用户浏览行为
                if not no_delay and i > 1:  # 第一个笔记不延迟
                    delay_time = random_delay(
                        min_seconds=1.0, 
                        max_seconds=3.5, 
                        note_index=i
                    )
                
                logger.info(f"📝 处理第 {i}/{min(num, len(notes))} 条笔记: {note.get('id', 'unknown')}")
                
                # 发送进度状态
                progress = int((i / min(num, len(notes))) * 50)  # 50% for note processing
                if webhook_url:
                    progress_data = {
                        "status": "progress",
                        "message": f"正在处理笔记 {i}/{min(num, len(notes))}",
                        "timestamp": datetime.now().isoformat(),
                        "run_id": run_id,
                        "progress": progress,
                        "data": {
                            "query": query,
                            "total_found": len(notes),
                            "notes": processed_notes
                        }
                    }
                    if task_id:
                        progress_data["task_id"] = task_id
                    send_webhook(webhook_url, progress_data)
                
                # 转换为符合schema的笔记数据
                xhs_note_data = convert_note_to_xhs_format(note, run_id)
                processed_notes.append(xhs_note_data)
                
                logger.success(f"✅ 成功处理笔记: {xhs_note_data['title'][:50] if xhs_note_data['title'] else '无标题'}...")
                
                # 4. 获取评论（如果需要）
                if get_comments:
                    try:
                        # 获取评论前稍微延迟一下，模拟用户浏览到评论的时间
                        if not no_delay:
                            comment_delay = random_delay(0.5, 1.5)
                        logger.info(f"💬 获取笔记评论: {note.get('id')}")
                        
                        comment_success, comment_msg, comments = xhs_apis.get_note_all_out_comment(
                            note_id=note.get('id'),
                            xsec_token=note.get('xsec_token'),
                            cookies_str=cookies_str,
                            proxies=None
                        )
                        
                        if comment_success:
                            # 转换评论数据格式
                            formatted_comments = []
                            for comment in comments:
                                formatted_comment = convert_comment_to_xhs_format(comment, note.get('id'))
                                formatted_comments.append(formatted_comment)
                            
                            all_comments[note.get('id')] = {
                                "success": True,
                                "count": len(formatted_comments),
                                "comments": formatted_comments
                            }
                            logger.success(f"✅ 获取到 {len(formatted_comments)} 条评论")
                        else:
                            all_comments[note.get('id')] = {
                                "success": False,
                                "error": comment_msg,
                                "count": 0,
                                "comments": []
                            }
                            logger.warning(f"⚠️ 获取评论失败: {comment_msg}")
                            errors.append(f"笔记 {note.get('id')} 评论获取失败: {comment_msg}")
                            
                    except Exception as comment_error:
                        error_msg = f"获取评论异常: {str(comment_error)}"
                        logger.error(f"❌ {error_msg}")
                        logger.debug(f"评论获取错误详情: {traceback.format_exc()}")
                        
                        all_comments[note.get('id')] = {
                            "success": False,
                            "error": error_msg,
                            "count": 0,
                            "comments": []
                        }
                        errors.append(error_msg)
                
            except Exception as note_error:
                error_msg = f"处理笔记失败 {note.get('id', 'unknown')}: {str(note_error)}"
                logger.error(f"❌ {error_msg}")
                logger.debug(f"笔记处理错误详情: {traceback.format_exc()}")
                errors.append(error_msg)
                continue
        
        # 5. 准备最终结果数据 - 符合 WebhookRequest 模式
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # 构建符合 XhsSearchResult 模式的数据
        search_result_data = {
            "query": query,
            "total_found": len(notes),
            "notes": processed_notes
        }
        
        # 如果获取了评论，添加评论数据
        if get_comments:
            comment_stats = {
                "total_notes_with_comments": len([c for c in all_comments.values() if c['success']]),
                "total_comments_count": sum([c['count'] for c in all_comments.values() if c['success']]),
                "failed_comments": len([c for c in all_comments.values() if not c['success']])
            }
            search_result_data["comments"] = all_comments
            search_result_data["comment_stats"] = comment_stats
            
            logger.info(f"💬 评论统计: {comment_stats['total_notes_with_comments']}/{len(processed_notes)} 篇笔记获取成功, 共 {comment_stats['total_comments_count']} 条评论")
        
        # 最终的webhook数据 - 符合 WebhookRequest 模式
        final_webhook_data = {
            "status": "success" if not errors else "completed",
            "message": f"成功处理 {len(processed_notes)} 条笔记" + (f"，有 {len(errors)} 个错误" if errors else ""),
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "elapsed_time": elapsed_time,
            "progress": 100,
            "data": search_result_data
        }
        
        if task_id:
            final_webhook_data["task_id"] = task_id
        
        # 如果有错误，添加错误信息
        if errors:
            final_webhook_data["errors"] = errors
        
        # 6. 发送到 webhook
        if webhook_url:
            webhook_success = send_webhook(webhook_url, final_webhook_data)
            if webhook_success:
                logger.success(f"🎉 成功发送 {len(processed_notes)} 条笔记到 webhook")
            else:
                logger.warning("⚠️ Webhook发送失败，但数据处理成功")
        else:
            logger.info("ℹ️  未提供Webhook URL，跳过发送")
        
        # 7. 显示摘要
        logger.info("\n" + "="*60)
        logger.info("📊 处理结果摘要:")
        logger.info(f"🔍 搜索关键词: {query}")
        logger.info(f"📈 找到笔记总数: {len(notes)}")
        logger.info(f"✅ 成功处理笔记: {len(processed_notes)}")
        logger.info(f"⏱️  总耗时: {elapsed_time:.2f}秒")
        if get_comments:
            logger.info(f"💬 获取评论情况: {comment_stats['total_notes_with_comments']}/{len(processed_notes)} 成功")
        if errors:
            logger.warning(f"⚠️  错误数量: {len(errors)}")
        logger.info("="*60)
        
        return True, "成功", processed_notes
        
    except Exception as e:
        error_msg = f"搜索过程发生错误: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.debug(f"详细错误: {traceback.format_exc()}")
        
        # 发送错误信息到 webhook
        if webhook_url:
            error_data = {
                "status": "failed",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
                "run_id": run_id,
                "elapsed_time": (datetime.now() - start_time).total_seconds(),
                "data": {
                    "query": query,
                    "total_found": 0,
                    "notes": []
                },
                "errors": [error_msg]
            }
            if task_id:
                error_data["task_id"] = task_id
            send_webhook(webhook_url, error_data)
        
        return False, error_msg, []


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='小红书搜索爬虫 GitHub Action (增强版)')
    parser.add_argument('--query', required=True, help='搜索关键词')
    parser.add_argument('--num', type=int, default=10, help='爬取数量 (默认: 10)')
    parser.add_argument('--sort-type', type=int, default=0, 
                       help='排序方式: 0-综合排序, 1-最新, 2-最多点赞, 3-最多评论, 4-最多收藏 (默认: 0)')
    parser.add_argument('--cookies', required=True, help='小红书 cookies')
    parser.add_argument('--webhook-url', default=None, help='Webhook URL (可选，用于接收爬取结果)')
    parser.add_argument('--get-comments', action='store_true', help='是否获取评论 (默认: 否)')
    parser.add_argument('--no-delay', action='store_true', help='禁用随机延迟 (默认: 启用延迟)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--run-id', default=None, help='运行ID (可选，用于追踪)')
    parser.add_argument('--task-id', default=None, help='任务ID (可选，用于webhook回调时识别任务)')
    
    args = parser.parse_args()
    
    # 生成运行ID
    run_id = args.run_id or generate_run_id()
    
    # 配置日志
    logger.remove()
    log_level = "DEBUG" if args.debug else "INFO"
    logger.add(sys.stdout, level=log_level, format="{time} | {level} | {message}")
    
    logger.info("🚀 启动增强版小红书搜索爬虫...")
    logger.info(f"运行ID: {run_id}")
    logger.info(f"参数: 关键词='{args.query}', 数量={args.num}, 排序={args.sort_type}, 获取评论={args.get_comments}")
    
    if args.no_delay:
        logger.info("⚡ 已禁用随机延迟，将快速执行")
    else:
        logger.info("⏱️  已启用随机延迟，模拟真实用户行为")
    
    if args.webhook_url:
        logger.info(f"Webhook URL: {args.webhook_url}")
    else:
        logger.info("未提供Webhook URL，结果将仅在日志中显示")
    
    # 执行搜索和处理
    success, msg, notes = search_and_process_notes(
        query=args.query,
        num=args.num,
        cookies_str=args.cookies,
        sort_type=args.sort_type,
        webhook_url=args.webhook_url,
        get_comments=args.get_comments,
        no_delay=args.no_delay,
        run_id=run_id,
        task_id=args.task_id
    )
    
    if success:
        logger.success("🎉 任务完成")
        if notes:
            logger.info(f"✅ 成功处理 {len(notes)} 条笔记数据")
        sys.exit(0)
    else:
        logger.error(f"❌ 任务失败: {msg}")
        sys.exit(1)


if __name__ == '__main__':
    main() 