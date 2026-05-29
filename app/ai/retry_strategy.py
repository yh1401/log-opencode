#!/usr/bin/env python3
"""
重试策略模块 - 实现智能重试机制
"""

import time
import functools
from typing import Callable, Any, Optional

class RetryStrategy:
    """重试策略管理器"""
    
    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0, 
                 backoff_factor: float = 2.0, max_delay: float = 60.0):
        """
        初始化重试策略
        
        Args:
            max_retries: 最大重试次数
            initial_delay: 初始延迟（秒）
            backoff_factor: 退避因子
            max_delay: 最大延迟（秒）
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
    
    def _get_delay(self, attempt: int) -> float:
        """计算第N次重试的延迟时间"""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)
    
    def retry(self, func: Callable) -> Callable:
        """装饰器：自动重试失败的函数"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    print(f"操作失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    
                    if attempt < self.max_retries - 1:
                        delay = self._get_delay(attempt)
                        print(f"等待 {delay:.2f} 秒后重试...")
                        time.sleep(delay)
            
            # 所有重试都失败
            raise last_exception
        
        return wrapper
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行带重试策略的函数"""
        return self.retry(func)(*args, **kwargs)

class RetryWithFallback(RetryStrategy):
    """带降级方案的重试策略"""
    
    def __init__(self, max_retries: int = 3, fallback_func: Optional[Callable] = None,
                 initial_delay: float = 1.0, backoff_factor: float = 2.0, max_delay: float = 60.0):
        super().__init__(max_retries, initial_delay, backoff_factor, max_delay)
        self.fallback_func = fallback_func
    
    def execute_with_fallback(self, func: Callable, *args, **kwargs) -> Any:
        """执行带重试和降级的函数"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                print(f"操作失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self._get_delay(attempt)
                    print(f"等待 {delay:.2f} 秒后重试...")
                    time.sleep(delay)
        
        # 所有重试都失败，尝试降级
        if self.fallback_func:
            print("🔄 尝试降级方案...")
            try:
                return self.fallback_func(*args, **kwargs)
            except Exception as e:
                print(f"❌ 降级方案也失败: {e}")
        
        raise last_exception

# 创建默认重试策略实例
default_retry = RetryStrategy(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    max_delay=30.0
)
