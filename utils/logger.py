import spdlog

def get_logger(name="RobotLogger"):
    """
    创建并返回一个控制台日志记录器
    
    Args:
        name: 日志记录器名称，默认为"RobotLogger"
        
    Returns:
        logger: spdlog控制台日志记录器实例
    """
    return spdlog.ConsoleLogger(name)