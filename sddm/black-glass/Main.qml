import QtQuick
import QtQuick.Effects
import "components"

// Black Glass - SDDM (Qt6) greeter theme.
// Context objects used from SDDM: sddm, userModel, sessionModel, config, keyboard.

Rectangle {
    id: root

    width: 1920
    height: 1080
    color: "#000000"
    clip: true

    // ------------------------------------------------------------------ config
    readonly property real s: Math.max(0.65, Math.min(1.6, Math.min(width / 1920, height / 1080)))
    readonly property string fontFamily: config.fontFamily || "Inter"
    readonly property bool fx: config.enableBlur !== "false"
    readonly property bool clock24h: config.clock24h !== "false"
    readonly property real bgBlur: config.backgroundBlur ? parseFloat(config.backgroundBlur) : 0.55
    readonly property url bgSource: Qt.resolvedUrl(config.background || "assets/background.png")
    readonly property int bleed: 80

    // ------------------------------------------------------------------- state
    property int sessionIndex: Math.max(0, sessionModel.lastIndex)
    property bool busy: false
    property string errorMessage: ""
    property string lastStatus: ""
    property real shakeX: 0
    property int userTick: 0

    readonly property bool capsOn: (typeof keyboard !== "undefined") && keyboard.capsLock
    readonly property string statusText: errorMessage !== "" ? errorMessage : (capsOn ? "Caps Lock is on" : "")
    onStatusTextChanged: if (statusText !== "") lastStatus = statusText

    // Intro / outro orchestration: one timeline, staggered per element.
    property real intro: 0
    property real leave: 0
    NumberAnimation on intro { from: 0; to: 1; duration: 1700; running: true }
    Behavior on leave { NumberAnimation { duration: 800; easing.type: Easing.InOutCubic } }

    function stage(a, b) {
        var t = Math.max(0, Math.min(1, (intro - a) / (b - a)))
        return 1 - Math.pow(1 - t, 3)
    }

    // ------------------------------------------------------------- user lookup
    Repeater {
        id: userRep
        model: userModel
        onItemAdded: root.userTick++
        delegate: Item {
            visible: false
            property string uname: model.name
            property string uicon: model.icon
        }
    }
    function userInfo(name) {
        userTick
        for (var i = 0; i < userRep.count; ++i) {
            var it = userRep.itemAt(i)
            if (it && it.uname === name)
                return it
        }
        return null
    }
    function iconUrl(p) {
        if (!p)
            return ""
        var str = String(p)
        return (str.indexOf("://") >= 0 || str.indexOf("qrc:") === 0) ? str : "file://" + str
    }
    readonly property var currentUser: userInfo(userField.text)

    // ------------------------------------------------------------------- login
    function attemptLogin() {
        if (busy)
            return
        if (userField.text.length === 0) {
            shake.restart()
            userField.input.forceActiveFocus()
            return
        }
        errorMessage = ""
        busy = true
        watchdog.restart()
        sddm.login(userField.text, passField.text, sessionIndex)
    }

    Connections {
        target: sddm
        function onLoginSucceeded() {
            watchdog.stop()
            root.leave = 1
        }
        function onLoginFailed() {
            watchdog.stop()
            root.busy = false
            root.errorMessage = "Incorrect username or password."
            passField.text = ""
            shake.restart()
            passField.input.forceActiveFocus()
        }
    }
    // If the daemon never answers (e.g. test mode), do not hang in the busy state.
    Timer {
        id: watchdog
        interval: 15000
        onTriggered: {
            root.busy = false
            root.errorMessage = "No response from the login service."
        }
    }

    SequentialAnimation {
        id: shake
        NumberAnimation { target: root; property: "shakeX"; to: -11 * root.s; duration: 55; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "shakeX"; to: 9 * root.s; duration: 90; easing.type: Easing.InOutCubic }
        NumberAnimation { target: root; property: "shakeX"; to: -6 * root.s; duration: 80; easing.type: Easing.InOutCubic }
        NumberAnimation { target: root; property: "shakeX"; to: 3 * root.s; duration: 70; easing.type: Easing.InOutCubic }
        NumberAnimation { target: root; property: "shakeX"; to: 0; duration: 70; easing.type: Easing.OutCubic }
    }

    // -------------------------------------------------------------- wallpaper
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#161616" }
            GradientStop { position: 1.0; color: "#050505" }
        }
    }
    Image {
        id: wallpaper
        x: -root.bleed
        y: -root.bleed
        width: root.width + root.bleed * 2
        height: root.height + root.bleed * 2
        source: root.bgSource
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        smooth: true
    }
    MultiEffect {
        id: wallBlur
        x: -root.bleed
        y: -root.bleed
        width: root.width + root.bleed * 2
        height: root.height + root.bleed * 2
        source: wallpaper
        visible: root.fx && wallpaper.status === Image.Ready
        autoPaddingEnabled: false
        blurEnabled: true
        blur: Math.max(0, Math.min(1, root.bgBlur))
        blurMax: 64
        brightness: -0.22
        saturation: -1.0
    }
    // subtle dark veil + vertical falloff for depth
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.38) }
            GradientStop { position: 0.45; color: Qt.rgba(0, 0, 0, 0.14) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.52) }
        }
    }

    // ------------------------------------------------------------------- clock
    Clock {
        id: clock
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.095 + (1 - root.stage(0.15, 0.65)) * 14 * root.s
        unit: root.s
        fontFamily: root.fontFamily
        use24h: root.clock24h
        opacity: root.stage(0.15, 0.65) * (1 - root.leave)
    }

    // ------------------------------------------------------------- login panel
    GlassPanel {
        id: panel
        backdrop: root.fx ? wallBlur : null
        fx: root.fx && wallBlur.visible
        radius: 32 * root.s
        width: 330 * root.s
        height: column.implicitHeight + 68 * root.s
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(root.height * 0.095 + clock.implicitHeight + 36 * root.s, root.height * 0.58 - height / 2)
        opacity: root.stage(0.30, 0.85) * (1 - root.leave)
        scale: 1 - root.leave * 0.04

        Column {
            id: column
            width: parent.width - 52 * root.s
            y: 34 * root.s + (1 - root.stage(0.35, 0.95)) * 12 * root.s
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.horizontalCenterOffset: root.shakeX
            spacing: 12 * root.s

            Avatar {
                anchors.horizontalCenter: parent.horizontalCenter
                size: 92 * root.s
                fontFamily: root.fontFamily
                name: userField.text
                icon: root.currentUser ? root.iconUrl(root.currentUser.uicon) : ""
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: sddm.hostName
                color: "#888888"
                font.family: root.fontFamily
                font.pixelSize: 13.5 * root.s
                topPadding: -2 * root.s
                bottomPadding: 8 * root.s
            }

            GlassField {
                id: userField
                width: parent.width
                unit: root.s
                fontFamily: root.fontFamily
                placeholder: "Username"
                nextItem: passField.input
                enabled: !root.busy
                onAccepted: passField.input.forceActiveFocus()
                onEdited: root.errorMessage = ""
            }

            GlassField {
                id: passField
                width: parent.width
                unit: root.s
                fontFamily: root.fontFamily
                placeholder: "Password"
                secret: true
                nextItem: loginButton
                enabled: !root.busy
                onAccepted: root.attemptLogin()
                onEdited: root.errorMessage = ""
            }

            GlassButton {
                id: loginButton
                width: parent.width
                unit: root.s
                fontFamily: root.fontFamily
                text: "Log In"
                busy: root.busy
                ready: userField.text.length > 0 && passField.text.length > 0
                onClicked: root.attemptLogin()
            }

            // discreet status line (errors, caps lock)
            Item {
                width: parent.width
                height: 20 * root.s
                Text {
                    anchors.centerIn: parent
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: root.statusText !== "" ? root.statusText : root.lastStatus
                    color: root.errorMessage !== "" ? "#E6E6E6" : "#888888"
                    font.family: root.fontFamily
                    font.pixelSize: 13 * root.s
                    opacity: root.statusText !== "" ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: 240; easing.type: Easing.OutCubic } }
                }
            }
        }
    }

    // ------------------------------------------------------------------ footer
    // click-away layer for the session menu
    MouseArea {
        anchors.fill: parent
        z: 9
        enabled: sessionPicker.open
        onClicked: sessionPicker.open = false
    }

    Item {
        id: footer
        z: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 36 * root.s
        height: 42 * root.s
        opacity: root.stage(0.55, 1.0) * (1 - root.leave)

        SessionPicker {
            id: sessionPicker
            anchors.left: parent.left
            anchors.leftMargin: 34 * root.s
            anchors.verticalCenter: parent.verticalCenter
            sessions: sessionModel
            currentIndex: root.sessionIndex
            backdrop: root.fx ? wallBlur : null
            fx: root.fx && wallBlur.visible
            unit: root.s
            fontFamily: root.fontFamily
            onSelected: function (index) { root.sessionIndex = index }
        }

        Row {
            anchors.centerIn: parent
            spacing: 16 * root.s

            PowerButton {
                visible: sddm.canReboot
                unit: root.s
                fontFamily: root.fontFamily
                label: "Restart"
                confirmLabel: "Click again to restart"
                iconPath: "M16 5.07 A8 8 0 1 0 18.93 16 M13.8 7.3 L18.77 6.67 L16.8 2.07"
                onActivated: sddm.reboot()
            }
            PowerButton {
                visible: sddm.canPowerOff
                unit: root.s
                fontFamily: root.fontFamily
                label: "Shut Down"
                confirmLabel: "Click again to shut down"
                iconPath: "M12 3 L12 11 M5.87 7.86 A8 8 0 1 0 18.13 7.86"
                onActivated: sddm.powerOff()
            }
        }
    }

    // ----------------------------------------------------- entrance / outro veil
    Rectangle {
        anchors.fill: parent
        z: 100
        color: "#000000"
        opacity: Math.max(1 - root.stage(0.0, 0.40), root.leave * 0.65)
    }

    // ----------------------------------------------------------------- startup
    Keys.onEscapePressed: sessionPicker.open = false
    focus: true

    Component.onCompleted: {
        userField.text = userModel.lastUser
        if (userField.text.length > 0)
            passField.input.forceActiveFocus()
        else
            userField.input.forceActiveFocus()
    }
}
