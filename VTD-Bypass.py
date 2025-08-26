import leechcorepyc
import struct
import binascii
import json
import time
import os
import mmap
import sys
import tempfile
import traceback
import logging
from cryptography.fernet import Fernet


# ================= DMAR表配置 =================
DEFAULT_DMAR_ADDRESS = "0x749b5000"
DMAR_CONTENT_HEX = "444D415250000000013F494E54454C2045444B322020202002000000494E544C1707202026030000000000000000000000002000010000000010D9FE000000000308000002001E070408000000001E06"

def init_leechcore_with_retry():
    """初始化LeechCore连接，失败时最多重连20次"""
    max_attempts = 20
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"初始化LeechCore连接... (尝试 {attempt}/{max_attempts})")
            lc = leechcorepyc.LeechCore("fpga")
            print("成功初始化LeechCore连接")
            return lc
        except Exception as e:
            print(f"LeechCore连接失败: {e}")
            lc.close()
            if attempt < max_attempts:
                print("等待1秒后重试...")
                time.sleep(1)
            else:
                print(f"已达到最大重试次数 ({max_attempts})，连接失败")
                raise e

def 获取DMAR表地址():
    """获取用户输入的DMAR表地址，默认值为0x749b4000"""
    #print(f"默认DMAR表地址: {DEFAULT_DMAR_ADDRESS}")
    使用默认 = input("是否使用默认DMAR表地址? (y/n): ").lower()
    
    if 使用默认 in ['y', 'yes', '是', '']:
        return DEFAULT_DMAR_ADDRESS
    
    while True:
        dmar_address = input("请输入DMAR表地址 (格式: 0xXXXXXXXX): ").strip()
        if dmar_address:
            # 验证地址格式
            try:
                if dmar_address.startswith('0x'):
                    int(dmar_address, 16)
                    return dmar_address
                else:
                    print("地址格式错误，请使用0x开头的十六进制格式")
            except ValueError:
                print("地址格式错误，请输入有效的十六进制地址")
        else:
            print("地址不能为空，请重新输入")

def get_config_path(filename):
    """获取C盘根目录下的配置文件路径"""
    return f"C:\\{filename}"

def save_config(config_data, filename="mod.config"):
    """加密保存配置到C盘根目录"""
    fernet = Fernet(CONFIG_KEY)
    data = json.dumps(config_data, ensure_ascii=False, indent=2).encode('utf-8')
    encrypted = fernet.encrypt(data)
    path = get_config_path(filename)
    with open(path, 'wb') as f:
        f.write(encrypted)
    print(f"配置已保存")

def load_config(filename="mod.config"):
    """从C盘根目录加载并解密配置文件"""
    fernet = Fernet(CONFIG_KEY)
    path = get_config_path(filename)
    try:
        with open(path, 'rb') as f:
            encrypted = f.read()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"加载配置文件失败: 未找到文件或解密失败")
        return None

def load_config_from_path(file_path):
    """从指定路径加载并解密配置文件"""
    fernet = Fernet(CONFIG_KEY)
    try:
        with open(file_path, 'rb') as f:
            encrypted = f.read()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"加载配置文件失败: 未找到文件或解密失败")
        return None

def dump_memory_region(lc, start_addr, end_addr, dump_file="memory_region.bin"):
    """将指定内存区域转储到文件"""
    size = end_addr - start_addr
    #print(f"开始转储内存区域 0x{start_addr:X} - 0x{end_addr:X} (大小: {size/(1024*1024):.2f} MB)")
    
    # 检查文件是否已存在
    if os.path.exists(dump_file):
        response = input(f"文件 {dump_file} 已存在，是否覆盖? (y/n): ")
        if response.lower() != 'y':
            print("使用现有转储文件")
            return True
    
    # 使用分块读取以处理大内存区域
    chunk_size = 10 * 1024 * 1024  # 10MB 块
    total_chunks = (size + chunk_size - 1) // chunk_size
    
    start_time = time.time()
    
    try:
        with open(dump_file, 'wb') as f:
            for i in range(total_chunks):
                chunk_start = start_addr + i * chunk_size
                chunk_end = min(chunk_start + chunk_size, end_addr)
                chunk_size_actual = chunk_end - chunk_start
                
                print(f"读取块 {i+1}/{total_chunks} (0x{chunk_start:X} - 0x{chunk_end:X})")
                try:
                    chunk_data = lc.read(chunk_start, chunk_size_actual)
                    f.write(chunk_data)
                    
                    # 显示进度
                    progress = (i + 1) / total_chunks * 100
                    elapsed = time.time() - start_time
                    rate = ((i + 1) * chunk_size) / (1024 * 1024 * elapsed) if elapsed > 0 else 0
                    print(f"进度: {progress:.1f}% (速率: {rate:.2f} MB/s)")
                    
                except Exception as e:
                    print(f"读取块失败: {e}")
                    # 写入零填充数据以保持文件大小一致
                    f.write(b'\x00' * chunk_size_actual)
        
        print(f"内存转储完成，用时: {time.time() - start_time:.2f}秒")
       # print(f"转储文件保存为: {os.path.abspath(dump_file)}")
        return True
    
    except Exception as e:
        print(f"转储内存失败: {e}")
        return False

def search_in_dump(dump_file, signature):
    """在内存转储文件中搜索签名"""
    print(f"在转储文件中搜索签名 '{signature}'")
    start_time = time.time()
    
    try:
        # 获取文件大小
        file_size = os.path.getsize(dump_file)
        print(f"转储文件大小: {file_size/(1024*1024):.2f} MB")
        
        # 使用内存映射搜索
        with open(dump_file, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                print("开始搜索...")
                
                # 查找所有匹配项
                matches = []
                offset = 0
                
                while True:
                    pos = mm.find(signature, offset)
                    if pos == -1:
                        break
                    
                    matches.append(pos)
                    offset = pos + 1
                
                search_time = time.time() - start_time
                print(f"搜索完成，用时: {search_time:.2f}秒")
                
                if matches:
                    print(f"找到 {len(matches)} 个匹配项:")
                    for i, pos in enumerate(matches):
                        print(f"{i+1}. 文件偏移: 0x{pos:X}")
                    return matches
                else:
                    print("未找到匹配项")
                    return []
    
    except Exception as e:
        print(f"搜索失败: {e}")
        return []

def read_table_from_dump(dump_file, offset, length=None):
    """从转储文件中读取表数据"""
    try:
        with open(dump_file, 'rb') as f:
            f.seek(offset)
            
            # 如果未指定长度，先读取表头获取长度
            if length is None:
                header = f.read(8)
                _, table_length = struct.unpack("<4sI", header)
                f.seek(offset)  # 重新定位到表开始
                data = f.read(table_length)
            else:
                data = f.read(length)
            
            return data
    except Exception as e:
        print(f"从转储文件读取数据失败: {e}")
        return None

def calculate_checksum(data):
    """计算ACPI表校验和"""
    return (0x100 - sum(data) & 0xFF) & 0xFF

def update_table_checksum(table_data):
    """更新表的校验和字段"""
    # 清除原校验和字段
    table_list = bytearray(table_data)
    table_list[9] = 0  # 校验和字段位于偏移量9处
    
    # 计算新校验和
    checksum = calculate_checksum(table_list)
    
    # 更新校验和字段
    table_list[9] = checksum
    
    return bytes(table_list)

def verify_memory(lc, address, expected_data):
    """验证内存中的数据是否与预期一致"""
    try:
        actual_data = lc.read(address, len(expected_data))
        if actual_data == expected_data:
            print(f"验证成功: 地址 0x{address:X} 的数据与预期一致")
            return True
        else:
            print(f"验证失败: 地址 0x{address:X} 的数据与预期不一致")
            # 显示不一致的字节
            mismatch_count = 0
            for i in range(min(len(actual_data), len(expected_data))):
                if actual_data[i] != expected_data[i]:
                    mismatch_count += 1
                    if mismatch_count <= 10:  # 只显示前10个不匹配
                        print(f"  偏移 {i}: 实际={actual_data[i]:02X}, 预期={expected_data[i]:02X}")
            
            if mismatch_count > 10:
                print(f"  ... 还有 {mismatch_count-10} 个不匹配的字节")
                
            return False
    except Exception as e:
        print(f"读取内存失败: {e}")
        return False

def read_and_modify_xsdt():
    """读取VT-d关闭状态的XSDT表，自动修改并插入DMAR表基址"""
    print("===== 读取并修改VT-d关闭状态的ACPI表 =====")
    print("请确保已关闭VT-d功能并进入正常系统")
    
    # 询问是否手动输入地址
    print("\n=== 地址输入选项 ===")
    手动输入dmar = input("是否手动输入DMAR表地址? (y/n): ").lower()
    if 手动输入dmar in ['y', 'yes', '是']:
        while True:
            dmar_address = input("请输入DMAR表地址 (格式: 0xXXXXXXXX): ").strip()
            if dmar_address:
                try:
                    if dmar_address.startswith('0x'):
                        int(dmar_address, 16)
                        break
                    else:
                        print("地址格式错误，请使用0x开头的十六进制格式")
                except ValueError:
                    print("地址格式错误，请输入有效的十六进制地址")
            else:
                print("地址不能为空，请重新输入")
    else:
        dmar_address = DEFAULT_DMAR_ADDRESS
    
    手动输入xsdt = input("是否手动输入XSDT表地址? (y/n): ").lower()
    if 手动输入xsdt in ['y', 'yes', '是']:
        while True:
            xsdt_addr_input = input("请输入XSDT表物理地址 (格式: 0xXXXXXXXX): ").strip()
            try:
                if xsdt_addr_input.startswith('0x'):
                    xsdt_addr = int(xsdt_addr_input, 16)
                    break
                else:
                    print("地址格式错误，请使用0x开头的十六进制格式")
            except ValueError:
                print("地址格式错误，请输入有效的十六进制地址")
    else:
        xsdt_addr = None  # 需要从转储文件中搜索
    
    # 存储配置信息
    config = {
        "vtd_mode": "disable",
        "xsdt_address": None,
        "xsdt_content_hex": None,
        "dmar_address": dmar_address,
        "dmar_content_hex": DMAR_CONTENT_HEX
    }
    
    try:
        # 初始化LeechCore连接（支持无限重连）
        lc = init_leechcore_with_retry()
        
        # 如果XSDT地址未手动输入，需要转储内存进行搜索
        if xsdt_addr is None:
            # 定义内存区域
            start_addr = 0x70000000
            end_addr = 0x80000000
            dump_file = "memory_region_disable.bin"
            
            # 转储内存区域
            if not dump_memory_region(lc, start_addr, end_addr, dump_file):
                print("内存转储失败，无法继续")
                lc.close()
                return 1
            
            # 在转储文件中搜索XSDT
            print("\n开始在转储文件中搜索XSDT...")
            xsdt_offsets = search_in_dump(dump_file, b'XSDT')
            
            if not xsdt_offsets:
                print("未找到XSDT，无法继续")
                lc.close()
                return 1
            
            # 如果找到多个XSDT，让用户选择
            if len(xsdt_offsets) > 1:
                print("找到多个XSDT，请选择，通常是第二个:")
                for i, offset in enumerate(xsdt_offsets):
                    print(f"{i+1}. 偏移: 0x{offset:X}")
                selection = input(f"请选择 (1-{len(xsdt_offsets)}): ")
                try:
                    selected_index = int(selection) - 1
                    xsdt_offset = xsdt_offsets[selected_index]
                except:
                    print("无效选择，使用第一个匹配项")
                    xsdt_offset = xsdt_offsets[0]
            else:
                xsdt_offset = xsdt_offsets[0]
            
            # 计算实际物理地址
            xsdt_addr = start_addr + xsdt_offset
            print(f"选择的XSDT偏移: 0x{xsdt_offset:X}, 物理地址: 0x{xsdt_addr:X}")
        
        config["xsdt_address"] = hex(xsdt_addr)
        
        # 处理XSDT表
        try:
            if xsdt_addr is not None and 手动输入xsdt in ['y', 'yes', '是']:
                # 直接从主机内存读取XSDT表头
                print(f"直接从主机内存读取XSDT表 - 地址: 0x{xsdt_addr:X}")
                xsdt_header = lc.read(xsdt_addr, 36)
            else:
                # 从转储文件读取XSDT表头
                xsdt_offset = xsdt_addr - start_addr
                xsdt_header = read_table_from_dump(dump_file, xsdt_offset, 36)
            
            signature = xsdt_header[:4]
            if signature != b'XSDT':
                print(f"警告: XSDT签名无效: {signature}")
                print("尝试继续处理...")
            
            length = struct.unpack("<I", xsdt_header[4:8])[0]
            print(f"原始XSDT长度: {length}")
            
            # 检查长度是否合理
            if length < 36 or length > 0x10000:
                print(f"警告: XSDT长度异常: {length}，使用默认值")
                length = 256  # 使用一个合理的默认值
            
            # 读取完整XSDT表
            if xsdt_addr is not None and 手动输入xsdt in ['y', 'yes', '是']:
                # 直接从主机内存读取
                xsdt_full = lc.read(xsdt_addr, length)
            else:
                # 从转储文件读取
                xsdt_full = read_table_from_dump(dump_file, xsdt_offset, length)
            
            # 计算XSDT中的条目数
            entry_count = (length - 36) // 8
            print(f"原始XSDT条目数: {entry_count}")
            
            # 打印原始XSDT表的十六进制表示
            print("\n原始XSDT表内容:")
            for i in range(0, min(len(xsdt_full), 128), 16):  # 只显示前128字节
                hex_line = ' '.join(f"{b:02X}" for b in xsdt_full[i:i+16])
                ascii_line = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in xsdt_full[i:i+16])
                print(f"{i:04X}: {hex_line:<48} {ascii_line}")
            
            # 3. 修改XSDT表，在表尾插入DMAR表基址
            print("\n开始修复XSDT表...")
            dmar_addr = int(dmar_address, 16)
            
            # 创建新的XSDT表
            xsdt_list = bytearray(xsdt_full)
            
            # 在表尾追加DMAR表基址
            xsdt_list.extend(struct.pack("<Q", dmar_addr))
            
            # 更新长度字段
            new_length = len(xsdt_list)
            xsdt_list[4:8] = struct.pack("<I", new_length)
            
            # 更新校验和
            xsdt_list[9] = 0  # 清除原校验和
            checksum = calculate_checksum(xsdt_list)
            xsdt_list[9] = checksum
            
            # 转换为bytes
            modified_xsdt = bytes(xsdt_list)
            
            print(f"修改后XSDT长度: {new_length}")
            print(f"新增条目数: 1 (DMAR表)")
          #  print(f"新校验和: 0x{checksum:02X}")
            
            # 打印修改后的XSDT表
          #  print("\n修改后的XSDT表内容:")
            for i in range(0, min(len(modified_xsdt), 128), 16):  # 只显示前128字节
                hex_line = ' '.join(f"{b:02X}" for b in modified_xsdt[i:i+16])
                ascii_line = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in modified_xsdt[i:i+16])
                print(f"{i:04X}: {hex_line:<48} {ascii_line}")
            
            # 保存修改后的XSDT表内容到配置
            xsdt_hex = binascii.hexlify(modified_xsdt).decode('utf-8').upper()
            config["xsdt_content_hex"] = xsdt_hex
            
            # 4. 保存配置到mod.config
            save_config(config, "mod.config")
            #print(f"\n配置已保存到 mod.config")
            print(f"XSDT地址: 0x{xsdt_addr:X}")
            print(f"DMAR地址: 0x{dmar_addr:X}")
            print(f"修改后的XSDT表大小: {len(modified_xsdt)} 字节")
            print(f"DMAR表大小: {len(DMAR_CONTENT_HEX)//2} 字节")
                
        except Exception as e:
            print(f"处理XSDT表失败: {e}")
            save_config(config, "mod.config")
        
        # 关闭连接以释放资源
        lc.close()
        print("已关闭LeechCore连接")
        print(f"\n读取并修改VT-d关闭状态ACPI表完成！")
        
    except Exception as e:
        print(f"错误: {e}")       
        # 确保关闭连接
        try:
            lc.close()
        except:
            pass
        
        return 1
    
    return 0


def write_acpi_tables():
    """写入ACPI表函数，从mod.config读取数据"""
    try:
        # 加载mod.config
        config = load_config("mod.config")
        if not config:
            print("未找到mod.config配置文件，请先运行'创建修改后的配置文件'选项")
            return 1
        
        # 获取地址和内容
        xsdt_addr = int(config.get("xsdt_address", "0x0"), 16)
        dmar_addr = int(config.get("dmar_address", "0x0"), 16)
        dmar_content_hex = config.get("dmar_content_hex", "")
        xsdt_content_hex = config.get("xsdt_content_hex", "")
        
        if xsdt_addr == 0 or dmar_addr == 0 or not dmar_content_hex or not xsdt_content_hex:
            print("配置文件中缺少必要信息")
            return 1
        
        print(f"XSDT地址: 0x{xsdt_addr:X}")
        print(f"DMAR地址: 0x{dmar_addr:X}")
        print(f"XSDT内容长度: {len(xsdt_content_hex)//2} 字节")
        print(f"DMAR内容长度: {len(dmar_content_hex)//2} 字节")
        
        # 准备数据
        xsdt_data = binascii.unhexlify(xsdt_content_hex)
        dmar_data = binascii.unhexlify(dmar_content_hex)
        
        # 执行写入操作
        print("\n开始执行写入操作...")
        
        # 写入次数
        write_count = 10
        
        for attempt in range(write_count):
            print(f"\n===== 写入尝试 #{attempt+1}/{write_count} =====")
            
            # 尝试初始化连接（支持无限重连）
            try:
                lc = init_leechcore_with_retry()
                
                # 首先写入XSDT表
                try:
                    print(f"写入XSDT表 - 地址: 0x{xsdt_addr:X}, 大小: {len(xsdt_data)} 字节")
                    lc.write(xsdt_addr, xsdt_data)
                    print("XSDT表写入完成")
                    
                    # 验证XSDT写入
                    verify_xsdt = verify_memory(lc, xsdt_addr, xsdt_data)
                    if not verify_xsdt:
                        print("XSDT表验证失败，跳过DMAR表写入")
                        continue
                    
                    # 然后写入DMAR表
                    print(f"写入DMAR表 - 地址: 0x{dmar_addr:X}, 大小: {len(dmar_data)} 字节")
                    lc.write(dmar_addr, dmar_data)
                    print("DMAR表写入完成")
                    
                    # 验证DMAR写入
                    verify_dmar = verify_memory(lc, dmar_addr, dmar_data)
                    if verify_dmar:
                        print("DMAR表验证成功")
                    else:
                        print("DMAR表验证失败")
                    
                except Exception as e:
                    print(f"写入表数据失败: {e}")
                
                # 关闭连接
                lc.close()
                print("已关闭LeechCore连接")
                
            except Exception as e:
                print(f"连接初始化失败: {e}")
            
            # 等待下一次尝试
            if attempt < write_count - 1:
                print(f"等待1秒后进行下一次尝试...")
                time.sleep(1)
        
        print("\n所有写入尝试已完成")
        return 0
        
    except Exception as e:
        print(f"发生错误: {e}")
        return 1

def load_dingzhi_config():
    """从dingzhi.config文件读取DMAR表和基址信息"""
    print("===== 定制dmar表加载配置 =====")
    
    # 从C盘根目录查找dingzhi.config文件
    dingzhi_path = "C:\\dingzhi.config"
    if not os.path.exists(dingzhi_path):
        print(f"未找到dingzhi.config文件: {dingzhi_path}")
        print("请确保dingzhi.config文件位于C盘根目录")
        return 1
    
    try:
        # 加载并解密dingzhi.config
        dingzhi_config = load_config_from_path(dingzhi_path)
        if not dingzhi_config:
            print("dingzhi.config文件解密失败或格式错误")
            return 1
        
        # 检查必要字段
        dmar_address = dingzhi_config.get("dmar_address")
        dmar_content_hex = dingzhi_config.get("dmar_content_hex")
        
        if not dmar_address or not dmar_content_hex:
            print("dingzhi.config文件中缺少dmar_address或dmar_content_hex字段")
            return 1
        
        print(f"从dingzhi.config读取")
       # print(f"DMAR地址: {dmar_address}")
        #print(f"DMAR内容长度: {len(dmar_content_hex)//2} 字节")
        
        # 检查是否已有mod.config文件
        existing_config = load_config("mod.config")
        if existing_config:
            # 保留现有的XSDT信息
            config = {
                "vtd_mode": "custom",
                "xsdt_address": existing_config.get("xsdt_address"),
                "xsdt_content_hex": existing_config.get("xsdt_content_hex"),
                "dmar_address": dmar_address,
                "dmar_content_hex": dmar_content_hex
            }
            print("已保留现有的XSDT表信息")
        else:
            # 创建新的配置
            config = {
                "vtd_mode": "custom",
                "xsdt_address": None,  # 这个需要从实际系统中读取
                "xsdt_content_hex": None,  # 这个需要从实际系统中读取
                "dmar_address": dmar_address,
                "dmar_content_hex": dmar_content_hex
            }
            print("注意: XSDT表信息需要从实际系统中读取，请运行选项1来获取")
        
        # 保存到mod.config
        save_config(config, "mod.config")
        print("配置已保存到config文件")
        
        return 0
        
    except Exception as e:
        print(f"处理dingzhi.config文件时发生错误: {e}")
        return 1

def main():
    print("===== VTD-Bypass =====")

    # 验证登录
    if not 单码操作示例():
        print("登录失败，程序退出。")
        return

    try:
        while True:
            print("\n===== VTD-Bypass =====")
            print("1. 读取VT-d关闭状态的表")
            print("2. 写入VTD-Bypass")
            print("3. 调试模式")
            print("0. 退出")
            
            choice = input("\n请选择操作 (0-3): ")
            
            if choice == "1":  
                read_and_modify_xsdt()
            elif choice == "2":
                print("\n===== 写入VTD-Bypass =====")
                print("\n" + "="*60 + "")
                print("\n" + "  重要提示 方法一 " + "")
                print("\n" + "请确保主机完全关机，然后再按下回车" + "")
                print("\n" + "请确保主机完全关机，然后再按下回车" + "")
                print("\n" + "请确保主机完全关机，然后再按下回车" + "")
                print("\n" + "  重要提示 " + "")
                print("\n" + "="*60 + "")
                print("\n" + "="*60 + "")
                print("\n" + "  重要提示 方法二 " + "")
                print("\n" + "主机按下开机键盘后等待2~3秒，然后再按下回车" + "")
                print("\n" + "主机按下开机键盘后等待2~3秒，然后再按下回车" + "")
                print("\n" + "主机按下开机键盘后等待2~3秒，然后再按下回车" + "")
                print("\n" + "  重要提示 " + "")
                print("\n" + "="*60 + "")
                confirm = input("\n是否继续? (Y/n): ")
                if confirm.lower() in ['y', 'yes', '']:
                    write_acpi_tables()
                else:
                    print("操作已取消")
            elif choice == "3":
                load_dingzhi_config()
            elif choice == "0":
                print("程序已退出")
                break
            else:
                print("无效选择，请重新输入")
              
if __name__ == "__main__":
    main()

