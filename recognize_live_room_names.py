"""识别图片中的直播间名字。

使用方法：
    python recognize_live_room_names.py <图片路径1> <图片路径2> ...

或者：
    from recognize_live_room_names import recognize_image

    # 识别单张图片
    names = recognize_image("path/to/image.jpg")
    print(names)
"""

import sys
from pathlib import Path

from paddleocr import PaddleOCR


def recognize_image(image_path: str) -> list[str]:
    """识别图片中的文字。

    Args:
        image_path: 图片路径

    Returns:
        识别出的文字列表
    """
    # 初始化 PaddleOCR
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang='ch',
        use_gpu=False,
        show_log=False,
    )

    # 识别图片
    result = ocr.ocr(image_path, cls=True)

    # 提取文字
    names = []
    if result and result[0]:
        for line in result[0]:
            if line:
                text = line[1][0]
                confidence = line[1][1]
                if text and confidence > 0.5:
                    names.append(text)

    return names


def main():
    if len(sys.argv) < 2:
        print("用法: python recognize_live_room_names.py <图片路径1> [图片路径2] ...")
        print("示例: python recognize_live_room_names.py 1.jpg 2.jpg 3.jpg")
        sys.exit(1)

    for image_path in sys.argv[1:]:
        if not Path(image_path).exists():
            print(f"错误: 文件不存在 {image_path}")
            continue

        print(f"\n{'='*50}")
        print(f"识别图片: {image_path}")
        print(f"{'='*50}")

        try:
            names = recognize_image(image_path)
            if names:
                print("识别到的文字:")
                for i, name in enumerate(names, 1):
                    print(f"  {i}. {name}")
            else:
                print("未识别到文字")
        except Exception as e:
            print(f"识别失败: {e}")


if __name__ == "__main__":
    main()
