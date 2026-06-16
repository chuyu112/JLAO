from app.services.jade_vlm_service import parse_vlm_attributes
from app.services.jade_yolo_service import jade_attributes_from_yolo_label
from app.services.jade_multimodal_service import (
    JadeAnalysis,
    _color_analysis_from_attributes,
    _refine_color_analysis_with_opencv,
    _visual_color_from_signals,
    _visual_style_from_signals,
    _visual_theme_from_signals,
    _visual_water_from_signals,
    merge_jade_analysis,
)


def test_vlm_parse_markdown_json_with_nested_attributes():
    text = """```json
{"attributes":{"颜色":{"value":"正阳绿"},"种水":["糯冰种"],"器型":{"label":"挂件"},"题材":"观音"}}
```"""

    result = parse_vlm_attributes(text)

    assert result == {
        "color": "阳绿",
        "water": "糯冰",
        "style": "吊坠",
        "theme": "观音",
    }


def test_vlm_parse_plain_description_when_no_json_or_labels():
    result = parse_vlm_attributes("白冰冰种观音吊坠")

    assert result == {
        "color": "白冰",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }


def test_vlm_parse_labeled_text_fills_missing_fields_from_full_response():
    result = parse_vlm_attributes("颜色: 蓝水。整体像高冰龙牌，牌型规整。")

    assert result == {
        "color": "蓝水",
        "water": "高冰",
        "style": "吊坠",
        "theme": "龙牌",
    }


def test_vlm_labeled_value_stops_at_chinese_sentence_separator():
    result = parse_vlm_attributes("颜色: 正阳绿。种水: 糯冰种；款式: 挂件，题材: 如意。")

    assert result == {
        "color": "阳绿",
        "water": "糯冰",
        "style": "吊坠",
        "theme": "如意",
    }


def test_vlm_parse_description_only_fills_missing_structured_fields():
    result = parse_vlm_attributes('{"color":"蓝水","description":"白冰冰种观音吊坠"}')

    assert result["color"] == "蓝水"
    assert result["water"] == "冰种"
    assert result["style"] == "吊坠"
    assert result["theme"] == "观音"


def test_visual_color_classifier_uses_pixel_features():
    assert _visual_color_from_signals(
        {
            "cv_features": {"hue_mean": 64, "saturation_mean": 0.195, "value_mean": 0.756, "green_ratio": 0.0},
            "vlm_features": {"object_style": "珠串"},
        },
        {"color_ratios": {"purple": 0.275, "white": 0.786, "red_brown": 0.207}},
        style="珠串",
    ) == "紫罗兰"
    assert _visual_color_from_signals(
        {
            "cv_features": {"hue_mean": 116.8, "saturation_mean": 0.073, "value_mean": 0.277, "green_ratio": 0.029},
            "vlm_features": {"object_style": "手镯"},
        },
        {"color_ratios": {"white": 0.168, "dark": 0.224, "cyan": 0.066, "green": 0.022}},
        style="手镯",
    ) == "无色"
    assert _visual_color_from_signals(
        {
            "cv_features": {"hue_mean": 108.4, "saturation_mean": 0.158, "value_mean": 0.459, "green_ratio": 0.035},
            "vlm_features": {"object_style": "挂件"},
        },
        {"color_ratios": {"cyan": 0.411, "blue": 0.004, "dark": 0.318, "white": 0.145}},
        style="挂件",
    ) == "蓝水"


def test_visual_color_classifier_preserves_supported_vlm_complex_colors():
    assert _visual_color_from_signals(
        {
            "cv_features": {"hue_mean": 77.9, "saturation_mean": 0.192, "value_mean": 0.462, "green_ratio": 0.0},
            "vlm_features": {"color": "春带彩"},
        },
        {"color_ratios": {"green": 0.155, "purple": 0.163, "red_brown": 0.105, "white": 0.170, "dark": 0.446}},
        current_color="春带彩",
    ) == "春带彩"
    assert _visual_color_from_signals(
        {
            "cv_features": {"hue_mean": 77.4, "saturation_mean": 0.060, "value_mean": 0.281, "green_ratio": 0.077},
            "vlm_features": {"color": "墨翠"},
        },
        {"color_ratios": {"green": 0.077, "cyan": 0.050, "white": 0.051, "dark": 0.347}},
        current_color="墨翠",
    ) == "墨翠"


def test_visual_color_classifier_recovers_common_visual_boundaries():
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 82.5, "saturation_mean": 0.315, "value_mean": 0.584}},
        {"color_ratios": {"green": 0.264, "cyan": 0.123, "white": 0.178, "dark": 0.420}},
        current_color="阳绿",
    ) == "白底青"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 91.9, "saturation_mean": 0.294, "value_mean": 0.449}},
        {"color_ratios": {"green": 0.093, "cyan": 0.296, "white": 0.314, "dark": 0.039}},
        current_color="绿色",
    ) == "飘花"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 95.6, "saturation_mean": 0.310, "value_mean": 0.353}},
        {"color_ratios": {"green": 0.133, "cyan": 0.096, "white": 0.025, "dark": 0.545}},
        current_color="帝王绿",
    ) == "墨翠"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 52.9, "saturation_mean": 0.472, "value_mean": 0.511}},
        {"color_ratios": {"green": 0.505, "cyan": 0.003, "white": 0.039, "dark": 0.167}},
        current_color="阳绿",
    ) == "苹果绿"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 68.0, "saturation_mean": 0.754, "value_mean": 0.488}},
        {"color_ratios": {"green": 0.345, "white": 0.050, "dark": 0.137}},
        current_color="阳绿",
    ) == "阳绿"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 122.4, "saturation_mean": 0.171, "value_mean": 0.566}},
        {"color_ratios": {"purple": 0.052, "cyan": 0.384, "white": 0.095}},
        current_color="紫罗兰",
    ) == "紫罗兰"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 75.9, "saturation_mean": 0.111, "value_mean": 0.388}},
        {"color_ratios": {"green": 0.366, "cyan": 0.174, "white": 0.318, "dark": 0.271}},
        current_color="晴水",
    ) == "晴水"
    assert _visual_color_from_signals(
        {"cv_features": {"hue_mean": 37.1, "saturation_mean": 0.235, "value_mean": 0.572}},
        {"color_ratios": {"green": 0.319, "yellow": 0.444, "red_brown": 0.170, "white": 0.198}},
        current_color="阳绿",
        style="手镯",
    ) == "绿色"


def test_color_pattern_refinement_does_not_narrow_explicit_multicolor():
    color_analysis = _color_analysis_from_attributes("多彩", {"color": "多彩"})

    changed = _refine_color_analysis_with_opencv(
        color_analysis,
        {"color_ratios": {"green": 0.116, "purple": 0.058, "yellow": 0.073, "white": 0.057, "dark": 0.298}},
    )

    assert changed is False
    assert color_analysis["primary"] == "多彩"


def test_visual_water_classifier_uses_transparency_features():
    assert _visual_water_from_signals(
        {"vlm_features": {"transparency": "高透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.239}},
        style="戒面",
        color="晴水",
    ) == "高冰"
    assert _visual_water_from_signals(
        {"vlm_features": {"transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0}},
        style="手镯",
        color="无色",
    ) == "玻璃种"


def test_visual_water_classifier_handles_complex_color_families():
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "高透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 367.115}},
        style="挂件",
        color="飘花",
    ) == "高冰"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "细糯", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 59.766}},
        style="珠串",
        color="豆绿",
    ) == "豆种"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 363.448}},
        style="挂件",
        color="冰黄",
    ) == "冰种"


def test_visual_water_classifier_handles_high_water_boundaries():
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "高冰", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.218, "texture": 88.791, "brightness": 118.739}},
        style="挂件",
        color="白冰",
    ) == "冰种"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.228, "texture": 58.182, "brightness": 109.902}},
        style="戒面",
        color="紫罗兰",
    ) == "高冰"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "高透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 299.451, "brightness": 110.059}},
        style="挂件",
        color="黄翡",
    ) == "高冰"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "高透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 203.002, "brightness": 87.683}},
        style="挂件",
        color="黄翡",
    ) == "冰种"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.0, "texture": 301.649, "brightness": 94.969}},
        style="蛋面",
        color="苹果绿",
    ) == "高冰"
    assert _visual_water_from_signals(
        {"vlm_features": {"water": "冰种", "transparency": "半透", "grain": "无明显", "texture_fineness": "细腻"}},
        {"water_features": {"clarity_score": 0.044, "texture": 117.694, "brightness": 103.508}},
        style="挂件",
        color="苹果绿",
    ) == "糯冰"


def test_visual_style_classifier_handles_shape_boundaries():
    assert _visual_style_from_signals(
        {"vlm_features": {"object_style": "牌子"}},
        {"style_features": {"hole_ratio": 0.9, "circularity": 0.5}},
        color="黄翡",
        current_style="挂件",
        current_theme="龙",
    ) == "吊坠"
    assert _visual_style_from_signals(
        {"vlm_features": {"object_style": "蛋面"}},
        {"style_features": {"hole_ratio": 0.84, "aspect_ratio": 0.09}},
        color="阳绿",
        current_style="蛋面",
        current_theme="",
    ) == "戒指"
    assert _visual_style_from_signals(
        {"vlm_features": {"object_style": "蛋面"}},
        {"style_features": {"hole_ratio": 0.84, "circularity": 0.087, "aspect_ratio": 0.93}},
        color="阳绿",
        current_style="蛋面",
        current_theme="",
    ) == "戒指"
    assert _visual_style_from_signals(
        {"vlm_features": {"object_style": "吊坠"}},
        {"style_features": {}},
        color="白冰",
        current_style="吊坠",
        current_theme="",
    ) == "吊坠"


def test_visual_theme_classifier_handles_ruyi_shape():
    assert _visual_theme_from_signals(
        {"vlm_features": {"shape_theme": "其他"}},
        {"style_features": {"aspect_ratio": 2.46}},
        color="辣绿",
        style="挂件",
        current_theme="其他",
    ) == "如意"
    assert _visual_theme_from_signals(
        {"vlm_features": {"shape_theme": "其他"}},
        {"style_features": {"aspect_ratio": 0.49, "hole_ratio": 0.99, "circularity": 0.51}},
        color="春带彩",
        style="吊坠",
        current_theme="其他",
    ) == "如意"


def test_yolo_label_maps_style_and_theme_from_english_label():
    style, theme = jade_attributes_from_yolo_label("jade_dragon_plaque")

    assert style == "吊坠"
    assert theme == "龙牌"


def test_yolo_label_maps_style_and_theme_from_chinese_label():
    style, theme = jade_attributes_from_yolo_label("山水牌")

    assert style == "吊坠"
    assert theme == "山水"


def test_multimodal_merge_combines_text_and_image_attributes():
    text = JadeAnalysis(
        color="白冰",
        water="冰种",
        evidence_texts=["白冰冰种"],
        confidence=0.42,
        signals={
            "attribute_sources": {
                "color": {"source": "speech", "method": "keyword", "value": "白冰"},
                "water": {"source": "speech", "method": "keyword", "value": "冰种"},
            }
        },
    )
    image = JadeAnalysis(
        style="吊坠",
        theme="龙牌",
        evidence_image_paths=["dragon-plaque.jpg"],
        detections=[{"label": "jade_dragon_plaque", "confidence": 0.88}],
        confidence=0.5,
        signals={
            "attribute_sources": {
                "style": {"source": "yolo", "method": "detection-label", "value": "吊坠"},
                "theme": {"source": "yolo", "method": "detection-label", "value": "龙牌"},
            }
        },
    )

    result = merge_jade_analysis(text, image, use_feedback_learning=False)

    assert result.color == "白冰"
    assert result.water == "冰种"
    assert result.style == "吊坠"
    assert result.theme == "龙牌"
    assert result.evidence_texts == ["白冰冰种"]
    assert result.evidence_image_paths == ["dragon-plaque.jpg"]
