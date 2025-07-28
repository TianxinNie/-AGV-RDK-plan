from AGV import get_audio_alarm_manager
def pick_mestick(robot, logger) -> int:
    """
    执行取内存条操作，包含重试机制
    
    Args:
        robot: 机器人对象
        logger: 日志记录器
        
    Returns:
        int: 操作结果
             10 - 成功
             101 - 拍照失败（重试3次后仍失败）
             102 - 取料失败（重试3次后仍失败）
             1999 - 系统异常
    """
    try:
        try_photo_num = 0
        try_pick_num = 0
        max_retries = 3
        
        logger.info("开始执行取内存条操作")
        
        # 检查机器人连接状态
        try:
            robot_mode = robot.mode()
            logger.info(f"机器人当前模式: {robot_mode}")
        except Exception as e:
            logger.error(f"无法获取机器人状态: {e}")
            return 1999
        
        # 检查PickMestick计划是否存在
        try:
            plan_list = robot.plan_list()
            if "PickMestick" not in plan_list:
                logger.error("机器人中没有找到PickMestick计划")
                logger.error("请确保机器人中包含PickMestick计划")
                return 1999
            logger.info("找到PickMestick计划，开始执行")
        except Exception as e:
            logger.error(f"无法获取计划列表: {e}")
            return 1999
        
        while True:
            try:
                # 执行计划
                logger.info("开始执行PickMestick计划...")
                robot.ExecutePlan("PickMestick", True)
                
                # 等待执行完成
                import time
                while robot.busy():
                    logger.info("PickMestick 执行中...")
                    time.sleep(1)  # 等待1秒再检查
                
                # 获取反馈
                global_vars = robot.global_variables()
                feedback = global_vars.get("WorkFeedBack", -1)
                
                try_pick_num += 1
                logger.info(f"PickMestick 第 {try_pick_num} 次尝试，反馈值: {feedback}")
                
            except Exception as e:
                logger.error(f"执行PickMestick计划时发生异常: {e}")
                return 1999
            
            if feedback == 101:  # 拍照失败
                try_photo_num += 1
                if try_photo_num > max_retries:
                    logger.error(f"拍照失败，已重试 {max_retries} 次，放弃操作")
                    # 启动连续音频报警 - 拍照失败
                    alarm_manager = get_audio_alarm_manager()
                    alarm_manager.start_continuous_alarm(3, "pick_photo_failed", interval=3.0, logger=logger)
                    return 101
                logger.warning(f"拍照失败，进行第 {try_photo_num} 次重试")
                continue
                
            elif feedback == 102:  # 取料失败
                if try_pick_num > max_retries:
                    logger.error(f"取料失败，已重试 {max_retries} 次，放弃操作")
                    # 启动连续音频报警 - 取料失败
                    alarm_manager = get_audio_alarm_manager()
                    alarm_manager.start_continuous_alarm(1, "pick_failed", interval=3.0, logger=logger)
                    return 102
                logger.warning(f"取料失败，进行第 {try_pick_num} 次重试")
                continue
                
            elif feedback == 10:  # 成功
                logger.info("取内存条操作成功完成")
                return 10
                
            else:
                logger.error(f"未知反馈值: {feedback}")
                if try_pick_num > max_retries:
                    return feedback
                continue
                
    except Exception as e:
        logger.error(f"PickMestick 执行异常: {e}")
        return 1999