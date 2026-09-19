# Recorded provider responses

`open_meteo_chicago_2026-09-18.json` was recorded on 2026-09-18 (evening, Chicago time) with:

```
https://api.open-meteo.com/v1/forecast?latitude=41.8781&longitude=-87.6298&timezone=America%2FChicago&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,precipitation_probability&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset&forecast_days=5&temperature_unit=celsius&wind_speed_unit=kmh
```

It uses the example coordinates from `config.example.yaml`, not a real address. The
`sunrise`/`sunset` fields are kept in the fixture only as an independent check of the
locally computed sun times; the provider does not request them.
