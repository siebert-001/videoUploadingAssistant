class AutomationCancelled(Exception):
    pass


class VideoSkipError(Exception):
    """当前视频缺少 AI 推荐标题/关键词，应跳过不提交。"""

    pass
