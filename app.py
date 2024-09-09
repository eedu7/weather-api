from fastapi import FastAPI, status, Depends
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter

from utils import fetch_data, generate_url, lifespan

app = FastAPI(title="Weather API", lifespan=lifespan,)


@app.get("/{city}", tags=["Fetch weather data"], dependencies=[Depends(RateLimiter(times=10, minutes=1))])
async def home(
    city: str, start_date: str | None = None, end_date: str | None = None
) -> JSONResponse:
    url = await generate_url(city, start_date, end_date)

    data = await fetch_data(url)

    return JSONResponse(status_code=status.HTTP_200_OK, content=data)
