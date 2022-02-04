from __future__ import annotations
import requests  # TODO: httpxに置換する
import httpx
from bs4 import BeautifulSoup

from . import customexceptions, datatypes, functions


class Client:
    def __init__(self,
                 user: str | None = None,
                 password: str | None = None,
                 api: bool = False):
        # ユーザ名
        self.user: None | User
        if user is None:
            self.user = None
        else:
            self.user = User.createUserObjectByName(self, user)
        # リクエストヘッダオブジェクト
        self.requestHeader: datatypes.AMCRequestHeader = datatypes.AMCRequestHeader()
        # WikidotAPIキー
        # api引数がFalse、またはAPIキーが取得できなかった場合はNoneとなる
        self.apiKeys: datatypes.APIKeys | None = None

        # ログイン試行
        if user is not None and password is not None:
            self._login(user, password)
            # APIキー取得試行
            if api is True:
                self.apiKeys = self._get_api_keys()

    def __del__(self):
        # セッションを破棄する
        if self.requestHeader.isCookieSet("WIKIDOT_SESSION_ID"):
            self._logout()
        del self
        return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # exit時にdelを呼び出してセッション破棄を行う
        self.__del__()
        return

    def __str__(self):
        if "WIKIDOT_SESSION_ID" in self.requestHeader.cookie:
            return f"<Client: {self.user.name}>"
        return "<Client: NoSession>"

    def _login(self, user: str, password: str) -> None:
        try:
            # AMC Session Open
            _loginRequest = requests.post(
                url="https://www.wikidot.com/default--flow/login__LoginPopupScreen",
                data={
                    "login": user,
                    "password": password,
                    "action": "Login2Action",
                    "event": "login"
                },
                headers=self.requestHeader.getHeader(),
                timeout=20
            )

            self.requestHeader.setCookie("WIKIDOT_SESSION_ID", _loginRequest.cookies['WIKIDOT_SESSION_ID'])

            functions.nonAsyncAjaxRequest(
                site=Site(client=self, name="www", ssl=True),
                body={
                    "moduleName": "dashboard/settings/DSAccountModule"
                }
            )

        except customexceptions.NotOK as e:
            if e.status_code == "no_permission":
                raise customexceptions.SessionCreateError(
                    "Failed to create session. Please check your username and password."
                )
            else:
                raise customexceptions.SessionCreateError(
                    f"Failed to create session due to unexpected problem: {e}, {e.status_code}",
                )

        except Exception as e:
            raise customexceptions.SessionCreateError(
                f"Failed to create session due to unexpected problem: {e}",
            )

    def _logout(self):
        try:
            functions.nonAsyncAjaxRequest(
                site=Site(client=self, name="www", ssl=True),
                body={
                    "action": "Login2Action",
                    "event": "logout",
                    "moduleName": "Empty"
                }
            )
            self.requestHeader.delCookie("WIKIDOT_SESSION_ID")
        except Exception:
            return False

    async def asyncAjaxRequest(self,
                               *,
                               site: Site = None,
                               body: dict,
                               attempt_limit: int = 6,
                               wait_time: float = 10,
                               timeout: float = 40,
                               unescape: bool = True,
                               ) -> dict:
        if site is None:
            site = Site(client=self, name="www", ssl=True)
        return await functions.asyncAjaxRequest(
            site=site,
            body=body,
            attempt_limit=attempt_limit,
            wait_time=wait_time,
            timeout=timeout,
            unescape=unescape
        )

    def nonAsyncAjaxRequest(self,
                            *,
                            site: Site = None,
                            body: dict,
                            attempt_limit: int = 6,
                            wait_time: float = 10,
                            timeout: float = 40,
                            unescape: bool = True,
                            ) -> dict:
        if site is None:
            site = Site(client=self, name="www", ssl=True)
        return functions.nonAsyncAjaxRequest(
            site=site,
            body=body,
            attempt_limit=attempt_limit,
            wait_time=wait_time,
            timeout=timeout,
            unescape=unescape
        )

    def isSessionCreated(self) -> book:
        return self.user is not None

    def getUser(self, name: str) -> User | None:
        return User.createUserObjectByName(self, name)

    def createNewMessage(self,
                         recipient: User,
                         subject: str,
                         body: str) -> PrivateMessage:
        if not self.isSessionCreated():
            raise

        return PrivateMessage.createNewMessage(self,
                                               recipient=recipient,
                                               subject=subject,
                                               body=body)


class Site:
    def __init__(self,
                 client: Client,
                 name: str,
                 title: str | None = None,
                 domain: str | None = None,
                 site_id: int | None = None,
                 ssl: bool = False,
                 private: bool = False,
                 forum_category: str = None):
        self.client = client
        self.name = name
        self.title = title
        self.domain = domain
        self.site_id = site_id
        self.ssl = ssl
        self.private = private
        self.forum_category = forum_category

        # getinfo
        _resp = requests.get(f"http://{self.name}.wikidot.com")
        for line in _resp.text.split("\n"):
            if "isUAMobile" in line:
                break
            elif "WIKIREQUEST.info.domain" in line:
                self.domain = line.replace('WIKIREQUEST.info.domain = "', "").replace('";', "").strip()
            elif "WIKIREQUEST.info.siteId" in line:
                self.site_id = int(line.replace('WIKIREQUEST.info.siteId =', "").replace(';', "").strip())
            elif "WIKIREQUEST.info.requestPageName" in line and "system:join" in line:
                self.private = True
        # force SSL
        for his in _resp.history:
            if his.status_code == 301 and "Location" in his.headers and "https://" in his.headers["Location"]:
                self.ssl = True

    def __str__(self):
        return f"<Site: {self.name}>"


class User:
    def __init__(self,
                 client: Client,
                 id: int,
                 name: str,
                 unixName: str):
        self.client = client
        self.id = id
        self.name = name
        self.unixName = unixName

    def __str__(self):
        return f"<User: {self.name}({self.id})>"

    @staticmethod
    def createUserObjectByName(client: Client, name: str) -> User:
        # nameをunix系に整形
        name = name.lower().replace(" ", "-").replace("_", "-")

        # user:infoをgetしてbs4でパース
        bs4Element = BeautifulSoup(httpx.get("https://www.wikidot.com/user:info/" + name).text, "lxml")

        # ユーザ存在判定　存在しなければNone
        pageContentElement = bs4Element.find(id="page-content")
        if pageContentElement is not None and pageContentElement.get_text().strip() == "User does not exist.":
            return None

        # ↓ユーザが存在↓
        # ユーザID取得
        writePMButtonElement = pageContentElement.find(class_="btn btn-default btn-xs")
        userId: int | None = None
        if "href" in writePMButtonElement.attrs \
                and "http://www.wikidot.com/account/messages#/new/" in writePMButtonElement.attrs["href"]:
            userId = int(
                writePMButtonElement.attrs["href"].replace("http://www.wikidot.com/account/messages#/new/", "").strip())

        # ユーザ名取得
        userName = pageContentElement.find(class_="profile-title").get_text().strip()
        userUnixName = userName.lower().replace(" ", "-").replace("_", "-")

        return User(client=client, id=userId, name=userName, unixName=userUnixName)


class PrivateMessage:
    def __init__(self,
                 client: Client,
                 sender: User,
                 recipient: User,
                 subject: str,
                 body: str,
                 sendStatus: bool):
        self.client: Client = client
        self.sender: User = sender
        self.recipient: User = recipient
        self.subject: str = subject
        self.body: str = body
        self.sendStatus: bool = sendStatus

    def send(self) -> PrivateMessage:
        self.client.nonAsyncAjaxRequest(
            body={
                "source": self.body,
                "subject": self.subject,
                "to_user_id": self.recipient.id,
                "action": "DashboardMessageAction",
                "event": "send",
                "moduleName": "Empty"
            }
        )
        self.sendStatus = True
        return self

    @staticmethod
    def createNewMessage(client: Client,
                         recipient: User,
                         subject: str,
                         body: str) -> PrivateMessage:
        if client.isSessionCreated():
            return PrivateMessage(
                client=client,
                sender=client.user,
                recipient=recipient,
                subject=subject,
                body=body,
                sendStatus=False
            )
