from app.services.live_room_name_service import extract_live_room_name


def test_extract_live_room_name_ignores_phone_status_carriers() -> None:
    assert extract_live_room_name(["中国移动HD1中国联通HD"]) == ""


def test_extract_live_room_name_ignores_mixed_status_bar_noise() -> None:
    assert extract_live_room_name(["12:08 中国移动 HD 5G 98%"]) == ""


def test_extract_live_room_name_keeps_known_jade_room() -> None:
    assert extract_live_room_name(["浅玩翡翠"]) == "浅玩翡翠-2号店"

