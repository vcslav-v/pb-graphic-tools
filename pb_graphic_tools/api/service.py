import asyncio
import io
import math
import os
import zipfile
import shutil

import aiohttp
from boto3 import session
from fastapi import UploadFile
from loguru import logger
from PIL import Image

from pb_graphic_tools import schemas

DO_SPACE_REGION = os.environ.get('DO_SPACE_REGION', '')
DO_SPACE_ENDPOINT = os.environ.get('DO_SPACE_ENDPOINT', '')
DO_SPACE_KEY = os.environ.get('DO_SPACE_KEY', '')
DO_SPACE_SECRET = os.environ.get('DO_SPACE_SECRET', '')
DO_SPACE_BUCKET = os.environ.get('DO_SPACE_BUCKET', '')

TINY_TOKEN = os.environ.get('TINIFY_TOKEN', '')


@logger.catch
async def tinify_img(session: aiohttp.ClientSession, path_file, width):
    with open(path_file, 'rb') as file:
        async with session.post('https://api.tinify.com/shrink', data=file.read()) as response:
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
        return (file.name, await result.read())


@logger.catch
async def tinify_imgs(prefix, width, is_tinify):
    local_session = session.Session()
    client = local_session.client(
        's3',
        region_name=DO_SPACE_REGION,
        endpoint_url=DO_SPACE_ENDPOINT,
        aws_access_key_id=DO_SPACE_KEY,
        aws_secret_access_key=DO_SPACE_SECRET
    )
    logger.debug('start dwn')
    s3_file_keys = await dwn_s3(prefix, client)
    if is_tinify:
        auth = aiohttp.BasicAuth('api', TINY_TOKEN)
        async with aiohttp.ClientSession(auth=auth) as session_ai:
            tasks = []
            for file_path in s3_file_keys:
                task = asyncio.create_task(tinify_img(session_ai, file_path, width))
                tasks.append(task)
            png_datas = await asyncio.gather(*tasks)
    else:
        png_datas = []
        for file_path in s3_file_keys:
            png_datas.append(resize_img(file_path, width))

    result_name = 'result.zip'
    with zipfile.ZipFile(os.path.join('temp', prefix, result_name), 'a') as result_zip:
        for png_data in png_datas:
            filename, filedata = png_data
            filename = '.'.join(filename.split('/')[-1].split('.')[:-1] + ['png'])
            logger.debug(filename)
            result_zip.writestr(filename, filedata)
    client.upload_file(
        os.path.join('temp', prefix, result_name),
        DO_SPACE_BUCKET,
        f'temp/{prefix}/{result_name}'
    )
    for s3_file_key in s3_file_keys:
        client.delete_object(Bucket=DO_SPACE_BUCKET, Key=s3_file_key)
    shutil.rmtree(os.path.join('temp', prefix))
    logger.debug('end')


@logger.catch
async def make_long_img(prefix: str, num_imgs: int, size=None, n_cols=1):
    local_session = session.Session()
    client = local_session.client(
        's3',
        region_name=DO_SPACE_REGION,
        endpoint_url=DO_SPACE_ENDPOINT,
        aws_access_key_id=DO_SPACE_KEY,
        aws_secret_access_key=DO_SPACE_SECRET
    )
    logger.debug('start dwn')
    s3_file_keys = await dwn_s3(prefix, client)
    n_rows = math.ceil(num_imgs / n_cols)
    sorted_imgs = sorted(os.listdir(os.path.join('temp', prefix)))
    sorted_imgs = [os.path.join('temp', prefix, sorted_img) for sorted_img in sorted_imgs]
    if not size:
        with Image.open(sorted_imgs[0]) as first_img:
            size = first_img.size
    logger.debug('open result')
    result_img = Image.new('RGB', (size[0] * n_cols, size[1] * n_rows))
    cur_row = 0
    cur_col = 0
    for img_file in sorted_imgs:
        logger.debug('new turn')
        with Image.open(img_file) as temp_img:
            resized_img = temp_img.resize(size)
            result_img.paste(resized_img, (size[0] * cur_col, size[1] * cur_row))
            cur_col += 1
            if cur_col >= n_cols:
                cur_col = 0
                cur_row += 1

    result_name = 'result.jpg'
    logger.debug('save result')
    result_img.save(os.path.join('temp', prefix, result_name), format='JPEG')
    client.upload_file(
        os.path.join('temp', prefix, result_name),
        DO_SPACE_BUCKET,
        f'temp/{prefix}/result.jpg'
    )
    for s3_file_key in s3_file_keys:
        client.delete_object(Bucket=DO_SPACE_BUCKET, Key=s3_file_key)
    shutil.rmtree(os.path.join('temp', prefix))
    logger.debug('end')


@logger.catch
async def cut_files(prefix: str, left: int, top: int, right: int, bottom: int):
    local_session = session.Session()
    client = local_session.client(
        's3',
        region_name=DO_SPACE_REGION,
        endpoint_url=DO_SPACE_ENDPOINT,
        aws_access_key_id=DO_SPACE_KEY,
        aws_secret_access_key=DO_SPACE_SECRET
    )
    logger.debug('start dwn')
    s3_file_keys = await dwn_s3(prefix, client)
    imgs_path = [os.path.join('temp', prefix, sorted_img) for sorted_img in os.listdir(os.path.join('temp', prefix)) if sorted_img.endswith('.jpg') or sorted_img.endswith('.png') or sorted_img.endswith('.jpeg')]
    cropped_images = []

    for image_path in imgs_path:
        with Image.open(image_path) as img:
            if img.width > (left + right) and img.height > (top + bottom):
                cropped_img = img.crop((left, top, img.width - right, img.height - bottom))
                cropped_img.save(image_path)
                cropped_images.append(image_path)

    result_path = os.path.join('temp', prefix, 'result.zip')
    with zipfile.ZipFile(result_path, 'w') as zipf:
        if cropped_images:
            for image_path in cropped_images:
                zipf.write(image_path, arcname=os.path.basename(image_path))
        else:
            with open("message.txt", "w") as f:
                f.write("No suitable images found.")
            zipf.write("message.txt")

    client.upload_file(
        result_path,
        DO_SPACE_BUCKET,
        f'temp/{prefix}/result.zip'
    )
    for s3_file_key in s3_file_keys:
        client.delete_object(Bucket=DO_SPACE_BUCKET, Key=s3_file_key)
    shutil.rmtree(os.path.join('temp', prefix))
    logger.debug('end')



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


async def dwn_s3(prefix: str, client: session.Session):
    s3_files = client.list_objects_v2(Bucket=DO_SPACE_BUCKET, Prefix=f'temp/{prefix}/')
    if not s3_files.get('Contents'):
        raise ValueError('Wrong prefix')
    os.mkdir(os.path.join('temp', prefix))
    s3_file_keys = [s3_file['Key'] for s3_file in s3_files['Contents']]
    for s3_file_key in s3_file_keys:
        client.download_file(Bucket=DO_SPACE_BUCKET, Key=s3_file_key, Filename=s3_file_key)
    return s3_file_keys


def resize_img(img_path, width) -> tuple[str, bytes]:
    with Image.open(img_path) as img:
        img_r = img.resize((width, round(img.size[1] * width / img.size[0])))
        buf = io.BytesIO()
        img_r.save(buf, format='PNG')
        filename = img_path.split('/')[-1]
        return (filename, buf.getvalue())


async def make_long_tile_img(
    prefix: str,
    schema: list[int],
    width: int,
    border: int,
    border_color: str,
):
    local_session = session.Session()
    client = local_session.client(
        's3',
        region_name=DO_SPACE_REGION,
        endpoint_url=DO_SPACE_ENDPOINT,
        aws_access_key_id=DO_SPACE_KEY,
        aws_secret_access_key=DO_SPACE_SECRET
    )
    logger.debug('start dwn')
    s3_file_keys = await dwn_s3(prefix, client)
    logger.debug('end dwn')
    sorted_imgs = sorted(os.listdir(os.path.join('temp', prefix)))
    sorted_imgs = [os.path.join('temp', prefix, sorted_img) for sorted_img in sorted_imgs]
    if not width:
        with Image.open(sorted_imgs[0]) as first_img:
            width = first_img.size[0]
    order_schema: list[list[str]] = []
    next_img_num = 0
    for row in schema:
        if row == 0:
            order_schema.append([])
            continue
        order_schema.append(
            [sorted_imgs[img_num] for img_num in range(next_img_num, row+next_img_num)]
        )
        next_img_num += row
    logger.debug('open result img')
    result = Image.new('RGB', (width, 0), color=border_color)
    first_flag = True
    for img_row in order_schema:
        if not img_row:
            new_result = Image.new('RGB', (width, result.size[1]+border), color=border_color)
            new_result.paste(result, (0, 0))
            result = new_result
            continue
        local_width = (width - (border * (len(img_row) - 1))) // len(img_row)
        with Image.open(img_row[0]) as first_row_img:
            first_row_img_size = first_row_img.size
        k = local_width / first_row_img_size[0]
        local_hight = round((first_row_img_size[1] * k))
        result_row = Image.new('RGB', (width, local_hight), color=border_color)
        cur_x = 0
        for img_file in img_row:
            with Image.open(img_file) as row_img:
                row_img_r = row_img.resize((local_width, local_hight))
                result_row.paste(row_img_r, (cur_x, 0))
                cur_x += local_width + border
        local_border = 0 if first_flag else border
        logger.debug('open new result img')
        new_result = Image.new('RGB', (width, result.size[1]+result_row.size[1]+local_border), color=border_color)
        new_result.paste(result, (0, 0))
        new_result.paste(result_row, (0, result.size[1]+local_border))
        result = new_result
        first_flag = False
        logger.debug('next turn')
    logger.debug('save')
    result_name = 'result.jpg'
    result.save(os.path.join('temp', prefix, result_name), format='JPEG')
    client.upload_file(
        os.path.join('temp', prefix, result_name),
        DO_SPACE_BUCKET,
        f'temp/{prefix}/result.jpg'
    )
    for s3_file_key in s3_file_keys:
        client.delete_object(Bucket=DO_SPACE_BUCKET, Key=s3_file_key)
    shutil.rmtree(os.path.join('temp', prefix))


def flush_temp_space():
    local_session = session.Session()
    client = local_session.client(
        's3',
        region_name=DO_SPACE_REGION,
        endpoint_url=DO_SPACE_ENDPOINT,
        aws_access_key_id=DO_SPACE_KEY,
        aws_secret_access_key=DO_SPACE_SECRET
    )
    s3_files = client.list_objects_v2(Bucket=DO_SPACE_BUCKET, Prefix=f'temp/')
    if not s3_files.get('Contents'):
        return
    s3_file_keys = [s3_file['Key'] for s3_file in s3_files['Contents']]
    for s3_file_key in s3_file_keys:
        client.delete_object(Bucket=DO_SPACE_BUCKET, Key=s3_file_key)
    temp_tree = os.listdir('temp')
    for temp_file in temp_tree:
        if os.path.isdir(os.path.join('temp', temp_file)):
            shutil.rmtree(os.path.join('temp', temp_file))
