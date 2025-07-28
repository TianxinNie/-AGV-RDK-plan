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
        Exception: 当错误无法清除时抛出异常
    """
    robot = flexivrdk.Robot(robot_sn)
    
    if robot.fault():
        logger.warn("检测到机器人错误，正在尝试清除 ...")
        if not robot.ClearFault():
            raise Exception("错误无法清除")
    
    robot.Enable()
    
    while not robot.operational():
        time.sleep(1)
    
    robot.SwitchMode(flexivrdk.Mode.NRT_PLAN_EXECUTION)
    logger.info("机器人初始化完成")
    
    return robot