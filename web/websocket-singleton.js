
class WebSock {
    constructor(url) {
        if (WebSock.inst) {
            return WebSock.inst
        }
  
        WebSock.inst = new WebSocket(url)
    }
}
