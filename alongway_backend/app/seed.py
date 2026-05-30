"""
Seed script to initialize MVP database with mock data.
18 POIs + 26 deals across 武汉 (HUST) and 上海 (Fudan/Wujiaochang),
covering diverse price×distance scenarios for multi-city testing.
"""
import json

from sqlalchemy.orm import Session

from app.database import get_engine, get_session_factory
from app.models import Base, Deal, POI


# =============================================================================
# POIs — 12 武汉 (HUST campus + nearby) + 6 上海 (Fudan/Wujiaochang)
# =============================================================================
POIS_DATA = [
    # ======================== 武汉 — 校园核心区 (HUST) ========================
    {
        "poi_id": "poi_001",
        "name": "韵苑奶茶铺",
        "type": "drink",
        "address": "华中科技大学韵苑生活区商业街1层",
        "location": "韵苑生活区·武汉",
        "longitude": 114.41520,
        "latitude": 30.51520,
        "rating": 4.5,
        "cost": 18,
        "source_keyword": "奶茶",
    },
    {
        "poi_id": "poi_002",
        "name": "东九咖啡角",
        "type": "drink",
        "address": "华中科技大学东九教学楼A座旁",
        "location": "东九教学楼·武汉",
        "longitude": 114.42180,
        "latitude": 30.51140,
        "rating": 4.8,
        "cost": 32,
        "source_keyword": "咖啡",
    },
    {
        "poi_id": "poi_003",
        "name": "西十二轻食窗口",
        "type": "food",
        "address": "华中科技大学西十二教学楼负一层",
        "location": "西十二教学楼·武汉",
        "longitude": 114.41070,
        "latitude": 30.51810,
        "rating": 4.2,
        "cost": 12,
        "source_keyword": "简餐",
    },
    {
        "poi_id": "poi_004",
        "name": "图书馆水果切",
        "type": "food",
        "address": "华中科技大学主图书馆东门外",
        "location": "主图书馆·武汉",
        "longitude": 114.41430,
        "latitude": 30.51260,
        "rating": 4.6,
        "cost": 16,
        "source_keyword": "水果",
    },
    {
        "poi_id": "poi_005",
        "name": "紫菘快递站",
        "type": "express",
        "address": "华中科技大学紫菘学生公寓服务点",
        "location": "紫菘生活区·武汉",
        "longitude": 114.40710,
        "latitude": 30.51490,
        "rating": 4.1,
        "cost": None,
        "source_keyword": "快递",
    },
    {
        "poi_id": "poi_006",
        "name": "百景园热卤饭",
        "type": "food",
        "address": "华中科技大学百景园食堂2层",
        "location": "百景园·武汉",
        "longitude": 114.41810,
        "latitude": 30.51450,
        "rating": 4.4,
        "cost": 19,
        "source_keyword": "简餐",
    },
    # ======================== 武汉 — 校园中环 ========================
    {
        "poi_id": "poi_007",
        "name": "集贸打印社",
        "type": "service",
        "address": "华中科技大学集贸市场南侧",
        "location": "集贸市场·武汉",
        "longitude": 114.41220,
        "latitude": 30.51660,
        "rating": 4.3,
        "cost": 6,
        "source_keyword": "打印",
    },
    {
        "poi_id": "poi_008",
        "name": "东操能量饮品",
        "type": "drink",
        "address": "华中科技大学东操场西门",
        "location": "东操场·武汉",
        "longitude": 114.42460,
        "latitude": 30.51690,
        "rating": 4.0,
        "cost": 9,
        "source_keyword": "饮品",
    },
    {
        "poi_id": "poi_009",
        "name": "沁苑便当铺",
        "type": "food",
        "address": "华中科技大学沁苑生活区北门",
        "location": "沁苑生活区·武汉",
        "longitude": 114.42620,
        "latitude": 30.50860,
        "rating": 4.7,
        "cost": 24,
        "source_keyword": "简餐",
    },
    {
        "poi_id": "poi_010",
        "name": "青年园咖啡车",
        "type": "drink",
        "address": "华中科技大学青年园入口",
        "location": "青年园·武汉",
        "longitude": 114.41670,
        "latitude": 30.51080,
        "rating": 4.9,
        "cost": 28,
        "source_keyword": "咖啡",
    },
    # ======================== 武汉 — 校园边缘+校外 ========================
    {
        "poi_id": "poi_011",
        "name": "南一门鲜果铺",
        "type": "food",
        "address": "华中科技大学南一门内侧",
        "location": "南一门·武汉",
        "longitude": 114.40420,
        "latitude": 30.50980,
        "rating": 4.2,
        "cost": 10,
        "source_keyword": "水果",
    },
    {
        "poi_id": "poi_012",
        "name": "韵苑智能取件柜",
        "type": "express",
        "address": "华中科技大学韵苑宿舍13栋旁",
        "location": "韵苑生活区·武汉",
        "longitude": 114.41480,
        "latitude": 30.51590,
        "rating": 4.0,
        "cost": None,
        "source_keyword": "取件",
    },
    # ======================== 上海 — 复旦大学/五角场区域 ========================
    {
        "poi_id": "poi_013",
        "name": "复旦奶茶铺",
        "type": "drink",
        "address": "杨浦区邯郸路220号复旦大学南区",
        "location": "复旦大学南区·上海",
        "longitude": 121.502,
        "latitude": 31.296,
        "rating": 4.6,
        "cost": 16,
        "source_keyword": "奶茶",
    },
    {
        "poi_id": "poi_014",
        "name": "五角场星巴克",
        "type": "drink",
        "address": "杨浦区淞沪路77号万达广场1层",
        "location": "五角场万达·上海",
        "longitude": 121.513,
        "latitude": 31.301,
        "rating": 4.4,
        "cost": 35,
        "source_keyword": "咖啡",
    },
    {
        "poi_id": "poi_015",
        "name": "大学路简餐吧",
        "type": "food",
        "address": "杨浦区大学路128号",
        "location": "大学路·上海",
        "longitude": 121.507,
        "latitude": 31.299,
        "rating": 4.5,
        "cost": 28,
        "source_keyword": "简餐",
    },
    {
        "poi_id": "poi_016",
        "name": "江湾便利店",
        "type": "convenience",
        "address": "杨浦区国权路500号",
        "location": "国权路·上海",
        "longitude": 121.509,
        "latitude": 31.294,
        "rating": 4.1,
        "cost": 10,
        "source_keyword": "便利店",
    },
    {
        "poi_id": "poi_017",
        "name": "复旦北区快递站",
        "type": "express",
        "address": "杨浦区武东路57号复旦大学北区",
        "location": "复旦大学北区·上海",
        "longitude": 121.498,
        "latitude": 31.303,
        "rating": 4.0,
        "cost": None,
        "source_keyword": "快递",
    },
    {
        "poi_id": "poi_018",
        "name": "万达影城",
        "type": "entertainment",
        "address": "杨浦区淞沪路77号万达广场5层",
        "location": "五角场万达·上海",
        "longitude": 121.514,
        "latitude": 31.302,
        "rating": 4.5,
        "cost": 45,
        "source_keyword": "电影院",
    },
]


# =============================================================================
# Deals — 18 武汉 + 8 上海 = 26 total
# 覆盖场景: 价格高但近 / 价格低但远 / 价格高且远 / 价格低且近 / 无团购
# =============================================================================
DEALS_DATA = [
    # ========== 武汉 deals (poi_001~poi_012, deal_001~deal_018) ==========

    # --- poi_001 韵苑奶茶铺 (near dorm, moderate price — 近且适中) ---
    {
        "deal_id": "deal_001",
        "poi_id": "poi_001",
        "name": "韵苑奶茶铺",
        "category": "奶茶",
        "deal_title": "近距离厚乳拿铁单杯券",
        "price": 21.9,
        "original_price": 28,
        "included_items": ["厚乳拿铁1杯", "珍珠或椰果任选1份"],
        "additional_information": "距离宿舍近，价格偏高，适合赶时间",
        "valid_time": "10:00-22:00",
        "rating": 4.6,
        "monthly_sales": 180,
        "reviews": ["出杯快", "离宿舍近", "甜度稳定"],
        "business_time": "09:30-22:30",
    },
    {
        "deal_id": "deal_002",
        "poi_id": "poi_001",
        "name": "韵苑奶茶铺",
        "category": "奶茶",
        "deal_title": "双拼水果茶下午券",
        "price": 17.5,
        "original_price": 24,
        "included_items": ["水果茶1杯", "脆波波1份"],
        "additional_information": "14:00后可用，部分新品不可用",
        "valid_time": "14:00-21:30",
        "rating": 4.4,
        "monthly_sales": 260,
        "reviews": ["水果量足", "排队时间短"],
        "business_time": "09:30-22:30",
    },

    # --- poi_002 东九咖啡角 (价格高但近 — HIGH price, CLOSE) ---
    {
        "deal_id": "deal_003",
        "poi_id": "poi_002",
        "name": "东九咖啡角",
        "category": "咖啡",
        "deal_title": "东九精品美式早课券",
        "price": 26.0,
        "original_price": 34,
        "included_items": ["冰美式或热美式1杯", "浓缩加量1次"],
        "additional_information": "离东九很近但单价较高 — 价格高但近",
        "valid_time": "07:30-11:00",
        "rating": 4.9,
        "monthly_sales": 90,
        "reviews": ["咖啡香气好", "适合早八"],
        "business_time": "07:30-19:30",
    },
    {
        "deal_id": "deal_004",
        "poi_id": "poi_002",
        "name": "东九咖啡角",
        "category": "咖啡",
        "deal_title": "燕麦拿铁加烘焙点心套券",
        "price": 39.0,
        "original_price": 48,
        "included_items": ["燕麦拿铁1杯", "司康1个"],
        "additional_information": "高价高评分，适合预算宽松 — 价格高但近",
        "valid_time": "09:00-18:00",
        "rating": 4.8,
        "monthly_sales": 70,
        "reviews": ["环境安静", "点心不错"],
        "business_time": "07:30-19:30",
    },

    # --- poi_003 西十二轻食窗口 (价格低但稍远 — LOW price, MID distance) ---
    {
        "deal_id": "deal_005",
        "poi_id": "poi_003",
        "name": "西十二轻食窗口",
        "category": "简餐",
        "deal_title": "鸡胸肉谷物碗低价券",
        "price": 13.9,
        "original_price": 22,
        "included_items": ["鸡胸肉谷物碗1份", "无糖茶1瓶"],
        "additional_information": "距离稍远但价格低 — 价格低但远",
        "valid_time": "10:30-13:30",
        "rating": 4.1,
        "monthly_sales": 520,
        "reviews": ["便宜管饱", "口味清淡"],
        "business_time": "10:30-20:00",
    },
    {
        "deal_id": "deal_006",
        "poi_id": "poi_003",
        "name": "西十二轻食窗口",
        "category": "简餐",
        "deal_title": "番茄牛肉意面学生券",
        "price": 18.8,
        "original_price": 26,
        "included_items": ["番茄牛肉意面1份"],
        "additional_information": "晚餐时段可用",
        "valid_time": "16:30-19:30",
        "rating": 4.3,
        "monthly_sales": 310,
        "reviews": ["出餐稳定", "分量适中"],
        "business_time": "10:30-20:00",
    },

    # --- poi_004 图书馆水果切 (价格低且近 — LOW price, CLOSE) ---
    {
        "deal_id": "deal_007",
        "poi_id": "poi_004",
        "name": "图书馆水果切",
        "category": "水果",
        "deal_title": "图书馆鲜切果盒补给券",
        "price": 15.9,
        "original_price": 23,
        "included_items": ["当日鲜切果盒1份", "叉勺1套"],
        "additional_information": "离图书馆近，价格实惠 — 价格低且近",
        "valid_time": "11:00-20:30",
        "rating": 4.7,
        "monthly_sales": 220,
        "reviews": ["水果新鲜", "复习间隙方便"],
        "business_time": "10:00-21:00",
    },

    # --- poi_005 紫菘快递站 (服务类, 低价格) ---
    {
        "deal_id": "deal_008",
        "poi_id": "poi_005",
        "name": "紫菘快递站",
        "category": "快递",
        "deal_title": "寄件纸箱胶带组合券",
        "price": 6.8,
        "original_price": 10,
        "included_items": ["小号纸箱1个", "胶带使用1次"],
        "additional_information": "适合顺路寄件，不含运费",
        "valid_time": "09:00-20:00",
        "rating": 4.0,
        "monthly_sales": 160,
        "reviews": ["打包方便", "人多时要排队"],
        "business_time": "09:00-20:30",
    },

    # --- poi_006 百景园热卤饭 (价格高但近, high sales — 价格高但近) ---
    {
        "deal_id": "deal_009",
        "poi_id": "poi_006",
        "name": "百景园热卤饭",
        "category": "简餐",
        "deal_title": "热卤鸡腿饭午餐券",
        "price": 19.9,
        "original_price": 28,
        "included_items": ["鸡腿饭1份", "例汤1碗"],
        "additional_information": "近主路，午高峰可能排队",
        "valid_time": "11:00-13:20",
        "rating": 4.5,
        "monthly_sales": 780,
        "reviews": ["销量高", "口味重"],
        "business_time": "10:30-20:30",
    },
    {
        "deal_id": "deal_010",
        "poi_id": "poi_006",
        "name": "百景园热卤饭",
        "category": "简餐",
        "deal_title": "香菇卤肉饭晚间券",
        "price": 16.8,
        "original_price": 24,
        "included_items": ["香菇卤肉饭1份"],
        "additional_information": "晚餐低价，评分中等",
        "valid_time": "17:00-20:00",
        "rating": 4.2,
        "monthly_sales": 640,
        "reviews": ["性价比高", "偏油"],
        "business_time": "10:30-20:30",
    },

    # --- poi_007 集贸打印社 (低价格, near campus) ---
    {
        "deal_id": "deal_011",
        "poi_id": "poi_007",
        "name": "集贸打印社",
        "category": "打印",
        "deal_title": "黑白打印二十页券",
        "price": 3.9,
        "original_price": 6,
        "included_items": ["黑白A4打印20页"],
        "additional_information": "不含装订，适合课前顺路打印",
        "valid_time": "08:00-22:00",
        "rating": 4.3,
        "monthly_sales": 430,
        "reviews": ["速度快", "文件清晰"],
        "business_time": "08:00-22:30",
    },
    {
        "deal_id": "deal_012",
        "poi_id": "poi_007",
        "name": "集贸打印社",
        "category": "打印",
        "deal_title": "彩印证件照排版券",
        "price": 12.0,
        "original_price": 18,
        "included_items": ["一寸证件照排版1张", "彩印1页"],
        "additional_information": "需提前上传文件",
        "valid_time": "09:00-21:00",
        "rating": 4.4,
        "monthly_sales": 120,
        "reviews": ["排版细致", "老板会提醒尺寸"],
        "business_time": "08:00-22:30",
    },

    # --- poi_008 东操能量饮品 (价格低但远 — LOW price, FAR) ---
    {
        "deal_id": "deal_013",
        "poi_id": "poi_008",
        "name": "东操能量饮品",
        "category": "饮品",
        "deal_title": "运动电解质水低价券",
        "price": 7.9,
        "original_price": 12,
        "included_items": ["电解质水1瓶"],
        "additional_information": "距离偏远但价格低 — 价格低但远",
        "valid_time": "08:30-21:30",
        "rating": 4.0,
        "monthly_sales": 560,
        "reviews": ["便宜", "运动后方便"],
        "business_time": "08:00-22:00",
    },

    # --- poi_009 沁苑便当铺 (价格高但远 — HIGH price, FAR) ---
    {
        "deal_id": "deal_014",
        "poi_id": "poi_009",
        "name": "沁苑便当铺",
        "category": "简餐",
        "deal_title": "照烧鸡排便当券",
        "price": 22.8,
        "original_price": 30,
        "included_items": ["照烧鸡排便当1份", "海带汤1份"],
        "additional_information": "高评分但离主图书馆较远 — 价格高但远",
        "valid_time": "10:30-19:30",
        "rating": 4.8,
        "monthly_sales": 210,
        "reviews": ["鸡排酥", "包装好"],
        "business_time": "10:00-20:00",
    },

    # --- poi_010 青年园咖啡车 (价格高且远 — HIGH price, FAR, low sales) ---
    {
        "deal_id": "deal_015",
        "poi_id": "poi_010",
        "name": "青年园咖啡车",
        "category": "咖啡",
        "deal_title": "手冲咖啡体验券",
        "price": 31.0,
        "original_price": 42,
        "included_items": ["当日豆单手冲1杯"],
        "additional_information": "评分高但销量低 — 价格高且远",
        "valid_time": "13:00-18:00",
        "rating": 4.9,
        "monthly_sales": 45,
        "reviews": ["风味特别", "适合不赶时间"],
        "business_time": "09:30-19:00",
    },

    # --- poi_011 南一门鲜果铺 (价格低但远 — LOW price, FAR) ---
    {
        "deal_id": "deal_016",
        "poi_id": "poi_011",
        "name": "南一门鲜果铺",
        "category": "水果",
        "deal_title": "远距离香蕉酸奶杯券",
        "price": 8.8,
        "original_price": 15,
        "included_items": ["香蕉酸奶杯1份"],
        "additional_information": "价格低但离校园中轴较远 — 价格低但远",
        "valid_time": "10:00-21:00",
        "rating": 4.1,
        "monthly_sales": 300,
        "reviews": ["便宜", "需要绕到南门"],
        "business_time": "09:00-21:30",
    },

    # --- poi_012 韵苑智能取件柜 (服务类, 低价格) ---
    {
        "deal_id": "deal_017",
        "poi_id": "poi_012",
        "name": "韵苑智能取件柜",
        "category": "取件",
        "deal_title": "临时存包两小时券",
        "price": 2.0,
        "original_price": 4,
        "included_items": ["小柜存放2小时"],
        "additional_information": "适合取件后短时存放",
        "valid_time": "08:00-23:00",
        "rating": 4.0,
        "monthly_sales": 150,
        "reviews": ["位置好找", "柜门偶尔紧"],
        "business_time": "00:00-23:59",
    },
    {
        "deal_id": "deal_018",
        "poi_id": "poi_012",
        "name": "韵苑智能取件柜",
        "category": "取件",
        "deal_title": "大件包裹代搬券",
        "price": 9.9,
        "original_price": 16,
        "included_items": ["韵苑范围内大件代搬1次"],
        "additional_information": "需提前15分钟预约",
        "valid_time": "10:00-20:00",
        "rating": 4.2,
        "monthly_sales": 80,
        "reviews": ["搬运省力", "预约后较准时"],
        "business_time": "09:00-21:00",
    },

    # ========== 上海 deals (poi_013~poi_018, deal_019~deal_026) ==========

    # --- poi_013 复旦奶茶铺 (near campus, moderate price) ---
    {
        "deal_id": "deal_019",
        "poi_id": "poi_013",
        "name": "复旦奶茶铺",
        "category": "奶茶",
        "deal_title": "复旦招牌奶茶单杯券",
        "price": 15.9,
        "original_price": 22,
        "included_items": ["招牌奶茶1杯", "珍珠1份"],
        "additional_information": "复旦南区内，步行即达",
        "valid_time": "09:00-22:00",
        "rating": 4.5,
        "monthly_sales": 320,
        "reviews": ["就在宿舍楼下", "下课来一杯方便"],
        "business_time": "09:00-22:30",
    },
    {
        "deal_id": "deal_020",
        "poi_id": "poi_013",
        "name": "复旦奶茶铺",
        "category": "奶茶",
        "deal_title": "双人水果茶套餐",
        "price": 24.9,
        "original_price": 36,
        "included_items": ["水果茶2杯", "脆波波2份"],
        "additional_information": "适合和同学拼单",
        "valid_time": "10:00-21:30",
        "rating": 4.7,
        "monthly_sales": 190,
        "reviews": ["量大划算", "水果新鲜"],
        "business_time": "09:00-22:30",
    },

    # --- poi_014 五角场星巴克 (价格高但稍远 — HIGH price, MID distance) ---
    {
        "deal_id": "deal_021",
        "poi_id": "poi_014",
        "name": "五角场星巴克",
        "category": "咖啡",
        "deal_title": "拿铁+蛋糕下午茶",
        "price": 38.0,
        "original_price": 49,
        "included_items": ["中杯拿铁1杯", "芝士蛋糕1块"],
        "additional_information": "五角场万达内，距复旦步行约15分钟 — 价格高,距离适中",
        "valid_time": "14:00-18:00",
        "rating": 4.5,
        "monthly_sales": 150,
        "reviews": ["环境好", "适合自习", "略贵"],
        "business_time": "07:30-22:00",
    },

    # --- poi_015 大学路简餐吧 (价格适中的上海网红店) ---
    {
        "deal_id": "deal_022",
        "poi_id": "poi_015",
        "name": "大学路简餐吧",
        "category": "简餐",
        "deal_title": "大学路招牌意面套餐",
        "price": 29.9,
        "original_price": 42,
        "included_items": ["奶油培根意面1份", "沙拉1份", "柠檬水1杯"],
        "additional_information": "大学路网红店，步行10分钟",
        "valid_time": "11:00-14:00,17:00-20:30",
        "rating": 4.6,
        "monthly_sales": 180,
        "reviews": ["网红打卡点", "意面好吃", "饭点人多"],
        "business_time": "10:30-21:00",
    },
    {
        "deal_id": "deal_023",
        "poi_id": "poi_015",
        "name": "大学路简餐吧",
        "category": "简餐",
        "deal_title": "双人晚餐套餐",
        "price": 59.9,
        "original_price": 88,
        "included_items": ["牛排1份", "意大利面1份", "红酒2杯"],
        "additional_information": "价格较高但口碑好",
        "valid_time": "17:00-20:30",
        "rating": 4.7,
        "monthly_sales": 60,
        "reviews": ["约会圣地", "值这个价"],
        "business_time": "10:30-21:00",
    },

    # --- poi_016 江湾便利店 (价格低距离近 — LOW price, CLOSE) ---
    {
        "deal_id": "deal_024",
        "poi_id": "poi_016",
        "name": "江湾便利店",
        "category": "便利店",
        "deal_title": "早餐饭团+豆浆套餐",
        "price": 5.9,
        "original_price": 10,
        "included_items": ["金枪鱼饭团1个", "甜豆浆1杯"],
        "additional_information": "早课路上方便买 — 价格低且近",
        "valid_time": "06:30-09:30",
        "rating": 4.2,
        "monthly_sales": 550,
        "reviews": ["便宜省时", "每天都要买的"],
        "business_time": "06:00-24:00",
    },

    # --- poi_017 复旦北区快递站 (服务类, 低价格) ---
    {
        "deal_id": "deal_025",
        "poi_id": "poi_017",
        "name": "复旦北区快递站",
        "category": "快递",
        "deal_title": "寄件打包服务券",
        "price": 5.0,
        "original_price": 8,
        "included_items": ["快递打包1次", "小号纸箱1个"],
        "additional_information": "不含运费，复旦北区可取",
        "valid_time": "09:00-20:00",
        "rating": 4.1,
        "monthly_sales": 120,
        "reviews": ["方便", "比外面便宜"],
        "business_time": "09:00-20:00",
    },

    # --- poi_018 万达影城 (上海, 价格高距离远 — HIGH price, FAR) ---
    {
        "deal_id": "deal_026",
        "poi_id": "poi_018",
        "name": "万达影城",
        "category": "娱乐",
        "deal_title": "2D通兑单人电影票",
        "price": 39.9,
        "original_price": 60,
        "included_items": ["2D电影票1张", "小份爆米花1份"],
        "additional_information": "五角场万达，距复旦步行约15-20分钟 — 价格高且远",
        "valid_time": "10:00-23:00",
        "rating": 4.6,
        "monthly_sales": 350,
        "reviews": ["屏幕大", "性价比不错", "周末人多"],
        "business_time": "09:30-24:00",
    },
    # poi_005/poi_012/poi_017 — 仅1个deal或0个deal的服务类POI
]


def seed_pois(db: Session) -> None:
    """Seed POI table with 18 mock POIs (12 Wuhan + 6 Shanghai)."""
    for poi_data in POIS_DATA:
        db.merge(POI(**poi_data))
    db.commit()
    print(f"Seeded {len(POIS_DATA)} POIs")


def seed_deals(db: Session) -> None:
    """Seed Deal table with 26 mock deals (18 Wuhan + 8 Shanghai)."""
    for deal_data in DEALS_DATA:
        serializable = {
            **deal_data,
            "included_items": json.dumps(deal_data["included_items"], ensure_ascii=False),
            "reviews": json.dumps(deal_data["reviews"], ensure_ascii=False),
        }
        db.merge(Deal(**serializable))
    db.commit()
    print(f"Seeded {len(DEALS_DATA)} Deals")


def init_db() -> None:
    """Initialize database and seed data."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("Database tables created")

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        seed_pois(db)
        seed_deals(db)
        print("Mock data seeded successfully")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
