#!/usr/bin/env python3
"""
PCAP 网络抓包解析器 - 解析网络数据包并生成分析报告
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

try:
    from scapy.all import rdpcap, IP, TCP, UDP, ICMP, ARP, DNS, HTTP, TLS, Raw
    from scapy.utils import PcapReader
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


class NetworkPacket:
    """表示单个网络数据包"""
    
    def __init__(self, timestamp: float, src_ip: str, dst_ip: str, 
                 protocol: str, src_port: int, dst_port: int, 
                 length: int, info: str, raw_data: bytes = b""):
        self.timestamp = timestamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.protocol = protocol
        self.src_port = src_port
        self.dst_port = dst_port
        self.length = length
        self.info = info
        self.raw_data = raw_data
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "protocol": self.protocol,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "length": self.length,
            "info": self.info
        }
    
    def __repr__(self):
        return f"[{self.timestamp}] {self.protocol} {self.src_ip}:{self.src_port} -> {self.dst_ip}:{self.dst_port}"


class PCAPParser:
    """解析 PCAP 网络抓包文件"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.packets: List[NetworkPacket] = []
        self.analysis_results: Dict = {}
    
    def parse_file(self, filepath: str) -> List[NetworkPacket]:
        """解析 PCAP 文件"""
        if not SCAPY_AVAILABLE:
            raise ImportError("scapy 未安装，请安装: pip install scapy")
        
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"PCAP 文件未找到: {filepath}")
        
        self.packets = []
        
        try:
            # 使用 PcapReader 处理大文件
            with PcapReader(str(path)) as reader:
                for pkt in reader:
                    packet = self._parse_packet(pkt)
                    if packet:
                        self.packets.append(packet)
        except Exception as e:
            # 尝试用 rdpcap
            try:
                packets = rdpcap(str(path))
                for pkt in packets:
                    packet = self._parse_packet(pkt)
                    if packet:
                        self.packets.append(packet)
            except Exception as ex:
                raise ValueError(f"无法解析 PCAP 文件: {str(ex)}")
        
        return self.packets
    
    def _parse_packet(self, pkt) -> Optional[NetworkPacket]:
        """解析单个数据包"""
        timestamp = float(pkt.time)
        src_ip = dst_ip = "unknown"
        src_port = dst_port = 0
        protocol = "Unknown"
        info = ""
        raw_data = b""
        
        # 获取 IP 层信息
        if IP in pkt:
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
            protocol = pkt[IP].proto
            
            # 协议号转协议名
            proto_map = {6: "TCP", 17: "UDP", 1: "ICMP", 50: "ESP", 51: "AH"}
            protocol = proto_map.get(protocol, str(protocol))
        
        elif ARP in pkt:
            src_ip = pkt[ARP].psrc
            dst_ip = pkt[ARP].pdst
            protocol = "ARP"
        
        # 获取传输层信息
        if TCP in pkt:
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport
            protocol = "TCP"
            
            # TCP 标志位
            flags = []
            if pkt[TCP].flags.S: flags.append("SYN")
            if pkt[TCP].flags.A: flags.append("ACK")
            if pkt[TCP].flags.F: flags.append("FIN")
            if pkt[TCP].flags.R: flags.append("RST")
            if pkt[TCP].flags.P: flags.append("PSH")
            if pkt[TCP].flags.U: flags.append("URG")
            
            info = f"TCP {src_port} -> {dst_port} {' '.join(flags)}"
            
            # 获取应用层数据
            if Raw in pkt:
                raw_data = bytes(pkt[Raw])
                
            # HTTP 检测
            if HTTP in pkt:
                info += " [HTTP]"
        
        elif UDP in pkt:
            src_port = pkt[UDP].sport
            dst_port = pkt[UDP].dport
            protocol = "UDP"
            info = f"UDP {src_port} -> {dst_port}"
            
            # DNS 检测
            if DNS in pkt:
                info += " [DNS]"
        
        elif ICMP in pkt:
            protocol = "ICMP"
            info = f"ICMP {pkt[ICMP].type}"
        
        elif ARP in pkt:
            info = f"ARP {pkt[ARP].op}"
        
        else:
            info = pkt.summary()[:50]
        
        return NetworkPacket(
            timestamp=timestamp,
            src_ip=src_ip,
            dst_ip=dst_ip,
            protocol=protocol,
            src_port=src_port,
            dst_port=dst_port,
            length=len(pkt),
            info=info,
            raw_data=raw_data
        )
    
    def analyze(self) -> Dict:
        """分析数据包并生成统计报告"""
        if not self.packets:
            return {}
        
        results = {
            "summary": {},
            "protocols": {},
            "top_talkers": {},
            "traffic_analysis": {},
            "security_issues": [],
            "dns_queries": [],
            "http_requests": []
        }
        
        # 基础统计
        total_packets = len(self.packets)
        total_bytes = sum(p.length for p in self.packets)
        start_time = min(p.timestamp for p in self.packets)
        end_time = max(p.timestamp for p in self.packets)
        duration = end_time - start_time
        
        results["summary"] = {
            "total_packets": total_packets,
            "total_bytes": total_bytes,
            "start_time": datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(duration, 2),
            "packets_per_second": round(total_packets / duration, 2) if duration > 0 else 0,
            "bytes_per_second": round(total_bytes / duration, 2) if duration > 0 else 0
        }
        
        # 协议分布
        proto_counts = {}
        for p in self.packets:
            proto_counts[p.protocol] = proto_counts.get(p.protocol, 0) + 1
        
        results["protocols"] = {
            "distribution": proto_counts,
            "top_protocols": sorted(proto_counts.items(), key=lambda x: -x[1])[:5]
        }
        
        # 流量分析 (Top Talkers)
        ip_pairs = {}
        ip_bytes = {}
        
        for p in self.packets:
            pair = (p.src_ip, p.dst_ip)
            ip_pairs[pair] = ip_pairs.get(pair, 0) + 1
            ip_bytes[pair] = ip_bytes.get(pair, 0) + p.length
        
        results["top_talkers"] = {
            "by_packets": sorted(ip_pairs.items(), key=lambda x: -x[1])[:10],
            "by_bytes": sorted(ip_bytes.items(), key=lambda x: -x[1])[:10]
        }
        
        # IP 统计
        src_ips = {}
        dst_ips = {}
        for p in self.packets:
            src_ips[p.src_ip] = src_ips.get(p.src_ip, 0) + 1
            dst_ips[p.dst_ip] = dst_ips.get(p.dst_ip, 0) + 1
        
        results["traffic_analysis"] = {
            "source_ips": sorted(src_ips.items(), key=lambda x: -x[1])[:10],
            "dest_ips": sorted(dst_ips.items(), key=lambda x: -x[1])[:10],
            "unique_src_ips": len(src_ips),
            "unique_dst_ips": len(dst_ips)
        }
        
        # 安全问题检测
        security_issues = []
        
        # 检测 SYN 洪水攻击
        syn_count = sum(1 for p in self.packets if "SYN" in p.info and "ACK" not in p.info)
        if syn_count > total_packets * 0.3:
            security_issues.append({
                "severity": "HIGH",
                "issue": "SYN 洪水攻击疑似",
                "description": f"检测到大量 SYN 包 ({syn_count} 个)，可能存在 SYN 洪水攻击",
                "count": syn_count
            })
        
        # 检测端口扫描
        unique_ports = len(set(p.dst_port for p in self.packets if p.dst_port > 0))
        if unique_ports > 100:
            security_issues.append({
                "severity": "MEDIUM",
                "issue": "端口扫描疑似",
                "description": f"检测到访问 {unique_ports} 个不同端口，可能存在端口扫描行为",
                "count": unique_ports
            })
        
        # 检测 DNS 查询
        dns_queries = []
        for p in self.packets:
            if p.protocol == "UDP" and (p.src_port == 53 or p.dst_port == 53):
                dns_queries.append({
                    "src_ip": p.src_ip,
                    "dst_ip": p.dst_ip,
                    "timestamp": datetime.fromtimestamp(p.timestamp).strftime("%H:%M:%S"),
                    "info": p.info
                })
        
        results["dns_queries"] = dns_queries[:50]
        
        # 检测 HTTP 请求
        http_requests = []
        for p in self.packets:
            if "HTTP" in p.info and p.raw_data:
                try:
                    http_data = p.raw_data.decode('utf-8', errors='ignore')
                    if http_data.startswith(('GET', 'POST', 'PUT', 'DELETE')):
                        lines = http_data.split('\n')[:3]
                        http_requests.append({
                            "src_ip": p.src_ip,
                            "dst_ip": p.dst_ip,
                            "timestamp": datetime.fromtimestamp(p.timestamp).strftime("%H:%M:%S"),
                            "request": '\n'.join(lines)[:200]
                        })
                except:
                    pass
        
        results["http_requests"] = http_requests[:30]
        
        results["security_issues"] = security_issues
        self.analysis_results = results
        
        return results
    
    def generate_report(self) -> str:
        """生成专业的网络分析报告（Markdown格式）"""
        if not self.analysis_results:
            return "# 网络分析报告\n\n暂无数据"
        
        results = self.analysis_results
        
        report = []
        
        # 标题
        report.append("# 网络流量分析报告")
        report.append("")
        report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("---")
        report.append("")
        
        # 1. 概览摘要
        report.append("## 1. 概览摘要")
        report.append("")
        summary = results["summary"]
        report.append(f"""| 指标 | 数值 |
|------|------|
| 总数据包数 | {summary['total_packets']:,} 个 |
| 总流量 | {self._format_bytes(summary['total_bytes'])} |
| 捕获时长 | {self._format_duration(summary['duration_seconds'])} |
| 平均包速率 | {summary['packets_per_second']} pps |
| 平均比特率 | {self._format_bps(summary['bytes_per_second'] * 8)} |
| 开始时间 | {summary['start_time']} |
| 结束时间 | {summary['end_time']} |""")
        report.append("")
        
        # 2. 协议分布
        report.append("## 2. 协议分布")
        report.append("")
        proto_dist = results["protocols"]
        report.append("### 协议统计")
        report.append("")
        report.append("| 协议 | 数据包数 | 占比 |")
        report.append("|------|----------|------|")
        total = results["summary"]["total_packets"]
        for proto, count in proto_dist["top_protocols"]:
            percent = round(count / total * 100, 2)
            report.append(f"| {proto} | {count:,} | {percent}% |")
        report.append("")
        
        # 3. Top Talkers
        report.append("## 3. Top Talkers")
        report.append("")
        
        report.append("### 按数据包数")
        report.append("")
        report.append("| 源IP -> 目的IP | 数据包数 |")
        report.append("|----------------|----------|")
        for (src, dst), count in results["top_talkers"]["by_packets"]:
            report.append(f"| `{src}` -> `{dst}` | {count:,} |")
        report.append("")
        
        report.append("### 按流量")
        report.append("")
        report.append("| 源IP -> 目的IP | 流量 |")
        report.append("|----------------|------|")
        for (src, dst), bytes_count in results["top_talkers"]["by_bytes"]:
            report.append(f"| `{src}` -> `{dst}` | {self._format_bytes(bytes_count)} |")
        report.append("")
        
        # 4. IP 分析
        report.append("## 4. IP 地址分析")
        report.append("")
        
        report.append("### 活跃源IP")
        report.append("")
        report.append(f"**唯一源IP数量**: {results['traffic_analysis']['unique_src_ips']}")
        report.append("")
        report.append("| 源IP | 数据包数 |")
        report.append("|------|----------|")
        for ip, count in results["traffic_analysis"]["source_ips"]:
            report.append(f"| `{ip}` | {count:,} |")
        report.append("")
        
        report.append("### 活跃目的IP")
        report.append("")
        report.append(f"**唯一目的IP数量**: {results['traffic_analysis']['unique_dst_ips']}")
        report.append("")
        report.append("| 目的IP | 数据包数 |")
        report.append("|--------|----------|")
        for ip, count in results["traffic_analysis"]["dest_ips"]:
            report.append(f"| `{ip}` | {count:,} |")
        report.append("")
        
        # 5. 安全告警
        report.append("## 5. 安全告警")
        report.append("")
        
        issues = results["security_issues"]
        if issues:
            for issue in issues:
                severity_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(issue["severity"], "⚪")
                report.append(f"### {severity_color} {issue['issue']}")
                report.append("")
                report.append(f"- **严重级别**: {issue['severity']}")
                report.append(f"- **描述**: {issue['description']}")
                report.append("")
        else:
            report.append("✅ 未检测到明显的安全威胁")
            report.append("")
        
        # 6. DNS 查询
        report.append("## 6. DNS 查询记录")
        report.append("")
        dns_queries = results["dns_queries"]
        if dns_queries:
            report.append("| 时间 | 源IP | 目的IP | 信息 |")
            report.append("|------|------|--------|------|")
            for q in dns_queries[:20]:
                report.append(f"| {q['timestamp']} | `{q['src_ip']}` | `{q['dst_ip']}` | {q['info']} |")
        else:
            report.append("未检测到 DNS 查询")
        report.append("")
        
        # 7. HTTP 请求
        report.append("## 7. HTTP 请求")
        report.append("")
        http_reqs = results["http_requests"]
        if http_reqs:
            report.append("| 时间 | 源IP | 目的IP | 请求 |")
            report.append("|------|------|--------|------|")
            for req in http_reqs[:15]:
                request = req['request'].replace('\n', ' ')[:80]
                report.append(f"| {req['timestamp']} | `{req['src_ip']}` | `{req['dst_ip']}` | `{request}` |")
        else:
            report.append("未检测到 HTTP 请求")
        report.append("")
        
        # 附录
        report.append("---")
        report.append("")
        report.append("## 附录")
        report.append("")
        report.append("### 报告说明")
        report.append("")
        report.append("- 报告基于 PCAP 抓包文件自动生成")
        report.append("- 安全告警仅供参考，需结合实际场景分析")
        report.append("- 数据量较大时，部分详细信息可能被截断")
        report.append("")
        
        return '\n'.join(report)
    
    def _format_bytes(self, bytes_count: int) -> str:
        """格式化字节数"""
        if bytes_count < 1024:
            return f"{bytes_count} B"
        elif bytes_count < 1024 * 1024:
            return f"{bytes_count / 1024:.2f} KB"
        elif bytes_count < 1024 * 1024 * 1024:
            return f"{bytes_count / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds:.2f} 秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes} 分 {secs:.1f} 秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours} 时 {minutes} 分 {secs:.1f} 秒"
    
    def _format_bps(self, bps: float) -> str:
        """格式化比特率"""
        if bps < 1000:
            return f"{bps:.1f} bps"
        elif bps < 1000 * 1000:
            return f"{bps / 1000:.2f} kbps"
        elif bps < 1000 * 1000 * 1000:
            return f"{bps / (1000 * 1000):.2f} Mbps"
        else:
            return f"{bps / (1000 * 1000 * 1000):.2f} Gbps"