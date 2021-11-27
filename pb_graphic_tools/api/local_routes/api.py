from fastapi import APIRouter, File, UploadFile, Response
from pb_graphic_tools.api import service
import os

router = APIRouter()


@router.post('/tinify')
async def tinify(token: str, width: int = None, files: list[UploadFile] = File(...)):
    """Tinify and resize img."""
    # if token != os.environ.get('TOKEN'):
    #     return {'error': 'Wrong token'}
    try:
        tinified_zip = await service.tinify_imgs(files, width)
    except ValueError as val_err:
        return {'error': val_err.args}
    return Response(content=tinified_zip, media_type='application/zip')
