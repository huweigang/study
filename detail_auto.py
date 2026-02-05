import pyautogui
import time
import random
import os
import cv2
import numpy as np
from PIL import Image, ImageGrab
import threading
from queue import Queue
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import keyboard  # 用于监听按键事件


@dataclass
class ClickRecord:
    """点击记录数据类"""
    timestamp: float
    x: int
    y: int
    screenshot: Optional[np.ndarray] = None
    screenshot_path: Optional[str] = None
    grid_x: Optional[int] = None  # 网格X坐标
    grid_y: Optional[int] = None  # 网格Y坐标


class LianLianKanAutomator:
    """连连看自动化控制器"""

    def __init__(self, game_region=(0, 0, 450, 550)):
        """
        初始化

        Args:
            game_region: 游戏区域 (left, top, width, height)
        """
        self.game_region = game_region
        self.records: List[ClickRecord] = []
        self.is_running = False
        self.is_paused = False
        self.save_dir = "lianliankan_records"
        self.grid_size = None  # 网格大小
        self.grid_rows = None  # 网格行数
        self.grid_cols = None  # 网格列数

        # 创建保存目录
        os.makedirs(self.save_dir, exist_ok=True)

        # 设置安全参数
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

        print(f"游戏区域: {game_region}")
        print(f"保存目录: {self.save_dir}")

    def detect_grid_layout(self):
        """检测连连看网格布局"""
        # 方法1：通过点击多个位置来探测网格
        self.grid_rows = 8  # 常见的连连看行数
        self.grid_cols = 10  # 常见的连连看列数

        # 计算网格大小
        grid_width = self.game_region[2] / self.grid_cols
        grid_height = self.game_region[3] / self.grid_rows

        self.grid_size = (int(grid_width), int(grid_height))

        print(f"检测到网格布局: {self.grid_cols}x{self.grid_rows}")
        print(f"网格大小: {self.grid_size}")

        return self.grid_rows, self.grid_cols

    def detect_red_blocks(self):
        """检测游戏区域内的红色块"""
        if self.grid_size is None:
            self.detect_grid_layout()

        # 直接截取整个游戏区域
        screenshot = pyautogui.screenshot(region=self.game_region)
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # 定义红色的HSV范围
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])

        # 将BGR转换为HSV
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)

        # 创建红色掩码
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # 查找轮廓
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        red_block_positions = []

        for contour in contours:
            area = cv2.contourArea(contour)
            # 过滤掉太小的区域（可能是噪声）
            if area > 100:  # 最小面积阈值
                # 计算轮廓的边界框
                x, y, w, h = cv2.boundingRect(contour)

                # 将坐标转换为相对于屏幕的绝对坐标
                abs_x = self.game_region[0] + x
                abs_y = self.game_region[1] + y

                # 计算中心点坐标（相对于屏幕）
                center_x = abs_x + w // 2
                center_y = abs_y + h // 2

                # 计算所在的网格行列
                grid_col = int((center_x - self.game_region[0]) / self.grid_size[0])
                grid_row = int((center_y - self.game_region[1]) / self.grid_size[1])

                # 确保网格坐标在有效范围内
                if 0 <= grid_row < self.grid_rows and 0 <= grid_col < self.grid_cols:
                    red_block_positions.append({
                        'abs_position': (center_x, center_y),
                        'grid_position': (grid_row, grid_col),
                        'area': area,
                        'bbox': (abs_x, abs_y, w, h)
                    })

                    print(f"发现红色块: 网格({grid_row}, {grid_col}), 坐标({center_x}, {center_y}), 面积: {area}")

        print(f"总共检测到 {len(red_block_positions)} 个红色块")
        return red_block_positions

    def auto_play_red_blocks(self):
        """自动点击检测到的红色块"""
        print("开始自动识别并点击红色块...")

        # 检测红色块
        red_blocks = self.detect_red_blocks()

        if not red_blocks:
            print("未检测到任何红色块")
            return

        # 按面积排序，优先点击较大的块（可能更容易识别）
        red_blocks.sort(key=lambda x: x['area'], reverse=True)

        for i, block in enumerate(red_blocks):
            if not self.is_running or self.is_paused:
                break

            print(f"点击第 {i+1}/{len(red_blocks)} 个红色块: {block['abs_position']}")

            # 点击红色块位置
            x, y = block['abs_position']
            self.click_with_record(x, y)

            # 等待一段时间让游戏响应
            time.sleep(0.3)

        print("红色块点击完成")

    def auto_match_and_remove(self, similarity_threshold=0.85):
        """
        自动找相同图片并点击消除
        在 scan_all_grids / auto_red 扫描完成后调用
        """

        if len(self.records) < 2:
            print("记录不足，无法匹配")
            return

        print("开始自动匹配可消除的牌...")

        used = set()

        for i in range(len(self.records)):
            if i in used:
                continue

            r1 = self.records[i]
            if r1.screenshot is None:
                continue

            for j in range(i + 1, len(self.records)):
                if j in used:
                    continue

                r2 = self.records[j]
                if r2.screenshot is None:
                    continue

                sim = self.compare_images(cv2.imread(r1.screenshot_path), cv2.imread(r2.screenshot_path))

                if sim >= similarity_threshold:
                    print(f"找到可消除对: ({r1.grid_x},{r1.grid_y}) <-> ({r2.grid_x},{r2.grid_y}) 相似度:{sim:.2f}")

                    # 点击第一张
                    self.click_with_record(r1.x, r1.y, save_screenshot=False)
                    time.sleep(0.15)

                    # 点击第二张
                    self.click_with_record(r2.x, r2.y, save_screenshot=False)
                    time.sleep(0.3)

                    used.add(i)
                    used.add(j)
                    break

        print("自动消除完成")

    def get_grid_center(self, row: int, col: int) -> Tuple[int, int]:
        """获取网格中心坐标"""
        if self.grid_size is None:
            self.detect_grid_layout()

        grid_width, grid_height = self.grid_size
        center_x = self.game_region[0] + col * grid_width + grid_width // 2
        center_y = self.game_region[1] + row * grid_height + grid_height // 2

        return (int(center_x), int(center_y))

    def get_all_grid_centers(self) -> List[Tuple[int, int]]:
        """获取所有网格中心坐标"""
        centers = []
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                centers.append(self.get_grid_center(row, col))
        return centers

    def take_screenshot(self, x: int, y: int,
                        size: Tuple[int, int] = (60, 60)) -> np.ndarray:
        """
        截取指定位置的图片，确保与原始位置精确对应

        Args:
            x, y: 中心坐标
            size: 截取区域大小 (width, height)
        """
        # 计算截取区域的左上角坐标
        half_width = size[0] // 2
        half_height = size[1] // 2

        left = x - half_width
        top = y - half_height
        width, height = size

        # 确保截取区域在屏幕范围内
        screen_width, screen_height = pyautogui.size()
        left = max(0, left)
        top = max(0, top)
        # 调整尺寸以适应屏幕边界
        width = min(width, screen_width - left)
        height = min(height, screen_height - top)

        # 截取指定区域
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    def save_screenshot(self, screenshot: np.ndarray,
                        prefix: str = "click") -> str:
        """保存截图到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(self.save_dir, filename)

        cv2.imwrite(filepath, screenshot)
        return filepath

    def click_with_record(self, x: int, y: int,
                          save_screenshot: bool = True) -> ClickRecord:
        """
        点击并记录，确保截图位置精确对应

        Args:
            x, y: 点击坐标
            save_screenshot: 是否保存截图
        """
        # 添加随机偏移，使其更自然
        offset_x = random.randint(-2, 2)
        offset_y = random.randint(-2, 2)

        click_x = x + offset_x
        click_y = y + offset_y

        # 移动到目标位置
        pyautogui.moveTo(click_x, click_y, duration=random.uniform(0.1, 0.3))

        # 短暂停顿
        time.sleep(random.uniform(0.05, 0.15))

        # 点击
        pyautogui.click()

        # 等待图片显示（连连看通常需要一点时间显示图片）
        time.sleep(0.3)

        # 截取点击后的图片 - 使用原始坐标，确保位置精确对应
        screenshot = None
        screenshot_path = None
        if save_screenshot:
            # 截取稍大的区域以包含完整图片，使用原始点击坐标为中心
            screenshot = self.take_screenshot(x, y, (80, 80))
            screenshot_path = self.save_screenshot(screenshot)

        # 计算网格坐标
        grid_x, grid_y = None, None
        if self.grid_size:
            grid_width, grid_height = self.grid_size
            grid_x = int((x - self.game_region[0]) / grid_width)
            grid_y = int((y - self.game_region[1]) / grid_height)

        # 创建记录
        record = ClickRecord(
            timestamp=time.time(),
            x=x,  # 使用原始坐标
            y=y,  # 使用原始坐标
            screenshot=screenshot,
            screenshot_path=screenshot_path,
            grid_x=grid_x,
            grid_y=grid_y
        )

        self.records.append(record)
        print(f"点击记录: 位置({x}, {y}), 网格({grid_x}, {grid_y}), 截图: {screenshot_path}")

        return record

    def scan_all_grids(self):
        """扫描所有网格位置"""
        print("开始扫描所有网格...")

        centers = self.get_all_grid_centers()
        total = len(centers)

        for i, (x, y) in enumerate(centers, 1):
            if not self.is_running or self.is_paused:
                break

            print(f"扫描进度: {i}/{total} ({i / total * 100:.1f}%)")

            # 点击并记录
            self.click_with_record(x, y)

            # 随机间隔，防止过快
            time.sleep(random.uniform(0.2, 0.5))

        print("扫描完成!")

    def random_exploration(self, num_clicks: int = 50):
        """随机探索点击"""
        print(f"开始随机探索，计划点击 {num_clicks} 次...")

        for i in range(num_clicks):
            if not self.is_running or self.is_paused:
                break

            # 在游戏区域内随机选择位置
            x = random.randint(
                self.game_region[0] + 20,
                self.game_region[0] + self.game_region[2] - 20
            )
            y = random.randint(
                self.game_region[1] + 20,
                self.game_region[1] + self.game_region[3] - 20
            )

            print(f"随机点击 {i + 1}/{num_clicks}: 位置({x}, {y})")
            self.click_with_record(x, y)

            # 随机间隔
            time.sleep(random.uniform(0.3, 0.8))

    def pattern_exploration(self, pattern: str = "row_by_row"):
        """
        按模式探索

        Args:
            pattern: 探索模式
                - 'row_by_row': 逐行扫描
                - 'col_by_col': 逐列扫描
                - 'spiral': 螺旋扫描
                - 'checkerboard': 跳棋模式
        """
        print(f"按 {pattern} 模式探索...")

        centers = self.get_all_grid_centers()

        if pattern == "row_by_row":
            # 逐行扫描
            pass  # get_all_grid_centers已经按行排序
        elif pattern == "col_by_col":
            # 逐列扫描
            # 需要重新排序centers
            sorted_centers = []
            for col in range(self.grid_cols):
                for row in range(self.grid_rows):
                    sorted_centers.append(self.get_grid_center(row, col))
            centers = sorted_centers
        elif pattern == "checkerboard":
            # 跳棋模式（先点奇数行奇数列，再点偶数行偶数列）
            odd_centers = []
            even_centers = []
            for row in range(self.grid_rows):
                for col in range(self.grid_cols):
                    if (row + col) % 2 == 0:
                        odd_centers.append(self.get_grid_center(row, col))
                    else:
                        even_centers.append(self.get_grid_center(row, col))
            centers = odd_centers + even_centers

        total = len(centers)
        for i, (x, y) in enumerate(centers, 1):
            if not self.is_running or self.is_paused:
                break

            print(f"模式探索进度: {i}/{total}")
            self.click_with_record(x, y)
            time.sleep(random.uniform(0.2, 0.4))

    def save_records(self):
        """保存所有记录到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"records_{timestamp}.json"
        filepath = os.path.join(self.save_dir, filename)

        # 转换为可序列化的格式
        serializable_records = []
        for record in self.records:
            serializable_records.append({
                'timestamp': record.timestamp,
                'x': record.x,
                'y': record.y,
                'screenshot_path': record.screenshot_path,
                'grid_x': record.grid_x,
                'grid_y': record.grid_y
            })

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'game_region': self.game_region,
                'grid_size': self.grid_size,
                'grid_rows': self.grid_rows,
                'grid_cols': self.grid_cols,
                'total_clicks': len(self.records),
                'records': serializable_records
            }, f, indent=2, ensure_ascii=False)

        print(f"记录已保存到: {filepath}")
        return filepath

    def load_records(self, filepath: str):
        """从文件加载记录"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.game_region = tuple(data['game_region'])
        self.grid_size = tuple(data['grid_size']) if data['grid_size'] else None
        self.grid_rows = data['grid_rows']
        self.grid_cols = data['grid_cols']

        self.records = []
        for record_data in data['records']:
            # 加载截图
            screenshot = None
            if record_data['screenshot_path'] and os.path.exists(record_data['screenshot_path']):
                screenshot = cv2.imread(record_data['screenshot_path'])

            record = ClickRecord(
                timestamp=record_data['timestamp'],
                x=record_data['x'],
                y=record_data['y'],
                screenshot=screenshot,
                screenshot_path=record_data['screenshot_path'],
                grid_x=record_data['grid_x'],
                grid_y=record_data['grid_y']
            )
            self.records.append(record)

        print(f"已加载 {len(self.records)} 条记录")

    def analyze_records(self):
        """分析记录，找出相同的图片"""
        if not self.records:
            print("没有记录可分析")
            return

        print(f"分析 {len(self.records)} 条记录...")

        # 提取所有截图
        screenshots = []
        for i, record in enumerate(self.records):
            if record.screenshot is not None:
                screenshots.append({
                    'index': i,
                    'screenshot': record.screenshot,
                    'grid_pos': (record.grid_x, record.grid_y),
                    'record': record
                })

        # 简单的图片相似度分析（基于颜色直方图）
        similar_pairs = []
        for i in range(len(screenshots)):
            for j in range(i + 1, len(screenshots)):
                sim = self.compare_images(
                    screenshots[i]['screenshot'],
                    screenshots[j]['screenshot']
                )

                if sim > 0.8:  # 相似度阈值
                    similar_pairs.append({
                        'pair': (i, j),
                        'similarity': sim,
                        'pos1': screenshots[i]['grid_pos'],
                        'pos2': screenshots[j]['grid_pos'],
                        'record1': screenshots[i]['record'],
                        'record2': screenshots[j]['record']
                    })

        print(f"找到 {len(similar_pairs)} 对相似的图片")

        # 保存分析结果
        analysis_file = os.path.join(self.save_dir, "analysis_result.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_records': len(self.records),
                'similar_pairs': [
                    {
                        'pair': pair['pair'],
                        'similarity': pair['similarity'],
                        'position1': pair['pos1'],
                        'position2': pair['pos2']
                    }
                    for pair in similar_pairs
                ]
            }, f, indent=2, ensure_ascii=False)

        print(f"分析结果已保存到: {analysis_file}")

        # 保存分析结果到实例变量，供后续查看
        self.analysis_result = {
            'total_records': len(self.records),
            'similar_pairs': similar_pairs,
            'analysis_file': analysis_file
        }

        return similar_pairs

    def get_analysis_report(self):
        """获取分析报告的文本形式"""
        if not hasattr(self, 'analysis_result') or not self.analysis_result:
            return "尚未进行分析，请先运行分析功能。"

        report = []
        report.append("=== 连连看图片分析报告 ===")
        report.append(f"总记录数: {self.analysis_result['total_records']}")
        report.append(f"相似图片对数: {len(self.analysis_result['similar_pairs'])}")
        report.append("")

        if self.analysis_result['similar_pairs']:
            report.append("相似图片对详情:")
            for idx, pair in enumerate(self.analysis_result['similar_pairs'], 1):
                pos1 = pair['pos1']
                pos2 = pair['pos2']
                sim = pair['similarity']
                report.append(f"  {idx}. 位置 {pos1} ↔ 位置 {pos2}, 相似度: {sim:.2f}")
        else:
            report.append("未找到相似的图片对。")

        report.append("")
        report.append(f"详细分析结果保存在: {self.analysis_result['analysis_file']}")

        return "\n".join(report)

    def compare_images(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """比较两张图片的相似度"""
        if img1 is None or img2 is None:
            return 0.0

        # 方法1：直方图比较
        img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        hist1 = cv2.calcHist([img1_gray], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([img2_gray], [0], None, [256], [0, 256])

        # 归一化
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

        return max(0.0, similarity)  # 确保非负

    def create_summary_image(self):
        """创建所有截图的汇总图片，按照原始网格位置排列"""
        if not self.records:
            print("没有记录可汇总")
            return

        # 收集所有有效记录及其网格位置
        valid_records = [(r.grid_x, r.grid_y, r) for r in self.records
                         if r.screenshot is not None and r.grid_x is not None and r.grid_y is not None]

        if not valid_records:
            print("没有有效的带网格坐标的截图")
            return

        # 找到网格的最大行列数
        max_col = max(r[0] for r in valid_records) if valid_records else 0
        max_row = max(r[1] for r in valid_records) if valid_records else 0

        # 计算单个缩略图大小
        thumb_size = (80, 80)  # 调整缩略图大小以便更好地显示

        # 创建大图，按照实际网格大小创建
        summary_img = np.zeros(
            ((max_row + 1) * thumb_size[1], (max_col + 1) * thumb_size[0], 3),
            dtype=np.uint8
        )

        # 填充白色背景
        summary_img.fill(255)

        # 按照网格位置放置截图
        for grid_x, grid_y, record in valid_records:
            # 调整截图大小
            resized = cv2.resize(record.screenshot, thumb_size)

            # 计算在汇总图片中的位置
            y_start = grid_y * thumb_size[1]
            y_end = y_start + thumb_size[1]
            x_start = grid_x * thumb_size[0]
            x_end = x_start + thumb_size[0]

            # 确保不超出图片边界
            if x_end <= summary_img.shape[1] and y_end <= summary_img.shape[0]:
                summary_img[y_start:y_end, x_start:x_end] = resized

                # 添加网格坐标标签
                label = f"({grid_x},{grid_y})"
                cv2.putText(
                    summary_img, label,
                    (x_start + 2, y_start + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (0, 0, 255), 1
                )

        # 保存汇总图片
        summary_path = os.path.join(self.save_dir, "summary.png")
        cv2.imwrite(summary_path, summary_img)

        print(f"汇总图片已保存到: {summary_path}")
        print(f"汇总图片尺寸: {summary_img.shape[1]}x{summary_img.shape[0]}, "
              f"网格大小: {max_col+1}x{max_row+1}")

        # 显示图片（可选）
        #try:
            #cv2.imshow("连连看截图汇总（按网格位置排列）", summary_img)
            #cv2.waitKey(3000)  # 显示3秒
           # cv2.destroyAllWindows()
       # except:
            #pass

        return summary_path

    def start_auto_explore(self, mode: str = "grid_scan", **kwargs):
        """开始自动探索"""
        if self.is_running:
            print("已经在运行中")
            return

        self.is_running = True
        self.is_paused = False

        print("开始自动探索...")
        print("按 ESC 键停止")
        print("按 SPACE 键暂停/继续")

        # 启动键盘监听
        threading.Thread(target=self.keyboard_listener, daemon=True).start()

        try:
            if mode == "grid_scan":
                self.detect_grid_layout()
                self.scan_all_grids()
            elif mode == "random":
                self.random_exploration(kwargs.get('num_clicks', 50))
            elif mode == "pattern":
                self.pattern_exploration(kwargs.get('pattern', 'row_by_row'))
            elif mode == "auto_red":
                self.auto_play_red_blocks()
            else:
                print(f"未知模式: {mode}")

        except pyautogui.FailSafeException:
            print("安全机制触发，程序已停止")
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            self.stop()

    def keyboard_listener(self):
        """键盘监听器"""
        while self.is_running:
            if keyboard.is_pressed('esc'):  # ESC键停止
                print("检测到ESC键，正在停止...")
                self.stop()
                break
            elif keyboard.is_pressed('space'):  # 空格键暂停/继续
                self.toggle_pause()
                time.sleep(0.5)  # 防抖
            time.sleep(0.1)

    def toggle_pause(self):
        """切换暂停状态"""
        self.is_paused = not self.is_paused
        status = "暂停" if self.is_paused else "继续"
        print(f"{status}...")

    def stop(self):
        """停止程序"""
        self.is_running = False
        print("程序已停止")

        # 保存记录
        if self.records:
            self.save_records()
            self.create_summary_image()
            self.auto_match_and_remove()
            print(f"共记录了 {len(self.records)} 次点击")

    def draw_game_region_boundary(self):
        """绘制游戏区域边界框，使用Canvas创建边框"""
        import tkinter as tk
        import threading

        # 隐藏任何现有的边框
        self.hide_game_region_boundary()

        # 创建一个新的顶级窗口
        self.region_window = tk.Tk()  # 使用Tk()而不是Toplevel()
        self.region_window.title("")
        self.region_window.configure(bg='')  # 设置背景

        # 设置窗口属性
        self.region_window.overrideredirect(True)  # 无边框
        self.region_window.attributes('-topmost', True)  # 置顶
        self.region_window.attributes('-alpha', 0.5)  # 半透明

        # 获取游戏区域坐标
        left, top, width, height = self.game_region

        # 设置窗口位置和大小
        self.region_window.geometry(f'{width}x{height}+{left}+{top}')

        # 创建画布
        canvas = tk.Canvas(
            self.region_window,
            highlightthickness=0,
            bg='',
            width=width,
            height=height
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        # 绘制边框（使用create_rectangle绘制一个边框矩形）
        # 绘制四条线来形成边框，而不是填充矩形
        canvas.create_line(2, 2, width-2, 2, fill='yellow', width=4)  # 顶边
        canvas.create_line(2, height-2, width-2, height-2, fill='yellow', width=4)  # 底边
        canvas.create_line(2, 2, 2, height-2, fill='yellow', width=4)  # 左边
        canvas.create_line(width-2, 2, width-2, height-2, fill='yellow', width=4)  # 右边

        # 绑定点击事件
        def close_window(event):
            self.hide_game_region_boundary()

        canvas.bind("<Button-1>", close_window)

        # 在独立线程中运行窗口
        def run_window():
            try:
                self.region_window.mainloop()
            except tk.TclError:
                pass

        # 启动窗口线程
        window_thread = threading.Thread(target=run_window, daemon=True)
        window_thread.start()

        print(f"已显示游戏区域边界框 (黄色)，点击边框可关闭")

    def hide_game_region_boundary(self):
        """隐藏游戏区域边界框"""
        try:
            if hasattr(self, 'region_window') and self.region_window:
                self.region_window.quit()  # 退出mainloop
                self.region_window.destroy()  # 销毁窗口
                self.region_window = None
        except tk.TclError:
            pass  # 如果窗口已被销毁则忽略错误
        except AttributeError:
            pass  # 如果属性不存在则忽略错误


# GUI界面
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class LianLianKanGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("连连看自动化工具")
        self.root.geometry("650x750")

        self.automator = None
        self.game_region = None

        self.setup_ui()

    def setup_ui(self):
        # 标题
        title_label = tk.Label(self.root, text="连连看自动化工具",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # 游戏区域设置
        region_frame = tk.LabelFrame(self.root, text="游戏区域设置", padx=10, pady=10)
        region_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(region_frame, text="游戏区域 (x1, y1, x2, y2):").grid(row=0, column=0, sticky="w")
        self.region_entry = tk.Entry(region_frame, width=30)
        self.region_entry.grid(row=0, column=1, padx=5)
        self.region_entry.insert(0, "844, 461, 450, 550")

        tk.Button(region_frame, text="手动选择",
                  command=self.select_region_manually).grid(row=0, column=2, padx=5)

        # 控制按钮
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=15)

        self.start_btn = tk.Button(control_frame, text="开始扫描",
                                   command=self.start_scan, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(control_frame, text="停止",
                                  command=self.stop_scan, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = tk.Button(control_frame, text="暂停",
                                   command=self.pause_scan, width=15, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        # 模式选择
        mode_frame = tk.LabelFrame(self.root, text="扫描模式", padx=10, pady=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        self.mode_var = tk.StringVar(value="auto_red")

        modes = [
            ("网格扫描", "grid_scan"),
            ("随机探索", "random"),
            ("逐行扫描", "pattern_row"),
            ("跳棋模式", "pattern_checkerboard"),
            ("自动识别红色块", "auto_red")
        ]

        for i, (text, value) in enumerate(modes):
            tk.Radiobutton(mode_frame, text=text, variable=self.mode_var,
                           value=value).grid(row=i // 2, column=i % 2, sticky="w", padx=10, pady=2)

        # 参数设置
        param_frame = tk.LabelFrame(self.root, text="参数设置", padx=10, pady=10)
        param_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(param_frame, text="点击次数:").grid(row=0, column=0, sticky="w")
        self.clicks_entry = tk.Entry(param_frame, width=10)
        self.clicks_entry.grid(row=0, column=1, padx=5)
        self.clicks_entry.insert(0, "50")

        # 状态显示
        status_frame = tk.LabelFrame(self.root, text="状态", padx=10, pady=10)
        status_frame.pack(fill="x", padx=10, pady=5)

        self.status_text = tk.Text(status_frame, height=6, width=50)
        self.status_text.pack()

        # 操作历史
        history_frame = tk.Frame(self.root)
        history_frame.pack(pady=10)

        tk.Button(history_frame, text="查看记录",
                  command=self.view_records).pack(side=tk.LEFT, padx=5)

        tk.Button(history_frame, text="分析图片",
                  command=self.analyze_pictures).pack(side=tk.LEFT, padx=5)

        tk.Button(history_frame, text="清除记录",
                  command=self.clear_records).pack(side=tk.LEFT, padx=5)

    def log_status(self, message):
        """记录状态信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.root.update()

    def select_region_manually(self):
        """手动选择游戏区域"""
        self.log_status("请将鼠标移动到游戏窗口左上角，5秒后记录...")
        time.sleep(5)
        x1, y1 = pyautogui.position()
        self.log_status(f"左上角: ({x1}, {y1})")

        self.log_status("请将鼠标移动到游戏窗口右下角，5秒后记录...")
        time.sleep(5)
        x2, y2 = pyautogui.position()
        self.log_status(f"右下角: ({x2}, {y2})")

        width = x2 - x1
        height = y2 - y1
        self.region_entry.delete(0, tk.END)
        self.region_entry.insert(0, f"{x1}, {y1}, {width}, {height}")

        self.game_region = (x1, y1, width, height)

    def start_scan(self):
        """开始扫描"""
        # 解析游戏区域
        try:
            region_str = self.region_entry.get()
            x1, y1, width, height = map(int, region_str.replace(" ", "").split(","))
            self.game_region = (x1, y1, width, height)
        except:
            messagebox.showerror("错误", "游戏区域格式错误！")
            return

        # 初始化自动化器
        self.automator = LianLianKanAutomator(self.game_region)

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL)

        # 获取模式参数
        mode = self.mode_var.get()

        # 在新线程中运行
        thread = threading.Thread(target=self.run_automator, args=(mode,))
        thread.daemon = True
        thread.start()

    def run_automator(self, mode):
        """运行自动化器"""
        try:
            if mode == "grid_scan":
                self.automator.start_auto_explore("grid_scan")
            elif mode == "random":
                num_clicks = int(self.clicks_entry.get())
                self.automator.start_auto_explore("random", num_clicks=num_clicks)
            elif mode == "pattern_row":
                self.automator.start_auto_explore("pattern", pattern="row_by_row")
            elif mode == "pattern_checkerboard":
                self.automator.start_auto_explore("pattern", pattern="checkerboard")
            elif mode == "auto_red":
                self.automator.start_auto_explore("auto_red")
        except Exception as e:
            self.log_status(f"错误: {e}")
        finally:
            self.after_scan()

    def stop_scan(self):
        """停止扫描"""
        if self.automator:
            self.automator.stop()

    def pause_scan(self):
        """暂停/继续扫描"""
        if self.automator:
            self.automator.toggle_pause()

    def after_scan(self):
        """扫描结束后更新UI"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.log_status("扫描完成！")

    def view_records(self):
        """查看记录"""
        if self.automator and self.automator.records:
            record_count = len(self.automator.records)
            messagebox.showinfo("记录信息", f"共有 {record_count} 条记录")
        else:
            messagebox.showinfo("记录信息", "暂无记录")

    def analyze_pictures(self):
        """分析图片"""
        if self.automator and self.automator.records:
            # 执行分析
            self.automator.analyze_records()
            self.automator.create_summary_image()

            # 获取分析报告
            report = self.automator.get_analysis_report()

            # 显示分析报告
            self.show_analysis_report(report)

            messagebox.showinfo("分析完成", "图片分析完成！")
        else:
            messagebox.showinfo("分析", "暂无记录可分析")

    def show_analysis_report(self, report):
        """显示分析报告"""
        # 创建新的窗口显示报告
        report_window = tk.Toplevel(self.root)
        report_window.title("图片分析报告")
        report_window.geometry("600x400")

        # 创建文本框显示报告
        text_frame = tk.Frame(report_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 插入报告内容
        text_widget.insert(tk.END, report)
        text_widget.config(state=tk.DISABLED)  # 设置为只读

    def clear_records(self):
        """清除记录"""
        if messagebox.askyesno("确认", "确定要清除所有记录吗？"):
            if self.automator:
                self.automator.records.clear()
            self.log_status("记录已清除")


def main():
    """主函数"""
    print("=== 连连看自动化工具 ===")
    print("功能说明:")
    print("1. 自动点击连连看网格")
    print("2. 记录每次点击后的图片")
    print("3. 分析相同图片对")
    print("4. 生成汇总报告")
    print()

    # 获取游戏区域
    print("请将鼠标移动到游戏窗口左上角，5秒后记录...")
    time.sleep(5)
    x1, y1 = pyautogui.position()
    print(f"左上角: ({x1}, {y1})")

    print("请将鼠标移动到游戏窗口右下角，5秒后记录...")
    time.sleep(5)
    x2, y2 = pyautogui.position()
    print(f"右下角: ({x2}, {y2})")

    width = x2 - x1
    height = y2 - y1
    game_region = (x1, y1, width, height)

    print(f"游戏区域: {game_region}")

    # 创建自动化器
    automator = LianLianKanAutomator(game_region)

    # 选择模式
    print("\n请选择模式:")
    print("1. 网格扫描 (逐格扫描所有位置)")
    print("2. 随机探索 (随机点击)")
    print("3. 模式探索 (按特定模式扫描)")

    choice = input("请输入选择 (1/2/3): ").strip()

    if choice == "1":
        automator.start_auto_explore("grid_scan")
    elif choice == "2":
        num_clicks = int(input("请输入点击次数 (默认50): ") or "50")
        automator.start_auto_explore("random", num_clicks=num_clicks)
    elif choice == "3":
        print("请选择模式:")
        print("1. 逐行扫描")
        print("2. 逐列扫描")
        print("3. 跳棋模式")
        pattern_choice = input("请输入选择 (1/2/3): ").strip()

        if pattern_choice == "1":
            automator.start_auto_explore("pattern", pattern="row_by_row")
        elif pattern_choice == "2":
            automator.start_auto_explore("pattern", pattern="col_by_col")
        elif pattern_choice == "3":
            automator.start_auto_explore("pattern", pattern="checkerboard")
        else:
            print("无效选择")
    else:
        print("无效选择")


if __name__ == "__main__":
    # 使用GUI版本
    root = tk.Tk()
    app = LianLianKanGUI(root)
    root.mainloop()

    # 或者使用命令行版本
    # main()