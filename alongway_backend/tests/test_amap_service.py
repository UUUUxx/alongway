from app.services.amap_service import normalize_amap_poi


def test_normalize_amap_poi_keeps_food():
    raw = {
        "id": "B001",
        "name": "测试餐厅",
        "type": "餐饮服务;中餐厅;中餐厅",
        "typecode": "050100",
        "address": "校园商业街",
        "location": "114.126,30.459",
        "biz_ext": {"rating": "4.6", "cost": "18"},
    }

    poi = normalize_amap_poi(raw, "餐厅")

    assert poi is not None
    assert poi.source_id == "B001"
    assert poi.type == "food"
    assert poi.category_major == "餐饮服务"


def test_normalize_amap_poi_filters_parking():
    raw = {
        "id": "P001",
        "name": "测试停车场",
        "type": "交通设施服务;停车场;公共停车场",
        "typecode": "150900",
        "address": "校园东门",
        "location": "114.126,30.459",
    }

    poi = normalize_amap_poi(raw, "停车")

    assert poi is None


def test_normalize_amap_poi_does_not_keep_only_because_keyword_matches():
    raw = {
        "id": "M001",
        "name": "四喜自助棋牌",
        "type": "医疗保健服务;专科医院;口腔医院",
        "typecode": "090202",
        "address": "珞喻东路",
        "location": "114.426,30.514",
        "biz_ext": {"rating": "4.2"},
    }

    poi = normalize_amap_poi(raw, "娱乐")

    assert poi is None
