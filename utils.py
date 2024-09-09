import json
import os
from contextlib import asynccontextmanager
from math import ceil
from time import sleep

import redis.asyncio as redis
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi_limiter import FastAPILimiter
from requests.exceptions import HTTPError, RequestException, Timeout

load_dotenv()

API_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"
API_KEY = os.getenv("API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

redis = redis.from_url(REDIS_URL, encoding="utf8", decode_responses=True)
cache_expiry = 60 * 60 * 12


async def generate_url(
    city: str, start_date: str | None = None, end_date: str | None = None
):
    url = API_URL + city
    if start_date:
        url = url + f"/{start_date}"
    if end_date:
        url = url + f"/{end_date}"
    return url + f"?key={API_KEY}"


async def fetch_data(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        sleep(30)

        return response.json()
    except HTTPError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key or url"
        )
    except Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request is taking a long time to process",
        )
    except RequestException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def service_name_identifier(request: Request):
    return request.headers.get("Service-Name")


async def custom_callback(request: Request, response: Response, pexpire: int):
    expire = ceil(pexpire / 1000)
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Too many requests. Retry after {expire} seconds",
        headers={"Retry-After": str(expire)},
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis_connection = redis.from_url(REDIS_URL, encoding="utf8")
    await FastAPILimiter.init(
        redis=redis_connection,
        identifier=service_name_identifier,
        http_callback=custom_callback,
    )
    yield await FastAPILimiter.close()


async def get_cache_data(city: str):
    json_data = await redis.get(city)
    if json_data:
        return json.loads(json_data)


async def set_cache_data(city: str, value: dict):
    json_value = json.dumps(value)
    await redis.set(city, json_value, ex=cache_expiry)
    return True
