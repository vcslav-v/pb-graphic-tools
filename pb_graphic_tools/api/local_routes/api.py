import os
import secrets

from fastapi import (APIRouter, BackgroundTasks, Depends, File, HTTPException,
                     Response, UploadFile, status)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger

from pb_graphic_tools.api import service

router = APIRouter()
security = HTTPBasic()

username = os.environ.get('API_USERNAME') or 'api'
password = os.environ.get('API_PASSWORD') or 'pass'


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, username)
    correct_password = secrets.compare_digest(credentials.password, password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.post('/tinify')
@logger.catch
async def tinify(
    background_tasks: BackgroundTasks,
    prefix: str,
    is_tinify: bool = False,
    width: int = None,
    _: str = Depends(get_current_username)
):
    """Tinify and resize img."""
    try:
        background_tasks.add_task(service.tinify_imgs, prefix, width, is_tinify)
    except ValueError as val_err:
        return {'error': val_err.args}
    return 200


@router.post('/long')
@logger.catch
async def long(
    background_tasks: BackgroundTasks,
    prefix: str,
    num_imgs: int,
    wide: int = -1,
    high: int = -1,
    n_cols: int = 1,
    _: str = Depends(get_current_username)
):
    """Make long img."""
    size = None
    if wide > 0 and high > 0:
        size = (wide, high)
    try:
        background_tasks.add_task(service.make_long_img, prefix, num_imgs, size, n_cols)
    except ValueError as val_err:
        return {'error': val_err.args}
    return 200


@router.post('/gif')
@logger.catch
async def gif(
    prefix: str = '',
    duration: int = 100,
    files: list[UploadFile] = File(...),
    _: str = Depends(get_current_username)
):
    """Make gif."""
    try:
        gif_data = await service.make_gif(prefix, duration, files)
    except ValueError as val_err:
        return {'error': val_err.args}
    return Response(
        content=gif_data,
        media_type='image/gif',
        headers={
            'Content-Disposition': 'attachment; filename=result.gif'
        }
    )


@router.post('/logn_tile')
@logger.catch
async def logn_tile(
    background_tasks: BackgroundTasks,
    prefix: str,
    raw_schema: str,
    width: int = 0,
    border: int = 0,
    raw_border_color: str = 'FFFFFF',
    _: str = Depends(get_current_username)
):
    schema = [int(row) for row in raw_schema.split('-')]
    border_color = f'#{raw_border_color}'
    try:
        background_tasks.add_task(service.make_long_tile_img, prefix, schema, width, border, border_color)
    except ValueError as val_err:
        return {'error': val_err.args}
    return 200


@router.get('/cut_pics')
@logger.catch
async def cut_pics(
    background_tasks: BackgroundTasks,
    left: int,
    top: int,
    right: int,
    bottom: int,
    prefix: str,
    _: str = Depends(get_current_username)
):
    try:
        background_tasks.add_task(service.cut_files, prefix, left, top, right, bottom)
    except ValueError as val_err:
        return {'error': val_err.args}
    return 200
