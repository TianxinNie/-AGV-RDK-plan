from simple_agv import SimpleAGV, AudioAlarmManager

def change_tool(robot, logger, work_num: int = 1) -> int:
    """
    执行换工具操作 - 使用新的简洁AGV控制器
    """
    try:
        logger.info(f"开始执行换工具操作，工作编号: {work_num}")
        
        # 检查机器人状态
        if not _check_robot_ready(robot, logger):
            return 1999
        
        # 检查计划存在
        if not _check_plan_exists(robot, "ChangeTool", logger):
            return 1999
        
        # 执行换工具
        return _execute_change_tool(robot, logger, work_num)
        
    except Exception as e:
        logger.error(f"ChangeTool 执行异常: {e}")
        return 1999


def _check_robot_ready(robot, logger) -> bool:
    """检查机器人就绪状态"""
    try:
        robot_mode = robot.mode()
        logger.info(f"机器人当前模式: {robot_mode}")
        return True
    except Exception as e:
        logger.error(f"无法获取机器人状态: {e}")
        _start_alarm(4, "robot_status_error", logger)
        return False


def _check_plan_exists(robot, plan_name: str, logger) -> bool:
    """检查计划是否存在"""
    try:
        plan_list = robot.plan_list()
        if plan_name not in plan_list:
            logger.error(f"机器人中没有找到{plan_name}计划")
            return False
        logger.info(f"找到{plan_name}计划，开始执行")
        return True
    except Exception as e:
        logger.error(f"无法获取计划列表: {e}")
        return False


def _execute_change_tool(robot, logger, work_num: int) -> int:
    """执行换工具主逻辑"""
    try:
        # 设置参数
        robot.SetGlobalVariables({"WorkNum": work_num})
        logger.info(f"设置WorkNum = {work_num}")
        
        # 执行计划
        logger.info("开始执行ChangeTool计划...")
        robot.ExecutePlan("ChangeTool", True)
        
        # 等待完成
        _wait_for_completion(robot, logger, "ChangeTool")
        
        # 获取结果
        feedback = _get_feedback(robot, logger)
        
        if feedback == 90:
            logger.info("换工具操作成功完成")
        else:
            logger.error(f"换工具操作失败，错误码: {feedback}")
            _start_alarm(4, "change_tool_failed", logger)
            
        return feedback
        
    except Exception as e:
        logger.error(f"执行ChangeTool计划时发生异常: {e}")
        return 1999


def _wait_for_completion(robot, logger, plan_name: str):
    """等待计划执行完成"""
    import time
    while robot.busy():
        logger.info(f"{plan_name} 执行中...")
        time.sleep(1)


def _get_feedback(robot, logger) -> int:
    """获取执行反馈"""
    try:
        global_vars = robot.global_variables()
        feedback = global_vars.get("WorkFeedBack", -1)
        logger.info(f"执行完成，反馈值: {feedback}")
        return feedback
    except Exception as e:
        logger.error(f"获取反馈异常: {e}")
        return 1999


def _start_alarm(audio_id: int, alarm_id: str, logger):
    """启动音频报警"""
    try:
        # 使用新的简洁AGV控制器
        agv = SimpleAGV()
        alarm_manager = AudioAlarmManager(agv)
        alarm_manager.start_alarm(audio_id, alarm_id, interval=5.0)
        logger.warning(f"已启动音频报警: {alarm_id}")
    except Exception as e:
        logger.error(f"启动音频报警失败: {e}")