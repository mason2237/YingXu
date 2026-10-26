import QtQuick
import QtWebEngine
import QtWebChannel
import QtQuick.Window

Item {
    id: root
    objectName: "nativeRoot"
    property url documentUrl: ""
    property int settleFrames: 0
    readonly property bool drawable: nativeHost.loaded && nativeHost.visible
                                    && nativeHost.visibility !== Window.Minimized
    WebChannel { id: localChannel; objectName: "localChannel" }
    WebEngineView {
        id: web
        objectName: "nativeWeb"
        anchors.fill: parent
        profile: nativeProfile
        webChannel: localChannel
        userScripts.collection: [{ name: "yingxu-native-bootstrap", sourceCode: nativeHost.bootScript,
            injectionPoint: WebEngineScript.DocumentCreation, worldId: WebEngineScript.MainWorld, runsOnSubFrames: false }]
        url: root.documentUrl
        backgroundColor: nativeHost.pageBackground
        focus: true
        settings.localContentCanAccessRemoteUrls: false
        settings.localContentCanAccessFileUrls: false
        settings.javascriptCanOpenWindows: false
        settings.pluginsEnabled: false
        settings.pdfViewerEnabled: false
        settings.fullScreenSupportEnabled: false
        onNavigationRequested: function(request) {
            if (!nativeHost.allowNavigation(request.url)) request.action = WebEngineNavigationRequest.IgnoreRequest
        }
        onPermissionRequested: function(permission) { permission.deny() }
        onContextMenuRequested: function(request) { request.accepted = true }
        onFileDialogRequested: function(request) { request.accepted = true; request.dialogReject() }
        onLoadingChanged: function(request) { nativeHost.loadingEvent(request.status) }
        onJavaScriptConsoleMessage: function(level, message, lineNumber, sourceID) {
            nativeHost.consoleMessage(level, message, lineNumber)
        }
        onRenderProcessTerminated: function(status, code) { nativeHost.renderTerminated(code) }
    }
    // SDR is drawn directly by WebEngine. Allocate an additional full-window
    // texture and color-conversion pass only for the actual HDR swapchain.
    Loader {
        id: hdrLayer
        objectName: "hdrLayer"
        anchors.fill: parent
        active: nativeHost.hdrActive
        visible: nativeHost.loaded
        sourceComponent: Item {
            function refreshTexture() { pageTexture.scheduleUpdate() }
            ShaderEffectSource {
                id: pageTexture
                sourceItem: web
                // Keep the direct node alive for Chromium visibility tracking.
                hideSource: false
                live: root.drawable
                textureSize: Qt.size(root.width * nativeHost.pixelRatio, root.height * nativeHost.pixelRatio)
            }
            ShaderEffect {
                anchors.fill: parent
                property variant source: pageTexture
                property real whiteScale: nativeHost.whiteScale
                property real hdrActive: nativeHost.hdrActive ? 1.0 : 0.0
                property real highlightBoost: nativeHost.highlightBoost
                property vector2d texelSize: Qt.vector2d(1.0 / Math.max(1, root.width * nativeHost.pixelRatio), 1.0 / Math.max(1, root.height * nativeHost.pixelRatio))
                fragmentShader: "hdr.frag.qsb"
            }
        }
    }
    // Live textures already follow WebEngine's damage. Only supplement a few
    // frames at overlay transitions, not 60 wakeups/s while settings sit idle.
    Timer {
        objectName: "modalFramePump"
        interval: 16
        repeat: true
        running: root.drawable && hdrLayer.active && root.settleFrames > 0
        onTriggered: {
            if (hdrLayer.item) hdrLayer.item.refreshTexture()
            root.settleFrames--
        }
    }
    Connections {
        target: compositorHints
        function onChanged(active) {root.settleFrames = 8}
    }
    Rectangle {
        anchors.fill: parent
        color: nativeHost.coverColor
        visible: !nativeHost.loaded
        Text { anchors.centerIn: parent; text: nativeHost.loadingText; color: "#aec5ea"; font.family: "Noto Sans SC"; font.pixelSize: 20 }
    }
    DropArea {
        anchors.fill: parent
        onEntered: function(drag) { drag.accepted = drag.hasUrls && drag.urls.length === 1 }
        onDropped: function(drop) {
            if (drop.hasUrls && drop.urls.length === 1) { nativeHost.dropFolder(drop.urls[0]); drop.accepted = true }
        }
    }
    Connections {
        target: nativeHost
        function onEvaluate(code, token) {
            web.runJavaScript(code, function(value) { nativeHost.javascriptResult(token, JSON.stringify(value) || "null") })
        }
        function onReloadWeb() { web.reload() }
        function onStopWeb() { web.stop() }
        function onEnableWeb(enabled) { web.enabled = enabled }
    }
    Shortcut { sequence: "Ctrl+R"; onActivated: nativeHost.reloadPage() }
}
