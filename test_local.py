#!/usr/bin/env python3
"""
本地测试版本
测试小红书搜索爬虫的数据获取功能，无需webhook
"""

import argparse
import json
import os
import sys
from datetime import datetime
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info


def search_and_save_local(
    query: str,
    num: int,
    cookies_str: str,
    sort_type: int,
    save_to_file: bool = True
):
    """搜索并保存到本地文件"""
    try:
        logger.info(f"🚀 开始搜索: 关键词='{query}', 数量={num}, 排序类型={sort_type}")
        
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
            logger.error(f"❌ 搜索失败: {msg}")
            return False, msg, []
        
        # 过滤笔记类型
        notes = list(filter(lambda x: x['model_type'] == "note", notes))
        logger.info(f'✅ 搜索到 {len(notes)} 条笔记')
        
        if not notes:
            logger.warning("⚠️ 没有找到相关笔记")
            return True, "搜索成功但无结果", []
        
        # 获取详细信息
        detailed_notes = []
        logger.info(f"📝 开始获取笔记详细信息...")
        
        for i, note in enumerate(notes[:num], 1):
            try:
                logger.info(f"正在处理第 {i}/{min(num, len(notes))} 条笔记: {note.get('id', 'unknown')}")
                
                note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                success, msg, note_info = xhs_apis.get_note_info(note_url, cookies_str, None)
                
                if success and note_info:
                    note_detail = note_info['data']['items'][0]
                    note_detail['url'] = note_url
                    note_detail = handle_note_info(note_detail)
                    detailed_notes.append(note_detail)
                    logger.success(f"✅ 成功获取笔记: {note_detail.get('title', '无标题')[:50]}...")
                else:
                    logger.warning(f"⚠️ 获取笔记详情失败: {msg}")
                    
            except Exception as e:
                logger.warning(f"⚠️ 处理笔记失败 {note.get('id', 'unknown')}: {e}")
                continue
        
        # 准备结果数据
        result_data = {
            "status": "success",
            "query": query,
            "search_time": datetime.now().isoformat(),
            "total_found": len(notes),
            "returned_count": len(detailed_notes),
            "sort_type": sort_type,
            "notes": detailed_notes
        }
        
        # 保存到文件
        if save_to_file:
            filename = f"search_result_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            logger.success(f"📁 结果已保存到: {filename}")
        
        # 显示摘要
        logger.info("\n" + "="*60)
        logger.info("📊 搜索结果摘要:")
        logger.info(f"🔍 搜索关键词: {query}")
        logger.info(f"📈 找到笔记总数: {len(notes)}")
        logger.info(f"✅ 成功获取详情: {len(detailed_notes)}")
        logger.info("="*60)
        
        # 显示前几条笔记信息
        if detailed_notes:
            logger.info("\n🔥 前几条笔记预览:")
            for i, note in enumerate(detailed_notes[:3], 1):
                title = note.get('title', '无标题')[:50]
                author = note.get('user', {}).get('nickname', '未知作者')
                like_count = note.get('interact_info', {}).get('liked_count', 0)
                logger.info(f"{i}. {title}... (作者: {author}, 点赞: {like_count})")
        
        return True, "成功", detailed_notes
        
    except Exception as e:
        logger.error(f"❌ 搜索过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False, f"搜索过程发生错误: {str(e)}", []


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='小红书搜索爬虫本地测试')
    parser.add_argument('--query', required=True, help='搜索关键词')
    parser.add_argument('--num', type=int, default=5, help='爬取数量 (默认: 5, 建议测试时用小数量)')
    parser.add_argument('--sort-type', type=int, default=0, 
                       help='排序方式: 0-综合排序, 1-最新, 2-最多点赞, 3-最多评论, 4-最多收藏 (默认: 0)')
    parser.add_argument('--cookies', required=True, help='小红书 cookies')
    parser.add_argument('--no-save', action='store_true', help='不保存到文件，仅显示结果')
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time} | {level} | {message}")
    
    logger.info("🧪 开始本地测试...")
    logger.info(f"参数: 关键词='{args.query}', 数量={args.num}, 排序={args.sort_type}")
    
    # 执行搜索
    success, msg, notes = search_and_save_local(
        query=args.query,
        num=args.num,
        cookies_str=args.cookies,
        sort_type=args.sort_type,
        save_to_file=not args.no_save
    )
    
    if success:
        logger.success("🎉 测试完成！数据获取功能正常工作")
        if notes:
            logger.info(f"✅ 成功获取 {len(notes)} 条笔记数据")
        sys.exit(0)
    else:
        logger.error(f"❌ 测试失败: {msg}")
        sys.exit(1)


if __name__ == '__main__':
    main() 