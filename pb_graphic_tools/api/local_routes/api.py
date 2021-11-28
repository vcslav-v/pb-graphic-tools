import os
import secrets

from fastapi import (APIRouter, Depends, File, HTTPException, Response,
                     UploadFile, status)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger
from pb_graphic_tools.api import service

router = APIRouter()
security = HTTPBasic()

username = os.environ.get('API_USERNAME') or 'root'
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
    width: int = None,
    files: list[UploadFile] = File(...),
    _: str = Depends(get_current_username)
):
    """Tinify and resize img."""
    try:
        tinified_zip = await service.tinify_imgs(files, width)
    except ValueError as val_err:
        return {'error': val_err.args}
    return Response(
        content=tinified_zip,
        media_type='application/x-zip-compressed',
        headers={
            'Content-Disposition': 'attachment; filename=tinified.zip'
        }
    )


@router.post('/long')
@logger.catch
async def long(
    files: list[UploadFile] = File(...),
    _: str = Depends(get_current_username)
):
    """Make long img."""
    try:
        long_img_data = await service.make_long_img(files)
    except ValueError as val_err:
        return {'error': val_err.args}
    return Response(
        content=long_img_data,
        media_type='image/jpeg',
        headers={
            'Content-Disposition': 'attachment; filename=long.jpg'
        }
    )
