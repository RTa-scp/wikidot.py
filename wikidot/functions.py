from __future__ import annotations

import asyncio
import html
import time

import httpx

from .customexceptions import AMCRequestError, NotOK, RequestError, ReturnedDataError, TemporaryErrorForHandle

# TODO: 変数が汚い
# TODO: エラーハンドリングがカオス


async def asyncAjaxRequest(*,
                           site,
                           body: dict,
                           attempt_limit: int = 6,
                           wait_time: float = 10,
                           timeout: float = 40,
                           unescape: bool = True,
                           ) -> dict:
    # リクエスト用関数
    async def _request(__site_name: str, __ssl: bool, __data: dict, __headers: dict, __timeout: float) -> dict:
        async with httpx.AsyncClient() as __client:
            try:
                __r = await __client.post(
                    f"{'https://' if __ssl else 'http://'}{__site_name}.wikidot.com/ajax-module-connector.php",
                    data=__data,
                    headers=__headers,
                    timeout=__timeout
                )
            except httpx.HTTPStatusError as e:
                raise AMCRequestError("Response Status is 4xx or 5xx.", status_code=e.response.status_code)
            except Exception:
                raise  # 拾った例外をそのままraise
        # HTTPステータスコードを確認 200以外ならRequestFailedError(スタックトレース用/arg2: <status_code>)をraise
        if __r.status_code != 200:
            raise AMCRequestError(
                "Status code is not 200.", status_code=__r.status_code
            )
        # jsonをhttpxのjson()関数でdictに変換
        try:
            __r_json = __r.json()
        except Exception:
            # json変換に失敗(=レスポンスがjsonフォーマットでない)時にReturnedDataError(arg2: not_json)をraise
            raise TypeError(
                "Returned data is not json format."
            )
        # 返り値が空だった場合にReturnedDataError(arg2: empty)をraise
        if __r_json is None:
            raise ReturnedDataError(
                "Wikidot returns empty data.", reason="empty"
            )
        # dictを返す
        return __r_json

    # リクエストボディを作成
    _request_body = {
        "wikidot_token7": "123456"
    }
    _request_body.update(body)

    # リクエストを実行
    _cnt = 1
    while True:
        try:
            _json = await _request(__site_name=site.name, __ssl=site.ssl,
                                   __headers=site.client.requestHeader.getHeader(), __data=_request_body,
                                   __timeout=timeout)
            _r_status = _json["status"]
            if _r_status == "try_again":
                raise TemporaryErrorForHandle(
                    "Wikidot returns 'try_again' status."
                )  # retry
            else:
                break  # success
        # ReturnedDataError(返り値が空だった場合にraise)のときはリクエスト自体に問題がある可能性が高いため、リトライしない
        except ReturnedDataError:
            raise

        except Exception:
            # 再試行
            if _cnt < attempt_limit:
                _cnt += 1
                await asyncio.sleep(wait_time)
                pass
            # 再試行ループ終了
            else:
                raise RequestError(
                    "Request attempted but failed."
                )

    # Wikidotステータスの処理 ok以外ならStatusError(arg2: <status>)をraise
    if _r_status != "ok":
        raise NotOK(
            f"Status is not OK: {_r_status}", status_code=_r_status
        )
    # bodyをHTMLアンエスケープ
    if "body" in _json and unescape is True:
        _json["body"] = html.unescape(_json["body"])
    # 処理終了
    return _json


def nonAsyncAjaxRequest(*,
                        site,
                        body: dict,
                        attempt_limit: int = 6,
                        wait_time: float = 10,
                        timeout: float = 40,
                        unescape: bool = True,
                        ) -> dict:
    # リクエスト用関数
    def _request(__site_name: str, __ssl: bool, __data: dict, __headers: dict, __timeout: float) -> dict:
        try:
            __r = httpx.post(
                f"{'https://' if __ssl else 'http://'}{__site_name}.wikidot.com/ajax-module-connector.php",
                data=__data,
                headers=__headers,
                timeout=__timeout
            )
        except httpx.HTTPStatusError as _e:
            raise AMCRequestError("Response Status is 4xx or 5xx.", status_code=_e.response.status_code)
        except Exception:
            raise  # 拾った例外をそのままraise
        # HTTPステータスコードを確認 200以外ならRequestFailedError(スタックトレース用/arg2: <status_code>)をraise
        if __r.status_code != 200:
            raise AMCRequestError(
                "Status code is not 200.", status_code=__r.status_code
            )
        # jsonをhttpxのjson()関数でdictに変換
        try:
            __r_json = __r.json()
        except Exception:
            # json変換に失敗(=レスポンスがjsonフォーマットでない)時にReturnedDataError(arg2: not_json)をraise
            raise TypeError(
                "Returned data is not json format."
            )
        # 返り値が空だった場合にReturnedDataError(arg2: empty)をraise
        if __r_json is None:
            raise ReturnedDataError(
                "Wikidot returns empty data.", reason="empty"
            )
        # dictを返す
        return __r_json

    # リクエストボディを作成
    _request_body = {
        "wikidot_token7": "123456"
    }
    _request_body.update(body)

    # リクエストを実行
    _cnt = 1
    while True:
        try:
            _json = _request(__site_name=site.name, __ssl=site.ssl,
                             __headers=site.client.requestHeader.getHeader(), __data=_request_body,
                             __timeout=timeout)
            _r_status = _json["status"]
            if _r_status == "try_again":
                raise TemporaryErrorForHandle(
                    "Wikidot returns 'try_again' status."
                )  # retry
            else:
                break  # success
        # ReturnedDataError(返り値が空だった場合にraise)のときはリクエスト自体に問題がある可能性が高いため、リトライしない
        except ReturnedDataError:
            raise

        except Exception:
            # 再試行
            if _cnt < attempt_limit:
                _cnt += 1
                time.sleep(wait_time)
                pass
            # 再試行ループ終了
            else:
                raise RequestError(
                    "Request attempted but failed."
                )

    # Wikidotステータスの処理 ok以外ならStatusError(arg2: <status>)をraise
    if _r_status != "ok":
        raise NotOK(
            f"Status is not OK: {_r_status}", status_code=_r_status
        )
    # bodyをHTMLアンエスケープ
    if "body" in _json and unescape is True:
        _json["body"] = html.unescape(_json["body"])
    # 処理終了
    return _json


