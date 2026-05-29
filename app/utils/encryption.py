#!/usr/bin/env python3
"""
加密工具模块
"""

import hashlib
from cryptography.fernet import Fernet
from typing import Optional

class EncryptionUtils:
    """加密工具类"""
    
    def __init__(self, key: Optional[bytes] = None):
        """初始化加密工具"""
        if key:
            self.cipher = Fernet(key)
        else:
            # 生成新密钥
            self.key = Fernet.generate_key()
            self.cipher = Fernet(self.key)
    
    def encrypt(self, data: str) -> str:
        """加密字符串"""
        if not data:
            return data
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密字符串"""
        if not encrypted_data:
            return encrypted_data
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    @staticmethod
    def md5_hash(data: str) -> str:
        """计算MD5哈希值"""
        return hashlib.md5(data.encode()).hexdigest()
    
    @staticmethod
    def sha256_hash(data: str) -> str:
        """计算SHA256哈希值"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def generate_key() -> bytes:
        """生成新的加密密钥"""
        return Fernet.generate_key()
