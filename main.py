#!/usr/bin/env python3

import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.rdk_init import init_robot
from core.work_handler import handle_work_step
from plans.change_tool import change_tool
from plans.pick_mestick import pick_mestick
from plans.Put_mestick import Put_mestick  
from utils.logger import get_logger
from AGV import move_agv_to_station, get_audio_alarm_manager, simple_initialize_agv, get_current_station, get_agv_connection  

def memory_stick_workflow(robot, logger, tool_num=1, check_mestick=True, agv_enabled=True, work_station=4):
    """
    内存条操作工作流程
    
    Args:
        robot: 机器人对象
        logger: 日志记录器对象
        tool_num: 工具编号，默认为1
        check_mestick: 是否进行内存条检查，默认为False
        agv_enabled: 是否启用AGV移动，默认为True
        work_station: AGV工作站点，默认为4
        
    Returns:
        int: 0-成功，非0-失败
    """
    logger.info(f"开始内存条工作流程，工具编号: {tool_num}")
    
    # 执行换工具操作
    logger.info("开始执行换工具流程...")
    if not handle_work_step(
        lambda r, l: change_tool(r, l, tool_num),
        robot, 
        logger, 
        expected_values=[90], 
        step_name="换工具"
    ):
        logger.error("换工具操作失败，程序终止")
        return 1
    
    # 执行取内存条操作
    logger.info("开始执行取内存条流程...")
    if not handle_work_step(
        pick_mestick,
        robot,
        logger,
        expected_values=[10],
        step_name="取内存条"
    ):
        logger.error("取内存条操作失败，程序终止")
        return 1
    
    # 在执行放内存条之前，AGV移动到站点5（做连接检测）
    if agv_enabled:
        logger.info("准备执行放内存条操作，AGV移动到站点5进行连接检测...")
        try:
            # 获取AGV全局连接
            global_conn = get_agv_connection()
            client = global_conn.get_client()
            
            if client:
                # 检查当前站点
                current_station = get_current_station(client)
                logger.info(f"AGV当前站点: {current_station}")
                
                if current_station == 5:
                    logger.info("✅ AGV已在站点5，无需移动")
                else:
                    logger.info(f"AGV需要从站点 {current_station} 移动到站点5")
                    success = move_agv_to_station(5, logger)
                    if success:
                        logger.info("AGV已成功到达站点5，准备执行放内存条操作")
                    else:
                        logger.warn("AGV移动到站点5失败，但程序将继续执行")
            else:
                logger.warn("无法获取AGV连接，跳过站点检查，直接尝试移动到站点5")
                success = move_agv_to_station(5, logger)
                if success:
                    logger.info("AGV已成功到达站点5，准备执行放内存条操作")
                else:
                    logger.warn("AGV移动到站点5失败，但程序将继续执行")
                    
        except Exception as e:
            logger.error(f"AGV移动到站点5过程中发生异常: {e}")
            logger.warn("AGV移动失败，但程序将继续执行")
    
    # 执行放内存条操作
    logger.info("开始执行放内存条流程...")
    try:
        result = Put_mestick(robot, logger, WorkServerMestick=1, PalletNum=1, PhotoNum=1)
        if result == 20:  # 成功
            logger.info("放内存条操作成功")
        else:
            logger.error(f"放内存条操作失败，错误码: {result}")
            return 2
    except Exception as e:
        logger.error(f"放内存条操作异常: {e}")
        return 2
    
    if check_mestick:
        logger.info("重新拔插内存条...")
        try:
            result = Put_mestick(robot, logger, WorkServerMestick=2)
            if result == 20:  # 成功
                logger.info("内存条状态检查通过")
            else:
                logger.error(f"内存条状态检查失败，错误码: {result}")
                return 3
        except Exception as e:
            logger.error(f"内存条状态检查异常: {e}")
            return 3

    logger.info("内存条工作流程完成！")
    return 0


def initialize_agv_system(logger):
    """
    初始化AGV系统，确保AGV位于站点4
    
    Args:
        logger: 日志记录器
        
    Returns:
        bool: True-初始化成功，False-初始化失败
    """
    logger.info("开始AGV初始化，确保AGV位于站点4...")
    
    # 先直接读取当前站点寄存器值
    try:
        global_conn = get_agv_connection()
        client = global_conn.get_client()
        if client:
            logger.info("📡 正在读取AGV当前站点寄存器...")
            res = client.read_input_registers(address=33, count=1)  # INPUT_CURRENT_STATION
            if not res.isError():
                raw_station = res.registers[0]
                logger.info(f"🏷️  [MAIN] AGV当前站点寄存器值: {raw_station}")
            else:
                logger.error(f"读取站点寄存器失败: {res}")
        else:
            logger.error("无法获取AGV连接")
    except Exception as e:
        logger.error(f"读取站点信息异常: {e}")
    
    try:
        init_success = simple_initialize_agv(logger)
        if init_success:
            logger.info("✅ AGV初始化成功，已确保AGV位于站点4")
            return True
        else:
            logger.warn("⚠️ AGV初始化失败，但程序将继续执行")
            logger.warn("建议检查AGV状态和网络连接")
            return False
    except Exception as e:
        logger.error(f"AGV初始化过程中发生异常: {e}")
        logger.warn("AGV初始化失败，但程序将继续执行")
        return False


def main():
    """
    主程序入口
    """
    parser = argparse.ArgumentParser(description="Flexiv机器人内存条处理自动化程序")
    parser.add_argument("--robot-sn", default="Rizon10-062283", help="机器人序列号")
    parser.add_argument("--work-num", type=int, default=1, help="工作编号，默认为1")
    parser.add_argument("--log-name", default="RobotLogger", help="日志记录器名称")
    parser.add_argument("--agv-ip", default="192.168.2.112", help="AGV的IP地址")
    parser.add_argument("--agv-port", type=int, default=502, help="AGV的Modbus端口")  
    parser.add_argument("--work-station", type=int, default=4, help="初始工作站点ID")
    parser.add_argument("--disable-agv", action="store_true", help="禁用AGV移动功能")
    parser.add_argument("--tool-num", type=int, default=1, help="工具编号")
    parser.add_argument("--check-mestick", action="store_true", help="启用内存条检查")
    
    args = parser.parse_args()
    
    # 初始化日志记录器
    logger = get_logger(args.log_name)
    logger.info("程序启动")
    logger.info(f"机器人序列号: {args.robot_sn}")
    
    # 停止所有连续音频报警（用户重新初始化）
    try:
        alarm_manager = get_audio_alarm_manager()
        stopped_count = alarm_manager.stop_all_alarms()
        if stopped_count > 0:
            logger.info(f"已停止 {stopped_count} 个连续音频报警")
    except Exception as e:
        logger.warn(f"停止音频报警时发生异常: {e}")
    
    # AGV默认启用，除非明确禁用
    agv_enabled = not args.disable_agv
    if agv_enabled:
        logger.info(f"AGV控制已启用 - 工作站点: {args.work_station}")
        
        # AGV初始化函数调用
        agv_init_success = initialize_agv_system(logger)
        if not agv_init_success:
            logger.error("AGV初始化失败，程序终止")
            logger.error("请确保AGV在有效站点(4,5,8,9,10)后重新运行程序")
            logger.info("音频报警将持续播放，按Ctrl+C可停止")
            
            # 等待用户手动停止，保持音频报警运行
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户手动停止程序")
                # 停止所有音频报警
                try:
                    alarm_manager = get_audio_alarm_manager()
                    stopped_count = alarm_manager.stop_all_alarms()
                    if stopped_count > 0:
                        logger.info(f"已停止 {stopped_count} 个音频报警")
                except Exception as e:
                    logger.warn(f"停止音频报警时发生异常: {e}")
                return 5  # AGV初始化失败退出码
    else:
        logger.info("AGV控制已禁用")

    try:
        # 初始化机器人连接
        logger.info("正在初始化机器人连接...")
        robot = init_robot(args.robot_sn, logger)

        # 检查机器人连接状态
        try:
            logger.info("检查机器人连接状态...")
            robot_mode = robot.mode()
            logger.info(f"机器人当前模式: {robot_mode}")
            
            # 等待机器人完全就绪
            import time
            logger.info("等待机器人完全就绪...")
            time.sleep(2)  # 给机器人一些时间完成初始化
            
        except Exception as e:
            logger.error(f"无法获取机器人状态: {e}")
            logger.error("机器人可能未正确连接，请检查:")
            logger.error("1. 机器人是否开机")
            logger.error("2. 网络连接是否正常")
            logger.error("3. 机器人序列号是否正确")
            logger.error("4. 机器人是否完成启动过程")
            return 3

        # 显示可用计划列表（带重试机制）
        max_retries = 3
        plan_list = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"获取计划列表 (第{attempt + 1}次尝试)...")
                plan_list = robot.plan_list()
                logger.info("成功获取计划列表:")
                for i in range(len(plan_list)):
                    logger.info(f"[{i}] {plan_list[i]}")
                break  # 成功获取，跳出重试循环
                
            except Exception as e:
                logger.warn(f"第{attempt + 1}次获取计划列表失败: {e}")
                if attempt < max_retries - 1:
                    logger.info("等待3秒后重试...")
                    time.sleep(3)
                else:
                    logger.error("多次尝试后仍无法获取计划列表")
                    logger.error("可能的原因:")
                    logger.error("1. 机器人仍在启动过程中")
                    logger.error("2. 机器人RDK服务未正常运行")
                    logger.error("3. 机器人处于错误状态")
                    logger.error("4. 机器人计划管理器未就绪")
                    logger.error("建议:")
                    logger.error("- 检查机器人控制器状态")
                    logger.error("- 重启机器人RDK服务")
                    logger.error("- 确认机器人完全启动完成")
                    return 3
        
        # 检查必需的计划是否存在
        if plan_list is not None:
            required_plans = ["ChangeTool", "PickMestick", "PutMestick"]
            missing_plans = []
            for plan in required_plans:
                if plan not in plan_list:
                    missing_plans.append(plan)
            
            if missing_plans:
                logger.error(f"缺少必需的计划: {missing_plans}")
                logger.error("请确保机器人中包含所有必需的计划")
                return 4

       

        # 执行内存条工作流程（包含AGV移动）
        result = memory_stick_workflow(
            robot, 
            logger, 
            tool_num=args.tool_num,
            check_mestick=True,
            agv_enabled=agv_enabled,
            work_station=args.work_station
        )
        
        if result == 0:
            logger.info("所有操作成功完成！")
        else:
            logger.error("工作流程执行失败")
            
        return result
        
    except KeyboardInterrupt:
        logger.warn("程序被用户中断")
        return 2
        
    except Exception as e:
        logger.error(f"程序执行过程中发生异常: {e}")
        return 3


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)