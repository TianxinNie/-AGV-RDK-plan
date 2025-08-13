from AGV import get_audio_alarm_manager

def change_tool(robot, logger, work_num: int = 1) -> int:
    """
    执行换工具操作
    
    Args:
        robot: 机器人对象
        logger: 日志记录器
        work_num: 工作编号，默认为1
        
    Returns:
        int: 操作结果，90表示成功，其他值表示失败
    """
    try:
        logger.info(f"开始执行换工具操作，工作编号: {work_num}")
        
        # 检查机器人连接状态
        try:
            robot_mode = robot.mode()
            logger.info(f"机器人当前模式: {robot_mode}")
        except Exception as e:
            logger.error(f"无法获取机器人状态: {e}")
            # 启动连续音频报警 - 机器人状态错误
            alarm_manager = get_audio_alarm_manager()
            alarm_manager.start_continuous_alarm(4, "robot_status_error", interval=5.0, audio_duration=4.0, logger=logger)
            return 1999
        
        # 检查ChangeTool计划是否存在
        try:
            plan_list = robot.plan_list()
            if "ChangeTool" not in plan_list:
                logger.error("机器人中没有找到ChangeTool计划")
                logger.error("请确保机器人中包含ChangeTool计划")
                return 1999
            logger.info("找到ChangeTool计划，开始执行")
        except Exception as e:
            logger.error(f"无法获取计划列表: {e}")
            return 1999
        
        try:
            # 设置全局变量
            robot.SetGlobalVariables({"WorkNum": work_num})
            logger.info(f"设置WorkNum = {work_num}")
            
            # 执行计划
            logger.info("开始执行ChangeTool计划...")
            robot.ExecutePlan("ChangeTool", True)
            
            # 等待执行完成
            import time
            while robot.busy():
                logger.info("ChangeTool 执行中...")
                time.sleep(1)  # 等待1秒再检查
            
            # 获取反馈
            global_vars = robot.global_variables()
            feedback = global_vars.get("WorkFeedBack", -1)
            
            logger.info(f"ChangeTool 完成，反馈值: {feedback}")
            
            if feedback == 90:
                logger.info("换工具操作成功完成")
            else:
                logger.error(f"换工具操作失败，错误码: {feedback}")
                # 启动连续音频报警 - 机器人状态错误（换工具失败通常是机器人状态问题）
                alarm_manager = get_audio_alarm_manager()
                alarm_manager.start_continuous_alarm(4, "change_tool_failed", interval=5.0, audio_duration=4.0, logger=logger)
                
            return feedback
            
        except Exception as e:
            logger.error(f"执行ChangeTool计划时发生异常: {e}")
            return 1999
        
    except Exception as e:
        logger.error(f"ChangeTool 执行失败: {e}")
        return 1999