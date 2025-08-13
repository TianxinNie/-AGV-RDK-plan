# Flexiv机器人+AGV集成系统 - 完整函数使用文档

## 目录

- [1. 系统概述](#1-系统概述)
- [2. 主程序使用](#2-主程序使用)
- [3. 机器人操作模块](#3-机器人操作模块)
- [4. AGV控制模块](#4-agv控制模块)
- [5. 音频报警系统](#5-音频报警系统)
- [6. 工具函数](#6-工具函数)
- [7. 完整使用示例](#7-完整使用示例)
- [8. 故障排除](#8-故障排除)

## 1. 系统概述

这是一个集成了Flexiv机器人和AGV（自动导引车）的内存条处理自动化系统，支持换工具、取料、放料、拍照检测以及连续音频报警功能。

### 1.1 项目结构

```
robot_project/
├── main.py                 # 主程序入口
├── AGV.py                  # AGV控制模块
├── core/
│   ├── rdk_init.py         # 机器人初始化
│   └── work_handler.py     # 工作流程处理器
├── plans/
│   ├── change_tool.py      # 换工具操作
│   ├── pick_mestick.py     # 取内存条操作
│   └── Put_mestick.py      # 放内存条操作
└── utils/
    └── logger.py           # 日志工具
```

## 2. 主程序使用

### 2.1 main.py - 主程序入口

#### 2.1.1 基本运行命令

```bash
# 使用默认参数运行
python main.py

# 指定参数运行
python main.py --robot-sn "Rizon10-062283" --work-station 4

# 完整参数示例
python main.py --robot-sn "Rizon10-062283" --work-station 4 --tool-num 2 --check-mestick
```

#### 2.1.2 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `--robot-sn` | str | "Rizon10-062283" | 机器人序列号 |
| `--work-num` | int | 1 | 工作编号 |
| `--log-name` | str | "RobotLogger" | 日志记录器名称 |
| `--agv-ip` | str | "192.168.2.112" | AGV的IP地址 |
| `--agv-port` | int | 502 | AGV的Modbus端口 |
| `--work-station` | int | 4 | AGV工作站点ID |
| `--disable-agv` | flag | False | 禁用AGV移动功能 |
| `--tool-num` | int | 1 | 工具编号 |
| `--check-mestick` | flag | False | 启用内存条检查 |

#### 2.1.3 主工作流程函数

```python
def memory_stick_workflow(robot, logger, tool_num=1, check_mestick=False, agv_enabled=True, work_station=4) -> int
```

**功能**: 执行完整的内存条处理工作流程

**参数**:
- `robot`: 机器人对象
- `logger`: 日志记录器对象
- `tool_num`: 工具编号，默认为1
- `check_mestick`: 是否进行内存条检查，默认为False
- `agv_enabled`: 是否启用AGV移动，默认为True
- `work_station`: AGV工作站点，默认为4

**返回值**:
- `0`: 所有操作成功
- `1`: 换工具失败
- `2`: 放内存条失败
- `3`: 内存条检查失败

**工作流程**:
1. 执行换工具操作
2. AGV移动到工作站点
3. 执行取内存条操作
4. 执行放内存条操作
5. 可选：重新拔插内存条检查

**使用示例**:
```python
from main import memory_stick_workflow
from core.rdk_init import init_robot
from utils.logger import get_logger

logger = get_logger("TestLogger")
robot = init_robot("Rizon10-062283", logger)

result = memory_stick_workflow(
    robot=robot,
    logger=logger,
    tool_num=1,
    check_mestick=False,
    agv_enabled=True,
    work_station=4
)
```

## 3. 机器人操作模块

### 3.1 plans/change_tool.py - 换工具操作

```python
def change_tool(robot, logger, work_num: int = 1) -> int
```

**功能**: 执行机器人换工具操作

**参数**:
- `robot`: 机器人对象
- `logger`: 日志记录器
- `work_num`: 工作编号，默认为1

**返回值**:
- `90`: 成功
- `其他值`: 失败（会触发连续音频报警 - 音频ID 4）
- `1999`: 系统异常

**使用示例**:
```python
from plans.change_tool import change_tool

result = change_tool(robot, logger, work_num=1)
if result == 90:
    print("换工具成功")
else:
    print(f"换工具失败，错误码: {result}")
```

### 3.2 plans/pick_mestick.py - 取内存条操作

```python
def pick_mestick(robot, logger) -> int
```

**功能**: 执行取内存条操作，包含重试机制

**参数**:
- `robot`: 机器人对象
- `logger`: 日志记录器

**返回值**:
- `10`: 成功
- `101`: 拍照失败（触发连续音频报警 - 音频ID 3）
- `102`: 取料失败（触发连续音频报警 - 音频ID 1）
- `1999`: 系统异常

**特点**:
- 拍照和取料失败都会自动重试3次
- 失败时自动触发连续音频报警

**使用示例**:
```python
from plans.pick_mestick import pick_mestick

result = pick_mestick(robot, logger)
if result == 10:
    print("取内存条成功")
elif result == 101:
    print("拍照失败")
elif result == 102:
    print("取料失败")
```

### 3.3 plans/Put_mestick.py - 放内存条操作

```python
def Put_mestick(robot, logger, WorkServerMestick: int, PalletNum: int = 1) -> int
```

**功能**: 执行放内存条操作，包含重试机制

**参数**:
- `robot`: 机器人对象
- `logger`: 日志记录器
- `WorkServerMestick`: 工作服务器内存条参数
- `PalletNum`: 托盘编号，默认为1

**返回值**:
- `20`: 成功
- `201`: 拍照失败（触发连续音频报警 - 音频ID 3）
- `202`: 放料失败（触发连续音频报警 - 音频ID 2）
- `203`: 未放过料无法取料
- `1999`: 系统异常

**使用示例**:
```python
from plans.Put_mestick import Put_mestick

result = Put_mestick(
    robot=robot,
    logger=logger,
    WorkServerMestick=1,
    PalletNum=1
)
if result == 20:
    print("放内存条成功")
```

## 4. AGV控制模块

### 4.1 简单移动函数（推荐）

```python
def move_agv_to_station(station_id, logger=None) -> bool
```

**功能**: AGV移动到指定站点

**参数**:
- `station_id`: 目标站点号
- `logger`: 日志记录器（可选）

**返回值**:
- `True`: 移动成功
- `False`: 移动失败

**特点**:
- 使用全局连接管理器，无需每次建立连接
- 自动处理控制权抢占和释放
- 支持智能阻挡检测和等待

**使用示例**:
```python
from AGV import move_agv_to_station

# 移动到站点4
success = move_agv_to_station(4, logger)
if success:
    print("AGV移动成功")
else:
    print("AGV移动失败")
```

### 4.2 AGV初始化函数

```python
def simple_initialize_agv(logger=None) -> bool
def initialize_agv_to_station4(logger=None) -> bool
```

**功能**: 初始化AGV到站点4

**移动策略**:
- **站点4**: 无需移动
- **站点5**: 直接移动至站点4
- **站点6**: 先移动至站点7，再移动至站点4
- **站点7**: 直接移动至站点4
- **其他站点**: 直接尝试移动至站点4

**参数**:
- `logger`: 日志记录器（可选）

**返回值**:
- `True`: 成功到达站点4
- `False`: 失败

**使用示例**:
```python
from AGV import simple_initialize_agv

# AGV初始化
success = simple_initialize_agv(logger)
if success:
    print("AGV初始化成功，已在站点4")
else:
    print("AGV初始化失败")
```

### 4.3 AGV状态函数

```python
def get_current_station(client) -> int
def check_agv_status(client) -> dict
```

**功能**: 获取AGV状态信息

**使用示例**:
```python
from AGV import get_agv_connection, get_current_station, check_agv_status

# 获取全局连接
global_conn = get_agv_connection()
client = global_conn.get_client()

# 获取当前站点
current_station = get_current_station(client)
print(f"当前站点: {current_station}")

# 获取AGV状态
status = check_agv_status(client)
print(f"定位状态: {status.get('localization')}")
print(f"控制权状态: {status.get('control')}")
```

### 4.4 AGVController类（高级使用）

```python
class AGVController:
    def __init__(self, ip=MODBUS_IP, port=MODBUS_PORT, logger=None)
    def connect(self) -> bool
    def disconnect(self)
    def acquire_control(self) -> bool
    def release_control(self) -> bool
    def move_to_station(self, station_id, vx=1.0, vy=0.0, w=0.5) -> bool
    def play_audio(self, audio_id) -> bool
    def get_status(self) -> dict
```

**使用示例**:
```python
from AGV import AGVController

# 方法1：上下文管理器（推荐）
try:
    with AGVController(logger=logger) as agv:
        # 移动到站点
        success = agv.move_to_station(4, vx=1.0, vy=0.0, w=0.5)
        
        # 播放音频
        success = agv.play_audio(1)
        
        # 获取状态
        status = agv.get_status()
        
except Exception as e:
    print(f"AGV操作失败: {e}")

# 方法2：手动管理连接
controller = AGVController(logger=logger)
if controller.connect():
    success = controller.move_to_station(4)
    controller.disconnect()
```

## 5. 音频报警系统

### 5.1 简单音频播放

```python
def simple_play_audio(audio_id, logger=None) -> bool
def play_audio(client, audio_id, logger=None) -> bool
```

**功能**: 播放单次音频

**音频ID说明**:
- `1`: 取料失败
- `2`: 放料失败
- `3`: 拍照失败
- `4`: 机器人状态错误

**使用示例**:
```python
from AGV import simple_play_audio

# 播放取料失败音频
success = simple_play_audio(1, logger)
if success:
    print("音频播放成功")
```

### 5.2 连续音频报警系统

```python
class AudioAlarmManager:
    def start_continuous_alarm(self, audio_id, alarm_id=None, interval=3.0, logger=None) -> str
    def stop_alarm(self, alarm_id) -> bool
    def stop_all_alarms(self) -> int
    def is_alarm_running(self, alarm_id) -> bool
    def get_active_alarms(self) -> list
```

**获取管理器**:
```python
def get_audio_alarm_manager() -> AudioAlarmManager
```

**使用示例**:
```python
from AGV import get_audio_alarm_manager

# 获取音频报警管理器
alarm_manager = get_audio_alarm_manager()

# 启动连续报警
alarm_id = alarm_manager.start_continuous_alarm(
    audio_id=1,           # 音频文件编号
    alarm_id="pick_fail", # 报警标识符（可选）
    interval=3.0,         # 播放间隔时间（秒）
    logger=logger         # 日志记录器（可选）
)

# 检查报警状态
is_running = alarm_manager.is_alarm_running("pick_fail")
active_alarms = alarm_manager.get_active_alarms()

# 停止指定报警
success = alarm_manager.stop_alarm("pick_fail")

# 停止所有报警（程序重新初始化时自动调用）
stopped_count = alarm_manager.stop_all_alarms()
```

### 5.3 音频报警映射表

| 错误类型 | 音频ID | 报警ID | 触发条件 | 触发位置 |
|---------|--------|--------|----------|----------|
| 取料失败 | 1 | "pick_failed" | pick_mestick返回102 | pick_mestick.py |
| 放料失败 | 2 | "put_failed" | Put_mestick返回202 | Put_mestick.py |
| 拍照失败 | 3 | "pick_photo_failed" | pick_mestick返回101 | pick_mestick.py |
| 拍照失败 | 3 | "put_photo_failed" | Put_mestick返回201 | Put_mestick.py |
| 机器人状态错误 | 4 | "robot_status_error" | 机器人连接失败 | change_tool.py |
| 换工具失败 | 4 | "change_tool_failed" | change_tool失败 | change_tool.py |

## 6. 工具函数

### 6.1 全局连接管理

```python
def get_agv_connection() -> AGVGlobalConnection
```

**功能**: 获取AGV全局连接管理器

**特点**:
- 单例模式，全局唯一实例
- 自动连接监控和恢复
- 线程安全的连接管理

**使用示例**:
```python
from AGV import get_agv_connection

# 获取全局连接
global_conn = get_agv_connection()

# 获取客户端
client = global_conn.get_client()

# 检查连接状态
is_connected = global_conn.is_connected()
```

### 6.2 低级控制函数

```python
# 控制权管理
def acquire_control(client) -> bool      # 抢占控制权
def release_control(client) -> bool      # 释放控制权

# 定位管理
def relocate_at_home(client) -> bool           # 在Home点重定位
def confirm_localization(client) -> bool       # 确认定位正确
def ensure_proper_localization(client) -> bool # 确保定位状态正确

# 阻挡检测
def check_block_status(client) -> tuple        # 返回 (is_blocked, reason)

# 导航监控
def monitor_navigation_with_block_handling(client, max_total_time=300, max_continuous_block_time=60) -> bool

# 底层移动控制
def move_to_station(client, station_id, vx=1.0, vy=0.0, w=0.5) -> bool
```

### 6.3 日志工具

```python
from utils.logger import get_logger

# 获取日志记录器
logger = get_logger("MyLogger")

# 使用日志
logger.info("信息消息")
logger.warning("警告消息")
logger.error("错误消息")
```

## 7. 完整使用示例

### 7.1 基本工作流程

```python
#!/usr/bin/env python3
from main import memory_stick_workflow
from core.rdk_init import init_robot
from utils.logger import get_logger

# 初始化
logger = get_logger("RobotTest")
robot = init_robot("Rizon10-062283", logger)

# 执行完整工作流程
result = memory_stick_workflow(
    robot=robot,
    logger=logger,
    tool_num=1,
    check_mestick=False,
    agv_enabled=True,
    work_station=4
)

if result == 0:
    print("工作流程执行成功")
else:
    print(f"工作流程执行失败，错误码: {result}")
```

### 7.2 单独功能测试

```python
from AGV import move_agv_to_station, simple_play_audio, get_audio_alarm_manager
from plans.change_tool import change_tool
from plans.pick_mestick import pick_mestick
from plans.Put_mestick import Put_mestick
from utils.logger import get_logger

logger = get_logger("TestLogger")

# 测试AGV移动
success = move_agv_to_station(4, logger)
print(f"AGV移动结果: {success}")

# 测试音频播放
success = simple_play_audio(1, logger)
print(f"音频播放结果: {success}")

# 测试连续报警
alarm_manager = get_audio_alarm_manager()
alarm_id = alarm_manager.start_continuous_alarm(1, "test_alarm", interval=5.0, logger=logger)
print(f"启动报警: {alarm_id}")

# 5秒后停止报警
import time
time.sleep(5)
alarm_manager.stop_alarm(alarm_id)
```

### 7.3 批量操作示例

```python
from AGV import move_agv_to_station
from utils.logger import get_logger

logger = get_logger("BatchTest")

# 批量移动到多个站点
stations = [4, 5, 6, 7]
for station in stations:
    success = move_agv_to_station(station, logger)
    if not success:
        logger.error(f"移动到站点 {station} 失败")
        break
    logger.info(f"成功到达站点 {station}")
    time.sleep(2)  # 间隔2秒
```

## 8. 故障排除

### 8.1 常见错误及解决方案

#### 8.1.1 AGV连接失败
```
[ERROR] AGV全局连接不可用
```
**解决方案**:
- 检查IP地址和端口设置 (`--agv-ip`, `--agv-port`)
- 确认AGV设备开机并连接网络
- 查看防火墙设置
- 验证Modbus TCP服务是否运行

#### 8.1.2 机器人连接失败
```
[ERROR] 无法获取机器人状态
```
**解决方案**:
- 检查机器人序列号是否正确 (`--robot-sn`)
- 确认机器人开机并连接网络
- 验证机器人中是否包含必需的计划
- 检查Flexiv RDK环境配置

#### 8.1.3 音频播放失败
```
[ERROR] 写入音频播放指令失败
```
**解决方案**:
- 检查AGV音频文件是否存在
- 确认音频ID范围（1-4）
- 查看AGV音频系统状态
- 验证Modbus通信是否正常

### 8.2 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

或者在命令行中：
```bash
python main.py --log-name "DebugLogger" 2>&1 | tee debug.log
```

### 8.3 系统配置检查

```python
from AGV import get_agv_connection, check_agv_status

# 检查AGV连接
global_conn = get_agv_connection()
if global_conn.is_connected():
    client = global_conn.get_client()
    status = check_agv_status(client)
    print("AGV状态正常")
    print(f"定位状态: {status.get('localization')}")
    print(f"控制权状态: {status.get('control')}")
else:
    print("AGV连接失败")
```

---

**版本**: v2.0  
**最后更新**: 2024年  
**技术支持**: 查看项目日志文件或联系系统管理员  

**快速参考**:
- 主程序: `python main.py --robot-sn "Rizon10-062283"`
- AGV移动: `move_agv_to_station(4, logger)`
- 音频播放: `simple_play_audio(1, logger)`
- 连续报警: `get_audio_alarm_manager().start_continuous_alarm(1)`