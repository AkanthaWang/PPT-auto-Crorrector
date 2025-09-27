import cv2
import numpy as np
import torch
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
import os
import glob
from natsort import natsorted  # 用于自然排序（可选）

# ================== 配置参数 ==================
INPUT_DIR = "input_dir"           # 原始图片文件夹
OUTPUT_DIR = "corrected_ppt"         # 输出文件夹

SAM_CHECKPOINT = "sam_vit_h_4b8939.pth"
MODEL_TYPE = "vit_h"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 输出图像尺寸 如16：9
TARGET_WIDTH = 1920*2
TARGET_HEIGHT = 1080*2

# 排序方式：'size_asc'（小到大）, 'size_desc'（大到小）, 'name'（文件名自然排序）
SORT_BY = "size_desc"


# ================== 工具函数 ==================
def sort_points(pts):
    """将四个点排序为：左上、右上、右下、左下"""
    pts = pts.astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    rect = np.zeros((4, 2), dtype=np.float32)
    rect[0] = pts[np.argmin(s)]      # 左上：x+y 最小
    rect[2] = pts[np.argmax(s)]      # 右下：x+y 最大
    rect[1] = pts[np.argmin(diff)]   # 右上：x-y 最小
    rect[3] = pts[np.argmax(diff)]   # 左下：x-y 最大

    return rect

def get_file_size(filepath):
    """获取文件大小（字节）"""
    return os.path.getsize(filepath)


def main():
    # 1. 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✅ 输出目录: {OUTPUT_DIR}")

    # 2. 查找所有 IMG 开头的 jpg 图像
    pattern = os.path.join(INPUT_DIR, "*.jpg")
    image_paths = glob.glob(pattern)

    if not image_paths:
        print(f"❌ 在 {INPUT_DIR} 中未找到 *.jpg 文件")
        return

    print(f"找到 {len(image_paths)} 张图像")

    # 3. 根据配置排序
    if SORT_BY == "size_asc":
        image_paths.sort(key=get_file_size)
        print("📌 按文件大小升序处理")
    elif SORT_BY == "size_desc":
        image_paths.sort(key=get_file_size, reverse=True)
        print("📌 按文件大小降序处理")
    else:  # name 自然排序（推荐用于时间序列）
        image_paths = natsorted(image_paths)  # 如 IMG20250926093230
        print("📌 按文件名自然排序")

    # 4. 加载 SAM 模型
    print("🚀 加载 SAM 模型...")
    sam = sam_model_registry[MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
    sam.to(device=DEVICE)
    mask_generator = SamAutomaticMaskGenerator(sam)
    print("✅ SAM 模型加载完成")

    # 5. 遍历并处理每张图像
    for idx, img_path in enumerate(image_paths):
        filename = os.path.basename(img_path)
        output_path = os.path.join(OUTPUT_DIR, f"corrected_{filename}")

        print(f"\n🔄 处理 [{idx+1}/{len(image_paths)}]: {filename}")

        # 读取图像
        image = cv2.imread(img_path)
        
        if image is None:
            print(f"⚠️ 跳过（无法读取）: {filename}")
            continue

        # 获取原图尺寸
        height, width = image.shape[:2]
    
        # 缩小为一半
        new_width = width // 2
        new_height = height // 2
    
        # 使用 cv2.resize 缩放
        image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


        # 生成分割掩码
        try:
            masks = mask_generator.generate(image)
        except Exception as e:
            print(f"❌ SAM 处理失败: {e}")
            os.makedirs("failed_images", exist_ok=True)
            import shutil
            shutil.copy(img_path, filename)
            print(f"📁 已保存到 failed_images: {filename}")
            continue

        # 找最佳区域（最大 + 接近16:9）
        best_mask = None
        max_score = 0
        preferred_ratio = 16 / 9

        for mask in masks:
            seg_mask = mask['segmentation']
            area = mask['area']
            bbox = mask['bbox']
            if bbox[2] == 0 or bbox[3] == 0:
                continue
            aspect_ratio = bbox[2] / bbox[3]
            aspect_score = 1 / (abs(aspect_ratio - preferred_ratio) + 0.5)
            area_score = area if area > 1000*100 else 0
            score = area_score * aspect_score
            if score > max_score:
                max_score = score
                best_mask = seg_mask

        if best_mask is None:
            print(f"⚠️ 未找到PPT区域: {filename}")
            continue

        # 提取轮廓
        best_mask_uint8 = best_mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(best_mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            print(f"⚠️ 无轮廓: {filename}")
            continue

        contour = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) >= 4:
            pts1 = np.array([point[0] for point in approx[:4]], dtype=np.float32)
        else:
            x, y, w, h = cv2.boundingRect(contour)
            pts1 = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32)

        src_points = sort_points(pts1)
        dst_points = np.array([[0, 0], [TARGET_WIDTH, 0], [TARGET_WIDTH, TARGET_HEIGHT], [0, TARGET_HEIGHT]], dtype=np.float32)

        # 透视变换
        M = cv2.getPerspectiveTransform(src_points, dst_points)
        corrected = cv2.warpPerspective(image, M, (TARGET_WIDTH, TARGET_HEIGHT))

        # 保存
        cv2.imwrite(output_path, corrected)
        print(f"✅ 已保存: {output_path}")

    print(f"\n🎉 所有图像处理完成！结果保存在: {OUTPUT_DIR}")


if __name__ == "__main__":
    # 安装 natsort: pip install natsort
    try:
        from natsort import natsorted
    except ImportError:
        print("⚠️ 未安装 natsort，将使用默认排序。建议 pip install natsort")
        natsorted = sorted

    main()