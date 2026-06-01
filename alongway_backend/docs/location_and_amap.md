# Location and Amap Routing

## Frontend Location Contract

The backend does not locate a user by itself. The frontend should request browser
location permission and send the resulting coordinates in `start_location` or
another chosen location field.

Recommended browser API:

```js
navigator.geolocation.getCurrentPosition(
  (position) => {
    const { latitude, longitude, accuracy } = position.coords;
  },
  (error) => {
    // Ask the user to choose a location manually.
  },
  { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
);
```

Notes:

- Browser geolocation requires user permission and usually requires a secure
  context such as HTTPS. Local `localhost` development is normally allowed.
- Phones are usually more accurate because GPS, cellular, and Wi-Fi signals are
  available.
- Desktop and laptop browsers often infer location from Wi-Fi or IP data, so
  accuracy can vary significantly.
- The backend accepts optional `accuracy_meters` and `source` fields on
  `LocationInput`, for example `source: "browser_geolocation"`.

## Amap Routing

`POST /internal/route/calculate` uses Amap Web Service route APIs. It no longer
falls back to local Haversine route estimation.

Required environment variables:

```env
AMAP_KEY=your_amap_web_service_api_key_here
AMAP_BASE_URL=https://restapi.amap.com
AMAP_TIMEOUT_SECONDS=10
```

Supported `travel_mode` values:

- `walking`: Amap walking route API.
- `driving`: Amap driving route API.
- `bicycling`: Amap bicycling route API.

If `AMAP_KEY` is missing, Amap rejects the request, the HTTP request fails, or
the response cannot be parsed, the internal route endpoint returns an explicit
error instead of returning an approximate local route.
