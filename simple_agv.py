"""
简洁的AGV控制器 - Linus式重构版本
- 150行以内核心功能
- 自动重连支持  
- 清晰的状态管理
- 零全局变量
"""
from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
import time
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable


class AGVError(Enum):
    CONNECT_FAILED = "连接失败"
    CONTROL_FAILED = "控制权失败"
    MOVE_FAILED = "移动失败"
    AUDIO_FAILED = "音频失败"


@dataclass
class AGVState:
    connected: bool = False
    has_control: bool = False
    current_station: Optional[int] = None
    is_moving: bool = False
    localized: bool = False


class SimpleAGV:
    """简洁的AGV控制器 - 自动重连 + 状态清晰"""
    
    # 寄存器地址
    COIL_ACQUIRE_CONTROL = 9
    COIL_RELEASE_CONTROL = 10
    ADDR_TARGET_STATION = 0
    ADDR_VX, ADDR_VY, ADDR_W = 4, 6, 8
    ADDR_PLAY_AUDIO = 29
    
    INPUT_CURRENT_STATION = 6
    INPUT_LOCALIZATION_STATE = 7
    INPUT_NAVIGATION_STATE = 8
    INPUT_CONTROL_OCCUPIED = 42
    
    def __init__(self, ip: str = '192.168.2.112', port: int = 502, auto_reconnect: bool = True):
        self.ip = ip
        self.port = port
        self.client = ModbusTcpClient(ip, port)
        self.state = AGVState()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        if auto_reconnect:
            self._start_monitor()
    
    def _start_monitor(self):
        """启动连接监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_connection(self):
        """连接监控循环 - 核心重连逻辑"""
        while not self._stop_monitor.wait(3.0):  # 每3秒检查一次
            try:
                # 测试连接
                if self.client.is_socket_open():
                    result = self.client.read_input_registers(self.INPUT_LOCALIZATION_STATE, 1)
                    if not result.isError():
                        if not self.state.connected:
                            self.state.connected = True
                            print(f"✅ AGV连接已恢复 {self.ip}")
                        continue
                
                # 连接异常，尝试重连
                if self.state.connected:
                    print(f"❌ AGV连接断开 {self.ip}")
                    self.state.connected = False
                    self.state.has_control = False
                
                self.client.close()
                if self.client.connect():
                    self.state.connected = True
                    print(f"✅ AGV重连成功 {self.ip}")
                    
            except Exception:
                self.state.connected = False
                self.state.has_control = False
    
    def connect(self) -> bool:
        """手动连接"""
        try:
            if self.client.connect():
                self.state.connected = True
                return True
            return False
        except Exception:
            return False
    
    def disconnect(self):
        """断开连接"""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
        
        if self.state.has_control:
            self._release_control()
        
        self.client.close()
        self.state.connected = False
    
    def _ensure_connected(self) -> bool:
        """确保连接可用"""
        if not self.state.connected:
            return self.connect()
        return True
    
    def _acquire_control(self) -> bool:
        """抢占控制权"""
        if not self._ensure_connected():
            return False
            
        try:
            # 检查定位状态
            result = self.client.read_input_registers(self.INPUT_LOCALIZATION_STATE, 1)
            if result.isError() or result.registers[0] != 1:
                print("❌ AGV未正确定位，无法抢占控制权")
                return False
            
            # 写入抢占命令
            result = self.client.write_coil(self.COIL_ACQUIRE_CONTROL, True)
            if result.isError():
                return False
                
            time.sleep(1)
            
            # 验证抢占成功
            result = self.client.read_coils(self.COIL_ACQUIRE_CONTROL, 1)
            if not result.isError() and not result.bits[0]:
                self.state.has_control = True
                return True
                
            return False
            
        except Exception:
            return False
    
    def _release_control(self) -> bool:
        """释放控制权"""
        if not self.state.connected:
            return True
            
        try:
            result = self.client.write_coil(self.COIL_RELEASE_CONTROL, True)
            if not result.isError():
                self.state.has_control = False
                return True
            return False
        except Exception:
            return False
    
    def _write_float32(self, address: int, value: float):
        """写入32位浮点数"""
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        builder.add_32bit_float(value)
        result = self.client.write_registers(address, builder.to_registers())
        if result.isError():
            raise Exception(f"写入浮点数失败: {address}={value}")
    
    def move_to_station(self, station_id: int, vx: float = 1.0, vy: float = 0.0, w: float = 0.5) -> bool:
        """移动到指定站点"""
        if not self._ensure_connected():
            return False
        
        # 自动抢占控制权
        if not self.state.has_control and not self._acquire_control():
            return False
        
        try:
            # 设置速度参数
            self._write_float32(self.ADDR_VX, vx)
            self._write_float32(self.ADDR_VY, vy)  
            self._write_float32(self.ADDR_W, w)
            
            # 设置目标站点（会自动开始导航）
            result = self.client.write_register(self.ADDR_TARGET_STATION, station_id)
            if result.isError():
                return False
            
            # 监控导航状态
            return self._wait_navigation_complete()
            
        except Exception:
            return False
    
    def _wait_navigation_complete(self, timeout: int = 300) -> bool:
        """等待导航完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                result = self.client.read_input_registers(self.INPUT_NAVIGATION_STATE, 1)
                if result.isError():
                    time.sleep(1)
                    continue
                    
                nav_state = result.registers[0]
                
                if nav_state == 4:  # 到达
                    return True
                elif nav_state in (5, 6, 7):  # 失败、取消、超时
                    return False
                    
                time.sleep(1)
                
            except Exception:
                time.sleep(1)
                
        return False
    
    def play_audio(self, audio_id: int) -> bool:
        """播放音频"""
        if not self._ensure_connected():
            return False
            
        try:
            result = self.client.write_register(self.ADDR_PLAY_AUDIO, audio_id)
            return not result.isError()
        except Exception:
            return False
    
    def get_current_station(self) -> Optional[int]:
        """获取当前站点"""
        if not self._ensure_connected():
            return None
            
        try:
            result = self.client.read_input_registers(self.INPUT_CURRENT_STATION, 1)
            if not result.isError():
                station = result.registers[0]
                return station if station > 0 else None
            return None
        except Exception:
            return None
    
    def __enter__(self):
        if self.connect():
            return self
        raise ConnectionError("AGV连接失败")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# 音频报警管理器 - 简化版本
class AudioAlarmManager:
    def __init__(self, agv: SimpleAGV):
        self.agv = agv
        self.alarms = {}  # {alarm_id: thread}
        
    def start_alarm(self, audio_id: int, alarm_id: str, interval: float = 5.0) -> str:
        """开始连续报警"""
        if alarm_id in self.alarms:
            self.stop_alarm(alarm_id)
        
        stop_event = threading.Event()
        
        def alarm_loop():
            while not stop_event.wait(interval):
                self.agv.play_audio(audio_id)
        
        thread = threading.Thread(target=alarm_loop, daemon=True)
        thread.start()
        
        self.alarms[alarm_id] = (thread, stop_event)
        return alarm_id
    
    def stop_alarm(self, alarm_id: str) -> bool:
        """停止报警"""
        if alarm_id in self.alarms:
            thread, stop_event = self.alarms[alarm_id]
            stop_event.set()
            del self.alarms[alarm_id]
            return True
        return False


# 便利函数
def move_agv_to_station(station_id: int, logger=None) -> bool:
    """简单的移动函数"""
    try:
        with SimpleAGV() as agv:
            success = agv.move_to_station(station_id)
            if logger:
                if success:
                    logger.info(f"✅ AGV成功到达站点 {station_id}")
                else:
                    logger.error(f"❌ AGV移动到站点 {station_id} 失败")
            return success
    except Exception as e:
        if logger:
            logger.error(f"AGV移动异常: {e}")
        return False


if __name__ == '__main__':
    # 测试代码
    print("测试简洁AGV控制器")
    try:
        with SimpleAGV() as agv:
            print(f"当前站点: {agv.get_current_station()}")
            print("播放音频1...")
            agv.play_audio(1)
    except Exception as e:
        print(f"测试失败: {e}")