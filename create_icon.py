"""
Создание иконки для приложения Trends
"""
from PIL import Image, ImageDraw

def create_app_icon():
    """Создаёт иконку приложения в разных размерах"""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Градиентный фон (от бирюзового к фиолетовому)
        # Упрощённо - просто бирюзовый круг
        padding = size // 8
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=(0, 212, 170)  # Бирюзовый
        )
        
        # Три столбца графика (белые)
        bar_width = size // 8
        bar_spacing = size // 16
        start_x = size // 4
        bottom = size - size // 4
        
        # Столбец 1 (низкий)
        h1 = size // 4
        x1 = start_x
        draw.rectangle([x1, bottom - h1, x1 + bar_width, bottom], fill=(255, 255, 255))
        
        # Столбец 2 (высокий)
        h2 = size // 2.5
        x2 = x1 + bar_width + bar_spacing
        draw.rectangle([x2, bottom - h2, x2 + bar_width, bottom], fill=(255, 255, 255))
        
        # Столбец 3 (средний)
        h3 = size // 3
        x3 = x2 + bar_width + bar_spacing
        draw.rectangle([x3, bottom - h3, x3 + bar_width, bottom], fill=(255, 255, 255))
        
        images.append(img)
    
    # Сохраняем как ICO (Windows)
    images[0].save(
        'assets/trends.ico',
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    
    # Сохраняем как PNG (для других целей)
    images[-1].save('assets/trends.png', format='PNG')
    
    print("✅ Icons created:")
    print("   - assets/trends.ico (Windows)")
    print("   - assets/trends.png (256x256)")


if __name__ == "__main__":
    import os
    os.makedirs("assets", exist_ok=True)
    create_app_icon()

