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
from AGV import move_agv_to_station, get_audio_alarm_manager

def memory_stick_workflow(robot, logger, tool_num=1, check_mestick=False, agv_enabled=True, work_station=4):
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
    
    # AGV移动到工作站点（换工具完成后）
    if agv_enabled:
        logger.info(f"AGV开始移动到工作站点 {work_station}...")
        try:
            success = move_agv_to_station(work_station, logger)
            if success:
                logger.info("AGV已成功到达工作站点")
            else:
                logger.warning("AGV移动失败，但程序将继续执行")
        except Exception as e:
            logger.error(f"AGV移动过程中发生异常: {e}")
            logger.warning("AGV操作失败，但程序将继续执行")
 
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
    
    # 执行放内存条操作
    logger.info("开始执行放内存条流程...")
    try:
        result = Put_mestick(robot, logger, WorkServerMestick=1)
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


def main():
    """
    主程序入口
    """
    parser = argparse.ArgumentParser(description="Flexiv机器人内存条处理自动化程序")
    parser.add_argument("--robot-sn", default="Rizon10-062283", help="机器人序列号")
    #parser.add_argument("robot_sn",default="Rizon10-062283", help="机器人序列号")
    parser.add_argument("--work-num", type=int, default=1, help="工作编号，默认为1")
    parser.add_argument("--log-name", default="RobotLogger", help="日志记录器名称")
    parser.add_argument("--agv-ip", default="192.168.2.112", help="AGV的IP地址")
    parser.add_argument("--agv-port", type=int, default=502, help="AGV的Modbus端口")  
    parser.add_argument("--work-station", type=int, default=4, help="工作站点ID")
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
        logger.warning(f"停止音频报警时发生异常: {e}")
    
    # AGV默认启用，除非明确禁用
    agv_enabled = not args.disable_agv
    if agv_enabled:
        logger.info(f"AGV控制已启用 - 工作站点: {args.work_station}")
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
        except Exception as e:
            logger.error(f"无法获取机器人状态: {e}")
            logger.error("机器人可能未正确连接，请检查:")
            logger.error("1. 机器人是否开机")
            logger.error("2. 网络连接是否正常")
            logger.error("3. 机器人序列号是否正确")
            return 3

        # 显示可用计划列表
        try:
            plan_list = robot.plan_list()
            logger.info("可用计划列表:")
            for i in range(len(plan_list)):
                logger.info(f"[{i}] {plan_list[i]}")
                
            # 检查必需的计划是否存在
            required_plans = ["ChangeTool", "PickMestick", "PutMestick"]
            missing_plans = []
            for plan in required_plans:
                if plan not in plan_list:
                    missing_plans.append(plan)
            
            if missing_plans:
                logger.error(f"缺少必需的计划: {missing_plans}")
                logger.error("请确保机器人中包含所有必需的计划")
                return 4
                
        except Exception as e:
            logger.error(f"无法获取计划列表: {e}")
            logger.error("这通常表示机器人通信有问题")
            return 3

        # 执行内存条工作流程（包含AGV移动）
        result = memory_stick_workflow(
            robot, 
            logger, 
            tool_num=args.tool_num,
            check_mestick=args.check_mestick,
            agv_enabled=agv_enabled,
            work_station=args.work_station
        )
        
        if result == 0:
            logger.info("所有操作成功完成！")
        else:
            logger.error("工作流程执行失败")
            
        return result
        
    except KeyboardInterrupt:
        logger.warning("程序被用户中断")
        return 2
        
    except Exception as e:
        logger.error(f"程序执行过程中发生异常: {e}")
        return 3


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)