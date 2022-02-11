from __future__ import annotations

import asyncio
from datetime import datetime

import bs4
import httpx
import requests  # TODO: httpxに置換する
from bs4 import BeautifulSoup, element as bs4Element

from . import customexceptions, datatypes, functions, logger

logger = logger.logger


class Parser:
    @staticmethod
    def userInfoPage(client: Client, src: str) -> User | None:
        """wikidot.com/user:info/~ のソースコード(str)からUserまたはNoneを返す

        Parameters
        ----------
        client: Client
            使用中のクライアント
        src: str
            user:infoページ全体のHTMLソースコード

        """
        element = BeautifulSoup(src, "lxml")

        # ユーザ存在判定　存在しなければNone
        pageContentElement = element.find(id="page-content")
        if (pageContentElement is not None and pageContentElement.get_text().strip() == "User does not exist.") or pageContentElement is None:
            return None

        # ↓ユーザが存在↓
        # ユーザID取得
        writePMButtonElement = pageContentElement.find(class_="btn btn-default btn-xs")
        userId: int | None = None
        if "href" in writePMButtonElement.attrs and "http://www.wikidot.com/account/messages#/new/" in writePMButtonElement.attrs["href"]:
            userId = int(writePMButtonElement.attrs["href"].replace("http://www.wikidot.com/account/messages#/new/", "").strip())

        # ユーザ名取得
        userName = pageContentElement.find(class_="profile-title").get_text().strip()
        userUnixName = userName.lower().replace(" ", "-").replace("_", "-")

        # その他パラメータ取得
        registration_date = None
        pro_status = False
        karma = None
        dlBox = pageContentElement.find("dl", class_="dl-horizontal")
        if dlBox is not None:
            dts = dlBox.find_all("dt", recursive=False)
            dds = dlBox.find_all("dd", recursive=False)
            for i in range(len(dts)):
                dt = dts[i].text
                dd = dds[i].text

                if "Wikidot user since" in dt:
                    registration_date = Parser.odate(dds[i].find("span", class_="odate"))
                elif "Account type" in dt:
                    if "Pro" in dd:
                        pro_status = True
                elif "Karma" in dt:
                    if "guru" in dd:
                        karma = 5
                    elif "very high" in dd:
                        karma = 4
                    elif "high" in dd:
                        karma = 3
                    elif "medium" in dd:
                        karma = 2
                    elif "low" in dd:
                        karma = 1
                    elif "none" in dd:
                        karma = 0

        return User.createUserObjectManually(client=client, id=userId, name=userName, unixName=userUnixName,
                                             registration_date=registration_date, pro_status=pro_status, karma=karma)

    @staticmethod
    def printUser(client: Client, printUserElement: bs4Element.Tag | bs4Element.NavigableString) -> User:
        """printuserクラスのbs4エレメントからUserクラスインスタンスを返す

        Parameters
        ----------
        client: Client
            使用中のクライアント
        printUserElement: bs4Element.Tag | bs4Element.NavigableString
            span.printuserのbs4エレメント
        """
        try:
            # Deleted Account
            if "class" in printUserElement.attrs and "deleted" in printUserElement["class"]:
                return User.createUserObjectManually(client=client, id=int(printUserElement["data-id"]), is_deleted=True)

            # Anonymous Account
            elif "class" in printUserElement.attrs and "anonymous" in printUserElement["class"]:
                return User.createUserObjectManually(client=client,
                                                     ip=printUserElement.find("span", class_="ip").get_text().replace("(", "").replace(")", "").strip(),
                                                     is_anonymous=True)

            # Wikidot (for ppd)
            elif printUserElement.get_text() == "Wikidot":
                return User.createUserObjectManually(client=client, is_wikidot=True)

            # [[user xxx]]構文用(アイコンなし)
            elif len(printUserElement.find_all("a", recursive=False)) == 1:
                _a_elem = printUserElement.find_all("a", recursive=False)[0]
                author_name = printUserElement.get_text()
                author_unix = author_name.replace("-", "_").replace(" ", "_").lower()
                author_id = None
                if "onclick" in _a_elem.attrs and "WIKIDOT.page.listeners.userInfo" in _a_elem["onclick"]:
                    author_id = int(
                        str(_a_elem["onclick"]).replace("WIKIDOT.page.listeners.userInfo(", "").replace(
                            "); return false;",
                            "")
                    )
                return User.createUserObjectManually(client=client, name=author_name, unixName=author_unix, id=author_id)

            # Unknown user
            elif "attrs" in vars(printUserElement) and "class" in printUserElement.attrs and "error-inline" in \
                    printUserElement.attrs["class"]:
                return User.createUserObjectManually(client=client, is_unknown=True)

            # Normal Account
            else:
                _author = printUserElement.find_all("a")[1]
                author_name = _author.get_text()
                author_unix = str(_author["href"]).replace("http://www.wikidot.com/user:info/", "")
                author_id = int(
                    str(_author["onclick"]).replace("WIKIDOT.page.listeners.userInfo(", "").replace("); return false;",
                                                                                                    "")
                )
                return User.createUserObjectManually(client=client, name=author_name, unixName=author_unix, id=author_id)

        except Exception:
            raise RuntimeError("Failed to parse a printuser element\n:" + printUserElement.prettify())

    @staticmethod
    def odate(odateElement: bs4Element.Tag | bs4Element.NavigableString) -> datetime:
        """odateのクラスからUnixタイムスタンプを取得してdatetime型にして返す

        Parameters
        ----------
        odateElement: bs4Element.Tag | bs4Element.NavigableString
            odateのbs4エレメント
        """
        _odate_classes = odateElement["class"]
        for _odate_class in _odate_classes:
            if "time_" in str(_odate_class):
                unixtime = int(str(_odate_class).replace("time_", ""))
                return datetime.fromtimestamp(unixtime)


class Client:
    """
    Wikidotへのセッション単位となる。
    wikidot.pyの諸機能はすべてClientオブジェクトから利用される。

    Attributes
    ----------
    self.user : User | None
        オブジェクト生成時にセッションを作成した場合、ログインユーザをUserオブジェクトで保持する。非ログイン時はNone。
    self.requestHeader : datatypes.AMCRequestHeader
        ajax-module-connector.phpへのリクエスト時のヘッダ情報を保持するオブジェクト。ログイン時はWIKIDOT_SESSION_IDが追加される。
    self.apiKeys : datatypes.APIKeys | None
        クライアントログインが行われ、api引数がTrueで、かつログインユーザがWikidotAPIを利用可能だった場合、datatypes.APIKeysオブジェクトが保持される。その他の場合はNone。
    """

    def __init__(self,
                 user: str | None = None,
                 password: str | None = None,
                 # api: bool = False,
                 asyncLimit: int = 40,
                 asyncLoopLength: int = 30,
                 asyncLoopWaitTime: float = 0,
                 amcAttemptLimit: int = 6,
                 amcWaitTime: float = 5,
                 amcTimeout: float = 40):
        """

        Parameters
        ----------
        user : str | None, default=None
            クライアントでログインするユーザ名。ログインしない場合はNone。
        password : str | None, default=None
            クライアントでログインするユーザのパスワード。ログインしない場合はNone。
            wikidot.pyはパスワードを直接保持せず、セッションIDのみを保持して利用する。
        # api : bool, default=False
        #     APIキーの取得を行うか。デフォルトではFalse。
        """
        
        self.asyncLimit = asyncLimit
        self.asyncLoopLength = asyncLoopLength
        self.asyncLoopWaitTime = asyncLoopWaitTime
        self.amcAttemptLimit = amcAttemptLimit
        self.amcWaitTime = amcWaitTime
        self.amcTimeout = amcTimeout

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
            # TODO: API処理実装
            # if api is True:
            #     self.apiKeys = self._get_api_keys()

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

    # ==================
    # クラス専用メソッド
    # ==================

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
                },
                attempt_limit=self.amcAttemptLimit,
                wait_time=self.amcWaitTime,
                timeout=self.amcTimeout,
                unescape=True
            )
            logger.debug("Session created.")

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
                },
                attempt_limit=self.amcAttemptLimit,
                wait_time=self.amcWaitTime,
                timeout=self.amcTimeout,
                unescape=True
            )
            self.requestHeader.delCookie("WIKIDOT_SESSION_ID")
            logger.debug("Session deleted.")
        except Exception:
            return False

    # AMCリクエスト用メソッド

    async def asyncAjaxRequest(self,
                               *,
                               site: Site = None,
                               body: dict,
                               attempt_limit: int = None,
                               wait_time: float = None,
                               timeout: float = None,
                               unescape: bool = True
                               ) -> dict:
        """Siteが指定されなかった場合にwww.wikidot.comにリクエストするようにしたfunctions.asyncAjaxRequest()
        """
        if site is None:
            site = Site(client=self, name="www", ssl=True)
        if attempt_limit is None:
            attempt_limit = self.amcAttemptLimit
        if wait_time is None:
            wait_time = self.amcWaitTime
        if timeout is None:
            timeout = self.amcTimeout
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
                            attempt_limit: int = None,
                            wait_time: float = None,
                            timeout: float = None,
                            unescape: bool = True,
                            ) -> dict:
        """Siteが指定されなかった場合にwww.wikidot.comにリクエストするようにしたfunctions.nonAsyncAjaxRequest()
        """
        if site is None:
            site = Site(client=self, name="www", ssl=True)
        if attempt_limit is None:
            attempt_limit = self.amcAttemptLimit
        if wait_time is None:
            wait_time = self.amcWaitTime
        if timeout is None:
            timeout = self.amcTimeout
        return functions.nonAsyncAjaxRequest(
            site=site,
            body=body,
            attempt_limit=attempt_limit,
            wait_time=wait_time,
            timeout=timeout,
            unescape=unescape
        )

    # ==========
    # boolReturn
    # ==========

    def isSessionCreated(self) -> bool:
        """ログインされているかを判定
        """
        return self.user is not None

    # ====================
    # 派生オブジェクト作成
    # ====================

    # Siteオブジェクト作成

    def getSite(self, name: str):
        """ユーザ名からSiteオブジェクトを作成して返す。

        Parameters
        ----------
        name : str
            サイトのUnix名
        """
        return Site.createSiteObjectByName(client=self, name=name)

    # Userオブジェクト作成

    def getUser(self, name: str) -> User | None:
        """ユーザ名からUserオブジェクトを作成して返す。ユーザが見つからなければNoneを返す。

        Parameters
        ----------
        name : str
            検索対象のユーザ名
        """
        return User.createUserObjectByName(self, name)

    # UserCollectionオブジェクト作成

    def getUsers(self, nameList: list[str] | tuple[str], asyncLimit: int | None = None) -> UserCollection:
        """ユーザ名からUserCollectionオブジェクトを作成して返す。見つからないユーザはスキップされる。

        Parameters
        ----------
        nameList : list[str] | tuple[str]
            検索対象のユーザ名のリスト
        asyncLimit : int | None
            並列リクエスト数
        """
        return UserCollection.createUserCollectionByNameList(self, nameList, asyncLimit)

    # PrivateMessageオブジェクト作成

    def createNewMessage(self,
                         recipient: User,
                         subject: str,
                         body: str) -> PrivateMessage:
        """[Session Required] 新規PMを作成する。送信にはPrivateMessage.save()メソッドが必要。

        Parameters
        ----------
        recipient : User
            宛先ユーザ
        subject : str
            件名
        body : str
            本文
        """
        if not self.isSessionCreated():
            raise customexceptions.SessionRequiredError()

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
                 id: int | None = None,
                 ssl: bool = False,
                 private: bool = False,
                 # forum_category: str = None
                 ):
        self.client = client
        self.name = name
        self.title = title
        self.domain = domain
        self.id = id
        self.ssl = ssl
        self.private = private
        # self.forum_category = forum_category

        # getinfo
        _resp = requests.get(f"http://{self.name}.wikidot.com")
        if _resp.status_code == 404:
            raise customexceptions.NotFound(f"{self.name}.wikidot.com is not found")

        # domain, id, private
        for line in _resp.text.split("\n"):
            if "isUAMobile" in line:
                break
            elif "WIKIREQUEST.info.domain" in line:
                self.domain = line.replace('WIKIREQUEST.info.domain = "', "").replace('";', "").strip()
            elif "WIKIREQUEST.info.siteId" in line:
                self.id = int(line.replace('WIKIREQUEST.info.siteId =', "").replace(';', "").strip())
            elif "WIKIREQUEST.info.requestPageName" in line and "system:join" in line:
                self.private = True
        # force SSL
        for his in _resp.history:
            if his.status_code == 301 and "Location" in his.headers and "https://" in his.headers["Location"]:
                self.ssl = True
        # get title
        bs4Parse = bs4.BeautifulSoup(_resp.text, "lxml")
        titleElem = bs4Parse.select_one("div#header > h1 > a > span")
        if titleElem is not None:
            self.title = titleElem.get_text().strip()

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        return f"<Site: {self.name}>"

    # =======================
    # AMCリクエスト用メソッド
    # =======================

    async def asyncAjaxRequest(self,
                               *,
                               site: Site | None = None,
                               body: dict,
                               attempt_limit: int = None,
                               wait_time: float = None,
                               timeout: float = None,
                               unescape: bool = True,
                               ) -> dict:
        """Siteが指定されなかった場合にselfにリクエストするようにしたfunctions.asyncAjaxRequest()
        """
        if site is None:
            site = self
        return await self.client.asyncAjaxRequest(
            site=site,
            body=body,
            attempt_limit=attempt_limit,
            wait_time=wait_time,
            timeout=timeout,
            unescape=unescape
        )

    def nonAsyncAjaxRequest(self,
                            *,
                            site: Site | None = None,
                            body: dict,
                            attempt_limit: int = None,
                            wait_time: float = None,
                            timeout: float = None,
                            unescape: bool = None,
                            ) -> dict:
        """Siteが指定されなかった場合にselfにリクエストするようにしたfunctions.nonAsyncAjaxRequest()
        """
        if site is None:
            site = self
        return self.client.nonAsyncAjaxRequest(
            site=site,
            body=body,
            attempt_limit=attempt_limit,
            wait_time=wait_time,
            timeout=timeout,
            unescape=unescape
        )

    # ========
    # self作成
    # ========
    @staticmethod
    def createSiteObjectByName(client: Client, name: str) -> Site:
        return Site(client=client, name=name)

    # ==============
    # クラスメソッド
    # ==============
    def getMembers(self, asyncLimit: int = None) -> SiteMemberCollection:
        return SiteMemberCollection.createSiteMemberCorrectionFromSiteObject(site=self, asyncLimit=asyncLimit)


class User:
    def __init__(self,
                 client: Client,
                 id: int = None,
                 name: str = None,
                 unixName: str = None,
                 ip: str = None,
                 registration_date: datetime = None,
                 pro_status: bool = False,
                 karma: int = None,
                 is_wikidot: bool = False,
                 is_anonymous: bool = False,
                 is_deleted: bool = False,
                 is_unknown: bool = False
                 ):

        # Check

        if is_wikidot:
            if name != "Wikidot" and unixName != "wikidot":
                raise ValueError("Incorrect instance creation may have occurred.")
        elif is_anonymous:
            if ip is None:
                raise ValueError("Give an IP address of the anonymous user.")
        elif is_deleted:
            if name != "account deleted" and unixName != "account-deleted":
                raise ValueError("Incorrect instance creation may have occurred.")
        elif is_unknown:
            if name != "unknown user" and unixName != "unknown-user":
                raise ValueError("Incorrect instance creation may have occurred.")

        self.client = client
        self.id = id
        self.name = name
        self.unixName = unixName
        self.ip = ip
        self.registration_date = registration_date
        self.pro_status = pro_status
        self.karma = karma
        self.is_wikidot = is_wikidot
        self.is_anonymous = is_anonymous
        self.is_deleted = is_deleted
        self.is_unknown = is_unknown

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        if self.is_wikidot:
            return f"<User: WikidotSystem>"
        elif self.is_anonymous:
            return f"<User: Anonumous({self.ip})>"
        elif self.is_deleted:
            return f"<User: DeletedUser({self.id})>"
        elif self.is_unknown:
            return f"<User: UnknownUser>"
        else:
            return f"<User: {self.name}({self.id})>"

    # ========
    # self作成
    # ========

    @staticmethod
    def createUserObjectByName(client: Client, name: str) -> User | None:
        # nameをunix系に整形
        name = name.lower().replace(" ", "-").replace("_", "-")
        # user:infoをgetしてbs4でパース
        src = httpx.get("https://www.wikidot.com/user:info/" + name).text
        return Parser.userInfoPage(client, src)

    @staticmethod
    def createUserObjectManually(client: Client,
                                 id: int = None,
                                 name: str = None,
                                 unixName: str = None,
                                 ip: str = None,
                                 registration_date: datetime = None,
                                 pro_status: bool = False,
                                 karma: int = None,
                                 is_wikidot: bool = False,
                                 is_anonymous: bool = False,
                                 is_deleted: bool = False,
                                 is_unknown: bool = False) -> User:
        if is_wikidot:
            return User(client=client, name="Wikidot", unixName="wikidot", is_wikidot=True)
        elif is_anonymous:
            return User(client=client, ip=ip, is_anonymous=True)
        elif is_deleted:
            return User(client=client, name="account deleted", unixName="account-deleted", is_deleted=True)
        elif is_unknown:
            return User(client=client, name="unknown user", unixName="unknown-user", is_unknown=True)
        else:
            return User(client=client, id=id, name=name, unixName=unixName, registration_date=registration_date,
                        pro_status=pro_status, karma=karma)

    # ========
    # 自己変換
    # ========

    def convertToSiteMember(self, site: Site, joinDate: datetime = None) -> SiteMember:
        return SiteMember.convertFromUserToSiteMember(user=self, site=site, joinDate=joinDate)


class UserCollection(list):
    def __init__(self, client: Client, objects: list[User] | tuple[User]):
        super().__init__()
        self.client = client
        self.extend(list(objects))

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        return f"<UserCollection({len(self)}): {', '.join([str(user) for user in self])}>"

    # ========
    # self作成
    # ========

    @staticmethod
    def createUserCollectionByNameList(client: Client, names: list[str] | tuple[str],
                                       asyncLimit: int | None = None) -> UserCollection:
        async def _getSource(_name: str):
            while True:
                try:
                    async with httpx.AsyncClient() as _client:
                        return await _client.get(
                            "https://www.wikidot.com/user:info/" + _name,
                            timeout=60
                        )
                except httpx.ConnectError:
                    # print("go continue")
                    await asyncio.sleep(client.amcWaitTime)
                    continue

        async def _main(_names, _limit):
            async def __executor(__name, __limit):
                async with asyncio.Semaphore(__limit):
                    __src = await _getSource(__name.lower().replace(" ", "-").replace("_", "-"))
                    __src = __src.text
                    return __name, __src

            stmt = [__executor(t, _limit) for t in _names]

            return await asyncio.gather(*stmt)

        if asyncLimit is None:
            asyncLimit = client.asyncLimit

        loop = asyncio.get_event_loop()
        sources = []
        while len(names) > 0:
            sources.extend(loop.run_until_complete(_main(names[:client.asyncLoopLength], asyncLimit)))
            del names[:client.asyncLoopLength]

        objects = []
        for name, src in sources:
            obj = Parser.userInfoPage(client, src)
            if obj is not None:
                objects.append(obj)

        return UserCollection(client=client, objects=objects)

    # ========
    # 自己変換
    # ========

    def convertToSiteMemberCollection(self, site: Site) -> SiteMemberCollection:
        return SiteMemberCollection.createSiteMemberCorrectionFromUserCollection(site=site, userCollection=self)


class SiteMember(User):
    def __init__(self, site: Site, id: int, name: str, unixName: str, joinDate: datetime = None):
        super().__init__(site.client, id, name, unixName)
        self.site = site
        self.joinDate = joinDate

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        return f"<SiteMember: {self.name}({self.id}) in {self.site.name}>"

    # ========
    # self作成
    # ========

    @staticmethod
    def createSiteMemberObjectByName(site: Site, name: str) -> SiteMember | None:
        user = User.createUserObjectByName(client=site.client, name=name)
        if user is None:
            return None
        else:
            return SiteMember(site=site, id=user.id, name=user.name, unixName=user.unixName)

    @staticmethod
    def createSiteMemberObjectManually(site: Site, id: int, name: str, unixName: str, joinDate: datetime = None) -> SiteMember:
        return SiteMember(site=site, id=id, name=name, unixName=unixName, joinDate=joinDate)

    # ========
    # 自己変換
    # ========

    @staticmethod
    def convertFromUserToSiteMember(user: User, site: Site, joinDate: datetime = None) -> SiteMember:
        return SiteMember(site=site, id=user.id, name=user.name, unixName=user.unixName, joinDate=joinDate)


class SiteMemberCollection(list):
    def __init__(self, client: Client, objects: list[SiteMember]):
        super().__init__()
        self: list[SiteMember]
        self.client = client
        self.extend(list(objects))

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        return f"<SiteMemberCollection({len(self)}): {', '.join([str(user) for user in self])}>"

    # ========
    # self作成
    # ========

    @staticmethod
    def createSiteMemberCorrectionFromUserCollection(site: Site,
                                                     userCollection: UserCollection) -> SiteMemberCollection:
        return SiteMemberCollection(client=site.client,
                                    objects=[user.convertToSiteMember(site=site) for user in userCollection])

    # ==============
    # クラスメソッド
    # ==============
    @staticmethod
    def createSiteMemberCorrectionFromSiteObject(site: Site, asyncLimit: int = None) -> SiteMemberCollection:
        async def _getData(_site: Site, _page: int):
            while True:
                try:
                    _r = await _site.asyncAjaxRequest(
                        body={
                            "moduleName": "membership/MembersListModule",
                            "page": _page,
                            "group": "",
                            "order": "",
                        }
                    )
                    if "body" in _r:
                        return _r["body"]
                    else:
                        raise customexceptions.ReturnedDataError("Error")
                except customexceptions.RequestError:
                    # print("go continue")
                    await asyncio.sleep(_site.client.amcWaitTime)
                    continue

        def _parseBody(_site: Site, _src: str):
            # parse
            _bodyElement = bs4.BeautifulSoup(_src, 'lxml')

            # pager
            _pager = _bodyElement.find("div", class_="pager")
            if _pager is not None:
                _total = int(_pager.find_all("span", class_="target")[-2].string)
            else:
                _total = 1

            _members = _bodyElement.find_all("tr")

            _r: list[SiteMember] = []

            if _members is None:
                return None
            else:
                for _member in _members:
                    _user = Parser.printUser(_site.client, _member.find("span", class_="printuser"))
                    _joinDate = Parser.odate(_member.find("span", class_="odate"))
                    _siteMember = _user.convertToSiteMember(site=_site, joinDate=_joinDate)
                    _r.append(_siteMember)

            # print("success")

            return _total, _r

        async def _main(_site: Site, _asyncLimit: int):
            async def __executor(__site: Site, __page: int, __asyncLimit: int, __first: bool):
                async with asyncio.Semaphore(__asyncLimit):
                    __src = await _getData(__site, __page)
                    if __first:
                        return _parseBody(__site, __src)
                    else:
                        return _parseBody(__site, __src)[1]

            _total, _users = await __executor(_site, 1, _asyncLimit, True)

            _stmt = [__executor(_site, _pageNum + 1, _asyncLimit, False) for _pageNum in range(_total)]

            _results = []

            while len(_stmt) > 0:
                # print("====loop====")
                _results.extend(await asyncio.gather(*_stmt[:site.client.asyncLoopLength]))
                del _stmt[:site.client.asyncLoopLength]
                await asyncio.sleep(site.client.asyncLoopWaitTime)

            return _results

        if asyncLimit is None:
            asyncLimit = site.client.asyncLimit

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(_main(site, asyncLimit))
        objects = []
        for r in results:
            objects.extend(r)
        return SiteMemberCollection(client=site.client, objects=objects)


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

    # ============
    # 組み込み関数
    # ============

    def __str__(self):
        return f"<PrivateMessage: from {self.sender.name} to {self.recipient.name}>"

    # ========
    # self作成
    # ========

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

    # ==============
    # クラスメソッド
    # ==============

    def send(self) -> PrivateMessage:
        try:
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
        except customexceptions.NotOK as e:
            if e.status_code == "no_permission":
                raise customexceptions.Forbidden("You can't send private messages to this recipient.")
            else:
                raise
