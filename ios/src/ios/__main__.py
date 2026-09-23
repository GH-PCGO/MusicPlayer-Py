# -*- coding: utf-8 -*-
"""iOS 入口: 启动本地 webapp 服务器, 并用 WKWebView 打开 127.0.0.1。

main.m 在 runpy 执行完本模块后调用 UIApplicationMain(..., @"PythonAppDelegate"),
因此这里只定义 AppDelegate (继承 UIResponder 以便 Rubicon 注册 ObjC 类), 不自己调用 UIApplicationMain。
"""
import os

from rubicon.objc import ObjCClass

from musicplayer import paths, webapp

NSURL = ObjCClass("NSURL")
NSFileManager = ObjCClass("NSFileManager")
UIResponder = ObjCClass("UIResponder")
UIWindow = ObjCClass("UIWindow")
UIScreen = ObjCClass("UIScreen")
UIColor = ObjCClass("UIColor")
UIViewController = ObjCClass("UIViewController")
WKWebView = ObjCClass("WKWebView")
WKWebViewConfiguration = ObjCClass("WKWebViewConfiguration")
WKWebsiteDataStore = ObjCClass("WKWebsiteDataStore")
NSURLRequest = ObjCClass("NSURLRequest")

NSDocumentDirectory = 9
NSUserDomainMask = 1
WKAudiovisualMediaTypeNone = 0


def _documents_dir():
    urls = NSFileManager.defaultManager().URLsForDirectory(
        NSDocumentDirectory, NSUserDomainMask
    )
    if urls and len(urls) > 0:
        return str(urls[0].path)
    return os.path.expanduser("~")


paths.set_download_dir(os.path.join(_documents_dir(), "music"))

PORT = webapp.start(port=8760, host="127.0.0.1")
BASE_URL = "http://127.0.0.1:%d/" % PORT


class PythonAppDelegate(UIResponder):
    def application_didFinishLaunchingWithOptions_(self, app, options):
        frame = UIScreen.mainScreen.bounds
        window = UIWindow.alloc().initWithFrame(frame)

        config = WKWebViewConfiguration.alloc().init()
        config.websiteDataStore = WKWebsiteDataStore.defaultDataStore

        webview = WKWebView.alloc().initWithFrame_configuration(frame, config)
        webview.allowsInlineMediaPlayback = True
        webview.mediaTypesRequiringUserActionForPlayback = WKAudiovisualMediaTypeNone
        webview.opaque = False
        webview.backgroundColor = UIColor.whiteColor

        controller = UIViewController.alloc().init()
        controller.view = webview
        window.rootViewController = controller
        window.makeKeyAndVisible()

        url = NSURL.URLWithString(BASE_URL)
        webview.loadRequest(NSURLRequest.requestWithURL(url))
        return True
