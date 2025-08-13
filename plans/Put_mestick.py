from time import sleep
from AGV import get_audio_alarm_manager

def Put_mestick(robot, logger, WorkServerMestick: int,PalletNum:int=1,PhotoNum:int=1) -> int:
    """
    执行放内存条操作，包含重试机制
    
    Args:
        robot: 机器人对象
        logger: 日志记录器
        WorkServerMestick: 工作服务器内存条参数
        
    Returns:
        int: 操作结果
             20 - 成功
             201 - 拍照失败（重试3次后仍失败）
             202 - 取料失败（重试3次后仍失败）
             1999 - 系统异常
    """
    try:
        try_photo_num = 0
        try_put_num = 0
        max_retries = 3
        
        logger.info("开始执行放内存条操作")
        
        # 检查机器人连接状态
        try:
            robot_mode = robot.mode()
            logger.info(f"机器人当前模式: {robot_mode}")
        except Exception as e:
            logger.error(f"无法获取机器人状态: {e}")
            return 1999
        
        # 检查PutMestick计划是否存在
        try:
            plan_list = robot.plan_list()
            if "PutMestick" not in plan_list:
                logger.error("机器人中没有找到PutMestick计划")
                logger.error("请确保机器人中包含PutMestick计划")
                return 1999
            logger.info("找到PutMestick计划，开始执行")
        except Exception as e:
            logger.error(f"无法获取计划列表: {e}")
            return 1999
        
        while True:
            try:
                # 设置全局变量
                robot.SetGlobalVariables({"WorkServerMestick": WorkServerMestick})
                logger.info(f"设置WorkServerMestick = {WorkServerMestick}")

                robot.SetGlobalVariables({"PalletNum": PalletNum})
                logger.info(f"设置PalletNum = {PalletNum}")

                robot.SetGlobalVariables({"PhotoNum": PhotoNum})
                logger.info(f"设置PhotoNum = {PhotoNum}")

                # 执行计划
                logger.info("开始执行PutMestick计划...")
                robot.ExecutePlan("PutMestick", True)
                
                # 等待执行完成
                while robot.busy():
                    logger.info("PutMestick 执行中...")
                    sleep(1)  # 等待1秒再检查
                
                # 获取反馈
                global_vars = robot.global_variables()
                feedback = global_vars.get("WorkFeedBack", -1)
                
                try_put_num += 1
                logger.info(f"PutMestick 第 {try_put_num} 次尝试，反馈值: {feedback}")
                
            except Exception as e:
                logger.error(f"执行PutMestick计划时发生异常: {e}")
                return 1999
            
            if feedback == 201:  # 拍照失败
                try_photo_num += 1
                if try_photo_num > max_retries:
                    logger.error(f"拍照失败，已重试 {max_retries} 次，放弃操作")
                    # 启动连续音频报警 - 拍照失败
                    alarm_manager = get_audio_alarm_manager()
                    alarm_manager.start_continuous_alarm(3, "put_photo_failed", interval=5.0, audio_duration=3.0, logger=logger)
                    return 201
                logger.warning(f"拍照失败，进行第 {try_photo_num} 次重试")
                continue
              
            elif feedback == 202:  # 放料失败
                logger.error("放内存条失败，放弃操作")
                # 启动连续音频报警 - 放料失败
                alarm_manager = get_audio_alarm_manager()
                alarm_manager.start_continuous_alarm(2, "put_failed", interval=6.0, audio_duration=4.0, logger=logger)
                return 202
                
            elif feedback == 203:  # 未放过料无法取料
                logger.error("未放过料，无法执行取内存条操作")
                return 203
            
            elif feedback == 20:  # 成功
                logger.info("放内存条操作成功完成")
                return 20

            else:
                logger.error(f"未知反馈值: {feedback}")
                if try_put_num > max_retries:
                    return feedback
                continue
                
    except Exception as e:
        logger.error(f"PutMestick 执行异常: {e}")
        return 1999