
import fitz
import os
from typing import List, Tuple, Union, Dict
import argparse
import json
from dataclasses import dataclass, asdict
import re
import numpy as np
from PIL import Image
import io
from collections import Counter
import gc

@dataclass
class ElementPattern:
    """水印元素模式"""
    type: str  # 元素类型：'text' 或 'image'
    bbox: Tuple[float, float, float, float]  # 边界框坐标
    text: str = ""  # 文本内容（对于文本元素）
    description: str = ""  # 模式描述
    
    def matches(self, element: Dict) -> bool:
        """检查元素是否匹配此模式"""
        if self.type == "text" and "lines" in element:
            # 检查文本内容
            text = " ".join(span["text"] for line in element["lines"] 
                          for span in line["spans"])
            return self.text in text
        elif self.type == "image" and "image" in element:
            # 检查边界框位置
            element_bbox = element["bbox"]
            return all(abs(a - b) < 1 for a, b in zip(self.bbox, element_bbox))
        return False

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ElementPattern':
        """从字典创建实例"""
        return cls(**data)

class ColorAnalyzer:
    def __init__(self, tolerance: float = 0.05, min_pixels: int = 100):
        """初始化颜色分析器
        
        Args:
            tolerance (float): 颜色合并的容差值
            min_pixels (int): 最小像素数，少于此数量的颜色将被忽略
        """
        self.tolerance = tolerance
        self.min_pixels = min_pixels

    def similar_colors(self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> bool:
        """判断两个颜色是否相似"""
        return all(abs(c1 - c2) <= self.tolerance * 255 for c1, c2 in zip(color1, color2))

    def analyze_image(self, image: Image.Image) -> List[Dict[str, Union[Tuple[int, int, int], float]]]:
        """分析图片中的主要颜色"""
        if image.mode != 'RGB':
            image = image.convert('RGB')

        pixels = list(image.getdata())
        total_pixels = len(pixels)
        color_counts = Counter(pixels)
        
        merged_colors = {}
        for color, count in color_counts.items():
            if count < self.min_pixels:
                continue
                
            found_similar = False
            for existing_color in list(merged_colors.keys()):
                if self.similar_colors(color, existing_color):
                    merged_colors[existing_color] += count
                    found_similar = True
                    break
            
            if not found_similar:
                merged_colors[color] = count
        
        color_info = []
        for color, count in merged_colors.items():
            percentage = (count / total_pixels) * 100
            if percentage >= 0.1:
                color_info.append({
                    "rgb": color,
                    "percentage": round(percentage, 2)
                })
        
        return sorted(color_info, key=lambda x: x["percentage"], reverse=True)

class PDFWatermarkRemover:
    def __init__(self, pdf_path: str):
        """初始化PDF处理器"""
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.patterns: List[ElementPattern] = []
        self.color_analyzer = ColorAnalyzer()
        self.temp_docs = []

    def __del__(self):
        """析构函数"""
        self.cleanup()

    def cleanup(self):
        """清理资源"""
        for doc in self.temp_docs:
            try:
                doc.close()
            except:
                pass
        self.temp_docs.clear()
        
        try:
            self.doc.close()
        except:
            pass
        
        gc.collect()

    def add_pattern(self, pattern: ElementPattern) -> None:
        """添加水印模式"""
        self.patterns.append(pattern)

    def save_patterns(self, file_path: str) -> None:
        """保存水印模式到文件"""
        patterns_data = [p.to_dict() for p in self.patterns]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(patterns_data, f, ensure_ascii=False, indent=2)

    def load_patterns(self, file_path: str) -> None:
        """从文件加载水印模式"""
        with open(file_path, 'r', encoding='utf-8') as f:
            patterns_data = json.load(f)
        self.patterns = [ElementPattern.from_dict(p) for p in patterns_data]

    def analyze_page_colors(self, page_num: int, dpi: int = 200) -> List[Dict]:
        """分析页面的颜色分布"""
        page = self.doc[page_num]
        matrix = fitz.Matrix(dpi/72, dpi/72)
        pixmap = page.get_pixmap(matrix=matrix)
        img_data = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        return self.color_analyzer.analyze_image(image)

    def create_clean_page(self, page_num: int) -> None:
        """创建清理后的页面（模式匹配方式）"""
        page = self.doc[page_num]
        elements = page.get_text("dict")["blocks"]
        
        temp_doc = fitz.open()
        temp_page = temp_doc.new_page(width=page.rect.width, height=page.rect.height)
        
        # 设置白色背景
        temp_page.draw_rect(temp_page.rect, color=(1, 1, 1), fill=(1, 1, 1))
        
        # 处理每个元素
        for element in elements:
            should_keep = True
            for pattern in self.patterns:
                if pattern.matches(element):
                    should_keep = False
                    break
            
            if should_keep:
                if "lines" in element:  # 文本元素
                    for line in element["lines"]:
                        for span in line["spans"]:
                            try:
                                temp_page.insert_text(
                                    fitz.Point(span["bbox"][0], span["bbox"][1]),
                                    span["text"],
                                    fontname=span.get("font", "helv"),
                                    fontsize=span.get("size", 11),
                                    color=span.get("color", (0, 0, 0))
                                )
                            except Exception as e:
                                print(f"警告: 处理文本时出错: {str(e)}")
                elif "image" in element:  # 图片元素
                    try:
                        xref = element.get("xref", 0)
                        if xref > 0:
                            image_data = self.doc.extract_image(xref)
                            if image_data:
                                temp_page.insert_image(
                                    fitz.Rect(element["bbox"]),
                                    stream=image_data["image"],
                                    mask=image_data.get("mask"),
                                    colorspace=image_data.get("colorspace"),
                                )
                    except Exception as e:
                        print(f"警告: 处理图片时出错: {str(e)}")
        
        self.doc.delete_page(page_num)
        self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num)
        temp_doc.close()

    def remove_color(self, page_num: int, target_color: Tuple[int, int, int], 
                    tolerance: float = 0.1, dpi: int = 200) -> bool:
        """通过颜色替换去除水印"""
        try:
            page = self.doc[page_num]
            matrix = fitz.Matrix(dpi/72, dpi/72)
            pixmap = page.get_pixmap(matrix=matrix)
            img_data = pixmap.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            del pixmap
            gc.collect()
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            del image
            
            color_mask = np.all(
                (np.abs(img_array - target_color) <= (tolerance * 255)),
                axis=2
            )
            img_array[color_mask] = [255, 255, 255]
            
            cleaned_image = Image.fromarray(img_array)
            del img_array
            
            temp_doc = fitz.open()
            self.temp_docs.append(temp_doc)
            temp_page = temp_doc.new_page(width=page.rect.width, height=page.rect.height)
            
            img_bytes = io.BytesIO()
            cleaned_image.save(img_bytes, format='PNG', optimize=True)
            img_bytes.seek(0)
            temp_page.insert_image(temp_page.rect, stream=img_bytes.getvalue())
            
            del cleaned_image
            img_bytes.close()
            gc.collect()
            
            self.doc.delete_page(page_num)
            self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num)
            
            return True
            
        except Exception as e:
            print(f"\n错误: 处理页面 {page_num + 1} 时出现问题: {str(e)}")
            return False
        finally:
            while self.temp_docs:
                try:
                    temp_doc = self.temp_docs.pop()
                    temp_doc.close()
                except:
                    pass
            gc.collect()

    def remove_watermarks_by_color(self, target_colors: List[Tuple[int, int, int]], 
                                 page_range: Union[Tuple[int, int], None] = None,
                                 tolerance: float = 0.1,
                                 dpi: int = 200,
                                 batch_size: int = 10) -> None:
        """使用颜色替换方式去除水印"""
        if page_range is None:
            start_page = 0
            end_page = len(self.doc) - 1
        else:
            start_page, end_page = page_range
            if start_page < 0 or end_page >= len(self.doc) or start_page > end_page:
                raise ValueError("无效的页面范围")
        
        total_pages = end_page - start_page + 1
        
        for batch_start in range(start_page, end_page + 1, batch_size):
            batch_end = min(batch_start + batch_size, end_page + 1)
            print(f"\n处理批次: {batch_start + 1} - {batch_end} / {total_pages}")
            
            for page_num in range(batch_start, batch_end):
                print(f"\r当前页面: {page_num + 1}", end="", flush=True)
                
                success = False
                for color in target_colors:
                    try:
                        if self.remove_color(page_num, color, tolerance, dpi):
                            success = True
                    except Exception as e:
                        print(f"\n警告: 处理页面 {page_num + 1} 的颜色 {color} 时出现问题: {str(e)}")
                        continue
                
                if not success:
                    print(f"\n警告: 页面 {page_num + 1} 处理失败")
            
            gc.collect()
        
        print("\n处理完成!")

    def remove_watermarks(self, page_range: Union[Tuple[int, int], None] = None) -> None:
        """使用模式匹配方式去除水印"""
        if not self.patterns:
            raise ValueError("没有定义水印模式")
            
        if page_range is None:
            start_page = 0
            end_page = len(self.doc) - 1
        else:
            start_page, end_page = page_range
            if start_page < 0 or end_page >= len(self.doc) or start_page > end_page:
                raise ValueError("无效的页面范围")
        
        total_pages = end_page - start_page + 1
        for i, page_num in enumerate(range(start_page, end_page + 1), 1):
            print(f"\r处理进度: {i}/{total_pages} 页", end="", flush=True)
            try:
                self.create_clean_page(page_num)
            except Exception as e:
                print(f"\n错误: 处理页面 {page_num + 1} 时出现问题: {str(e)}")
                continue
            
            # 定期进行垃圾回收
            if i % 10 == 0:
                gc.collect()
        
        print("\n处理完成!")

    def save(self, output_path: str, batch_size: int = 10) -> None:
        """保存处理后的PDF"""
        try:
            temp_doc = fitz.open()
            total_pages = len(self.doc)
            
            for start in range(0, total_pages, batch_size):
                end = min(start + batch_size, total_pages)
                print(f"\r保存进度: {end}/{total_pages}", end="", flush=True)
                
                temp_doc.insert_pdf(
                    self.doc,
                    from_page=start,
                    to_page=end-1,
                    start_at=start
                )
                gc.collect()
            
            temp_doc.save(
                output_path,
                garbage=4,
                deflate=True,
                clean=True,
                linear=True,
            )
            print(f"\n已成功保存到: {output_path}")
            
        except Exception as e:
            print(f"\n保存文件时出错: {str(e)}")
        finally:
            try:
                temp_doc.close()
            except:
                pass
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(description="PDF水印去除工具")
    parser.add_argument("input", help="输入PDF文件路径")
    parser.add_argument("--output", help="输出PDF文件路径")
    parser.add_argument("--page", type=int, help="分析指定页面的颜色或元素")
    
    # 颜色模式参数
    parser.add_argument("--color-mode", action="store_true", help="使用颜色替换模式")
    parser.add_argument("--colors", nargs="+", help="要替换的RGB颜色值，格式：R,G,B")
    parser.add_argument("--tolerance", type=float, default=0.1, help="颜色匹配容差 (0-1)")
    parser.add_argument("--dpi", type=int, default=200, help="处理图像的DPI")
    parser.add_argument("--batch-size", type=int, default=10, help="批处理大小")
    
    # 模式选择参数
    parser.add_argument("--mode", choices=['color', 'pattern'], 
                       help="处理模式：color(颜色替换) 或 pattern(模式匹配)")
    
    # 模式匹配参数
    parser.add_argument("--add-patterns", nargs="+", type=int, 
                       help="要添加的模式元素索引")
    parser.add_argument("--text-patterns", nargs="+", 
                       help="要匹配的文本模式")
    parser.add_argument("--descriptions", nargs="+", 
                       help="模式描述")
    parser.add_argument("--save-patterns", help="保存模式到JSON文件")
    parser.add_argument("--load-patterns", help="从JSON文件加载模式")
    
    # 页面范围参数
    parser.add_argument("--start-page", type=int, help="起始页码")
    parser.add_argument("--end-page", type=int, help="结束页码")
    
    args = parser.parse_args()
    
    try:
        remover = PDFWatermarkRemover(args.input)
        
        # 设置页面范围
        page_range = None
        if args.start_page is not None or args.end_page is not None:
            start = args.start_page or 0
            end = args.end_page or (len(remover.doc) - 1)
            page_range = (start, end)
        
        # 1. 页面分析模式
        if args.page is not None:
            if args.color_mode or args.mode == 'color':
                # 颜色分析模式
                colors = remover.analyze_page_colors(args.page)
                print("\n页面颜色分析结果:")
                for i, color in enumerate(colors, 1):
                    rgb = color["rgb"]
                    print(f"{i}. RGB{rgb}: {color['percentage']}%")
            else:
                # 元素分析模式
                elements = remover.analyze_page_elements(args.page)
                print("\n页面元素分析结果:")
                for i, element in enumerate(elements, 1):
                    print(f"\n元素 {i}:")
                    print(json.dumps(element, indent=2, ensure_ascii=False))
            return
        
        # 2. 颜色替换模式
        if args.color_mode or args.mode == 'color':
            if not args.colors:
                print("错误: 颜色模式需要指定 --colors 参数")
                return
                
            target_colors = []
            for color_str in args.colors:
                try:
                    r, g, b = map(int, color_str.split(","))
                    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                        raise ValueError
                    target_colors.append((r, g, b))
                except ValueError:
                    print(f"错误: 无效的颜色值 '{color_str}'，应为'R,G,B'格式，值范围0-255")
                    return
            
            print(f"开始处理，目标颜色: {target_colors}")
            remover.remove_watermarks_by_color(
                target_colors,
                page_range=page_range,
                tolerance=args.tolerance,
                dpi=args.dpi,
                batch_size=args.batch_size
            )
        
        # 3. 模式匹配模式
        elif args.mode == 'pattern' or args.load_patterns or args.add_patterns:
            # 3.1 添加新模式
            if args.add_patterns:
                if not args.page:
                    print("错误: 添加模式需要指定 --page 参数")
                    return
                if not args.text_patterns or not args.descriptions:
                    print("错误: 添加模式需要同时指定 --text-patterns 和 --descriptions 参数")
                    return
                if len(args.add_patterns) != len(args.text_patterns) or \
                   len(args.add_patterns) != len(args.descriptions):
                    print("错误: patterns、text_patterns 和 descriptions 的数量必须相同")
                    return
                
                elements = remover.analyze_page_elements(args.page)
                for idx, text_pattern, desc in zip(args.add_patterns, 
                                                 args.text_patterns, 
                                                 args.descriptions):
                    try:
                        element = elements[idx - 1]  # 转换为0基索引
                        remover.add_pattern_from_element(element, text_pattern, desc)
                    except IndexError:
                        print(f"错误: 无效的元素索引 {idx}")
                        return
                    except Exception as e:
                        print(f"错误: 添加模式时出错: {str(e)}")
                        return
                
                # 保存模式
                if args.save_patterns:
                    remover.save_patterns(args.save_patterns)
                    print(f"模式已保存到: {args.save_patterns}")
                return
            
            # 3.2 加载现有模式
            if args.load_patterns:
                try:
                    remover.load_patterns(args.load_patterns)
                    print(f"已加载模式文件: {args.load_patterns}")
                except Exception as e:
                    print(f"错误: 加载模式文件失败: {str(e)}")
                    return
            
            # 执行模式匹配去水印
            if not remover.patterns:
                print("错误: 未定义任何模式，请先添加模式或加载模式文件")
                return
            
            print("开始处理...")
            remover.remove_watermarks(page_range)
        
        else:
            print("错误: 请指定处理模式 (--color-mode 或 --mode)")
            return
        
        # 保存结果
        output_path = args.output or "output.pdf"
        print(f"\n正在保存结果到: {output_path}")
        remover.save(output_path, batch_size=args.batch_size)
        print("处理完成!")
        
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            remover.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()