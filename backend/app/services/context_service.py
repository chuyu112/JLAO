from app.schemas import Product, TranscriptSegment


def extract_keywords(text: str) -> list[str]:
    dictionary = [
        "证书",
        "A货",
        "圈口",
        "自然光",
        "飘花",
        "冰感",
        "棉",
        "纹",
        "裂",
        "价格",
        "上手",
        "色差",
        "厚度",
    ]
    return [word for word in dictionary if word in text]


def build_context(product: Product | None, transcripts: list[TranscriptSegment]) -> str:
    recent_text = " ".join(item.text for item in transcripts[-6:])
    if not product:
        return f"最近直播内容：{recent_text}"

    product_block = (
        f"当前商品：{product.name}，分类：{product.category}，颜色：{product.color}，"
        f"种水：{product.water}，尺寸：{product.size}，证书：{product.certificate}，"
        f"瑕疵：{product.flaws}，注意事项：{product.cautions}。"
    )
    return f"{product_block}\n最近直播内容：{recent_text}"

