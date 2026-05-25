RISK_REWRITES = {
    "肯定升值": "这件更适合喜欢长期佩戴和欣赏的用户，价值感主要看颜色、种水和完美度。",
    "保证升值": "这件的优势在颜色和种水表现，建议从佩戴效果和品质细节来介绍。",
    "稳赚不赔": "翡翠购买要以喜欢和适合为主，不建议做收益承诺。",
    "全网最低": "今天这个价格比较有诚意，但不要做绝对化对比。",
    "绝对无瑕": "这件整体品相不错，但天然翡翠建议把棉、纹、裂说明清楚。",
    "戴了能转运": "可以说题材寓意好，但不要承诺功效。",
}


def find_risk_terms(text: str) -> list[str]:
    return [term for term in RISK_REWRITES if term in text]


def rewrite_if_risky(text: str) -> tuple[str, str, list[str]]:
    terms = find_risk_terms(text)
    if not terms:
        return text, "低", []

    rewritten = text
    for term in terms:
        rewritten = rewritten.replace(term, RISK_REWRITES[term])

    risk_level = "高" if any(term in ["肯定升值", "保证升值", "稳赚不赔", "戴了能转运"] for term in terms) else "中"
    return rewritten, risk_level, terms

