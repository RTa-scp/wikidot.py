class AMCRequestHeader:
    def __init__(self,
                 contentType: str | None = None,
                 userAgent: str | None = None,
                 referer: str | None = None,
                 cookie: dict | None = None):
        self.contentType = "application/x-www-form-urlencoded; charset=UTF-8" if contentType is None else contentType
        self.userAgent = "Python-wikidotpy" if userAgent is None else userAgent
        self.referer = "https://www.wikidot.com/" if referer is None else referer
        self.cookie = {
            "wikidot_token7": 123456
        }
        if cookie is not None:
            self.cookie.update(cookie)
        return

    def setCookie(self, name, value) -> None:
        self.cookie[name] = value
        return

    def delCookie(self, name) -> None:
        del self.cookie[name]
        return

    def isCookieSet(self, name) -> bool:
        return name in self.cookie

    def getHeader(self) -> dict:
        cookieStr = ""
        for name, value in self.cookie.items():
            cookieStr += f"{name}={value};"
        return {
            "Content-Type": self.contentType,
            "User-Agent": self.userAgent,
            "Referer": self.referer,
            "Cookie": cookieStr
        }


class APIKeys:
    def __init__(self,
                 ro: str | None = None,
                 rw: str | None = None):
        self.ro = ro
        self.rw = rw
        return

    def getReadOnlyKey(self):
        return self.ro

    def getReadWriteKey(self):
        return self.rw
