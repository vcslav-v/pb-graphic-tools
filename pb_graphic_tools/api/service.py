import asyncio
import io
import os
import zipfile

import aiohttp
from fastapi import UploadFile
from loguru import logger
from pb_graphic_tools import schemas


@logger.catch
async def tinify_img(session: aiohttp.ClientSession, file: UploadFile, width):
    async with session.post('https://api.tinify.com/shrink', data=file.file.read()) as response:
        r = await response.read()
        logger.debug(r)
        logger.debug(schemas.TinyResponse.parse_raw(r))
        tiny_resp = schemas.TinyResponse.parse_raw(r)
        if tiny_resp.error:
            return tiny_resp.error

    data = {
        'resize': {
            'method': 'scale',
            'width': width or tiny_resp.output.width
        }
    }

    async with session.post(tiny_resp.output.url, json=data) as result:
        return (file.filename, await result.read())


@logger.catch
async def tinify_imgs(files: list[UploadFile], width):
    auth = aiohttp.BasicAuth('api', os.environ.get('TINIFY_TOKEN'))
    async with aiohttp.ClientSession(auth=auth) as session:
        tasks = []
        for file in files:
            task = asyncio.create_task(tinify_img(session, file, width))
            tasks.append(task)
        png_datas = await asyncio.gather(*tasks)
        with io.BytesIO() as result_zip_file:
            with zipfile.ZipFile(result_zip_file, 'a') as result_zip:
                for png_data in png_datas:
                    filename, filedata = png_data
                    filename = '.'.join(filename.split('.')[:-1].append('png'))
                    result_zip.writestr(filename, filedata)
            return result_zip_file.read()
