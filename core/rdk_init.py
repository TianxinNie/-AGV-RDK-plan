import flexivrdk
import time

def init_robot(robot_sn, logger):
    """
    初始化Flexiv机器人连接
    
    Args:
        robot_sn: 机器人序列号
        logger: 日志记录器
        
    Returns:
        robot: 已初始化的机器人对象
        
    Raises:
        Exception: 当初始化失败时抛出异常
    """
    try:
        logger.info(f"正在创建机器人连接，序列号: {robot_sn}")
        robot = flexivrdk.Robot(robot_sn)
        
        # 检查机器人故障状态
        if robot.fault():
            logger.warn("检测到机器人错误，正在尝试清除...")
            if not robot.ClearFault():
                raise Exception("机器人错误无法清除，请检查机器人状态")
            logger.info("机器人错误已清除")
        
        # 启用机器人
        logger.info("正在启用机器人...")
        robot.Enable()
        
        # 等待机器人进入操作状态
        logger.info("等待机器人进入操作状态...")
        timeout = 30  # 30秒超时
        start_time = time.time()
        
        while not robot.operational():
            if time.time() - start_time > timeout:
                raise Exception("机器人初始化超时，未能进入操作状态")
            time.sleep(1)
            logger.info("机器人仍在初始化中...")
        
        # 切换到计划执行模式
        logger.info("切换到计划执行模式...")
        robot.SwitchMode(flexivrdk.Mode.NRT_PLAN_EXECUTION)
        
        # 等待模式切换完成
        time.sleep(2)
        
        # 验证当前模式
        current_mode = robot.mode()
        logger.info(f"机器人当前模式: {current_mode}")
        
        logger.info("✅ 机器人初始化完成")
        return robot
        
    except Exception as e:
        logger.error(f"机器人初始化失败: {e}")
        logger.error("请检查:")
        logger.error("1. 机器人是否正确开机")
        logger.error("2. 网络连接是否正常")
        logger.error("3. 机器人序列号是否正确")
        logger.error("4. 机器人RDK服务是否运行")
        logger.error("5. 机器人是否存在硬件故障")
        raise