import asyncio
import io
import os
import zipfile
from PIL import Image
import aiohttp
from fastapi import UploadFile
from loguru import logger
from pb_graphic_tools import schemas


@logger.catch
async def tinify_img(session: aiohttp.ClientSession, file: UploadFile, width):
    async with session.post('https://api.tinify.com/shrink', data=file.file.read()) as response:
        tiny_resp = schemas.TinyResponse.parse_raw(await response.read())
        if tiny_resp.error:
            return tiny_resp.error

    data = {
        'resize': {
            'method': 'scale',
            'width': width or tiny_resp.output.width  # type: ignore
        }
    }

    async with session.post(tiny_resp.output.url, json=data) as result:  # type: ignore
        return (file.filename, await result.read())


@logger.catch
async def tinify_imgs(files: list[UploadFile], width):
    auth = aiohttp.BasicAuth('api', os.environ.get('TINIFY_TOKEN') or 'token')
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
                    filename = '.'.join(filename.split('.')[:-1] + ['png'])
                    logger.debug(filename)
                    result_zip.writestr(filename, filedata)
            return result_zip_file.getvalue()


@logger.catch
async def make_long_img(imgs: list[UploadFile]):
    sorted_imgs = sorted(imgs, key=lambda x: x.filename)
    with Image.open(sorted_imgs[0].file) as first_img:
        wide, high = first_img.size

    for img_file in sorted_imgs[1:]:
        with Image.open(img_file.file) as temp_img:
            high += temp_img.size[1]

    result_img = Image.new('RGB', (wide, high))
    point_high = 0
    for img_file in sorted_imgs:
        with Image.open(img_file.file) as temp_img:
            result_img.paste(temp_img, (0, point_high))
            point_high += temp_img.size[1]

    buf = io.BytesIO()
    result_img.save(buf, format='JPEG')
    return buf.getvalue()


async def make_gif(prefix: str, duration: int, imgs: list[UploadFile]):
    sorted_imgs = sorted(imgs, key=lambda x: int(
        os.path.splitext(x.filename)[0][len(prefix):]
    ))
    opened_img = [Image.open(img.file) for img in sorted_imgs]
    buf = io.BytesIO()
    opened_img[0].save(
        buf,
        format='gif',
        save_all=True,
        append_images=opened_img[1:],
        optimize=True,
        duration=duration,
        loop=0
    )
    return buf.getvalue()
