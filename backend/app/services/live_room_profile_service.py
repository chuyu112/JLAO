"""Live room profile configuration service."""


_SPECIAL_ATTENTION_LIVE_ROOM_NAMES = {
    "浅玩翡翠-2号店",
    "菲菲珠宝闲置店",
    "佳心珠宝回流寄售",
    "且慢翡翠珠宝定制",
    "闲值珠宝",
    "春风翡翠寄售回流",
}

_SPECIAL_ATTENTION_LIVE_ROOM_CANONICAL_BY_LABEL = {
    name: name
    for name in _SPECIAL_ATTENTION_LIVE_ROOM_NAMES
}


# WeChat Channels light badge names and aliases used by comment OCR parsing.
_VIDEO_ACCOUNT_LIGHT_BADGE_NAMES = {
    "富婆",
    "几级富婆",
    "某富婆",
}

_LIGHT_BADGE_CANONICAL_BY_LABEL = {
    "富婆": "某富婆",
    "几级富婆": "某富婆",
    "某富婆": "某富婆",
}


def live_badge_catalog() -> tuple[set[str], dict[str, str]]:
    return _VIDEO_ACCOUNT_LIGHT_BADGE_NAMES, _LIGHT_BADGE_CANONICAL_BY_LABEL


def live_room_catalog() -> tuple[set[str], dict[str, str]]:
    return _SPECIAL_ATTENTION_LIVE_ROOM_NAMES, _SPECIAL_ATTENTION_LIVE_ROOM_CANONICAL_BY_LABEL


def is_special_attention_live_room(name: str) -> bool:
    return name in _SPECIAL_ATTENTION_LIVE_ROOM_CANONICAL_BY_LABEL
