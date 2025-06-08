# Clash代理客户端部署指南

本指南详细介绍如何在不同环境中部署和运行Clash代理客户端。

## 🚀 快速部署

### 1. 环境准备

#### 系统要求
- Python 3.8+
- 2GB+ 内存
- 稳定的网络连接
- Linux/Windows/macOS

#### 安装依赖
```bash
# 克隆或下载项目
git clone <repository-url>
cd nautilus_trader-develop

# 安装Python依赖
pip install -r nautilus_trader/adapters/clash/requirements.txt

# 或者单独安装
pip install aiohttp pyyaml psutil requests beautifulsoup4
```

### 2. 安装Clash核心

#### Linux系统
```bash
# 下载Mihomo (推荐)
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.0/mihomo-linux-amd64-v1.18.0.gz
gunzip mihomo-linux-amd64-v1.18.0.gz
chmod +x mihomo-linux-amd64-v1.18.0
sudo mv mihomo-linux-amd64-v1.18.0 /usr/local/bin/mihomo

# 验证安装
mihomo -v
```

#### Windows系统
```powershell
# 下载Windows版本
# 访问 https://github.com/MetaCubeX/mihomo/releases
# 下载 mihomo-windows-amd64-v1.18.0.zip
# 解压到 C:\Program Files\mihomo\
# 添加到系统PATH环境变量

# 验证安装
mihomo.exe -v
```

#### macOS系统
```bash
# 使用Homebrew (如果可用)
brew install mihomo

# 或手动下载
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.0/mihomo-darwin-amd64-v1.18.0.gz
gunzip mihomo-darwin-amd64-v1.18.0.gz
chmod +x mihomo-darwin-amd64-v1.18.0
sudo mv mihomo-darwin-amd64-v1.18.0 /usr/local/bin/mihomo
```

### 3. 快速测试

```bash
# 进入项目目录
cd nautilus_trader/adapters/clash

# 运行快速测试
python quick_start.py

# 运行完整测试
python test_client.py
```

## 🐳 Docker部署

### Dockerfile
```dockerfile
FROM python:3.9-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Mihomo
RUN wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.0/mihomo-linux-amd64-v1.18.0.gz \
    && gunzip mihomo-linux-amd64-v1.18.0.gz \
    && chmod +x mihomo-linux-amd64-v1.18.0 \
    && mv mihomo-linux-amd64-v1.18.0 /usr/local/bin/mihomo

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY nautilus_trader/adapters/clash/ ./clash/
COPY requirements.txt .

# 安装Python依赖
RUN pip install -r requirements.txt

# 创建配置目录
RUN mkdir -p /app/clash_configs

# 暴露端口
EXPOSE 7890 9090

# 启动命令
CMD ["python", "clash/quick_start.py"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  clash-proxy:
    build: .
    container_name: clash-proxy-client
    ports:
      - "7890:7890"  # 代理端口
      - "9090:9090"  # 管理端口
    volumes:
      - ./clash_configs:/app/clash_configs
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/proxies"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 可选：添加监控服务
  monitor:
    build: .
    container_name: clash-monitor
    command: python clash/monitor.py
    depends_on:
      - clash-proxy
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
```

### 构建和运行
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f clash-proxy

# 停止服务
docker-compose down
```

## 🔧 生产环境部署

### 1. 系统服务配置

#### systemd服务 (Linux)
```ini
# /etc/systemd/system/clash-proxy.service
[Unit]
Description=Clash Proxy Client
After=network.target

[Service]
Type=simple
User=clash
Group=clash
WorkingDirectory=/opt/clash-proxy
ExecStart=/usr/bin/python3 /opt/clash-proxy/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# 启用和启动服务
sudo systemctl enable clash-proxy
sudo systemctl start clash-proxy
sudo systemctl status clash-proxy
```

#### 主程序文件
```python
# /opt/clash-proxy/main.py
import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from clash.client import ClashProxyClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/clash-proxy.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ProxyService:
    def __init__(self):
        self.client = ClashProxyClient(config_dir='/etc/clash-proxy')
        self.running = False
    
    async def start(self):
        """启动代理服务"""
        try:
            success = await self.client.start(
                config_type='scraping',
                enable_auto_update=True
            )
            
            if success:
                self.running = True
                logger.info("代理服务启动成功")
                
                # 保持运行
                while self.running:
                    await asyncio.sleep(10)
            else:
                logger.error("代理服务启动失败")
                
        except Exception as e:
            logger.error(f"代理服务异常: {e}")
        finally:
            await self.client.stop()
    
    def stop(self):
        """停止代理服务"""
        self.running = False
        logger.info("正在停止代理服务...")

# 全局服务实例
service = ProxyService()

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，正在关闭服务...")
    service.stop()

# 注册信号处理器
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("服务被用户中断")
    except Exception as e:
        logger.error(f"服务运行异常: {e}")
        sys.exit(1)
```

### 2. 配置文件管理

#### 配置目录结构
```
/etc/clash-proxy/
├── config.yaml          # 主配置文件
├── proxies/             # 代理配置目录
│   ├── clash.yaml
│   └── backups/
├── logs/                # 日志目录
└── scripts/             # 脚本目录
    ├── health_check.py
    └── update_proxies.py
```

#### 主配置文件
```yaml
# /etc/clash-proxy/config.yaml
proxy_client:
  config_dir: "/etc/clash-proxy"
  clash_binary_path: "/usr/local/bin/mihomo"
  auto_update_interval: 3600
  
health_check:
  interval: 300
  timeout: 10
  max_concurrent: 10
  
logging:
  level: "INFO"
  file: "/var/log/clash-proxy.log"
  max_size: "100MB"
  backup_count: 5
```

### 3. 监控和告警

#### 健康检查脚本
```python
# /opt/clash-proxy/health_check.py
import asyncio
import json
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

from clash.client import ClashProxyClient

class HealthMonitor:
    def __init__(self):
        self.client = ClashProxyClient()
        self.alert_threshold = 0.3  # 健康率低于30%时告警
        
    async def check_health(self):
        """检查代理健康状态"""
        try:
            await self.client.start()
            info = await self.client.get_proxy_info()
            
            health_rate = info['proxy_stats']['health_rate']
            
            # 记录状态
            status = {
                'timestamp': datetime.now().isoformat(),
                'health_rate': health_rate,
                'total_proxies': info['proxy_stats']['total_proxies'],
                'healthy_proxies': info['proxy_stats']['healthy_proxies']
            }
            
            # 保存状态到文件
            with open('/var/log/proxy_health.json', 'a') as f:
                f.write(json.dumps(status) + '\n')
            
            # 检查是否需要告警
            if health_rate < self.alert_threshold:
                await self.send_alert(status)
            
            return status
            
        finally:
            await self.client.stop()
    
    async def send_alert(self, status):
        """发送告警邮件"""
        try:
            msg = MIMEText(f"""
            代理健康状态告警
            
            时间: {status['timestamp']}
            健康率: {status['health_rate']:.1%}
            总代理数: {status['total_proxies']}
            健康代理数: {status['healthy_proxies']}
            
            请及时检查代理服务状态。
            """)
            
            msg['Subject'] = '代理服务健康告警'
            msg['From'] = 'monitor@example.com'
            msg['To'] = 'admin@example.com'
            
            # 发送邮件 (需要配置SMTP服务器)
            # smtp = smtplib.SMTP('smtp.example.com', 587)
            # smtp.send_message(msg)
            
            logging.warning(f"健康告警已发送: {status}")
            
        except Exception as e:
            logging.error(f"发送告警失败: {e}")

if __name__ == "__main__":
    monitor = HealthMonitor()
    asyncio.run(monitor.check_health())
```

#### 定时任务配置
```bash
# 添加到crontab
# crontab -e

# 每5分钟检查一次健康状态
*/5 * * * * /usr/bin/python3 /opt/clash-proxy/health_check.py

# 每小时更新代理列表
0 * * * * /usr/bin/python3 /opt/clash-proxy/update_proxies.py

# 每天清理旧日志
0 2 * * * find /var/log -name "clash-proxy*.log" -mtime +7 -delete
```

## 🔍 故障排除

### 常见问题

1. **代理客户端启动失败**
   ```bash
   # 检查Clash二进制文件
   which mihomo
   mihomo -v
   
   # 检查端口占用
   netstat -tlnp | grep 7890
   netstat -tlnp | grep 9090
   
   # 检查权限
   ls -la /usr/local/bin/mihomo
   ```

2. **无法获取代理节点**
   ```bash
   # 测试网络连接
   curl -I https://raw.githubusercontent.com/Flikify/getNode/main/clash.yaml
   
   # 检查DNS解析
   nslookup raw.githubusercontent.com
   
   # 使用代理测试
   curl --proxy http://127.0.0.1:7890 http://httpbin.org/ip
   ```

3. **代理连接失败**
   ```bash
   # 检查Clash进程
   ps aux | grep mihomo
   
   # 检查Clash日志
   tail -f /var/log/clash-proxy.log
   
   # 测试Clash API
   curl http://127.0.0.1:9090/proxies
   ```

### 日志分析

```bash
# 查看实时日志
tail -f /var/log/clash-proxy.log

# 搜索错误信息
grep -i error /var/log/clash-proxy.log

# 统计成功率
grep "成功" /var/log/clash-proxy.log | wc -l
```

### 性能监控

```bash
# 监控系统资源
top -p $(pgrep -f clash-proxy)

# 监控网络连接
ss -tuln | grep -E "(7890|9090)"

# 监控代理使用情况
curl -s http://127.0.0.1:9090/proxies | jq '.proxies | length'
```

通过以上部署指南，您可以在生产环境中稳定运行Clash代理客户端，为爬虫应用提供可靠的代理服务。
