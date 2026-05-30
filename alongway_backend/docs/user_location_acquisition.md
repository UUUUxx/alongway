# 用户位置获取 — User Location Acquisition

## 概述

后端 `POST /api/plan` 接口的 `start_location` 和 `end_location` 字段需要经纬度坐标。
本文档说明各平台如何获取用户位置并传递给后端。

---

## 1. 浏览器端 (Web)

### API: `navigator.geolocation.getCurrentPosition()`

```javascript
// 前端代码示例
function getUserLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("浏览器不支持定位"));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          longitude: position.coords.longitude,  // WGS-84
          latitude: position.coords.latitude,
          accuracy: position.coords.accuracy,     // 精度(米)
        });
      },
      (error) => {
        switch (error.code) {
          case error.PERMISSION_DENIED:
            reject(new Error("用户拒绝了定位请求"));
            break;
          case error.POSITION_UNAVAILABLE:
            reject(new Error("位置信息不可用"));
            break;
          case error.TIMEOUT:
            reject(new Error("定位请求超时"));
            break;
        }
      },
      {
        enableHighAccuracy: true,  // 移动设备会用GPS, 耗电更多
        timeout: 10000,            // 10秒超时
        maximumAge: 30000,         // 缓存30秒
      }
    );
  });
}
```

### 注意事项
- **需要 HTTPS**（localhost 除外）
- 用户首次访问会看到浏览器权限弹窗
- 返回的是 WGS-84 坐标，可直接用于高德 API
- `enableHighAccuracy: true` 在手机上会用 GPS（更准但更耗电）
- **Fallback**: 如果用户拒绝定位，可调用高德 IP 定位 API:
  `GET https://restapi.amap.com/v3/ip?key=YOUR_KEY`

### 封装到 PlanRequest

```javascript
const location = await getUserLocation();
const request = {
  user_query: "帮我规划从宿舍到图书馆的路线",
  start_location: {
    name: "我的位置",
    address: "",
    location: `${location.longitude},${location.latitude}`,
    longitude: location.longitude,
    latitude: location.latitude,
    accuracy_meters: location.accuracy,
    source: "browser_gps"
  },
  end_location: { /* 用户输入的目的地 */ },
  city: "武汉",
  travel_mode: "walking",
  preferences: {
    prefer_low_price: true,
    prefer_fast_arrival: false,
    // ...
  }
};
```

---

## 2. 微信小程序

### API: `wx.getLocation()`

```javascript
// 需要在 app.json 中声明
// "requiredPrivateInfos": ["getLocation"],
// "permission": { "scope.userLocation": { "desc": "用于路线规划" } }

wx.getLocation({
  type: 'wgs84',     // 或 'gcj02' (火星坐标,高德可直接用)
  success(res) {
    const { latitude, longitude, accuracy } = res;
    // 填充到 PlanRequest.start_location
  },
  fail(err) {
    console.error('定位失败', err);
  }
});
```

### 注意事项
- 需要在 `app.json` 声明 `requiredPrivateInfos: ["getLocation"]`
- `type: 'wgs84'` — GPS 原始坐标; `type: 'gcj02'` — 高德火星坐标
- 后端/高德 API 内部会做坐标转换，两种都可以

---

## 3. React Native (移动端 App)

```javascript
import Geolocation from '@react-native-community/geolocation';
// 或使用 expo-location

Geolocation.getCurrentPosition(
  (position) => {
    const { latitude, longitude } = position.coords;
    // 发送到 POST /api/plan
  },
  (error) => console.error(error),
  { enableHighAccuracy: true, timeout: 15000 }
);
```

---

## 4. Flutter (移动端 App)

```dart
import 'package:geolocator/geolocator.dart';

Position position = await Geolocator.getCurrentPosition(
  desiredAccuracy: LocationAccuracy.high,
);
// position.longitude, position.latitude
```

---

## 5. 数据流总结

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│  浏览器    │────▶│  FastAPI      │────▶│  Agent Service│
│ /小程序    │     │  /api/plan    │     │  (外部)       │
│ /App      │     │  + debug 日志  │     │              │
└──────────┘     └───────────────┘     └──────────────┘
   │                                        │
   │ navigator.geolocation                  │ 调用
   │ wx.getLocation                         ▼
   │ geolocator                    ┌──────────────────┐
   └──────────────────────────────▶│ /internal/pois    │
                                   │ /internal/deals   │
                                   │ /internal/route   │
                                   └──────────────────┘
```

### 前端 → 后端
1. 前端通过定位 API 获取 GPS 坐标 (WGS-84)
2. 用户输入/选择目的地地址
3. （可选）调用 `POST /api/geocode` 将地址转为坐标
4. 组装 `PlanRequest`，发送 `POST /api/plan`
5. 后端 **DEBUG 模式** 下记录完整请求体（含 preferences/constraints）

### 坐标系统
| 坐标系 | 说明 | 高德可用 |
|--------|------|---------|
| WGS-84 | GPS 原始坐标 | ✅ (高德会自动转换) |
| GCJ-02 | 火星坐标 (中国标准) | ✅ (高德原生) |
| BD-09  | 百度坐标 | ❌ (需转换) |

---

## 6. 相关端点

| 端点 | 用途 |
|------|------|
| `POST /api/plan` | 主规划请求（含 start_location + end_location） |
| `POST /api/geocode` | 地址 → 坐标代理（保护 AMAP_KEY） |
| `GET /api/plan/history` | 获取历史规划记录（前端缓存） |

---

## 7. 电脑 vs 手机定位精度对比

| 设备 | 定位方式 | 精度 | 适用场景 |
|------|---------|------|---------|
| 台式机 | IP 定位 / WiFi | 100m-1000m | 仅大致参考 |
| 笔记本 | WiFi + 少量 GPS | 30m-200m | 粗略定位 |
| 手机(室外) | GPS + 基站 | 3m-15m | **最佳** |
| 手机(室内) | WiFi + 基站 | 10m-50m | 可用 |

**建议**：路线规划类功能优先考虑手机端（GPS精度高），电脑端可用 IP 定位做粗略起点或让用户手动输入起点。
