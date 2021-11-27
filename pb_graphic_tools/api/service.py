import os
from loguru import logger
from fastapi import UploadFile
from pb_graphic_tools import schemas
import asyncio
import aiohttp


@logger.catch
async def tinify_img(session: aiohttp.ClientSession, file: UploadFile, width):
    async with session.post('https://api.tinify.com/shrink', data=file.file.read()) as response:
        logger.debug(response.__dict__)
        logger.debug(response)
        logger.debug(response.content)
        logger.debug(response.read())
        tiny_resp = schemas.TinyResponse.parse_raw(response.content)
        if not tiny_resp.error:
            data = {
                'resize': {
                    'method': 'scale',
                    'width': width or tiny_resp.output.width
                }
            }
            async with session.post(tiny_resp.output.url, json=data) as result:
                return result.content


@logger.catch
async def tinify_imgs(files: list[UploadFile], width):
    auth = aiohttp.BasicAuth('api', os.environ.get('TINIFY_TOKEN'))
    async with aiohttp.ClientSession(auth=auth) as session:
        tasks = []
        for file in files:
            task = asyncio.create_task(tinify_img(session, file, width))
            tasks.append(task)
        return await asyncio.gather(*tasks)
