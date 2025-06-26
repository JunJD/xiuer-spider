#!/usr/bin/env python3
"""
GitHub Action 触发服务
用于从 xiuer 项目后端触发小红书爬虫任务
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class SortType(int, Enum):
    """排序方式枚举"""
    COMPREHENSIVE = 0  # 综合排序
    LATEST = 1         # 最新
    MOST_LIKED = 2     # 最多点赞
    MOST_COMMENTS = 3  # 最多评论
    MOST_COLLECTED = 4 # 最多收藏


@dataclass
class CrawlTask:
    """爬虫任务配置"""
    query: str                          # 搜索关键词
    webhook_url: Optional[str] = None   # 接收结果的webhook URL (可选)
    num: int = 10                      # 爬取数量
    sort_type: SortType = SortType.COMPREHENSIVE  # 排序方式
    get_comments: bool = False         # 是否获取评论
    no_delay: bool = False            # 是否禁用随机延迟
    cookies: Optional[str] = None      # 自定义cookies
    
    def to_payload(self) -> Dict[str, Any]:
        """转换为GitHub Action的payload格式"""
        return {
            "query": self.query,
            "num": self.num,
            "sort_type": int(self.sort_type),
            "cookies": self.cookies or os.getenv("XHS_COOKIES", ""),
            "webhook_url": self.webhook_url,
            "get_comments": self.get_comments,
            "no_delay": self.no_delay,
            "trigger_time": datetime.now().isoformat()
        }


class GitHubActionTrigger:
    """GitHub Action 触发器"""
    
    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        github_token: str
    ):
        """
        初始化触发器
        
        Args:
            repo_owner: GitHub 仓库所有者
            repo_name: GitHub 仓库名称  
            github_token: GitHub Personal Access Token
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/dispatches"
    
    def trigger_crawl_task(
        self,
        task: CrawlTask,
        event_type: str = "search-xhs"
    ) -> Dict[str, Any]:
        """
        触发爬虫任务
        
        Args:
            task: 爬虫任务配置
            event_type: 事件类型
            
        Returns:
            触发结果字典
        """
        
        # 构建请求
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        data = {
            "event_type": event_type,
            "client_payload": task.to_payload()
        }
        
        try:
            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 204:
                # 成功触发
                return {
                    "success": True,
                    "message": "GitHub Action 触发成功",
                    "task_id": f"github_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "github_run_url": f"https://github.com/{self.repo_owner}/{self.repo_name}/actions",
                    "payload": task.to_payload()
                }
            else:
                # 触发失败
                return {
                    "success": False,
                    "message": f"GitHub Action 触发失败: HTTP {response.status_code}",
                    "error": response.text,
                    "task_id": None,
                    "github_run_url": None
                }
                
        except Exception as e:
            # 请求异常
            return {
                "success": False,
                "message": f"触发 GitHub Action 时发生异常: {str(e)}",
                "error": str(e),
                "task_id": None,
                "github_run_url": None
            }
    
    def get_workflow_runs(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取最近的 workflow 运行记录
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            运行记录字典
        """
        
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        params = {
            "per_page": limit,
            "page": 1
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "total_count": data.get("total_count", 0),
                    "workflow_runs": data.get("workflow_runs", [])
                }
            else:
                return {
                    "success": False,
                    "message": f"获取 workflow 运行记录失败: HTTP {response.status_code}",
                    "error": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"获取 workflow 运行记录时发生异常: {str(e)}",
                "error": str(e)
            }


# 便捷函数
def create_trigger_from_env() -> Optional[GitHubActionTrigger]:
    """
    从环境变量创建触发器
    
    环境变量:
        - GITHUB_REPO_OWNER: GitHub 仓库所有者
        - GITHUB_REPO_NAME: GitHub 仓库名称
        - GITHUB_TOKEN: GitHub Personal Access Token
    """
    
    repo_owner = os.getenv("GITHUB_REPO_OWNER")
    repo_name = os.getenv("GITHUB_REPO_NAME") 
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not all([repo_owner, repo_name, github_token]):
        return None
    
    return GitHubActionTrigger(
        repo_owner=repo_owner,
        repo_name=repo_name,
        github_token=github_token
    )


def trigger_simple_crawl(
    query: str,
    webhook_url: Optional[str] = None,
    num: int = 10,
    get_comments: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    简单的爬虫任务触发函数
    
    Args:
        query: 搜索关键词
        webhook_url: 接收结果的webhook URL
        num: 爬取数量
        get_comments: 是否获取评论
        **kwargs: 其他参数
        
    Returns:
        触发结果字典
    """
    
    trigger = create_trigger_from_env()
    if not trigger:
        return {
            "success": False,
            "message": "无法从环境变量创建 GitHub Action 触发器，请检查配置",
            "task_id": None,
            "github_run_url": None
        }
    
    task = CrawlTask(
        query=query,
        webhook_url=webhook_url,
        num=num,
        get_comments=get_comments,
        **kwargs
    )
    
    return trigger.trigger_crawl_task(task)


# 测试函数
def test_trigger():
    """测试触发器功能"""
    
    # 从环境变量或参数设置
    import sys
    
    if len(sys.argv) < 5:
        print("用法: python trigger_service.py <repo_owner> <repo_name> <github_token> <query> <webhook_url>")
        sys.exit(1)
    
    repo_owner = sys.argv[1]
    repo_name = sys.argv[2] 
    github_token = sys.argv[3]
    query = sys.argv[4]
    webhook_url = sys.argv[5]
    
    # 创建触发器
    trigger = GitHubActionTrigger(
        repo_owner=repo_owner,
        repo_name=repo_name,
        github_token=github_token
    )
    
    # 创建任务
    task = CrawlTask(
        query=query,
        webhook_url=webhook_url,
        num=2,
        get_comments=True,
        no_delay=True
    )
    
    # 触发任务
    result = trigger.trigger_crawl_task(task)
    
    print("触发结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result["success"]


if __name__ == "__main__":
    test_trigger() 