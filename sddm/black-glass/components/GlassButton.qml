import QtQuick

// Primary action button. Dim while the form is incomplete, bright when ready;
// lifts on hover, compresses on press and shows pulsing dots while busy.
Item {
    id: btn

    property real unit: 1
    property string fontFamily: ""
    property string text: ""
    property bool busy: false
    property bool ready: true

    signal clicked()

    readonly property int dur: 240
    readonly property bool hovered: hover.hovered
    readonly property bool pressed: tap.pressed

    implicitWidth: 280 * unit
    implicitHeight: 46 * unit
    activeFocusOnTab: true
    scale: pressed && !busy ? 0.97 : 1.0
    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

    Keys.onReturnPressed: if (!busy) clicked()
    Keys.onEnterPressed: if (!busy) clicked()
    Keys.onSpacePressed: if (!busy) clicked()

    Rectangle {
        id: face
        width: parent.width
        height: parent.height
        y: (btn.hovered && !btn.pressed && !btn.busy) ? -1 * btn.unit : 0
        radius: height / 2
        color: btn.ready
               ? (btn.pressed ? "#CFCFCF" : btn.hovered ? "#FFFFFF" : "#F2F2F2")
               : (btn.hovered ? Qt.rgba(1, 1, 1, 0.13) : Qt.rgba(1, 1, 1, 0.08))
        border.width: btn.activeFocus ? 2 : 1
        border.color: btn.activeFocus ? Qt.rgba(1, 1, 1, 0.55)
                      : btn.ready ? Qt.rgba(1, 1, 1, 0.35) : Qt.rgba(1, 1, 1, 0.07)
        Behavior on y { NumberAnimation { duration: btn.dur; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: btn.dur; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: btn.dur; easing.type: Easing.OutCubic } }

        Text {
            anchors.centerIn: parent
            text: btn.text
            color: btn.ready ? "#0B0B0B" : "#888888"
            font.family: btn.fontFamily
            font.pixelSize: 16 * btn.unit
            font.weight: Font.DemiBold
            opacity: btn.busy ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: btn.dur; easing.type: Easing.OutCubic } }
        }

        Row {
            anchors.centerIn: parent
            spacing: 6 * btn.unit
            opacity: btn.busy ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Repeater {
                model: 3
                Rectangle {
                    width: 6 * btn.unit
                    height: width
                    radius: width / 2
                    color: btn.ready ? "#0B0B0B" : "#F2F2F2"
                    SequentialAnimation on opacity {
                        running: btn.busy
                        loops: Animation.Infinite
                        PauseAnimation { duration: index * 150 }
                        NumberAnimation { from: 0.25; to: 1.0; duration: 350; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 1.0; to: 0.25; duration: 350; easing.type: Easing.InOutSine }
                        PauseAnimation { duration: (2 - index) * 150 }
                    }
                }
            }
        }
    }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: if (!btn.busy) btn.clicked() }
}
