# GitHub Action 触发指南

本指南介绍如何通过 GitHub API 触发小红书爬虫 GitHub Action。

## 📋 目录

- [概述](#概述)
- [环境配置](#环境配置)
- [GitHub Action 配置](#github-action-配置)
- [API 触发方式](#api-触发方式)
- [集成到 xiuer 项目](#集成到-xiuer-项目)
- [测试方法](#测试方法)
- [故障排除](#故障排除)

## 🎯 概述

GitHub Action 支持通过 `repository_dispatch` 事件进行远程触发，这允许我们：

1. **从外部系统触发爬虫任务** - 通过 HTTP API 调用
2. **动态传递参数** - 搜索关键词、数量、排序方式等
3. **接收处理结果** - 通过 webhook 回调获取爬取的数据
4. **监控执行状态** - 查看 GitHub Actions 页面了解执行情况

## ⚙️ 环境配置

### 1. GitHub Personal Access Token

创建一个具有 `repo` 权限的 Personal Access Token：

1. 访问 GitHub Settings → Developer settings → Personal access tokens
2. 点击 "Generate new token (classic)"
3. 选择权限：`repo` (Full control of private repositories)
4. 复制生成的 token

### 2. 环境变量设置

设置以下环境变量：

```bash
export GITHUB_REPO_OWNER="your-username"
export GITHUB_REPO_NAME="xiuer-spider"
export GITHUB_TOKEN="your-personal-access-token"
export XHS_COOKIES="your-xiaohongshu-cookies"
```

## 🔧 GitHub Action 配置

### workflow 文件

位置：`.github/workflows/search-keyword.yml`

支持两种触发方式：

1. **手动触发** (`workflow_dispatch`) - 在 GitHub Actions 页面手动执行
2. **API 触发** (`repository_dispatch`) - 通过 API 远程触发

### 支持的参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索关键词 |
| `num` | number | ❌ | 10 | 爬取数量 |
| `sort_type` | number | ❌ | 0 | 排序方式 (0-4) |
| `cookies` | string | ✅ | - | 小红书 cookies |
| `webhook_url` | string | ❌ | - | 接收结果的 webhook URL (可选，用于调试) |
| `get_comments` | boolean | ❌ | false | 是否获取评论 |
| `no_delay` | boolean | ❌ | false | 是否禁用随机延迟 |

## 🚀 API 触发方式

### 1. 使用命令行工具

```bash
python trigger_github_action.py \
  --repo-owner "your-username" \
  --repo-name "xiuer-spider" \
  --github-token "your-token" \
  --query "家政 合肥" \
  --num 10 \
  --cookies "your-cookies" \
  --webhook-url "http://localhost:8000/api/webhook/xhs-result" \
  --get-comments

# 或者不使用 webhook (用于调试)
python trigger_github_action.py \
  --repo-owner "your-username" \
  --repo-name "xiuer-spider" \
  --github-token "your-token" \
  --query "家政 合肥" \
  --num 5 \
  --cookies "your-cookies" \
  --get-comments
```

### 2. 使用 Python 服务类

```python
from trigger_service import GitHubActionTrigger, CrawlTask, SortType

# 创建触发器
trigger = GitHubActionTrigger(
    repo_owner="your-username",
    repo_name="xiuer-spider",
    github_token="your-token"
)

# 创建任务
task = CrawlTask(
    query="家政 合肥",
    webhook_url="http://localhost:8000/api/webhook/xhs-result",
    num=10,
    sort_type=SortType.LATEST,
    get_comments=True,
    no_delay=False
)

# 触发任务
result = trigger.trigger_crawl_task(task)
print(result)
```

### 3. 直接使用 HTTP API

```bash
curl -X POST \
  https://api.github.com/repos/your-username/xiuer-spider/dispatches \
  -H "Authorization: token your-github-token" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "search-xhs",
    "client_payload": {
      "query": "家政 合肥",
      "num": 10,
      "sort_type": 0,
      "cookies": "your-cookies",
      "webhook_url": "http://localhost:8000/api/webhook/xhs-result",
      "get_comments": true,
      "no_delay": false
    }
  }'
```

## 🔗 集成到 xiuer 项目

### 在 FastAPI 中添加触发端点

```python
from trigger_service import trigger_simple_crawl

@router.post("/api/tasks/trigger-crawl")
async def trigger_crawl_task(request: CrawlTaskRequest):
    """触发 GitHub Action 爬虫任务"""
    
    result = trigger_simple_crawl(
        query=request.keyword,
        webhook_url=request.webhook_url,
        num=request.target_count,
        get_comments=True,
        sort_type=request.sort_type,
        cookies=request.cookies
    )
    
    return TaskTriggerResponse(**result)
```

### 环境变量配置

在 xiuer 项目的 `.env` 文件中添加：

```env
# GitHub Action 配置
GITHUB_REPO_OWNER=your-username
GITHUB_REPO_NAME=xiuer-spider
GITHUB_TOKEN=your-personal-access-token
XHS_COOKIES=your-default-cookies
```

## 🧪 测试方法

### 1. 本地测试触发

```bash
# 设置环境变量
export GITHUB_REPO_OWNER="your-username"
export GITHUB_REPO_NAME="xiuer-spider"
export GITHUB_TOKEN="your-token"

# 测试触发
python trigger_service.py \
  your-username \
  xiuer-spider \
  your-token \
  "测试关键词" \
  "http://localhost:8000/api/webhook/xhs-result"
```

### 2. 验证 webhook 接收

启动 xiuer 后端服务，然后触发任务，观察控制台日志是否收到 webhook 数据。

### 3. 查看执行状态

访问 GitHub Actions 页面查看任务执行状态：
```
https://github.com/your-username/xiuer-spider/actions
```

## 🐛 故障排除

### 常见问题

1. **401 Unauthorized**
   - 检查 GitHub token 是否正确
   - 确认 token 具有 `repo` 权限

2. **404 Not Found**
   - 检查仓库所有者和名称是否正确
   - 确认仓库存在且可访问

3. **422 Validation Error**
   - 检查请求体格式是否正确
   - 确认 `event_type` 在 workflow 中已定义

4. **Workflow 不执行**
   - 检查 workflow 文件语法是否正确
   - 确认 `repository_dispatch` 事件已配置

### 调试技巧

1. **查看 Action 日志**
   ```bash
   # 获取最近的 workflow 运行记录
   curl -H "Authorization: token your-token" \
     https://api.github.com/repos/your-username/xiuer-spider/actions/runs
   ```

2. **验证 payload 数据**
   ```python
   import json
   from trigger_service import CrawlTask
   
   task = CrawlTask(query="测试", webhook_url="http://test.com")
   print(json.dumps(task.to_payload(), indent=2, ensure_ascii=False))
   ```

3. **测试 webhook 接收**
   ```bash
   # 使用 ngrok 暴露本地服务用于测试
   ngrok http 8000
   ```

## 📞 支持

如果遇到问题，请检查：

1. GitHub Actions 页面的执行日志
2. xiuer 后端的 webhook 接收日志
3. 网络连接和防火墙设置
4. 环境变量配置是否正确

---

## 🎉 完整流程示例

1. **配置环境变量**
2. **启动 xiuer 后端服务** (监听 8000 端口)
3. **触发爬虫任务**：
   ```python
   from trigger_service import trigger_simple_crawl
   
   result = trigger_simple_crawl(
       query="家政 合肥",
       webhook_url="http://your-domain.com/api/webhook/xhs-result",
       num=5,
       get_comments=True
   )
   ```
4. **监控执行** - 查看 GitHub Actions 页面
5. **接收结果** - xiuer 后端接收 webhook 数据并处理 