import QtQuick
import QtQuick.Shapes

// Small round glass control. First click arms it (tooltip asks for confirmation),
// a second click within three seconds triggers the action.
Item {
    id: pb

    property real unit: 1
    property string fontFamily: ""
    property string iconPath: ""
    property string label: ""
    property string confirmLabel: ""
    property bool armed: false

    signal activated()

    readonly property int dur: 240
    readonly property bool hovered: hover.hovered

    width: 42 * unit
    height: width
    activeFocusOnTab: true
    scale: tap.pressed ? 0.92 : 1.0
    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

    function trigger() {
        if (armed) {
            armed = false
            activated()
        } else {
            armed = true
            disarm.restart()
        }
    }
    Timer { id: disarm; interval: 3000; onTriggered: pb.armed = false }
    Keys.onReturnPressed: trigger()
    Keys.onSpacePressed: trigger()
    onActiveFocusChanged: if (!activeFocus) armed = false

    Rectangle {
        width: parent.width
        height: parent.height
        radius: width / 2
        y: pb.hovered ? -2 * pb.unit : 0
        color: pb.armed ? Qt.rgba(1, 1, 1, 0.24)
             : pb.hovered ? Qt.rgba(1, 1, 1, 0.14)
             : Qt.rgba(1, 1, 1, 0.075)
        border.width: pb.activeFocus ? 2 : 1
        border.color: pb.activeFocus ? Qt.rgba(1, 1, 1, 0.5) : Qt.rgba(1, 1, 1, 0.10)
        Behavior on y { NumberAnimation { duration: pb.dur; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: pb.dur; easing.type: Easing.OutCubic } }
    }

    Shape {
        width: 24
        height: 24
        anchors.centerIn: parent
        scale: (pb.width * 0.43) / 24
        layer.enabled: true
        layer.samples: 4
        layer.textureSize: Qt.size(96, 96)
        ShapePath {
            strokeColor: (pb.hovered || pb.armed) ? "#FFFFFF" : Qt.rgba(0.95, 0.95, 0.95, 0.78)
            strokeWidth: 1.8
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: pb.iconPath }
        }
    }

    // tooltip
    Rectangle {
        id: tip
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: (pb.hovered || pb.armed || pb.activeFocus ? 10 : 6) * pb.unit
        width: tipText.implicitWidth + 22 * pb.unit
        height: 28 * pb.unit
        radius: height / 2
        color: Qt.rgba(0.06, 0.06, 0.06, 0.82)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.10)
        opacity: (pb.hovered || pb.armed || pb.activeFocus) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: pb.dur; easing.type: Easing.OutCubic } }
        Behavior on anchors.bottomMargin { NumberAnimation { duration: pb.dur; easing.type: Easing.OutCubic } }
        Text {
            id: tipText
            anchors.centerIn: parent
            text: pb.armed ? pb.confirmLabel : pb.label
            color: "#F2F2F2"
            font.family: pb.fontFamily
            font.pixelSize: 12.5 * pb.unit
        }
    }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: pb.trigger() }
}
