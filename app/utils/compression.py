#!/usr/bin/env python3
"""
压缩工具模块
"""

import gzip
import zlib
from io import BytesIO

class CompressionUtils:
    """压缩工具类"""
    
    @staticmethod
    def gzip_compress(data: str) -> bytes:
        """使用gzip压缩字符串"""
        return gzip.compress(data.encode())
    
    @staticmethod
    def gzip_decompress(data: bytes) -> str:
        """解压gzip数据"""
        return gzip.decompress(data).decode()
    
    @staticmethod
    def zlib_compress(data: str, level: int = 6) -> bytes:
        """使用zlib压缩字符串"""
        return zlib.compress(data.encode(), level)
    
    @staticmethod
    def zlib_decompress(data: bytes) -> str:
        """解压zlib数据"""
        return zlib.decompress(data).decode()
    
    @staticmethod
    def compress_file(input_path: str, output_path: str) -> bool:
        """压缩文件"""
        try:
            with open(input_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            return True
        except Exception as e:
            print(f"文件压缩失败: {e}")
            return False
    
    @staticmethod
    def decompress_file(input_path: str, output_path: str) -> bool:
        """解压文件"""
        try:
            with gzip.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True
        except Exception as e:
            print(f"文件解压失败: {e}")
            return False
