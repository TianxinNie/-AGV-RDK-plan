from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.constants import Endian
import time
import threading
import asyncio

MODBUS_IP = '192.168.2.112'
MODBUS_PORT = 502

# 重要寄存器地址 - 根据AGV.txt文档修正 (文档地址-1)
# 线圈寄存器 (Coil Registers) - 用于控制命令
COIL_RELOCATE_HOME = 1          # 在Home点重定位 (00002-1)
COIL_CONFIRM_LOCALIZATION = 2   # 确认定位正确 (00003-1)  
COIL_ACQUIRE_CONTROL = 9        # 抢占控制权 (00010-1)
COIL_RELEASE_CONTROL = 10       # 释放控制权 (00011-1)

# 保持寄存器 (Holding Registers) - 用于写入参数
ADDR_TARGET_STATION = 0         # 目标站点id (00001-1)
ADDR_VX = 4                    # VX速度 (00005-1)
ADDR_VY = 6                    # VY速度 (00007-1) 
ADDR_W = 8                     # 角速度 (00009-1)
ADDR_PLAY_AUDIO = 29           # 播放音频 (00030-1)

# 输入寄存器 (Input Registers) - 用于读取状态
INPUT_ROBOT_X = 0              # 机器人X坐标 (00001-1)
INPUT_ROBOT_Y = 2              # 机器人Y坐标 (00003-1)
INPUT_ROBOT_ANGLE = 4          # 机器人角度 (00005-1)
INPUT_CURRENT_STATION = 33     # 当前所在站点 (00034-1) - 机器人实际物理位置
INPUT_LOCALIZATION_STATE = 7   # 定位状态 (00008-1)
INPUT_NAVIGATION_STATE = 8     # 导航状态 (00009-1)
INPUT_FATAL_ERROR = 30         # Fatal错误码 (00031-1)
INPUT_ERROR_CODE = 31          # Error错误码 (00032-1)
INPUT_CONTROL_OCCUPIED = 42    # 控制权是否被外部抢占 (00043-1)
INPUT_IS_BLOCKED = 1           # 是否被阻挡 (00002-1)
INPUT_BLOCK_REASON = 43        # 被阻挡的原因 (00044-1)

# 全局连接管理器
class AGVGlobalConnection:
    """AGV全局连接管理器 - 单例模式"""
    
    _instance = None
    _client = None
    _monitor = None
    _is_connected = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._setup_connection()
    
    def _setup_connection(self):
        """设置连接和监控"""
        print(f"[GLOBAL] 初始化AGV全局连接管理器")
        
        # 创建客户端
        self._client = ModbusTcpClient(MODBUS_IP, port=MODBUS_PORT)
        
        # 创建监控器
        self._monitor = AGVConnectionMonitor(MODBUS_IP, MODBUS_PORT, check_interval=3)
        self._monitor.add_connection_callback(self._on_connection)
        self._monitor.add_disconnection_callback(self._on_disconnection)
        
        # 启动监控
        self._monitor.start_monitoring()
        
        # 初始连接
        self._connect()
    
    def _connect(self):
        """建立连接"""
        try:
            if self._client.connect():
                self._is_connected = True
                print(f"[GLOBAL] AGV连接已建立")
                return True
            else:
                self._is_connected = False
                print(f"[GLOBAL] AGV连接失败")
                return False
        except Exception as e:
            self._is_connected = False
            print(f"[GLOBAL] AGV连接异常: {e}")
            return False
    
    def _on_connection(self):
        """连接恢复回调"""
        print("[GLOBAL] AGV连接已恢复")
        if not self._is_connected:
            self._connect()
    
    def _on_disconnection(self):
        """连接断开回调"""
        print("[GLOBAL] AGV连接已断开")
        self._is_connected = False
    
    def get_client(self):
        """获取客户端（如果连接正常）"""
        if self._is_connected and self._client:
            return self._client
        else:
            # 尝试重连
            if self._connect():
                return self._client
            return None
    
    def is_connected(self):
        """检查连接状态"""
        return self._is_connected
    
    def close(self):
        """关闭连接和监控"""
        if self._monitor:
            self._monitor.stop_monitoring()
        if self._client:
            self._client.close()
        self._is_connected = False
        print("[GLOBAL] AGV全局连接已关闭")

# 创建全局连接管理器实例
_agv_global_connection = None

def get_agv_connection():
    """获取AGV全局连接"""
    global _agv_global_connection
    if _agv_global_connection is None:
        _agv_global_connection = AGVGlobalConnection()
    return _agv_global_connection

class AudioAlarmManager:
    """AGV音频报警管理器 - 支持连续音频播放直至用户确认"""
    
    def __init__(self):
        self.alarm_threads = {}  # {alarm_id: thread}
        self.alarm_events = {}   # {alarm_id: stop_event}
        self.is_running = {}     # {alarm_id: is_running}
        
    def start_continuous_alarm(self, audio_id, alarm_id=None, interval=5.0, audio_duration=3.0, logger=None):
        """
        开始连续音频报警
        
        Args:
            audio_id: 音频文件编号
            alarm_id: 报警标识符（默认使用audio_id）
            interval: 两次播放之间的静默间隔时间（秒），默认5秒
            audio_duration: 预估音频播放时长（秒），默认3秒
            logger: 日志记录器
            
        Returns:
            str: 报警ID，用于停止报警
        """
        if alarm_id is None:
            alarm_id = f"alarm_{audio_id}"
            
        def log(msg, level="info"):
            if logger:
                getattr(logger, level)(msg)
            else:
                print(f"[ALARM] {msg}")
        
        # 如果已有相同的报警在运行，先停止
        if alarm_id in self.is_running and self.is_running[alarm_id]:
            log(f"停止已存在的报警: {alarm_id}", "warning")
            self.stop_alarm(alarm_id)
        
        # 创建停止事件
        stop_event = threading.Event()
        self.alarm_events[alarm_id] = stop_event
        self.is_running[alarm_id] = True
        
        def alarm_loop():
            """报警循环线程"""
            log(f"开始连续音频报警: {alarm_id}, 音频ID: {audio_id}, 音频时长: {audio_duration}s, 静默间隔: {interval}s")
            
            while not stop_event.is_set():
                try:
                    # 使用全局连接播放音频
                    log(f"播放音频 {audio_id}...")
                    success = simple_play_audio(audio_id, logger)
                    if not success:
                        log(f"音频播放失败: {audio_id}", "warning")
                    
                    # 等待音频播放完成
                    if stop_event.wait(timeout=audio_duration):
                        break  # 收到停止信号
                    
                    # 音频播放完成后，等待静默间隔
                    log(f"音频播放完成，等待 {interval}s 后播放下一次...")
                    if stop_event.wait(timeout=interval):
                        break  # 收到停止信号
                        
                except Exception as e:
                    log(f"报警循环异常: {e}", "error")
                    time.sleep(1)  # 异常时短暂等待
            
            log(f"连续音频报警已停止: {alarm_id}")
            self.is_running[alarm_id] = False
        
        # 启动报警线程
        alarm_thread = threading.Thread(target=alarm_loop, daemon=True)
        alarm_thread.start()
        
        self.alarm_threads[alarm_id] = alarm_thread
        log(f"✅ 连续音频报警已启动: {alarm_id}")
        
        return alarm_id
    
    def stop_alarm(self, alarm_id):
        """
        停止指定的连续报警
        
        Args:
            alarm_id: 报警标识符
            
        Returns:
            bool: 是否成功停止
        """
        if alarm_id not in self.alarm_events:
            print(f"[ALARM] 未找到报警: {alarm_id}")
            return False
        
        try:
            # 发送停止信号
            self.alarm_events[alarm_id].set()
            
            # 等待线程结束
            if alarm_id in self.alarm_threads:
                self.alarm_threads[alarm_id].join(timeout=2)
                del self.alarm_threads[alarm_id]
            
            # 清理事件和状态
            del self.alarm_events[alarm_id]
            if alarm_id in self.is_running:
                del self.is_running[alarm_id]
            
            print(f"[ALARM] ✅ 已停止连续报警: {alarm_id}")
            return True
            
        except Exception as e:
            print(f"[ALARM] 停止报警异常: {e}")
            return False
    
    def stop_all_alarms(self):
        """停止所有连续报警"""
        alarm_ids = list(self.alarm_events.keys())
        stopped_count = 0
        
        for alarm_id in alarm_ids:
            if self.stop_alarm(alarm_id):
                stopped_count += 1
        
        print(f"[ALARM] 已停止 {stopped_count} 个连续报警")
        return stopped_count
    
    def get_active_alarms(self):
        """获取当前活跃的报警列表"""
        active_alarms = []
        for alarm_id, is_running in self.is_running.items():
            if is_running:
                active_alarms.append(alarm_id)
        return active_alarms
    
    def is_alarm_running(self, alarm_id):
        """检查指定报警是否正在运行"""
        return self.is_running.get(alarm_id, False)

# 创建全局音频报警管理器实例
_audio_alarm_manager = None

def get_audio_alarm_manager():
    """获取全局音频报警管理器"""
    global _audio_alarm_manager
    if _audio_alarm_manager is None:
        _audio_alarm_manager = AudioAlarmManager()
    return _audio_alarm_manager

class AGVConnectionMonitor:
    """AGV异步连接监控器"""
    
    def __init__(self, ip, port, check_interval=5):
        self.ip = ip
        self.port = port
        self.check_interval = check_interval
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None
        self.connection_callbacks = []
        self.disconnection_callbacks = []
        
    def add_connection_callback(self, callback):
        """添加连接回调函数"""
        self.connection_callbacks.append(callback)
        
    def add_disconnection_callback(self, callback):
        """添加断连回调函数"""
        self.disconnection_callbacks.append(callback)
        
    def _test_connection(self):
        """测试连接是否正常"""
        try:
            test_client = ModbusTcpClient(self.ip, port=self.port)
            if test_client.connect():
                # 尝试读取一个简单的寄存器来验证通信
                result = test_client.read_input_registers(address=INPUT_LOCALIZATION_STATE, count=1)
                test_client.close()
                return not result.isError()
            return False
        except Exception:
            return False
            
    def _monitor_loop(self):
        """监控循环"""
        print(f"[MONITOR] 开始监控AGV连接 {self.ip}:{self.port}")
        
        while self.monitoring:
            current_status = self._test_connection()
            
            # 检测状态变化
            if current_status != self.is_connected:
                if current_status:
                    # 从断连变为连接
                    print(f"✅ [MONITOR] AGV连接恢复 {self.ip}:{self.port}")
                    for callback in self.connection_callbacks:
                        try:
                            callback()
                        except Exception as e:
                            print(f"[ERROR] 连接回调执行失败: {e}")
                else:
                    # 从连接变为断连
                    print(f"❌ [MONITOR] AGV连接断开 {self.ip}:{self.port}")
                    for callback in self.disconnection_callbacks:
                        try:
                            callback()
                        except Exception as e:
                            print(f"[ERROR] 断连回调执行失败: {e}")
                            
                self.is_connected = current_status
            
            time.sleep(self.check_interval)
            
    def start_monitoring(self):
        """开始监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
            
    def get_status(self):
        """获取当前连接状态"""
        return self.is_connected

def check_agv_status(client):
    """检查AGV当前状态，返回状态信息"""
    print("[INFO] 检查AGV当前状态...")
    status = {}
    
    try:
        # 读取定位状态
        res = client.read_input_registers(address=INPUT_LOCALIZATION_STATE, count=1)
        if not res.isError():
            loc_state = res.registers[0]
            status['localization'] = loc_state
            loc_desc = {0: "定位失败", 1: "定位正确", 2: "正在重定位", 3: "定位完成"}.get(loc_state, "未知")
            print(f"[INFO] 定位状态: {loc_state} ({loc_desc})")
            if loc_state == 0:
                print("[WARNING] AGV定位失败，无法抢占控制权")
        else:
            print(f"[ERROR] 读取定位状态失败: {res}")
            status['localization'] = -1
            
        # 读取控制权状态
        res = client.read_input_registers(address=INPUT_CONTROL_OCCUPIED, count=1)
        if not res.isError():
            control_state = res.registers[0]
            status['control'] = control_state
            control_desc = {0: "自己抢占或未被抢占", 1: "被外部抢占"}.get(control_state, "未知")
            print(f"[INFO] 控制权状态: {control_state} ({control_desc})")
        else:
            print(f"[ERROR] 读取控制权状态失败: {res}")
            status['control'] = -1
            
        # 读取Fatal错误
        res = client.read_input_registers(address=INPUT_FATAL_ERROR, count=1)
        if not res.isError():
            fatal_error = res.registers[0]
            status['fatal'] = fatal_error
            if fatal_error != 0:
                print(f"[ERROR] AGV有Fatal错误: {fatal_error}")
            else:
                print("[INFO] 无Fatal错误")
        else:
            print(f"[ERROR] 读取Fatal错误失败: {res}")
            status['fatal'] = -1
            
        # 读取Error错误
        res = client.read_input_registers(address=INPUT_ERROR_CODE, count=1)
        if not res.isError():
            error_code = res.registers[0]
            status['error'] = error_code
            if error_code != 0:
                print(f"[WARNING] AGV有Error错误: {error_code}")
            else:
                print("[INFO] 无Error错误")
        else:
            print(f"[ERROR] 读取Error错误失败: {res}")
            status['error'] = -1
            
    except Exception as e:
        print(f"[ERROR] 检查AGV状态异常: {e}")
    
    return status

def relocate_at_home(client):
    """在Home点重定位"""
    print("[INFO] 开始在Home点重定位...")
    
    rr = client.write_coil(address=COIL_RELOCATE_HOME, value=True)
    if rr.isError():
        print(f"[ERROR] 发送重定位命令失败: {rr}")
        return False
    print("[SUCCESS] 成功发送重定位命令")
    
    # 等待重定位完成
    print("[INFO] 等待重定位完成...")
    for _ in range(30):  # 最多等30秒
        time.sleep(1)
        res = client.read_input_registers(address=INPUT_LOCALIZATION_STATE, count=1)
        if not res.isError():
            loc_state = res.registers[0]
            print(f"[DEBUG] 重定位进度 - 定位状态: {loc_state}")
            if loc_state in (1, 3):  # 定位正确或定位完成
                print("✅ 重定位成功")
                return True
            elif loc_state == 0:  # 定位失败
                print("❌ 重定位失败")
                return False
        else:
            print(f"[ERROR] 读取定位状态失败: {res}")
    
    print("⏳ 重定位超时")
    return False

def confirm_localization(client):
    """确认定位正确"""
    print("[INFO] 确认定位正确...")
    
    rr = client.write_coil(address=COIL_CONFIRM_LOCALIZATION, value=True)
    if rr.isError():
        print(f"[ERROR] 发送确认定位命令失败: {rr}")
        return False
    print("[SUCCESS] 成功发送确认定位命令")
    
    # 检查定位状态是否变为1
    time.sleep(1)
    res = client.read_input_registers(address=INPUT_LOCALIZATION_STATE, count=1)
    if not res.isError():
        loc_state = res.registers[0]
        if loc_state == 1:
            print("✅ 定位状态确认成功")
            return True
        else:
            print(f"❌ 定位状态确认失败，当前状态: {loc_state}")
            return False
    else:
        print(f"[ERROR] 读取定位状态失败: {res}")
        return False


def check_block_status(client):
    """检查AGV阻挡状态"""
    try:
        # 读取是否被阻挡
        res = client.read_input_registers(address=INPUT_IS_BLOCKED, count=1)
        if res.isError():
            print(f"[ERROR] 读取阻挡状态失败: {res}")
            return None, None
            
        is_blocked = res.registers[0]
        
        if is_blocked == 0:
            return False, None  # 未阻挡
            
        # 如果被阻挡，读取阻挡原因
        reason_res = client.read_input_registers(address=INPUT_BLOCK_REASON, count=1)
        if reason_res.isError():
            print(f"[ERROR] 读取阻挡原因失败: {reason_res}")
            return True, "未知原因"
            
        block_reason = reason_res.registers[0]
        reason_desc = {
            0: "超声传感器", 1: "激光传感器", 2: "防跌落传感器", 
            3: "碰撞传感器", 4: "红外传感器", 5: "锁车开关",
            6: "动态障碍物", 7: "虚拟激光点", 8: "3D相机",
            9: "距离传感器", 10: "DI超声"
        }.get(block_reason, f"未知原因({block_reason})")
        
        return True, reason_desc
        
    except Exception as e:
        print(f"[ERROR] 检查阻挡状态异常: {e}")
        return None, None

def print_detailed_sensor_status(client):
    """打印详细的传感器和系统状态信息"""
    print("\n📊 === AGV详细传感器状态 ===")
    
    try:
        # 1. 阻挡传感器详细信息
        print("🚧 阻挡传感器状态:")
        block_res = client.read_input_registers(address=INPUT_IS_BLOCKED, count=1)
        reason_res = client.read_input_registers(address=INPUT_BLOCK_REASON, count=1)
        
        if not block_res.isError():
            is_blocked = block_res.registers[0]
            print(f"  · 阻挡状态: {'🔴 被阻挡' if is_blocked else '🟢 未阻挡'} ({is_blocked})")
            
            if is_blocked and not reason_res.isError():
                block_reason = reason_res.registers[0]
                reason_map = {
                    0: "超声传感器", 1: "激光传感器", 2: "防跌落传感器",
                    3: "碰撞传感器", 4: "红外传感器", 5: "锁车开关",
                    6: "动态障碍物", 7: "虚拟激光点", 8: "3D相机",
                    9: "距离传感器", 10: "DI超声"
                }
                reason_desc = reason_map.get(block_reason, f"未知({block_reason})")
                print(f"  · 触发传感器: 🚨 {reason_desc} (代码:{block_reason})")
                
                # 根据阻挡原因读取更详细信息
                if block_reason == 0:  # 超声传感器
                    ultrasonic_id_res = client.read_input_registers(address=44, count=1)
                    if not ultrasonic_id_res.isError():
                        ultrasonic_id = ultrasonic_id_res.registers[0]
                        print(f"  · 超声传感器ID: {ultrasonic_id}")
                        
                elif block_reason in [2, 3, 4]:  # 防跌落、碰撞、红外传感器
                    di_id_res = client.read_input_registers(address=45, count=1)
                    if not di_id_res.isError():
                        di_id = di_id_res.registers[0]
                        print(f"  · DI传感器ID: {di_id}")
                
                # 读取阻挡位置坐标
                block_pos_res = client.read_input_registers(address=46, count=4)
                if not block_pos_res.isError() and len(block_pos_res.registers) >= 4:
                    try:
                        import struct
                        x_bytes = struct.pack('>HH', block_pos_res.registers[0], block_pos_res.registers[1])
                        y_bytes = struct.pack('>HH', block_pos_res.registers[2], block_pos_res.registers[3])
                        block_x = struct.unpack('>f', x_bytes)[0]
                        block_y = struct.unpack('>f', y_bytes)[0]
                        print(f"  · 阻挡位置: X={block_x:.3f}m, Y={block_y:.3f}m")
                    except:
                        pass
        
        # 2. 减速传感器状态
        print("\n🐌 减速传感器状态:")
        slow_res = client.read_coils(address=0, count=1)
        if not slow_res.isError():
            is_slowing = slow_res.bits[0]
            print(f"  · 减速状态: {'🟡 减速中' if is_slowing else '🟢 正常'} ({int(is_slowing)})")
            
            if is_slowing:
                slow_reason_res = client.read_input_registers(address=83, count=1)
                if not slow_reason_res.isError():
                    slow_reason = slow_reason_res.registers[0]
                    slow_reason_map = {
                        0: "超声传感器", 1: "激光传感器", 2: "防跌落传感器",
                        3: "碰撞传感器", 4: "红外传感器", 5: "锁车开关",
                        6: "动态障碍物", 7: "虚拟激光点", 8: "3D相机",
                        9: "距离传感器", 10: "DI超声"
                    }
                    slow_desc = slow_reason_map.get(slow_reason, f"未知({slow_reason})")
                    print(f"  · 减速原因: 🟡 {slow_desc} (代码:{slow_reason})")
        
        # 3. 安全状态检查
        print("\n🛡️ 安全状态检查:")
        safety_res = client.read_coils(address=2, count=5)
        if not safety_res.isError():
            safety_states = [
                ("充电状态", "🔋 充电中" if safety_res.bits[0] else "⚡ 未充电"),
                ("急停状态", "🚨 急停" if safety_res.bits[1] else "✅ 正常"),
                ("抱闸状态", "🔒 抱闸" if safety_res.bits[2] else "🔓 未抱闸"),
                ("货叉到位", "📦 到位" if safety_res.bits[3] else "📦 未到位"),
                ("控制模式", "🤖 自动" if safety_res.bits[4] else "👨 手动")
            ]
            for desc, status in safety_states:
                print(f"  · {desc}: {status}")
        
        # 4. DI传感器状态 (前16个)
        print("\n🔌 DI传感器状态 (DI0-DI15):")
        di_res = client.read_coils(address=19, count=16)
        if not di_res.isError():
            for i in range(16):
                state = "🟢 HIGH" if di_res.bits[i] else "🔴 LOW"
                print(f"  · DI{i:2d}: {state}")
        
        # 5. 系统状态详情
        print("\n⚠️ 系统状态:")
        system_res = client.read_coils(address=7, count=4)
        if not system_res.isError():
            has_fatal = system_res.bits[0]
            has_error = system_res.bits[1] 
            has_warning = system_res.bits[2]
            lift_enabled = system_res.bits[3] if len(system_res.bits) > 3 else False
            
            print(f"  · Fatal错误: {'🚨 有' if has_fatal else '✅ 无'}")
            print(f"  · Error错误: {'⚠️ 有' if has_error else '✅ 无'}")
            print(f"  · Warning警告: {'🟡 有' if has_warning else '✅ 无'}")
            print(f"  · 顶升启用: {'📤 启用' if lift_enabled else '📥 未启用'}")
        
        # 6. 机器人运动状态
        print("\n🤖 运动状态:")
        motion_res = client.read_coils(address=16, count=3)
        if not motion_res.isError():
            is_loaded = motion_res.bits[0] if len(motion_res.bits) > 0 else False
            is_static = motion_res.bits[2] if len(motion_res.bits) > 2 else False
            
            print(f"  · 载货状态: {'📦 载货中' if is_loaded else '📭 空载'}")
            print(f"  · 运动状态: {'🛑 静止' if is_static else '🏃 运动中'}")
        
        # 7. 速度状态
        print("\n📏 当前速度:")
        speed_res = client.read_input_registers(address=50, count=6)
        if not speed_res.isError() and len(speed_res.registers) >= 6:
            try:
                import struct
                vx_bytes = struct.pack('>HH', speed_res.registers[0], speed_res.registers[1])
                vy_bytes = struct.pack('>HH', speed_res.registers[2], speed_res.registers[3])
                w_bytes = struct.pack('>HH', speed_res.registers[4], speed_res.registers[5])
                
                vx = struct.unpack('>f', vx_bytes)[0]
                vy = struct.unpack('>f', vy_bytes)[0] 
                w = struct.unpack('>f', w_bytes)[0]
                
                print(f"  · VX速度: {vx:+.3f} m/s")
                print(f"  · VY速度: {vy:+.3f} m/s") 
                print(f"  · 角速度: {w:+.3f} rad/s")
            except:
                print("  · 速度信息解析失败")
                
    except Exception as e:
        print(f"❌ 读取传感器状态时发生异常: {e}")
    
    print("=" * 50)

def diagnose_navigation_failure(client, nav_status):
    """诊断导航失败的具体原因"""
    print(f"\n🔍 诊断导航失败原因 (状态码={nav_status})...")
    
    # 读取当前站点和目标站点
    try:
        current_station_res = client.read_input_registers(address=INPUT_CURRENT_STATION, count=1)
        target_station_res = client.read_holding_registers(address=ADDR_TARGET_STATION, count=1)
        
        if not current_station_res.isError() and not target_station_res.isError():
            current_station = current_station_res.registers[0]
            target_station = target_station_res.registers[0]
            print(f"📍 当前站点: {current_station}, 目标站点: {target_station}")
        
        # 读取机器人位置
        pos_res = client.read_input_registers(address=INPUT_ROBOT_X, count=6)  # X,Y,角度
        if not pos_res.isError():
            # 简化显示，不解析float32
            print(f"📍 机器人位置寄存器: X={pos_res.registers[0:2]}, Y={pos_res.registers[2:4]}, 角度={pos_res.registers[4:6]}")
            
    except Exception as e:
        print(f"⚠️ 位置信息读取异常: {e}")
    
    # 检查错误码
    try:
        fatal_res = client.read_input_registers(address=INPUT_FATAL_ERROR, count=1)
        error_res = client.read_input_registers(address=INPUT_ERROR_CODE, count=1)
        
        if not fatal_res.isError() and not error_res.isError():
            fatal_code = fatal_res.registers[0]
            error_code = error_res.registers[0]
            
            if fatal_code != 0:
                print(f"❌ Fatal错误: {fatal_code}")
            if error_code != 0:
                print(f"⚠️ Error错误: {error_code}")
            if fatal_code == 0 and error_code == 0:
                print("✅ 无系统错误")
                
    except Exception as e:
        print(f"⚠️ 错误码读取异常: {e}")

def monitor_navigation_with_block_handling(client, max_total_time=300, max_continuous_block_time=60, wait_forever_on_block=False):
    """
    智能导航监控，处理阻挡等待
    
    Args:
        client: Modbus客户端
        max_total_time: 总超时时间(秒)，默认5分钟
        max_continuous_block_time: 连续阻挡最大等待时间(秒)，默认1分钟
        wait_forever_on_block: 是否无限等待障碍物消失，默认False
    
    Returns:
        bool: 导航是否成功
    """
    start_time = time.time()
    block_start_time = None
    total_block_time = 0
    
    print("[INFO] 开始智能导航监控...")
    
    # 等待一小段时间让导航命令生效
    time.sleep(0.5)
    
    attempt = 0
    while time.time() - start_time < max_total_time:
        attempt += 1
        current_time = time.time()
        elapsed = current_time - start_time
        
        # 读取导航状态
        nav_res = client.read_input_registers(address=INPUT_NAVIGATION_STATE, count=1)
        if nav_res.isError():
            print(f"⚠️ 读取导航状态失败: {nav_res}")
            time.sleep(1)
            continue
            
        nav_status = nav_res.registers[0]
        
        # 检查导航完成状态
        if nav_status == 4:  # 到达
            print("✅ 机器人已到达目标站点")
            return True
        elif nav_status in (5, 6, 7):  # 失败、取消、超时
            status_desc = {5: "失败", 6: "取消", 7: "超时"}.get(nav_status)
            print(f"❌ 导航{status_desc}，状态码={nav_status}")
            
            # 进行详细诊断
            diagnose_navigation_failure(client, nav_status)
            
            # 如果是立即取消，可能是配置问题
            if nav_status == 6 and elapsed < 2:
                print("💡 可能原因:")
                print("  1. 目标站点不存在或不可达")
                print("  2. 当前地图中没有该站点")
                print("  3. 路径规划失败")
                print("  4. AGV处于禁止导航状态")
            
            return False
            
        # 检查阻挡状态
        is_blocked, block_reason = check_block_status(client)
        
        if is_blocked is None:  # 读取阻挡状态失败
            print(f"⚠️ [第{attempt}次] 无法读取阻挡状态，继续监控...")
        elif is_blocked:  # 被阻挡
            if block_start_time is None:
                block_start_time = current_time
                print(f"🚧 [第{attempt}次] AGV被阻挡: {block_reason}，开始等待...")
                # 打印详细传感器状态
                print_detailed_sensor_status(client)
            else:
                block_duration = current_time - block_start_time
                total_block_time += 1
                
                # 检查是否连续阻挡时间过长
                if not wait_forever_on_block and block_duration > max_continuous_block_time:
                    print(f"⏰ AGV连续阻挡时间过长({block_duration:.1f}秒)，可能需要人工干预")
                    return False
                    
                status_msg = f"🚧 [第{attempt}次] 仍被阻挡: {block_reason} (已等待{block_duration:.1f}s)"
                if wait_forever_on_block:
                    status_msg += " [无限等待模式]"
                print(status_msg)
        else:  # 未阻挡
            if block_start_time is not None:
                block_duration = current_time - block_start_time
                print(f"✅ 阻挡解除，继续前进 (阻挡持续了{block_duration:.1f}秒)")
                block_start_time = None
            
            # 显示正常导航状态
            status_desc = {0: "无", 1: "等待执行", 2: "执行中", 3: "暂停"}.get(nav_status, "未知")
            print(f"⌛ [第{attempt}次] 导航状态: {nav_status} ({status_desc}) | 已用时: {elapsed:.1f}s")
            
        time.sleep(1)
    
    print(f"⏳ 导航总超时({max_total_time}s)，累计阻挡时间: {total_block_time}s")
    return False

def ensure_proper_localization(client):
    """确保AGV处于正确的定位状态"""
    print("[INFO] 检查并确保AGV定位状态正确...")
    
    status = check_agv_status(client)
    loc_state = status.get('localization', -1)
    
    # 如果有Fatal错误，不能继续
    if status.get('fatal', 0) != 0:
        print("[ERROR] AGV存在Fatal错误，无法继续操作")
        return False
    
    if loc_state == 0:  # 定位失败
        print("[INFO] 定位失败，尝试重定位...")
        if not relocate_at_home(client):
            print("[ERROR] 重定位失败")
            return False
        # 重新检查状态
        status = check_agv_status(client)
        loc_state = status.get('localization', -1)
    
    if loc_state == 3:  # 定位完成，需要确认
        print("[INFO] 定位已完成，需要确认定位正确...")
        if not confirm_localization(client):
            print("[ERROR] 确认定位失败")
            return False
    
    # 最终检查
    status = check_agv_status(client)
    if status.get('localization', -1) == 1:
        print("✅ AGV定位状态正确，可以进行控制权抢占")
        return True
    else:
        print(f"❌ AGV定位状态异常: {status.get('localization', -1)}")
        return False

def write_float32(client, address, value):
    """写入32位浮点数到保持寄存器"""
    builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
    builder.add_32bit_float(value)
    payload = builder.to_registers()
    print(f"[DEBUG] 写入float32: 地址={address}, 值={value}, payload={payload}")
    rr = client.write_registers(address=address, values=payload)
    if rr.isError():
        print(f"[ERROR] 写入浮点数失败，地址={address}, 值={value}, 错误={rr}")
        raise Exception(f"写入浮点数失败，地址={address}")
    print(f"[SUCCESS] 成功写入float32: 地址={address}, 值={value}")

def acquire_control(client):
    """抢占AGV控制权"""
    print("[INFO] 开始抢占控制权...")
    
    # 先确保定位状态正确
    if not ensure_proper_localization(client):
        print("[ERROR] 定位状态不正确，无法抢占控制权")
        return False
    
    # 检查是否已经被其他系统抢占
    # status = check_agv_status(client)
    # if status.get('control', -1) == 1:
    #     print("[ERROR] 控制权已被其他系统抢占，无法抢占")
    #     return False
    
    # 写入抢占控制权命令 - 使用线圈寄存器
    print(f"[DEBUG] 写入线圈寄存器 {COIL_ACQUIRE_CONTROL} = True")
    rr = client.write_coil(address=COIL_ACQUIRE_CONTROL, value=True)
    if rr.isError():
        print(f"[ERROR] 抢占控制权失败，写线圈失败: {rr}")
        return False
    print("[SUCCESS] 成功写入抢占控制权线圈")

    # 写完延时1秒，等待设备响应
    print("[INFO] 等待设备响应...")
    time.sleep(1)

    # 读取线圈确认是否被清零（成功抢占控制权线圈被设备自动清零）
    print(f"[DEBUG] 读取线圈寄存器 {COIL_ACQUIRE_CONTROL} 状态")
    rr = client.read_coils(address=COIL_ACQUIRE_CONTROL, count=1)
    if rr.isError():
        print(f"[ERROR] 读取抢占控制权线圈失败: {rr}")
        return False
    
    val = rr.bits[0]  # 线圈寄存器用bits不是registers
    print(f"[DEBUG] 抢占线圈当前值: {val}")
    if not val:  # 清零(False)表示成功
        print("✅ 成功抢占控制权")
        # 再次检查控制权状态确认
        print("[INFO] 确认控制权状态...")
        status = check_agv_status(client)
        if status.get('control', -1) == 0:
            print("✅ 控制权状态确认正确")
            return True
        else:
            print("❌ 控制权状态确认失败")
            return False
    else:
        print("❌ 抢占控制权失败，线圈未清零")
        # 检查可能的原因
        print("[INFO] 检查失败原因...")
        check_agv_status(client)
        return False


def release_control(client):
    """释放AGV控制权"""
    print("[INFO] 开始释放控制权...")
    
    # 写入释放控制权命令 - 使用线圈寄存器
    print(f"[DEBUG] 写入线圈寄存器 {COIL_RELEASE_CONTROL} = True")
    rr = client.write_coil(address=COIL_RELEASE_CONTROL, value=True)
    if rr.isError():
        print(f"[ERROR] 释放控制权失败，写线圈失败: {rr}")
        return False
    print("[SUCCESS] 成功写入释放控制权线圈")

    # 等待线圈清零，确认释放成功
    print("[INFO] 等待线圈清零确认...")
    for attempt in range(10):
        print(f"[DEBUG] 第{attempt+1}次检查释放控制权线圈状态")
        rr = client.read_coils(address=COIL_RELEASE_CONTROL, count=1)
        if rr.isError():
            print(f"[ERROR] 读取释放控制权线圈失败: {rr}")
            return False
        val = rr.bits[0]  # 线圈寄存器用bits
        print(f"[DEBUG] 释放线圈当前值: {val}")
        if not val:  # 清零(False)表示成功
            print("✅ 成功释放控制权")
            # 验证控制权状态
            status = check_agv_status(client)
            return status.get('control', -1) == 0
        time.sleep(0.2)

    print("❌ 释放控制权超时")
    return False

def move_to_station(client, station_id, vx=1.0, vy=0.0, w=0.5, wait_forever_on_block=True):
    """
    控制AGV移动到指定站点
    
    Args:
        client: Modbus客户端
        station_id: 目标站点号
        vx: VX速度，默认1.0，范围(0, 3.0]
        vy: VY速度，默认0.0，范围[-3.0, 3.0]
        w: 角速度，默认0.5，范围[0, 3.0]
        wait_forever_on_block: 遇到障碍物时是否无限等待，默认True
        
    Returns:
        bool: 是否成功到达目标站点
    """
    print(f"[INFO] 开始移动到站点 {station_id}, 速度参数: VX={vx}, VY={vy}, W={w}")
    
    # 参数验证
    if not (0 < vx <= 3.0):
        print(f"[ERROR] VX速度超出范围 (0, 3.0]: {vx}")
        return False
    if not (-3.0 <= vy <= 3.0):
        print(f"[ERROR] VY速度超出范围 [-3.0, 3.0]: {vy}")
        return False
    if not (-6.28 <= w <= 6.28):  # 2π
        print(f"[ERROR] 角速度超出范围 [-2π, 2π]: {w}")
        return False
    
    # 检查当前导航状态，确保没有正在进行的导航
    print("[INFO] 检查当前导航状态...")
    try:
        nav_res = client.read_input_registers(address=INPUT_NAVIGATION_STATE, count=1)
        if not nav_res.isError():
            current_nav_status = nav_res.registers[0]
            if current_nav_status in (1, 2):  # 等待执行或执行中
                print(f"[WARNING] 当前有导航正在进行 (状态={current_nav_status})，建议先取消")
        else:
            print(f"[WARNING] 无法读取当前导航状态: {nav_res}")
    except Exception as e:
        print(f"[WARNING] 导航状态检查异常: {e}")
    
    # 设置速度参数
    print("[INFO] 设置速度参数...")
    try:
        write_float32(client, ADDR_VX, vx)
        write_float32(client, ADDR_VY, vy)
        write_float32(client, ADDR_W, w)
        print(f"[SUCCESS] 速度参数设置完成 VX={vx}, VY={vy}, W={w}")
    except Exception as e:
        print(f"[ERROR] 设置速度参数失败: {e}")
        return False

    # 设置目标站点
    print(f"[INFO] 设置目标站点为 {station_id}")
    print(f"[DEBUG] 写入保持寄存器 {ADDR_TARGET_STATION} = {station_id}")
    rr = client.write_register(address=ADDR_TARGET_STATION, value=station_id)
    if rr.isError():
        print(f"[ERROR] 写入目标站点失败: {rr}")
        return False
    print(f"[SUCCESS] 成功设置目标站点为 {station_id}")

    # 注意：目标站点写入后，机器人会自动开始导航
    print("[INFO] 机器人开始路径导航，使用智能阻挡处理...")
    
    # 使用新的智能导航监控（支持阻挡等待）
    return monitor_navigation_with_block_handling(client, max_total_time=300, max_continuous_block_time=60, wait_forever_on_block=wait_forever_on_block)

class AGVController:
    """AGV控制器类，封装AGV的所有操作"""
    
    def __init__(self, ip=MODBUS_IP, port=MODBUS_PORT, logger=None):
        self.ip = ip
        self.port = port
        self.logger = logger
        self.client = None
        self.monitor = None
        self.is_connected = False
        self.has_control = False
        
    def _log(self, level, message):
        """统一日志记录"""
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
            
    def connect(self):
        """连接AGV"""
        try:
            self._log("info", f"正在连接AGV {self.ip}:{self.port}...")
            self.client = ModbusTcpClient(self.ip, port=self.port)
            
            if self.client.connect():
                self._log("info", f"成功连接到AGV - {self.ip}:{self.port}")
                self.is_connected = True
                
                # 启动连接监控
                self.monitor = AGVConnectionMonitor(self.ip, self.port, check_interval=3)
                self.monitor.add_disconnection_callback(self._on_disconnection)
                self.monitor.start_monitoring()
                
                return True
            else:
                self._log("error", f"连接失败 - {self.ip}:{self.port}")
                return False
                
        except Exception as e:
            self._log("error", f"连接异常: {e}")
            return False
            
    def disconnect(self):
        """断开AGV连接"""
        try:
            if self.has_control:
                self._log("info", "释放控制权...")
                self.release_control()
                
            if self.monitor:
                self.monitor.stop_monitoring()
                self.monitor = None
                
            if self.client:
                self.client.close()
                self.client = None
                
            self.is_connected = False
            self._log("info", "AGV连接已断开")
            
        except Exception as e:
            self._log("error", f"断开连接异常: {e}")
            
    def _on_disconnection(self):
        """连接断开回调"""
        self._log("warning", "AGV连接意外断开")
        self.is_connected = False
        self.has_control = False
        
    def acquire_control(self):
        """抢占控制权"""
        if not self.is_connected or not self.client:
            self._log("error", "AGV未连接，无法抢占控制权")
            return False
            
        try:
            success = acquire_control(self.client)
            if success:
                self.has_control = True
                self._log("info", "成功抢占AGV控制权")
            else:
                self._log("error", "抢占AGV控制权失败")
            return success
            
        except Exception as e:
            self._log("error", f"抢占控制权异常: {e}")
            return False
            
    def release_control(self):
        """释放控制权"""
        if not self.is_connected or not self.client:
            self._log("warning", "AGV未连接，无需释放控制权")
            return True
            
        try:
            success = release_control(self.client)
            if success:
                self.has_control = False
                self._log("info", "成功释放AGV控制权")
            else:
                self._log("warning", "释放AGV控制权失败")
            return success
            
        except Exception as e:
            self._log("error", f"释放控制权异常: {e}")
            return False
            
    def move_to_station(self, station_id, vx=1.0, vy=0.0, w=0.5):
        """移动到指定站点"""
        if not self.is_connected or not self.client:
            self._log("error", "AGV未连接，无法执行移动")
            return False
            
        # 自动抢占控制权
        if not self.has_control:
            if not self.acquire_control():
                return False
                
        try:
            self._log("info", f"开始移动到站点 {station_id}")
            success = move_to_station(self.client, station_id, vx, vy, w)
            
            if success:
                self._log("info", f"成功到达站点 {station_id}")
            else:
                self._log("error", f"移动到站点 {station_id} 失败")
                
            return success
            
        except Exception as e:
            self._log("error", f"移动异常: {e}")
            return False
            
    def get_status(self):
        """获取AGV状态"""
        if not self.is_connected or not self.client:
            return None
            
        try:
            return check_agv_status(self.client)
        except Exception as e:
            self._log("error", f"获取状态异常: {e}")
            return None
    
    def play_audio(self, audio_id):
        """播放音频文件"""
        if not self.is_connected or not self.client:
            self._log("error", "AGV未连接，无法播放音频")
            return False
            
        try:
            self._log("info", f"播放音频文件 {audio_id}")
            success = play_audio(self.client, audio_id, self.logger)
            
            if success:
                self._log("info", f"音频 {audio_id} 播放指令发送成功")
            else:
                self._log("error", f"音频 {audio_id} 播放失败")
                
            return success
            
        except Exception as e:
            self._log("error", f"播放音频异常: {e}")
            return False
            
    def __enter__(self):
        """上下文管理器入口"""
        if self.connect():
            return self
        else:
            raise ConnectionError("无法连接到AGV")
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

def move_agv_to_station(station_id, logger=None):
    """
    超简单的AGV移动函数 - 使用全局连接，无需每次建立连接
    
    Args:
        station_id: 目标站点号
        logger: 日志记录器（可选）
        
    Returns:
        bool: True-成功，False-失败
        
    使用方法:
        success = move_agv_to_station(4)  # 移动到站点4
        success = move_agv_to_station(5, logger)  # 带日志
    """
    def log(msg, level="info"):
        if logger:
            getattr(logger, level)(msg)
        else:
            print(f"[AGV] {msg}")
    
    try:
        log(f"开始移动AGV到站点 {station_id}")
        
        # 使用全局连接管理器
        global_conn = get_agv_connection()
        client = global_conn.get_client()
        
        if not client:
            log("AGV全局连接不可用", "error")
            return False
        
        # 抢占控制权并移动
        if acquire_control(client):
            success = move_to_station(client, station_id, vx=1.0, vy=0.0, w=0.5)
            release_control(client)  # 释放控制权
            
            if success:
                log(f"✅ AGV成功到达站点 {station_id}")
                return True
            else:
                log(f"❌ AGV移动到站点 {station_id} 失败", "error")
                return False
        else:
            log("AGV控制权抢占失败", "error")
            return False
            
    except Exception as e:
        log(f"AGV移动异常: {e}", "error")
        return False

def play_audio(client, audio_id, logger=None):
    """
    AGV播放音频文件
    
    Args:
        client: Modbus客户端
        audio_id: 音频文件编号（从1开始）
        logger: 日志记录器（可选）
        
    Returns:
        bool: True-成功，False-失败
        
    使用方法:
        success = play_audio(client, 1)  # 播放音频1
        success = play_audio(client, 3, logger)  # 播放音频3，带日志
    """
    def log(msg, level="info"):
        if logger:
            getattr(logger, level)(msg)
        else:
            print(f"[AUDIO] {msg}")
    
    try:
        if not isinstance(audio_id, int) or audio_id < 1:
            log(f"无效的音频ID: {audio_id}，音频ID必须是大于0的整数", "error")
            return False
            
        log(f"开始播放音频文件 {audio_id}")
        
        # 写入音频编号到保持寄存器
        log(f"写入保持寄存器 {ADDR_PLAY_AUDIO} = {audio_id}")
        rr = client.write_register(address=ADDR_PLAY_AUDIO, value=audio_id)
        if rr.isError():
            log(f"写入音频播放指令失败: {rr}", "error")
            return False
            
        log(f"✅ 成功发送音频播放指令，音频ID: {audio_id}")
        
        # 等待一小段时间确保指令被处理
        time.sleep(0.5)
        
        # 验证寄存器是否被清零（AGV收到后会将该地址改为0）
        try:
            check_res = client.read_holding_registers(address=ADDR_PLAY_AUDIO, count=1)
            if not check_res.isError():
                current_value = check_res.registers[0]
                if current_value == 0:
                    log(f"✅ 音频播放指令已被AGV接收并处理")
                    return True
                else:
                    log(f"⚠️ 音频播放指令可能未被处理，当前值: {current_value}", "warning")
                    return True  # 仍然返回True，因为指令已发送
            else:
                log(f"无法验证音频播放状态: {check_res}", "warning")
                return True  # 仍然返回True，因为指令已发送
        except Exception as e:
            log(f"验证音频播放状态时发生异常: {e}", "warning")
            return True  # 仍然返回True，因为指令已发送
            
    except Exception as e:
        log(f"播放音频异常: {e}", "error")
        return False

def get_current_station(client):
    """获取AGV当前所在站点"""
    try:
        res = client.read_input_registers(address=INPUT_CURRENT_STATION, count=1)
        if not res.isError():
            raw_value = res.registers[0]
            print(f"🏷️  [STATION] 当前读取到的站点号: {raw_value}")
            print(f"[DEBUG] AGV原始寄存器值: {raw_value}")
            
            # 定义有效站点列表
            valid_stations = [4, 5, 8, 9, 10]
            
            # 站点有效性检查
            if raw_value == 0:
                print("[INFO] AGV报告站点0，表示不在任何站点")
                return None
            elif raw_value in valid_stations:
                print(f"[INFO] AGV在有效站点: {raw_value}")
                return raw_value
            else:
                print(f"[WARNING] AGV报告未知站点ID: {raw_value}，视为不在有效站点")
                print(f"[DEBUG] 有效站点列表: {valid_stations}")
                return None  # 将未知站点ID当作不在任何站点处理
        else:
            print(f"[ERROR] 读取当前站点失败: {res}")
            return None
    except Exception as e:
        print(f"[ERROR] 获取当前站点异常: {e}")
        return None

def initialize_agv_to_station4(logger=None):
    """
    初始化AGV到站点4
    
    根据当前位置执行不同的移动策略：
    - 站点4: 无需移动
    - 其他有效站点(5,8,9,10): 直接移动至站点4
    - 无效站点: 音频报警，等待人工处理
    
    Args:
        logger: 日志记录器（可选）
        
    Returns:
        bool: True-成功到达站点4，False-失败
    """
    def log(msg, level="info"):
        if logger:
            getattr(logger, level)(msg)
        else:
            print(f"[AGV_INIT] {msg}")
    
    try:
        log("开始AGV初始化，目标站点4")
        
        # 使用全局连接管理器
        global_conn = get_agv_connection()
        client = global_conn.get_client()
        
        if not client:
            log("AGV全局连接不可用", "error")
            return False
        
        # 获取当前站点
        current_station = get_current_station(client)
        if current_station is None:
            log("⚠️  AGV当前不在任何预设站点（4,5,8,9,10）", "error")
            log("AGV可能在站点0（未定位）或其他未知站点", "error")
            log("开始循环播放音频文件6提醒操作员", "warn")
            
            # 获取音频报警管理器
            alarm_manager = get_audio_alarm_manager()
            
            # 启动连续音频报警
            alarm_manager.start_continuous_alarm(
                audio_id=6,
                alarm_id="agv_unknown_position",
                interval=3.0,  # 每3秒播放一次
                audio_duration=2.0,  # 音频时长2秒
                logger=logger
            )
            
            log("已启动音频报警，请操作员检查AGV位置并重新定位", "error")
            return False
        
        # 根据当前站点执行不同策略
        if current_station == 4:
            log("✅ AGV已在站点4，无需移动")
            return True
            
        elif current_station in [5, 8, 9, 10]:
            log(f"AGV在站点{current_station}，直接移动至站点4")
            success = move_agv_to_station(4, logger)
            if success:
                log(f"✅ AGV成功从站点{current_station}移动到站点4")
                return True
            else:
                log(f"❌ AGV从站点{current_station}移动到站点4失败", "error")
                return False
                
        else:
            log(f"AGV在未知站点{current_station}，开始循环播放音频文件6提醒操作员", "warn")
            
            # 获取音频报警管理器
            alarm_manager = get_audio_alarm_manager()
            
            # 启动连续音频报警
            alarm_manager.start_continuous_alarm(
                audio_id=6,
                alarm_id="agv_unknown_station",
                interval=3.0,  # 每3秒播放一次
                audio_duration=2.0,  # 音频时长2秒
                logger=logger
            )
            
            log(f"AGV在未识别的站点{current_station}，已启动音频报警", "error")
            log("请操作员检查AGV位置，手动移动AGV到有效站点(4,5,8,9,10)", "error")
            return False
                
    except Exception as e:
        log(f"AGV初始化异常: {e}", "error")
        return False

def simple_initialize_agv(logger=None):
    """
    简化的AGV初始化函数 - 别名函数，方便调用
    
    Args:
        logger: 日志记录器（可选）
        
    Returns:
        bool: True-成功，False-失败
    """
    return initialize_agv_to_station4(logger)

def simple_play_audio(audio_id, logger=None):
    """
    简化的AGV音频播放函数 - 使用全局连接，无需每次建立连接
    
    Args:
        audio_id: 音频文件编号（从1开始）
        logger: 日志记录器（可选）
        
    Returns:
        bool: True-成功，False-失败
        
    使用方法:
        success = simple_play_audio(1)  # 播放音频1
        success = simple_play_audio(3, logger=logger)  # 播放音频3，带日志
    """
    def log(msg, level="info"):
        if logger:
            getattr(logger, level)(msg)
        else:
            print(f"[AUDIO] {msg}")
    
    try:
        log(f"开始播放AGV音频 {audio_id}")
        
        # 使用全局连接管理器
        global_conn = get_agv_connection()
        client = global_conn.get_client()
        
        if not client:
            log("AGV全局连接不可用", "error")
            return False
            
        success = play_audio(client, audio_id, logger)
        return success
            
    except Exception as e:
        log(f"播放音频异常: {e}", "error")
        return False

if __name__ == '__main__':
    print("[INFO] 开始连接AGV...")
    print(f"[DEBUG] 目标IP: {MODBUS_IP}, 端口: {MODBUS_PORT}")
    
    # 音频播放示例 - 测试新的间隔逻辑
    print("\n=== AGV音频播放示例（改进版） ===")
    
    # 方法1: 使用简化函数
    print("方法1: 使用简化函数播放音频")
    success = simple_play_audio(1)
    if success:
        print("✅ 音频1播放成功")
    else:
        print("❌ 音频1播放失败")
    
    # 方法2: 测试连续音频播放（改进的间隔逻辑）
    print("\n方法2: 测试连续音频播放（改进的间隔逻辑）")
    try:
        alarm_manager = get_audio_alarm_manager()
        
        # 启动连续音频报警，指定音频时长和静默间隔
        alarm_id = alarm_manager.start_continuous_alarm(
            audio_id=1,              # 音频文件编号
            alarm_id="test_alarm",   # 报警标识符
            interval=5.0,            # 静默间隔5秒
            audio_duration=3.0       # 音频播放时长3秒
        )
        
        print(f"✅ 连续音频报警已启动: {alarm_id}")
        print("播放逻辑: 播放3秒音频 → 等待5秒静默 → 重复")
        
        # 运行10秒后停止
        import time
        time.sleep(10)
        
        success = alarm_manager.stop_alarm(alarm_id)
        if success:
            print("✅ 连续音频报警已停止")
    except Exception as e:
        print(f"❌ 连续音频播放测试失败: {e}")
    
    # 方法3: 使用AGVController类播放音频
    print("\n方法3: 使用AGVController类播放音频")
    try:
        with AGVController() as agv:
            success = agv.play_audio(2)
            if success:
                print("✅ 音频2播放成功")
            else:
                print("❌ 音频2播放失败")
    except Exception as e:
        print(f"❌ AGVController音频播放失败: {e}")
    
    print("\n[INFO] 音频播放示例结束")
    print("改进说明:")
    print("- 连续播放现在会等待音频播放完成后再等待静默间隔")
    print("- 默认音频时长3秒，静默间隔5秒")
    print("- 可以根据实际音频文件长度调整参数")
    print("- 避免了音频重叠播放的问题")
