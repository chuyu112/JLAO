from app.services.jade_multimodal_service import analyze_jade_text


def test_text_recognizes_color_water_style_and_theme():
    result = analyze_jade_text("这件蓝水高冰龙牌，牌型规整，雕工清晰。", use_feedback_learning=False)

    assert result.color == "蓝水"
    assert result.water == "高冰"
    assert result.style == "吊坠"
    assert result.theme == "龙牌"


def test_text_recognizes_size_and_price_when_present():
    result = analyze_jade_text("白冰冰种观音吊坠，高 45mm，宽 18mm，报价 1.8 万。", use_feedback_learning=False)

    assert result.color == "白冰"
    assert result.water == "冰种"
    assert result.style == "吊坠"
    assert result.theme == "观音"
    assert result.size
    assert result.price == 18000
