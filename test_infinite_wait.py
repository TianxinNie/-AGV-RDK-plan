#!/usr/bin/env python3
"""
测试AGV无限等待障碍物消失功能 + 详细传感器状态打印
"""

from AGV import move_to_station, print_detailed_sensor_status
from pymodbus.client import ModbusTcpClient

def test_infinite_wait_example():
    """演示如何使用无限等待功能"""
    
    # 连接AGV (需要替换为实际的AGV IP地址)
    client = ModbusTcpClient(host='192.168.1.100', port=502)
    
    try:
        if not client.connect():
            print("❌ 无法连接到AGV")
            return False
            
        print("=== 普通模式 (60秒超时) ===")
        # 普通模式：遇到障碍物最多等待60秒
        success = move_to_station(
            client=client,
            station_id=5,
            vx=1.0,
            vy=0.0,
            w=0.5,
            wait_forever_on_block=False  # 默认行为
        )
        print(f"普通模式结果: {'成功' if success else '失败/超时'}")
        
        print("\n=== 无限等待模式 ===")
        # 无限等待模式：遇到障碍物会一直等待，直到障碍物消失
        # 当检测到阻挡时，会自动打印详细传感器状态
        success = move_to_station(
            client=client,
            station_id=6,
            vx=1.0,
            vy=0.0,
            w=0.5,
            wait_forever_on_block=True  # 启用无限等待
        )
        print(f"无限等待模式结果: {'成功' if success else '失败'}")
        
        print("\n=== 手动传感器状态测试 ===")
        print("手动调用详细传感器状态...")
        print_detailed_sensor_status(client)
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        return False
    finally:
        client.close()
        
    return True

if __name__ == "__main__":
    print("AGV无限等待障碍物功能 + 详细传感器状态测试")
    print("=" * 60)
    print("功能说明:")
    print("1. 支持无限等待障碍物消失 (wait_forever_on_block=True)")
    print("2. 检测到阻挡时自动打印详细传感器状态")
    print("3. 包含超声、激光、DI、安全状态等完整信息")
    print("注意：运行前请确保AGV IP地址正确")
    print("=" * 60)
    
    test_infinite_wait_example()