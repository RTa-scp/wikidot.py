from __future__ import annotations

import asyncio
import html
import re
import time

import httpx

from . import logger
from .customexceptions import AMCRequestError, NotOK, RequestError, ReturnedDataError, TemporaryErrorForHandle

logger = logger.logger


# TODO: 変数が汚い
# TODO: エラーハンドリングがカオス


async def asyncAjaxRequest(*,
                           site,
                           body: dict,
                           attempt_limit: int,
                           wait_time: float,
                           timeout: float,
                           unescape: bool,
                           ) -> dict:
    # リクエスト用関数
    async def _request(__site_name: str, __ssl: bool, __data: dict, __headers: dict, __timeout: float) -> dict:
        async with httpx.AsyncClient() as __client:
            try:
                logger.debug(f"POST Ajax Request:\n"
                             f"\tURI: {'https://' if __ssl else 'http://'}{__site_name}.wikidot.com/ajax-module-connector.php\n"
                             f"\tHeaders: {__headers}\n"
                             f"\tData: {__data}")
                __r = await __client.post(
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

        except Exception as e:
            # 再試行
            if _cnt < attempt_limit:
                logger.warning(f"Retry AjaxRequest: {type(e)}({e.args})")
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
                        attempt_limit: int,
                        wait_time: float,
                        timeout: float,
                        unescape: bool,
                        ) -> dict:
    # リクエスト用関数
    def _request(__site_name: str, __ssl: bool, __data: dict, __headers: dict, __timeout: float) -> dict:
        try:
            logger.debug(f"POST Ajax Request:\n"
                         f"\tURI: {'https://' if __ssl else 'http://'}{__site_name}.wikidot.com/ajax-module-connector.php\n"
                         f"\tHeaders: {__headers}\n"
                         f"\tData: {__data}")
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

        except Exception as e:
            # 再試行
            if _cnt < attempt_limit:
                logger.warning(f"Retry AjaxRequest: {type(e)}({e.args})")
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


def strToUnix(string: str) -> str:
    charTable = {"À": "A", "À": "A", "Á": "A", "Á": "A", "Â": "A", "Â": "A", "Ã": "A", "Ã": "A", "Ä": "Ae", "Ä": "A", "Å": "A", "Å": "A", "Æ": "Ae", "Æ": "AE", "Ā": "A",
                 "Ą": "A", "Ă": "A", "Ç": "C", "Ç": "C", "Ć": "C", "Č": "C", "Ĉ": "C", "Ċ": "C", "Ď": "D", "Đ": "D", "Ð": "D", "Ð": "D", "È": "E", "È": "E", "É": "E",
                 "É": "E", "Ê": "E", "Ê": "E", "Ë": "E", "Ë": "E", "Ē": "E", "Ę": "E", "Ě": "E", "Ĕ": "E", "Ė": "E", "Ĝ": "G", "Ğ": "G", "Ġ": "G", "Ģ": "G", "Ĥ": "H",
                 "Ħ": "H", "Ì": "I", "Ì": "I", "Í": "I", "Í": "I", "Î": "I", "Î": "I", "Ï": "I", "Ï": "I", "Ī": "I", "Ĩ": "I", "Ĭ": "I", "Į": "I", "İ": "I", "Ĳ": "IJ",
                 "Ĵ": "J", "Ķ": "K", "Ł": "K", "Ľ": "K", "Ĺ": "K", "Ļ": "K", "Ŀ": "K", "Ñ": "N", "Ñ": "N", "Ń": "N", "Ň": "N", "Ņ": "N", "Ŋ": "N", "Ò": "O", "Ò": "O",
                 "Ó": "O", "Ó": "O", "Ô": "O", "Ô": "O", "Õ": "O", "Õ": "O", "Ö": "Oe", "Ö": "Oe", "Ø": "O", "Ø": "O", "Ō": "O", "Ő": "O", "Ŏ": "O", "Œ": "OE", "Ŕ": "R",
                 "Ř": "R", "Ŗ": "R", "Ś": "S", "Š": "S", "Ş": "S", "Ŝ": "S", "Ș": "S", "Ť": "T", "Ţ": "T", "Ŧ": "T", "Ț": "T", "Ù": "U", "Ù": "U", "Ú": "U", "Ú": "U",
                 "Û": "U", "Û": "U", "Ü": "Ue", "Ū": "U", "Ü": "Ue", "Ů": "U", "Ű": "U", "Ŭ": "U", "Ũ": "U", "Ų": "U", "Ŵ": "W", "Ý": "Y", "Ý": "Y", "Ŷ": "Y", "Ÿ": "Y",
                 "Ź": "Z", "Ž": "Z", "Ż": "Z", "Þ": "T", "Þ": "T", "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "ae", "ä": "ae", "å": "a", "ā": "a", "ą": "a", "ă": "a",
                 "å": "a", "æ": "ae", "ç": "c", "ć": "c", "č": "c", "ĉ": "c", "ċ": "c", "ď": "d", "đ": "d", "ð": "d", "è": "e", "é": "e", "ê": "e", "ë": "e", "ē": "e",
                 "ę": "e", "ě": "e", "ĕ": "e", "ė": "e", "ƒ": "f", "ĝ": "g", "ğ": "g", "ġ": "g", "ģ": "g", "ĥ": "h", "ħ": "h", "ì": "i", "í": "i", "î": "i", "ï": "i",
                 "ī": "i", "ĩ": "i", "ĭ": "i", "į": "i", "ı": "i", "ĳ": "ij", "ĵ": "j", "ķ": "k", "ĸ": "k", "ł": "l", "ľ": "l", "ĺ": "l", "ļ": "l", "ŀ": "l", "ñ": "n",
                 "ń": "n", "ň": "n", "ņ": "n", "ŉ": "n", "ŋ": "n", "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "oe", "ö": "oe", "ø": "o", "ō": "o", "ő": "o", "ŏ": "o",
                 "œ": "oe", "ŕ": "r", "ř": "r", "ŗ": "r", "š": "s", "ù": "u", "ú": "u", "û": "u", "ü": "ue", "ū": "u", "ü": "ue", "ů": "u", "ű": "u", "ŭ": "u", "ũ": "u",
                 "ų": "u", "ŵ": "w", "ý": "y", "ÿ": "y", "ŷ": "y", "ž": "z", "ż": "z", "ź": "z", "þ": "t", "ß": "ss", "ſ": "ss", "à": "a", "á": "a", "â": "a", "ã": "a",
                 "ä": "ae", "å": "a", "æ": "ae", "ç": "c", "ð": "d", "è": "e", "é": "e", "ê": "e", "ë": "e", "ì": "i", "í": "i", "î": "i", "ï": "i", "ñ": "n", "ò": "o",
                 "ó": "o", "ô": "o", "õ": "o", "ö": "oe", "ø": "o", "ù": "u", "ú": "u", "û": "u", "ü": "ue", "ý": "y", "ÿ": "y", "þ": "t", "ß": "ss", " ": "-", ",": "-",
                 "/": "-", ".": "-"}

    table = str.maketrans(charTable)
    string = string.translate(table)

    string = string.lower()

    string = re.sub(r'[^a-z0-9\-:_]', '-', string)
    string = re.sub(r'^_', ':_', string)
    string = re.sub(r'(?<!:)_', '-', string)
    string = re.sub(r'^-*', '', string)
    string = re.sub(r'-*$', '', string)
    string = re.sub(r'[\-]{2,}', '-', string)
    string = re.sub(r'[:]{2,}', ':', string)

    string = string.replace(':-', ':')
    string = string.replace('-:', ':')
    string = string.replace('_-', '_')
    string = string.replace('-_', '_')

    string = re.sub(r'^:', '', string)
    string = re.sub(r':$', '', string)

    return string
