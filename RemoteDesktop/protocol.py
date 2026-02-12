"""
远程桌面通信协议
定义数据包格式和序列化/反序列化方法
"""

import struct
import zlib
from typing import List, Dict, Optional, Tuple

# 数据包类型
PKT_INIT = 0        # 初始化包（屏幕信息）
PKT_FRAME = 1       # 完整帧
PKT_DIRTY = 2       # 脏矩形增量更新
PKT_SKIP = 3        # 跳帧（无变化）
PKT_HEARTBEAT = 4   # 心跳包

class Protocol:
    """通信协议处理类"""
    
    @staticmethod
    def pack_init(width: int, height: int) -> bytes:
        """打包初始化数据包
        
        格式: [type:1][width:4][height:4]
        """
        return struct.pack('!BII', PKT_INIT, width, height)
    
    @staticmethod
    def unpack_init(data: bytes) -> Tuple[int, int]:
        """解包初始化数据包
        
        Returns:
            (width, height)
        """
        pkt_type, width, height = struct.unpack('!BII', data[:9])
        if pkt_type != PKT_INIT:
            raise ValueError(f"Invalid packet type: {pkt_type}")
        return width, height
    
    @staticmethod
    def pack_frame(frame_data: bytes, compress: bool = True) -> bytes:
        """打包完整帧数据包
        
        格式: [type:1][compressed:1][original_size:4][data_size:4][data:N]
        """
        original_size = len(frame_data)
        
        if compress:
            compressed_data = zlib.compress(frame_data, level=1)  # 快速压缩
            data_size = len(compressed_data)
            header = struct.pack('!BBII', PKT_FRAME, 1, original_size, data_size)
            return header + compressed_data
        else:
            header = struct.pack('!BBII', PKT_FRAME, 0, original_size, original_size)
            return header + frame_data
    
    @staticmethod
    def unpack_frame(data: bytes) -> bytes:
        """解包完整帧数据包
        
        Returns:
            frame_data (解压后的原始数据)
        """
        pkt_type, compressed, original_size, data_size = struct.unpack('!BBII', data[:10])
        
        if pkt_type != PKT_FRAME:
            raise ValueError(f"Invalid packet type: {pkt_type}")
        
        frame_data = data[10:10+data_size]
        
        if compressed:
            return zlib.decompress(frame_data)
        else:
            return frame_data
    
    @staticmethod
    def pack_dirty(rects: List[Dict], frame_data: bytes, compress: bool = True) -> bytes:
        """打包脏矩形增量更新数据包
        
        格式: [type:1][compressed:1][rect_count:2][original_size:4][data_size:4]
              [rects...][data:N]
        
        每个rect: [left:4][top:4][right:4][bottom:4]
        """
        rect_count = len(rects)
        original_size = len(frame_data)
        
        # 打包矩形数据
        rects_data = b''
        for r in rects:
            rects_data += struct.pack('!IIII', r['left'], r['top'], r['right'], r['bottom'])
        
        # 压缩帧数据
        if compress:
            compressed_data = zlib.compress(frame_data, level=1)
            data_size = len(compressed_data)
            header = struct.pack('!BBHII', PKT_DIRTY, 1, rect_count, original_size, data_size)
            return header + rects_data + compressed_data
        else:
            header = struct.pack('!BBHII', PKT_DIRTY, 0, rect_count, original_size, original_size)
            return header + rects_data + frame_data
    
    @staticmethod
    def unpack_dirty(data: bytes) -> Tuple[List[Dict], bytes]:
        """解包脏矩形增量更新数据包
        
        Returns:
            (rects, frame_data)
        """
        pkt_type, compressed, rect_count, original_size, data_size = struct.unpack('!BBHII', data[:12])
        
        if pkt_type != PKT_DIRTY:
            raise ValueError(f"Invalid packet type: {pkt_type}")
        
        # 解析矩形
        rects = []
        offset = 12
        for i in range(rect_count):
            left, top, right, bottom = struct.unpack('!IIII', data[offset:offset+16])
            rects.append({
                'left': left,
                'top': top,
                'right': right,
                'bottom': bottom,
                'width': right - left,
                'height': bottom - top
            })
            offset += 16
        
        # 解析帧数据
        frame_data = data[offset:offset+data_size]
        
        if compressed:
            frame_data = zlib.decompress(frame_data)
        
        return rects, frame_data
    
    @staticmethod
    def pack_skip() -> bytes:
        """打包跳帧数据包（无变化）
        
        格式: [type:1]
        """
        return struct.pack('!B', PKT_SKIP)
    
    @staticmethod
    def unpack_skip(data: bytes) -> bool:
        """解包跳帧数据包
        
        Returns:
            True if valid skip packet
        """
        pkt_type, = struct.unpack('!B', data[:1])
        return pkt_type == PKT_SKIP
    
    @staticmethod
    def pack_heartbeat() -> bytes:
        """打包心跳数据包
        
        格式: [type:1][timestamp:8]
        """
        import time
        timestamp = int(time.time() * 1000)
        return struct.pack('!BQ', PKT_HEARTBEAT, timestamp)
    
    @staticmethod
    def unpack_heartbeat(data: bytes) -> int:
        """解包心跳数据包
        
        Returns:
            timestamp
        """
        pkt_type, timestamp = struct.unpack('!BQ', data[:9])
        if pkt_type != PKT_HEARTBEAT:
            raise ValueError(f"Invalid packet type: {pkt_type}")
        return timestamp
    
    @staticmethod
    def get_packet_type(data: bytes) -> int:
        """获取数据包类型"""
        if len(data) < 1:
            raise ValueError("Invalid packet: too short")
        return data[0]
    
    @staticmethod
    def send_packet(sock, data: bytes) -> None:
        """发送数据包（带长度前缀）
        
        格式: [length:4][data:N]
        """
        length = len(data)
        sock.sendall(struct.pack('!I', length))
        sock.sendall(data)
    
    @staticmethod
    def recv_packet(sock) -> Optional[bytes]:
        """接收数据包（读取长度前缀）
        
        Returns:
            packet data or None if connection closed
        """
        # 读取长度
        length_data = Protocol._recv_exact(sock, 4)
        if not length_data:
            return None
        
        length, = struct.unpack('!I', length_data)
        
        # 读取数据
        return Protocol._recv_exact(sock, length)
    
    @staticmethod
    def _recv_exact(sock, size: int) -> Optional[bytes]:
        """精确接收指定字节数"""
        data = b''
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data
