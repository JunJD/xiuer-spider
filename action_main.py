#!/usr/bin/env python3
"""
GitHub Action 入口文件
用于在 GitHub Action 中运行小红书搜索爬虫
"""

import argparse
import json
import os
import sys
import requests
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info


def send_webhook(webhook_url: str, data: dict):
    """发送数据到 webhook"""
    try:
        response = requests.post(
            webhook_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        logger.info(f"Webhook 发送成功: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Webhook 发送失败: {e}")
        return False


def search_and_send_webhook(
    query: str,
    num: int,
    cookies_str: str,
    sort_type: int,
    webhook_url: str
):
    """搜索并发送到 webhook"""
    try:
        xhs_apis = XHS_Apis()
        
        # 搜索笔记
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
            logger.error(f"搜索失败: {msg}")
            # 发送失败信息到 webhook
            error_data = {
                "status": "error",
                "message": f"搜索失败: {msg}",
                "query": query,
                "timestamp": logger.opt(record=True).bind().record["time"].isoformat()
            }
            send_webhook(webhook_url, error_data)
            return False
        
        # 过滤笔记类型
        notes = list(filter(lambda x: x['model_type'] == "note", notes))
        logger.info(f'搜索关键词 {query} 笔记数量: {len(notes)}')
        
        # 获取详细信息
        detailed_notes = []
        for note in notes[:num]:  # 限制数量
            try:
                note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                success, msg, note_info = xhs_apis.get_note_info(note_url, cookies_str, None)
                
                if success and note_info:
                    note_detail = note_info['data']['items'][0]
                    note_detail['url'] = note_url
                    note_detail = handle_note_info(note_detail)
                    detailed_notes.append(note_detail)
                    
            except Exception as e:
                logger.warning(f"获取笔记详情失败 {note.get('id', 'unknown')}: {e}")
                continue
        
        # 发送结果到 webhook
        webhook_data = {
            "status": "success",
            "query": query,
            "total_found": len(notes),
            "returned_count": len(detailed_notes),
            "sort_type": sort_type,
            "notes": detailed_notes,
            "timestamp": logger.opt(record=True).bind().record["time"].isoformat()
        }
        
        success = send_webhook(webhook_url, webhook_data)
        if success:
            logger.info(f"成功发送 {len(detailed_notes)} 条笔记到 webhook")
        
        return success
        
    except Exception as e:
        logger.error(f"搜索过程发生错误: {e}")
        # 发送错误信息到 webhook
        error_data = {
            "status": "error",
            "message": f"搜索过程发生错误: {str(e)}",
            "query": query,
            "timestamp": logger.opt(record=True).bind().record["time"].isoformat()
        }
        send_webhook(webhook_url, error_data)
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='小红书搜索爬虫 GitHub Action')
    parser.add_argument('--query', required=True, help='搜索关键词')
    parser.add_argument('--num', type=int, default=10, help='爬取数量 (默认: 10)')
    parser.add_argument('--sort-type', type=int, default=0, 
                       help='排序方式: 0-综合排序, 1-最新, 2-最多点赞, 3-最多评论, 4-最多收藏 (默认: 0)')
    parser.add_argument('--cookies', required=True, help='小红书 cookies')
    parser.add_argument('--webhook-url', required=True, help='Webhook URL')
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time} | {level} | {message}")
    
    logger.info(f"开始搜索: 关键词={args.query}, 数量={args.num}, 排序={args.sort_type}")
    
    # 执行搜索并发送 webhook
    success = search_and_send_webhook(
        query=args.query,
        num=args.num,
        cookies_str=args.cookies,
        sort_type=args.sort_type,
        webhook_url=args.webhook_url
    )
    
    if success:
        logger.info("任务完成")
        sys.exit(0)
    else:
        logger.error("任务失败")
        sys.exit(1)


if __name__ == '__main__':
    main() 