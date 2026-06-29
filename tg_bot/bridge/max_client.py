"""HTTP-клиент MAX Bot API."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = 'https://platform-api.max.ru'


class MaxApiError(Exception):
    def __init__(self, status: int, payload: Any):
        super().__init__(f'MAX API {status}: {payload}')
        self.status = status
        self.payload = payload


class MaxClient:
    def __init__(self, token: str, *, timeout: float = 60.0):
        self.token = token.strip()
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={'Authorization': self.token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        response = await self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            raise MaxApiError(response.status_code, payload)
        if not response.content:
            return None
        return response.json()

    async def get_me(self) -> dict:
        return await self._request('GET', '/me')

    async def get_updates(
        self,
        *,
        marker: int | None = None,
        timeout: int = 30,
        types: list[str] | None = None,
    ) -> dict:
        params: dict[str, Any] = {'timeout': timeout, 'limit': 100}
        if marker is not None:
            params['marker'] = marker
        if types:
            params['types'] = ','.join(types)
        return await self._request('GET', '/updates', params=params)

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        attachments: list[dict] | None = None,
        notify: bool = True,
    ) -> dict:
        body: dict[str, Any] = {'text': text, 'notify': notify}
        if attachments:
            body['attachments'] = attachments
        return await self._request(
            'POST',
            '/messages',
            params={'chat_id': int(chat_id)},
            json=body,
        )

    async def create_upload(self, upload_type: str) -> dict:
        return await self._request('POST', '/uploads', params={'type': upload_type})

    async def upload_multipart(self, upload_url: str, data: bytes, filename: str) -> dict:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                upload_url,
                files={'data': (filename, data)},
            )
            if response.status_code >= 400:
                raise MaxApiError(response.status_code, response.text)
            return response.json()

    async def upload_video(self, data: bytes, filename: str = 'video.mp4') -> dict:
        meta = await self.create_upload('video')
        upload_url = meta.get('url')
        if not upload_url:
            raise MaxApiError(500, meta)
        result = await self.upload_multipart(upload_url, data, filename)
        token = result.get('token') or meta.get('token')
        if not token:
            raise MaxApiError(500, {'error': 'no video token', 'meta': meta, 'result': result})
        return {'type': 'video', 'payload': {'token': token}}

    async def upload_image(self, data: bytes, filename: str = 'image.jpg') -> dict:
        meta = await self.create_upload('image')
        upload_url = meta.get('url')
        if not upload_url:
            raise MaxApiError(500, meta)
        result = await self.upload_multipart(upload_url, data, filename)
        token = result.get('token')
        if not token and isinstance(result, dict):
            token = meta.get('token')
        if not token:
            raise MaxApiError(500, {'error': 'no image token', 'meta': meta, 'result': result})
        return {'type': 'image', 'payload': {'token': token}}

    async def upload_file(self, data: bytes, filename: str) -> dict:
        meta = await self.create_upload('file')
        upload_url = meta.get('url')
        if not upload_url:
            raise MaxApiError(500, meta)
        result = await self.upload_multipart(upload_url, data, filename)
        token = result.get('token')
        if not token:
            raise MaxApiError(500, {'error': 'no file token', 'meta': meta, 'result': result})
        return {'type': 'file', 'payload': {'token': token}}

    async def send_with_retry(
        self,
        *,
        chat_id: int,
        text: str,
        attachments: list[dict] | None = None,
        retries: int = 5,
    ) -> dict:
        delay = 0.5
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                return await self.send_message(
                    chat_id=chat_id,
                    text=text,
                    attachments=attachments,
                )
            except MaxApiError as exc:
                last_error = exc
                code = ''
                if isinstance(exc.payload, dict):
                    code = str(exc.payload.get('code') or '')
                if code != 'attachment.not.ready' or attempt + 1 >= retries:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8.0)
        if last_error:
            raise last_error
        raise RuntimeError('send_with_retry failed')
