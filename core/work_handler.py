def handle_work_step(step_func, robot, logger, expected_values: list[int], step_name: str) -> bool:
    """
    通用工作步骤处理器，提供统一的执行、日志记录和错误处理
    
    Args:
        step_func: 要执行的函数
        robot: 机器人对象
        logger: 日志记录器
        expected_values: 期望的返回值列表
        step_name: 步骤名称（用于日志）
        
    Returns:
        bool: 执行成功返回True，失败返回False
    """
    try:
        logger.info(f"开始执行步骤: {step_name}")
        result = step_func(robot, logger)
        logger.info(f"{step_name} 返回值: {result}")
        
        if result in expected_values:
            logger.info(f"{step_name} 执行成功")
            return True
        else:
            logger.error(f"{step_name} 执行失败，返回值 {result} 不在期望范围 {expected_values} 内")
            return False
            
    except Exception as e:
        logger.error(f"{step_name} 执行异常: {e}")
        return False
    


# def Put_mestick(robot, logger,expected_values: list[int], step_name: str,WorkServerMestick: int) -> bool:
#     """
#     执行放内存条操作，包含重试机制
    
#     Args:
#         robot: 机器人对象
#         logger: 日志记录器
#         WorkServerMestick: 工作服务器内存条状态
        
#     Returns:
#         int: 操作结果
#              20 - 成功
#              201 - 拍照失败（重试3次后仍失败）
#              202 - 放料失败（重试3次后仍失败）
#              203 - 未放过料无法取料
#              1999 - 系统异常
#     """
#     try:
#         try_photo_num = 0
#         max_retries = 3
        
#         logger.info("开始执行放内存条操作")
        
#         while True:
#             robot.ExecutePlan("PutMestick", True)
            
#             while robot.busy():
#                 logger.info("PutMestick 执行中 ...")
            
#             global_vars = robot.global_variables()
#             robot.SetGlobalVariables({"WorkServerMestick": WorkServerMestick})
#             feedback = global_vars.get("WorkFeedBack", -1)
            
#             try_pick_num += 1
#             logger.info(f"PutMestick 第 {try_pick_num} 次尝试，反馈值: {feedback}")
            
#             if feedback == 201:  # 拍照失败
#                 try_photo_num += 1
#                 if try_photo_num > max_retries:
#                     logger.error(f"拍照失败，已重试 {max_retries} 次，放弃操作")
#                     return 201
#                 logger.warn(f"拍照失败，进行第 {try_photo_num} 次重试")
#                 continue
              
#             elif feedback == 202:  # 放料失败
#                 logger.error(f"放内存条失败，放弃操作")
#                 return 202
                
#             elif feedback == 203:  # 未放过料无法取料
#                 logger.error("未放过料，无法执行取内存条操作")
#                 return 203
            
#             elif feedback == 20:  # 成功
#                 logger.info("放内存条操作成功完成")
#                 return 20

#             else:
#                 logger.error(f"未知反馈值: {feedback}")
#                 if try_pick_num > max_retries:
#                     return feedback
#                 continue
                
#     except Exception as e:
#         logger
