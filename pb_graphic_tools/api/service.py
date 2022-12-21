import asyncio
import io
import math
import os
import zipfile

import aiohttp
from fastapi import UploadFile
from loguru import logger
from PIL import Image

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
async def make_long_img(imgs: list[UploadFile], size=None, n_cols=1):
    n_rows = math.ceil(len(imgs) / n_cols)
    sorted_imgs = sorted(imgs, key=lambda x: x.filename)
    if not size:
        with Image.open(sorted_imgs[0].file) as first_img:
            size = first_img.size

    result_img = Image.new('RGB', (size[0] * n_cols, size[1] * n_rows))
    cur_row = 0
    cur_col = 0
    for img_file in sorted_imgs:
        with Image.open(img_file.file) as temp_img:
            resized_img = temp_img.resize(size)
            result_img.paste(resized_img, (size[0] * cur_col, size[1] * cur_row))
            cur_col += 1
            if cur_col >= n_cols:
                cur_col = 0
                cur_row += 1

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


async def make_long_tile_img(
    imgs: list[UploadFile],
    schema: list[int],
    width: int,
    border: int,
    border_color: str,
):
    sorted_imgs = sorted(imgs, key=lambda x: x.filename)
    if not width:
        with Image.open(sorted_imgs[0].file) as first_img:
            width = first_img.size[0]
    order_schema: list[list[UploadFile]] = []
    next_img_num = 0
    for row in schema:
        order_schema.append(
            [sorted_imgs[img_num] for img_num in range(next_img_num, row+next_img_num)]
        )
        next_img_num += row
    result = Image.new('RGB', (width, 0), color=border_color)
    for img_row in order_schema:
        local_width = (width - (border * (len(img_row) - 1))) // len(img_row)
        with Image.open(img_row[0].file) as first_row_img:
            first_row_img_size = first_row_img.size
        k = local_width / first_row_img_size[0]
        local_hight = round((first_row_img_size[1] * k))
        result_row = Image.new('RGB', (width, local_hight), color=border_color)
        cur_x = 0
        for img_file in img_row:
            with Image.open(img_file.file) as row_img:
                row_img_r = row_img.resize((local_width, local_hight))
                result_row.paste(row_img_r, (cur_x, 0))
                cur_x += local_width + border
        local_border = 0 if result.size[1] == 0 else border
        new_result = Image.new('RGB', (width, result.size[1]+result_row.size[1]+local_border), color=border_color)
        new_result.paste(result, (0, 0))
        new_result.paste(result_row, (0, result.size[1]+local_border))
        result = new_result

    buf = io.BytesIO()
    result.save(buf, format='JPEG')
    return buf.getvalue()
