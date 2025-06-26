#!/usr/bin/env python3
"""
通过 GitHub API 触发小红书爬虫 GitHub Action
使用 repository_dispatch 事件来远程触发爬虫任务
"""

import requests
import json
import argparse
import sys
from datetime import datetime


def trigger_github_action(
    repo_owner: str,
    repo_name: str,
    github_token: str,
    event_type: str = "search-xhs",
    **payload
):
    """
    触发 GitHub Action
    
    Args:
        repo_owner: GitHub 仓库所有者
        repo_name: GitHub 仓库名称
        github_token: GitHub Personal Access Token
        event_type: 事件类型 (search-xhs 或 crawl-task)
        **payload: 传递给 Action 的参数
    """
    
    # GitHub API 端点
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/dispatches"
    
    # 请求头
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    # 请求体
    data = {
        "event_type": event_type,
        "client_payload": payload
    }
    
    print(f"🚀 触发 GitHub Action...")
    print(f"📍 仓库: {repo_owner}/{repo_name}")
    print(f"🎯 事件类型: {event_type}")
    print(f"📦 负载数据: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 204:
            print("✅ 成功触发 GitHub Action!")
            print(f"🔗 查看运行状态: https://github.com/{repo_owner}/{repo_name}/actions")
            return True
        else:
            print(f"❌ 触发失败: {response.status_code}")
            print(f"📄 响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='触发小红书爬虫 GitHub Action')
    
    # GitHub 相关参数
    parser.add_argument('--repo-owner', required=True, help='GitHub 仓库所有者')
    parser.add_argument('--repo-name', required=True, help='GitHub 仓库名称')
    parser.add_argument('--github-token', required=True, help='GitHub Personal Access Token')
    parser.add_argument('--event-type', default='search-xhs', choices=['search-xhs', 'crawl-task'], 
                       help='事件类型 (默认: search-xhs)')
    
    # 爬虫参数
    parser.add_argument('--query', required=True, help='搜索关键词')
    parser.add_argument('--num', type=int, default=10, help='爬取数量 (默认: 10)')
    parser.add_argument('--sort-type', type=int, default=0, choices=[0,1,2,3,4],
                       help='排序方式: 0-综合排序, 1-最新, 2-最多点赞, 3-最多评论, 4-最多收藏 (默认: 0)')
    parser.add_argument('--cookies', required=True, help='小红书 cookies')
    parser.add_argument('--webhook-url', default=None, help='Webhook URL (可选，用于接收爬取结果)')
    parser.add_argument('--get-comments', action='store_true', help='是否获取评论')
    parser.add_argument('--no-delay', action='store_true', help='是否禁用随机延迟')
    
    args = parser.parse_args()
    
    # 构建 payload
    payload = {
        "query": args.query,
        "num": args.num,
        "sort_type": args.sort_type,
        "cookies": args.cookies,
        "webhook_url": args.webhook_url,
        "get_comments": args.get_comments,
        "no_delay": args.no_delay,
        "trigger_time": datetime.now().isoformat()
    }
    
    # 触发 GitHub Action
    success = trigger_github_action(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        github_token=args.github_token,
        event_type=args.event_type,
        **payload
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 