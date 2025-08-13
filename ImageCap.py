import socket

# 全局变量
generated_data = []
current_index = 0

def get_user_config():
    """从用户输入获取配置参数（可回车使用默认值）"""
    def get_value(prompt, default):
        val = input(f"{prompt} (默认 {default}): ").strip()
        return int(val) if val else default

    print("\n🛠 请设置新的数据参数：")
    step_pos = get_value("位置步长（X/Y）", 5)
    step_rot = get_value("姿态步长（RX/RY/RZ）", 1)
    count = get_value("每个方向的步数（±）", 3)

    return step_pos, step_rot, count

def get_server_config():
    """获取服务器配置参数"""
    def get_str_value(prompt, default):
        val = input(f"{prompt} (默认 {default}): ").strip()
        return val if val else default
    
    def get_int_value(prompt, default):
        val = input(f"{prompt} (默认 {default}): ").strip()
        return int(val) if val else default

    print("\n🌐 请设置服务器参数：")
    host = get_str_value("监听IP地址", "0.0.0.0")
    port = get_int_value("监听端口", 9000)

    return host, port

def generate_data_fixed_format(step_pos, step_rot, count):
    """生成 X,Y,RX,RY,RZ,1 格式的数据"""
    sequence = []
    dim = 5  # X, Y, RX, RY, RZ

    # X, Y 变化
    for axis in [0, 1]:  # X, Y
        for sign in [1, -1]:
            for i in range(1, count + 1):
                pt = [0] * dim
                pt[axis] = sign * step_pos * i
                pt.append(1)
                sequence.append(pt)

    # RX, RY, RZ 变化
    for axis in [2, 3, 4]:  # RX, RY, RZ
        for sign in [1, -1]:
            for i in range(1, count + 1):
                pt = [0] * dim
                pt[axis] = sign * step_rot * i
                pt.append(1)
                sequence.append(pt)

    return sequence

def get_next_data():
    global current_index, generated_data

    if not generated_data or current_index >= len(generated_data):
        print("✅ 所有数据已发送完毕。")
        step_pos, step_rot, count = get_user_config()
        generated_data.clear()
        generated_data.extend(generate_data_fixed_format(step_pos, step_rot, count))
        current_index = 0
        print(f"✅ 已生成 {len(generated_data)} 条新数据")

    pt = generated_data[current_index]
    current_index += 1
    return ','.join(str(v) for v in pt) + '\r\n'

def start_server():
    global generated_data

    # 服务器配置
    host, port = get_server_config()
    
    # 首次用户输入
    step_pos, step_rot, count = get_user_config()
    generated_data = generate_data_fixed_format(step_pos, step_rot, count)
    print(f"✅ 初始生成 {len(generated_data)} 条数据")

    # 启动 TCP 服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"✅ 服务端启动成功，监听 {host}:{port}...")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"📥 客户端已连接：{addr}")

            try:
                while True:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    print(f"📨 收到数据: {data}")

                    if b'S' in data:
                        response = get_next_data()
                        client_socket.sendall(response.encode('utf-8'))
                        print(f"📤 发送数据: {response.strip()}")
            except Exception as e:
                print(f"⚠️ 通信异常: {e}")
                client_socket.close()
                print("🔌 客户端已断开连接")

    except KeyboardInterrupt:
        print("\n🛑 服务端手动关闭")
    finally:
        server_socket.close()

if __name__ == '__main__':
    start_server()
