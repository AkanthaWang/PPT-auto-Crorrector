import os
from natsort import natsorted
from PIL import Image
from tqdm import tqdm

# ================== 配置参数 ==================
IMAGE_DIR = "corrected_ppt"         # 输入图像文件夹
OUTPUT_PDF = "ppt_slides.pdf"      # 输出PDF文件名

DPI = 72                           # PDF 默认 DPI（1 pixel = 1 point），保持原尺寸
                                     # 可改为 96、150 等以调整打印尺寸

def main():
    # 检查文件夹是否存在
    if not os.path.exists(IMAGE_DIR):
        print(f"❌ 错误：图像文件夹不存在: {IMAGE_DIR}")
        return

    # 获取所有 .jpg 文件并自然排序
    image_files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith('.jpg')]
    if not image_files:
        print(f"❌ 在 {IMAGE_DIR} 中未找到 .jpg 文件")
        return

    image_paths = [os.path.join(IMAGE_DIR, f) for f in natsorted(image_files)]
    print(f"✅ 找到 {len(image_paths)} 张图像，按文件名自然排序")

    # 加载图像
    image_list = []
    print("🖼️  开始加载图像...")
    for idx, img_path in enumerate(tqdm(image_paths, desc="📄 处理图像")):
        try:
            img = Image.open(img_path).convert("RGB")  # 转为RGB以支持PDF
            image_list.append(img)
        except Exception as e:
            print(f"⚠️ 跳过无法读取的图像 {img_path}: {e}")

    if not image_list:
        print("❌ 没有有效图像可生成 PDF")
        return

    # 保存为 PDF
    try:
        first_img = image_list[0]
        first_img.save(
            OUTPUT_PDF,
            "PDF",
            resolution=DPI,           # 控制 PDF 中的 DPI（影响打印尺寸）
            save_all=True,
            append_images=image_list[1:]
        )
        print(f"\n🎉 成功生成 PDF: {OUTPUT_PDF}")
        print(f"📊 共 {len(image_list)} 页 | DPI: {DPI} | 每页尺寸 = 原图像素尺寸")
        print(f"🔍 提示：1 pixel ≈ 1 point (1/72 inch) at {DPI} DPI")
    except Exception as e:
        print(f"❌ 保存 PDF 失败: {e}")

if __name__ == "__main__":
    main()